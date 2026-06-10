<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import { streamChat, clearConversation } from '../api/chat.js'
import { loadChatSession, saveChatSession, clearChatSession } from '../utils/chatSession.js'
import { detectCrisis } from '../utils/crisis.js'
import { friendlyNetworkError, friendlyStreamError } from '../utils/errors.js'
import ShireenAvatar from './ShireenAvatar.vue'

const MAX_INPUT_LENGTH = 800

const messages = ref([])
const input = ref('')
const inputHint = ref('')
const loading = ref(false)
const chatContainer = ref(null)
const showMenu = ref(false)
const showAbout = ref(false)

const featureSections = [
  {
    title: '基础功能',
    items: [
      '一键复制 AI 回答',
      '一键清空输入框',
      '响应式 UI，适配手机与电脑',
      '识别极端情绪时，引导拨打紧急服务电话（如 110）',
      '引导文案与使用示例，降低上手成本',
    ],
  },
  {
    title: '输入字数限制',
    items: [
      '上限 800 字，适合一段日记/感受的长度',
      '右下角显示「当前字数/800」',
      '达到 90%（720 字）时计数变橙色提醒',
      '达到 800 字时变粉色，无法继续输入',
      '超限或为空时禁用发送按钮',
      '后端同步校验 max_length=800',
    ],
  },
  {
    title: '历史对话',
    items: ['对话自动保存在本机浏览器', '刷新网页后恢复聊天现场', '「开始新对话」可清空当前记录'],
  },
  {
    title: '健壮性',
    items: [
      '空输入、纯空格、超长文本校验与提示',
      '网络异常、超时、接口报错友好文案',
      '不向用户展示原始 API 错误信息',
    ],
  },
]

const fallbackRows = [
  { scene: '网络异常', show: '「网络不太稳定，请检查连接后重试。」', action: '前端捕获；后端可降级模板' },
  { scene: '请求超时（90s）', show: '「请求超时，请稍后再试。」', action: '超时后降级模板' },
  { scene: '接口报错（500 等）', show: '「服务暂时不可用，请稍后再试。」', action: '千问失败 → 模板' },
  { scene: '配额不足', show: '「AI 服务额度不足…」+ 降级提示条', action: '识别 quota → 模板' },
  { scene: '降级到模板', show: '灰色提示条 + 正常三张卡片', action: '不阻断使用' },
  { scene: '彻底失败', show: '粉色错误气泡', action: '仅展示友好文案' },
]
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

function validateInput(text) {
  if (!text) {
    inputHint.value = '请先输入你的感受或日记内容'
    return false
  }
  if (text.length > MAX_INPUT_LENGTH) {
    inputHint.value = `内容过长，请控制在 ${MAX_INPUT_LENGTH} 字以内`
    return false
  }
  if (!/\S/.test(text)) {
    inputHint.value = '请输入有效文字内容'
    return false
  }
  inputHint.value = ''
  return true
}

async function sendMessage() {
  const text = input.value.trim()
  if (loading.value || !validateInput(text)) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  scrollToBottom()

  const lang = hasChinese(text) ? 'zh' : 'en'
  const crisisAlert = detectCrisis(text)
  const botMsg = {
    role: 'assistant',
    content: '',
    streaming: true,
    lang,
    crisisAlert,
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
      lang,
      signal: abortController.signal,
      onChunk(data) {
        if (data.event === 'provider_fallback') {
          messages.value[botIndex].fallbackNotice = data.notice || ''
          messages.value[botIndex].isTemplate = true
        }
        if (data.event === 'message' && data.answer != null && data.answer !== '') {
          messages.value[botIndex].content += data.answer
          messages.value[botIndex].isError = false
          scrollToBottom()
        }
        if (data.event === 'error') {
          messages.value[botIndex].isError = true
          messages.value[botIndex].content = friendlyStreamError(data, lang)
        }
      },
      onDone() {
        messages.value[botIndex].streaming = false
        const parsed = parseTherapyResponse(messages.value[botIndex].content, lang)
        if (parsed) {
          messages.value[botIndex].parsed = parsed
          messages.value[botIndex].isError = false
        }
      },
    })
  } catch (err) {
    if (err.name !== 'AbortError') {
      messages.value[botIndex].isError = true
      messages.value[botIndex].content = friendlyNetworkError(err, lang) || err.message
    }
    messages.value[botIndex].streaming = false
  } finally {
    loading.value = false
    messages.value[botIndex].streaming = false
    abortController = null
    saveChatSession(messages.value)
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
  clearChatSession()
  messages.value = []
  loading.value = false
  showMenu.value = false
}

function restoreSession() {
  const stored = loadChatSession()
  if (!stored.length) return

  messages.value = stored.map((msg) => {
    if (msg.role === 'assistant' && msg.content && !msg.parsed) {
      const parsed = parseTherapyResponse(msg.content, msg.lang)
      if (parsed) return { ...msg, parsed }
    }
    return msg
  })
}

watch(
  messages,
  (msgs) => {
    if (!loading.value) saveChatSession(msgs)
  },
  { deep: true },
)

async function copyMessage(index, content) {
  try {
    await navigator.clipboard.writeText(content)
    copiedIndex.value = index
    setTimeout(() => { copiedIndex.value = -1 }, 2000)
  } catch { /* ignore */ }
}

function hasChinese(text) {
  return /[\u4e00-\u9fff\u3400-\u4dbf]/.test(text)
}

function speakMessage(content, parsed) {
  window.speechSynthesis?.cancel()
  const text = parsed?.gentle_next_step || content
  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = parsed?.lang === 'en' ? 'en-US' : 'zh-CN'
  window.speechSynthesis?.speak(utter)
}

function toggleSave(index) {
  if (savedSet.value.has(index)) savedSet.value.delete(index)
  else savedSet.value.add(index)
  savedSet.value = new Set(savedSet.value)
}

function normalizeTherapyJson(json) {
  if (json['感受摘要'] && json['核心情绪'] && json['温暖的小建议']) {
    return {
      lang: 'zh',
      summary: json['感受摘要'],
      key_emotion: json['核心情绪'],
      gentle_next_step: json['温暖的小建议'],
    }
  }
  if (json.summary && json.key_emotion && json.gentle_next_step) {
    return {
      lang: 'en',
      summary: json.summary,
      key_emotion: json.key_emotion,
      gentle_next_step: json.gentle_next_step,
    }
  }
  return null
}

function parseTherapyResponse(content, userLang) {
  if (!content) return null
  const tryParse = (text) => {
    try {
      const parsed = normalizeTherapyJson(JSON.parse(text.trim()))
      if (parsed) return parsed
    } catch { /* ignore */ }
    return null
  }
  const direct = tryParse(content)
  const match = content.match(/\{[\s\S]*\}/)
  const parsed = direct || (match ? tryParse(match[0]) : null)
  if (parsed && userLang) parsed.lang = userLang
  return parsed
}

function therapyLabels(lang) {
  if (lang === 'zh') {
    return { summary: '感受摘要', emotion: '核心情绪', nextStep: '温暖的小建议' }
  }
  return { summary: 'Summary', emotion: 'Key emotion', nextStep: 'Gentle next step' }
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
  inputHint.value = ''
}

function clearInput() {
  input.value = ''
  inputHint.value = ''
}

onMounted(() => {
  restoreSession()
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
            <button @click="showMenu = false; showAbout = true">功能说明</button>
          </div>
        </div>
        <button type="button" class="about-btn" title="功能说明" @click="showAbout = true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 16v-4M12 8h.01" stroke-linecap="round"/>
          </svg>
        </button>
      </header>

      <div v-if="showAbout" class="about-overlay" @click.self="showAbout = false">
        <div class="about-panel" role="dialog" aria-labelledby="about-title">
          <div class="about-header">
            <h2 id="about-title" class="about-title">功能说明</h2>
            <button type="button" class="about-close" aria-label="关闭" @click="showAbout = false">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
          <div class="about-body">
            <section v-for="section in featureSections" :key="section.title" class="about-section">
              <h3 class="about-section-title">{{ section.title }}</h3>
              <ul class="about-list">
                <li v-for="item in section.items" :key="item">{{ item }}</li>
              </ul>
            </section>
            <section class="about-section">
              <h3 class="about-section-title">Fallback 机制</h3>
              <div class="fallback-table-wrap">
                <table class="fallback-table">
                  <thead>
                    <tr>
                      <th>场景</th>
                      <th>用户看到</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in fallbackRows" :key="row.scene">
                      <td>{{ row.scene }}</td>
                      <td>{{ row.show }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
            <p class="about-note">Shireen 提供情绪支持，不能替代专业医疗或心理咨询。遇紧急危险请立即拨打 110。</p>
          </div>
        </div>
      </div>

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
                <div v-if="msg.crisisAlert" class="crisis-alert">
                  <p class="crisis-alert-title">你并不孤单，请优先保障自身安全</p>
                  <p class="crisis-alert-text">
                    如果你正处于紧急危险中，或有伤害自己的想法，请立即拨打
                    <a href="tel:110">110</a>
                    或当地紧急服务电话。也可拨打全国心理援助热线
                    <a href="tel:4001619995">400-161-9995</a>。
                  </p>
                </div>
                <p v-if="msg.fallbackNotice" class="fallback-notice">{{ msg.fallbackNotice }}</p>
                <div v-if="msg.parsed" class="therapy-response">
                  <div class="therapy-section therapy-section--summary">
                    <span class="therapy-label">{{ therapyLabels(msg.parsed.lang || msg.lang).summary }}</span>
                    <p class="therapy-text">{{ msg.parsed.summary }}</p>
                  </div>
                  <div class="therapy-section therapy-section--emotion">
                    <span class="therapy-label">{{ therapyLabels(msg.parsed.lang || msg.lang).emotion }}</span>
                    <p class="therapy-emotion">{{ msg.parsed.key_emotion }}</p>
                  </div>
                  <div class="therapy-section therapy-step">
                    <span class="therapy-label">{{ therapyLabels(msg.parsed.lang || msg.lang).nextStep }}</span>
                    <p class="therapy-text therapy-text--step">{{ msg.parsed.gentle_next_step }}</p>
                  </div>
                </div>
                <p v-else-if="msg.content" class="ai-text" :class="{ 'ai-text--error': msg.isError }">{{ msg.content }}</p>
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
            :maxlength="MAX_INPUT_LENGTH"
            :disabled="loading"
            @keydown="handleKeydown"
            @input="inputHint = ''"
          />

          <div class="input-toolbar">
            <span class="input-hint" :class="{ 'input-hint--warn': inputHint }">
              {{ inputHint || 'Enter 发送 · Shift+Enter 换行' }}
            </span>
            <div class="input-actions">
              <button
                v-if="input"
                type="button"
                class="clear-input-btn"
                title="清空输入"
                :disabled="loading"
                @click="clearInput"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
                </svg>
              </button>
              <span
                class="char-count"
                :class="{
                  'char-count--warn': input.length >= MAX_INPUT_LENGTH * 0.9,
                  'char-count--limit': input.length >= MAX_INPUT_LENGTH,
                }"
              >{{ input.length }}/{{ MAX_INPUT_LENGTH }}</span>
              <button
              class="send-btn"
              :class="{ active: input.trim() && !loading && input.length <= MAX_INPUT_LENGTH }"
              type="button"
              :disabled="!input.trim() || loading || input.length > MAX_INPUT_LENGTH"
              @click="sendMessage"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
            </div>
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 0 12px;
  flex-shrink: 0;
}

.about-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: var(--surface);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
  transition: background 0.15s, color 0.15s;
}

.about-btn:hover {
  background: var(--accent-soft);
  color: var(--accent);
}

.about-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(61, 46, 40, 0.35);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.about-panel {
  width: 100%;
  max-width: 420px;
  max-height: min(85vh, 640px);
  background: var(--surface-solid);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.about-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.about-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text);
}

.about-close {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
}

.about-close:hover {
  background: var(--accent-soft);
  color: var(--text);
}

.about-body {
  padding: 16px 20px 20px;
  overflow-y: auto;
}

.about-section {
  margin-bottom: 16px;
}

.about-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  margin-bottom: 6px;
}

.about-list {
  list-style: none;
  padding: 0;
}

.about-list li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.65;
  padding: 2px 0 2px 12px;
  position: relative;
}

.about-list li::before {
  content: '·';
  position: absolute;
  left: 0;
  color: var(--text-muted);
}

.fallback-table-wrap {
  overflow-x: auto;
  margin: 0 -4px;
}

.fallback-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}

.fallback-table th,
.fallback-table td {
  border: 1px solid var(--border-light);
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
  line-height: 1.5;
}

.fallback-table th {
  background: var(--therapy-summary);
  color: var(--text-secondary);
  font-weight: 600;
}

.fallback-table td {
  color: var(--text-secondary);
}

.fallback-table td:first-child {
  white-space: nowrap;
  color: var(--text);
  font-weight: 500;
}

.crisis-alert {
  background: rgba(212, 132, 138, 0.12);
  border: 1px solid rgba(212, 132, 138, 0.35);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 12px;
}

.crisis-alert-title {
  font-size: 13px;
  font-weight: 600;
  color: #b85c5c;
  margin-bottom: 6px;
}

.crisis-alert-text {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.65;
}

.crisis-alert a {
  color: #b85c5c;
  font-weight: 600;
  text-decoration: none;
}

.crisis-alert a:hover {
  text-decoration: underline;
}

.clear-input-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s, color 0.15s;
}

.clear-input-btn:hover:not(:disabled) {
  background: var(--accent-soft);
  color: var(--accent);
}

.clear-input-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.about-note {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.6;
  margin-top: 8px;
  padding-top: 14px;
  border-top: 1px solid var(--border-light);
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

.input-hint--warn {
  color: #d4848a;
}

.fallback-notice {
  font-size: 12px;
  color: var(--text-muted);
  background: rgba(232, 168, 124, 0.12);
  border-radius: 10px;
  padding: 8px 12px;
  margin-bottom: 12px;
  line-height: 1.5;
}

.ai-text--error {
  color: #b85c5c;
  background: rgba(212, 132, 138, 0.08);
  border-radius: 12px;
  padding: 12px 14px;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.char-count {
  font-size: 11px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.char-count--warn {
  color: #c9876b;
}

.char-count--limit {
  color: #d4848a;
  font-weight: 500;
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
