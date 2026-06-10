const STORAGE_KEY = 'shireen_chat_session'

export function loadChatSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const messages = JSON.parse(raw)
    if (!Array.isArray(messages)) return []
    return messages.filter(
      (m) => (m.role === 'user' || m.role === 'assistant') && !m.streaming && m.content,
    )
  } catch {
    return []
  }
}

export function saveChatSession(messages) {
  const toSave = messages
    .filter((m) => !m.streaming && m.content)
    .map(({ role, content, lang, parsed, fallbackNotice, isTemplate, isError, crisisAlert }) => ({
      role,
      content,
      ...(lang ? { lang } : {}),
      ...(parsed ? { parsed } : {}),
      ...(fallbackNotice ? { fallbackNotice } : {}),
      ...(isTemplate ? { isTemplate } : {}),
      ...(isError ? { isError } : {}),
      ...(crisisAlert ? { crisisAlert } : {}),
    }))

  if (toSave.length) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}

export function clearChatSession() {
  localStorage.removeItem(STORAGE_KEY)
}
