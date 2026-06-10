import { CHAT_TIMEOUT_MS, friendlyHttpError } from '../utils/errors.js'

const USER_ID_KEY = 'dify_chat_user_id'
const CONVERSATION_ID_KEY = 'dify_chat_conversation_id'

function getUserId() {
  let id = localStorage.getItem(USER_ID_KEY)
  if (!id) {
    id = `user-${crypto.randomUUID().slice(0, 12)}`
    localStorage.setItem(USER_ID_KEY, id)
  }
  return id
}

export function getConversationId() {
  return localStorage.getItem(CONVERSATION_ID_KEY) || ''
}

export function setConversationId(id) {
  if (id) {
    localStorage.setItem(CONVERSATION_ID_KEY, id)
  }
}

export function clearConversation() {
  localStorage.removeItem(CONVERSATION_ID_KEY)
}

function parseSSELine(line) {
  const trimmed = line.trim()
  if (!trimmed.startsWith('data:')) return null
  const raw = trimmed.slice(5).trim()
  if (!raw || raw === '[DONE]') return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

/**
 * 流式对话。每收到一行 data: 立即回调，不等待完整 SSE 事件块。
 */
export async function streamChat({ query, history = [], onChunk, onDone, signal, lang = 'zh' }) {
  const timeoutController = new AbortController()
  let timedOut = false
  const timeoutId = setTimeout(() => {
    timedOut = true
    timeoutController.abort()
  }, CHAT_TIMEOUT_MS)

  const onAbort = () => timeoutController.abort()
  if (signal) {
    if (signal.aborted) timeoutController.abort()
    else signal.addEventListener('abort', onAbort, { once: true })
  }

  let response
  try {
    response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        conversation_id: getConversationId(),
        user: getUserId(),
        history,
        inputs: {},
        files: [],
      }),
      signal: timeoutController.signal,
    })
  } catch (err) {
    if (timedOut) {
      const timeoutErr = new Error('timeout')
      timeoutErr.name = 'TimeoutError'
      throw timeoutErr
    }
    throw err
  } finally {
    clearTimeout(timeoutId)
    if (signal) signal.removeEventListener('abort', onAbort)
  }

  if (!response.ok) {
    const text = await response.text()
    throw new Error(friendlyHttpError(response.status, text, lang))
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let lineBuffer = ''

  const processText = (text) => {
    lineBuffer += text.replace(/\r\n/g, '\n')
    const lines = lineBuffer.split('\n')
    lineBuffer = lines.pop() || ''

    for (const line of lines) {
      const data = parseSSELine(line)
      if (!data) continue

      if (data.conversation_id) {
        setConversationId(data.conversation_id)
      }
      onChunk(data)

      if (data.event === 'message_end' || data.event === 'error') {
        onDone?.(data)
      }
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    processText(decoder.decode(value, { stream: true }))
  }

  if (lineBuffer.trim()) {
    const data = parseSSELine(lineBuffer)
    if (data) {
      onChunk(data)
      if (data.event === 'message_end' || data.event === 'error') {
        onDone?.(data)
      }
    }
  }
}
