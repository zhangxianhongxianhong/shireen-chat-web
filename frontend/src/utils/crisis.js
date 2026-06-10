const CRISIS_KEYWORDS = [
  '自杀', '想死', '不想活', '活不下去', '轻生', '结束生命', '自残', '割腕',
  'suicide', 'kill myself', 'want to die', 'end my life', 'self-harm',
]

export function detectCrisis(text) {
  const lower = text.toLowerCase()
  return CRISIS_KEYWORDS.some((kw) => lower.includes(kw.toLowerCase()))
}
