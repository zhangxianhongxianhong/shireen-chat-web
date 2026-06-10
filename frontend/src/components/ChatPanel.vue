<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { streamChat, clearConversation } from '../api/chat.js'
import ShireenAvatar from './ShireenAvatar.vue'

const messages = ref([])
const input = ref('')
const loading = ref(false)
const chatContainer = ref(null)
const showMenu = ref(false)
const copiedIndex = ref(-1)
const savedSet = ref(new Set())
let abortController = null

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

async function sendMessage() {
  const text = input.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  scrollToBottom()

  const botMsg = {
    role: 'assistant',
    content: '',
    streaming: true,
  }
  messages.value.push(botMsg)
  const botIndex = messages.value.length - 1

  abortController = new AbortController()

  const history = messages.value
    .slice(0, -1)
    .filter((msg) => msg.content)
    .map((msg) => ({ role: msg.role, content: msg.content }))

  try {
    await streamChat({
      query: text,
      history,
      signal: abortController.signal,
      onChunk(data) {
        if (data.event === 'message' && data.answer != null && data.answer !== '') {
          messages.value[botIndex].content += data.answer
          scrollToBottom()
        }
        if (data.event === 'error') {
          messages.value[botIndex].content = data.message || '请求失败'
        }
      },
      onDone() {
        messages.value[botIndex].streaming = false
        const parsed = parseTherapyResponse(messages.value[botIndex].content)
        if (parsed) messages.value[botIndex].parsed = parsed
      },
    })
  } catch (err) {
    if (err.name !== 'AbortError') {
      messages.value[botIndex].content = err.message || '网络错误，请重试'
    }
    messages.value[botIndex].streaming = false
  } finally {
    loading.value = false
    messages.value[botIndex].streaming = false
    abortController = null
    scrollToBottom()
  }
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function newChat() {
  if (loading.value && abortController) abortController.abort()
  clearConversation()
  messages.value = []
  loading.value = false
  showMenu.value = false
}

async function copyMessage(index, content) {
  try {
    await navigator.clipboard.writeText(content)
    copiedIndex.value = index
    setTimeout(() => { copiedIndex.value = -1 }, 2000)
  } catch { /* ignore */ }
}

function speakMessage(content, parsed) {
  window.speechSynthesis?.cancel()
  const text = parsed?.gentle_next_step || content
  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = 'zh-CN'
  window.speechSynthesis?.speak(utter)
}

function toggleSave(index) {
  if (savedSet.value.has(index)) savedSet.value.delete(index)
  else savedSet.value.add(index)
  savedSet.value = new Set(savedSet.value)
}

function parseTherapyResponse(content) {
  if (!content) return null
  const tryParse = (text) => {
    try {
      const json = JSON.parse(text.trim())
      if (json.summary && json.key_emotion && json.gentle_next_step) return json
    } catch { /* ignore */ }
    return null
  }
  const direct = tryParse(content)
  if (direct) return direct
  const match = content.match(/\{[\s\S]*\}/)
  return match ? tryParse(match[0]) : null
}

function displayContent(content, parsed) {
  if (parsed) {
    return [parsed.summary, parsed.key_emotion, parsed.gentle_next_step].join('\n\n')
  }
  return content
}

const suggestions = [
  '今天发生了一些让我难过的事…',
  '我最近总是感到焦虑',
  '想聊聊和朋友之间的事',
]

function useSuggestion(text) {
  input.value = text
}

onMounted(() => {
  scrollToBottom()
  document.addEventListener('click', () => { showMenu.value = false })
})
</script>

<template>
  <div class="page">
    <div class="ambient" aria-hidden="true">
      <div class="ambient-blob ambient-blob--1" />
      <div class="ambient-blob ambient-blob--2" />
      <div class="ambient-blob ambient-blob--3" />
    </div>

    <div class="page-inner">
      <header class="top-bar">
        <div class="brand-pill dropdown" @click.stop="showMenu = !showMenu">
          <ShireenAvatar :size="28" />
          <div class="brand-text">
            <span class="brand-name">Shireen</span>
            <span class="brand-tag">陪你倾听与梳理</span>
          </div>
          <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <div v-if="showMenu" class="dropdown-menu">
            <button @click="newChat">开始新对话</button>
          </div>
        </div>
      </header>

      <main class="chat-area" ref="chatContainer">
        <div v-if="messages.length === 0" class="empty-state">
          <div class="empty-avatar-wrap">
            <ShireenAvatar :size="72" />
          </div>
          <p class="empty-title">你好，我是 Shireen</p>
          <p class="empty-hint">写下今天的感受或日记，我会温柔地陪你一起梳理</p>
          <div class="suggestions">
            <button
              v-for="item in suggestions"
              :key="item"
              type="button"
              class="suggestion-chip"
              @click="useSuggestion(item)"
            >
              {{ item }}
            </button>
          </div>
        </div>

        <template v-for="(msg, i) in messages" :key="i">
          <div v-if="msg.role === 'user'" class="msg-user">
            <div class="user-pill">{{ msg.content }}</div>
          </div>

          <div v-else class="msg-ai">
            <ShireenAvatar :size="34" class="ai-avatar" />
            <div class="ai-card">
              <div v-if="msg.streaming && !msg.parsed" class="thinking">
                <span class="dots"><span></span><span></span><span></span></span>
              </div>
              <template v-else>
                <div v-if="msg.parsed" class="therapy-response">
                  <div class="therapy-section therapy-section--summary">
                    <span class="therapy-label">感受摘要</span>
                    <p class="therapy-text">{{ msg.parsed.summary }}</p>
                  </div>
                  <div class="therapy-section therapy-section--emotion">
                    <span class="therapy-label">核心情绪</span>
                    <p class="therapy-emotion">{{ msg.parsed.key_emotion }}</p>
                  </div>
                  <div class="therapy-section therapy-step">
                    <span class="therapy-label">温暖的小建议</span>
                    <p class="therapy-text therapy-text--step">{{ msg.parsed.gentle_next_step }}</p>
                  </div>
                </div>
                <p v-else-if="msg.content" class="ai-text">{{ msg.content }}</p>
                <div v-if="!msg.streaming && msg.content" class="msg-actions">
                <button class="action-btn" title="朗读" @click="speakMessage(msg.content, msg.parsed)">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                    <path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"/>
                  </svg>
                </button>
                <button class="action-btn" title="复制" @click="copyMessage(i, displayContent(msg.content, msg.parsed))">
                  <svg v-if="copiedIndex !== i" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                    <rect x="9" y="9" width="13" height="13" rx="2"/>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                  <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </button>
                <button
                  class="action-btn"
                  :class="{ saved: savedSet.has(i) }"
                  title="收藏"
                  @click="toggleSave(i)"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" :fill="savedSet.has(i) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.8">
                    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                  </svg>
                </button>
                </div>
              </template>
            </div>
          </div>
        </template>
      </main>

      <footer class="bottom-area">
        <div class="input-card">
          <textarea
            v-model="input"
            class="input-field"
            placeholder="写下你的感受或今天的日记…"
            rows="2"
            :disabled="loading"
            @keydown="handleKeydown"
          />

          <div class="input-toolbar">
            <span class="input-hint">Enter 发送 · Shift+Enter 换行</span>
            <button
              class="send-btn"
              :class="{ active: input.trim() && !loading }"
              type="button"
              :disabled="!input.trim() || loading"
              @click="sendMessage"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
        </div>

        <p class="disclaimer">Shireen 提供情绪支持，不能替代专业医疗或心理咨询。</p>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.page {
  position: relative;
  height: 100%;
  overflow: hidden;
}

.ambient {
  position: fixed;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}

.ambient-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.55;
}

.ambient-blob--1 {
  width: 320px;
  height: 320px;
  top: -80px;
  right: -60px;
  background: rgba(255, 200, 170, 0.45);
}

.ambient-blob--2 {
  width: 280px;
  height: 280px;
  bottom: 10%;
  left: -80px;
  background: rgba(232, 180, 200, 0.35);
}

.ambient-blob--3 {
  width: 200px;
  height: 200px;
  top: 40%;
  right: 15%;
  background: rgba(200, 220, 200, 0.3);
}

.page-inner {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 680px;
  margin: 0 auto;
  padding: 0 20px;
  min-width: 0;
}

.top-bar {
  padding: 20px 0 12px;
  flex-shrink: 0;
}

.dropdown {
  position: relative;
  cursor: pointer;
  user-select: none;
}

.brand-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px 8px 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(12px);
  transition: box-shadow 0.2s, transform 0.2s;
}

.brand-pill:hover {
  box-shadow: var(--shadow-md);
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.brand-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.2;
}

.brand-tag {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.2;
}

.chevron {
  margin-left: 2px;
  color: var(--text-muted);
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  background: var(--surface-solid);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-md);
  padding: 6px;
  min-width: 140px;
  z-index: 10;
}

.dropdown-menu button {
  display: block;
  width: 100%;
  padding: 10px 14px;
  border: none;
  background: none;
  text-align: left;
  font-size: 14px;
  color: var(--text-secondary);
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.dropdown-menu button:hover {
  background: var(--accent-soft);
  color: var(--text);
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 24px 0 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
  scrollbar-width: thin;
  scrollbar-color: rgba(200, 170, 150, 0.4) transparent;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  padding: 20px 0 40px;
}

.empty-avatar-wrap {
  padding: 16px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.6);
  box-shadow: var(--shadow-glow);
  margin-bottom: 4px;
}

.empty-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: 0.02em;
}

.empty-hint {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-secondary);
  max-width: 320px;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 20px;
  width: 100%;
  max-width: 360px;
}

.suggestion-chip {
  padding: 12px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
  cursor: pointer;
  text-align: left;
  transition: background 0.2s, border-color 0.2s, transform 0.15s, box-shadow 0.2s;
  backdrop-filter: blur(8px);
}

.suggestion-chip:hover {
  background: var(--surface-solid);
  border-color: rgba(212, 132, 138, 0.35);
  color: var(--text);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.msg-user {
  display: flex;
  justify-content: flex-end;
  width: 100%;
  min-width: 0;
}

.user-pill {
  background: var(--user-message-bg);
  border: 1px solid var(--user-message-border);
  color: var(--text);
  padding: 12px 18px;
  border-radius: 20px 20px 6px 20px;
  font-size: 15px;
  line-height: 1.65;
  max-width: 82%;
  min-width: 0;
  width: fit-content;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: pre-wrap;
  box-shadow: var(--shadow-sm);
}

.msg-ai {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.ai-avatar {
  margin-top: 6px;
  flex-shrink: 0;
}

.ai-card {
  flex: 1;
  min-width: 0;
  background: var(--ai-card-bg);
  border: 1px solid var(--border);
  border-radius: 6px 20px 20px 20px;
  padding: 16px 18px;
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(10px);
}

.ai-text {
  font-size: 15px;
  line-height: 1.75;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}

.therapy-response {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.therapy-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 14px;
}

.therapy-section--summary {
  background: var(--therapy-summary);
}

.therapy-section--emotion {
  background: var(--therapy-emotion);
}

.therapy-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-warm);
  letter-spacing: 0.06em;
}

.therapy-section--emotion .therapy-label {
  color: var(--accent);
}

.therapy-step .therapy-label {
  color: var(--accent-sage);
}

.therapy-text {
  font-size: 15px;
  line-height: 1.75;
  color: var(--text);
}

.therapy-text--step {
  color: var(--text-secondary);
}

.therapy-emotion {
  display: inline-block;
  font-size: 14px;
  font-weight: 500;
  color: var(--accent);
  background: rgba(255, 255, 255, 0.75);
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  width: fit-content;
  border: 1px solid rgba(212, 132, 138, 0.2);
}

.therapy-step {
  background: var(--therapy-step);
  border: 1px solid rgba(232, 180, 150, 0.25);
  padding: 14px 16px;
}

.msg-actions {
  display: flex;
  gap: 2px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}

.action-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  border-radius: 10px;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, background 0.15s;
}

.action-btn:hover {
  color: var(--accent);
  background: var(--accent-soft);
}

.action-btn.saved {
  color: var(--accent);
}

.thinking {
  display: flex;
  align-items: center;
  padding: 4px 0;
}

.dots {
  display: flex;
  gap: 5px;
}

.dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent-warm);
  animation: bounce 1.2s ease-in-out infinite;
}

.dots span:nth-child(2) { animation-delay: 0.15s; }
.dots span:nth-child(3) { animation-delay: 0.3s; }

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.35; }
  30% { transform: translateY(-5px); opacity: 1; }
}

.bottom-area {
  flex-shrink: 0;
  padding-bottom: 24px;
}

.input-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  padding: 16px 18px 14px;
  backdrop-filter: blur(16px);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input-card:focus-within {
  border-color: rgba(212, 132, 138, 0.4);
  box-shadow: var(--shadow-md), 0 0 0 3px rgba(212, 132, 138, 0.08);
}

.input-field {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-family: inherit;
  font-size: 15px;
  line-height: 1.65;
  color: var(--text);
  background: transparent;
  min-height: 48px;
  max-height: 140px;
}

.input-field::placeholder {
  color: var(--text-muted);
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  gap: 12px;
}

.input-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.send-btn {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: rgba(235, 210, 195, 0.5);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.2s, color 0.2s, transform 0.15s, box-shadow 0.2s;
}

.send-btn.active {
  background: linear-gradient(135deg, #e8a87c 0%, #d4848a 100%);
  color: white;
  box-shadow: 0 4px 14px rgba(212, 132, 138, 0.35);
}

.send-btn.active:hover:not(:disabled) {
  transform: scale(1.05);
}

.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.disclaimer {
  text-align: center;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 14px;
  line-height: 1.6;
  opacity: 0.85;
}

@media (max-width: 480px) {
  .page-inner { padding: 0 14px; }
  .brand-tag { display: none; }
  .input-hint { display: none; }
  .empty-title { font-size: 20px; }
  .user-pill { max-width: 88%; }
}
</style>
