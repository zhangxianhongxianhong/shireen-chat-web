export const CHAT_TIMEOUT_MS = 90000

export function friendlyHttpError(status, body = '', lang = 'zh') {
  if (status === 422) {
    return lang === 'zh'
      ? '输入内容不符合要求，请检查字数或格式后重试。'
      : 'Invalid input. Please check length or format and try again.'
  }
  if (status === 429) {
    return lang === 'zh'
      ? '请求过于频繁，请稍后再试。'
      : 'Too many requests. Please try again later.'
  }
  if (status >= 500) {
    return lang === 'zh'
      ? '服务暂时不可用，请稍后再试。'
      : 'Service is temporarily unavailable. Please try again later.'
  }
  return lang === 'zh'
    ? '请求失败，请检查网络后重试。'
    : 'Request failed. Please check your network and try again.'
}

export function friendlyStreamError(data, lang = 'zh') {
  const code = data?.code || ''
  const raw = (data?.message || '').toLowerCase()

  if (code === 'quota' || /quota|余额|配额|insufficient/.test(raw)) {
    return lang === 'zh'
      ? 'AI 服务额度不足，请稍后再试。'
      : 'AI quota exceeded. Please try again later.'
  }
  if (code === 'timeout' || /timeout|超时/.test(raw)) {
    return lang === 'zh'
      ? '响应超时，请稍后再试。'
      : 'Response timed out. Please try again.'
  }
  if (code === 'network' || /network|连接|connect/.test(raw)) {
    return lang === 'zh'
      ? '网络不太稳定，请检查连接后重试。'
      : 'Network error. Please check your connection.'
  }
  if (code === 'unconfigured') {
    return lang === 'zh'
      ? 'AI 服务尚未配置，请联系管理员。'
      : 'AI service is not configured.'
  }
  return lang === 'zh'
    ? '暂时无法获取回复，请稍后再试。'
    : 'Unable to get a reply right now. Please try again.'
}

export function friendlyNetworkError(err, lang = 'zh') {
  if (err?.name === 'AbortError') return ''
  if (err?.name === 'TimeoutError' || /timeout/i.test(err?.message || '')) {
    return lang === 'zh' ? '请求超时，请稍后再试。' : 'Request timed out. Please try again.'
  }
  return lang === 'zh'
    ? '网络不太稳定，请检查连接后重试。'
    : 'Network error. Please check your connection and try again.'
}
