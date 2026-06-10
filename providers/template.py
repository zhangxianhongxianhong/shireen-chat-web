"""关键词模板模式：不调用大模型，按关键词匹配返回预设心理咨询式 JSON。"""

import json
import re
import uuid
from typing import AsyncIterator, Optional

from providers.qwen import _detect_response_language
from providers.sse import sse_event

# (关键词列表, 中文模板, 英文模板)
_RULES: list[tuple[list[str], dict[str, str], dict[str, str]]] = [
    (
        ["焦虑", "紧张", "担心", "害怕", "慌", "anxious", "anxiety", "worried", "nervous"],
        {
            "感受摘要": "你正被焦虑感包围，心里有些放不下来。",
            "核心情绪": "焦虑",
            "温暖的小建议": "先慢慢呼吸三次，然后写下此刻最让你担心的那一件事，只写一句就好。",
        },
        {
            "summary": "You feel caught up in anxiety and find it hard to settle.",
            "key_emotion": "anxiety",
            "gentle_next_step": "Take three slow breaths, then write down just one thing worrying you most right now.",
        },
    ),
    (
        ["难过", "伤心", "哭", "失落", "沮丧", "sad", "upset", "hurt", "crying"],
        {
            "感受摘要": "你现在心里很难过，这份感受值得被认真看见。",
            "核心情绪": "难过",
            "温暖的小建议": "给自己一杯温水，找一个安静的地方坐五分钟，允许自己此刻就是不舒服的。",
        },
        {
            "summary": "You are going through a painful moment that deserves to be acknowledged.",
            "key_emotion": "sadness",
            "gentle_next_step": "Get a glass of water, sit quietly for five minutes, and allow yourself to feel low right now.",
        },
    ),
    (
        ["生气", "愤怒", "烦", "恼火", "angry", "mad", "frustrated", "annoyed"],
        {
            "感受摘要": "你心里有股火气，可能混杂着委屈或无力感。",
            "核心情绪": "愤怒",
            "温暖的小建议": "试着把「发生了什么」和「我感受到了什么」分成两行写下来，不必发给任何人。",
        },
        {
            "summary": "There is anger in you, perhaps mixed with hurt or helplessness.",
            "key_emotion": "anger",
            "gentle_next_step": "Write two lines: what happened, and what you felt—just for yourself.",
        },
    ),
    (
        ["孤独", "孤单", "没人", "alone", "lonely", "isolated"],
        {
            "感受摘要": "你感到有些孤独，渴望被理解或陪伴。",
            "核心情绪": "孤独",
            "温暖的小建议": "今天给一位你信任的人发一条很简单的消息，比如「最近还好吗」，不必解释太多。",
        },
        {
            "summary": "You feel lonely and long for understanding or connection.",
            "key_emotion": "loneliness",
            "gentle_next_step": "Send a simple message to someone you trust today—even just asking how they are.",
        },
    ),
    (
        ["压力", "累", "疲惫", "加班", "burnout", "stress", "tired", "exhausted", "overwhelmed"],
        {
            "感受摘要": "你承受了不少压力，身心都有些疲惫。",
            "核心情绪": "疲惫",
            "温暖的小建议": "今晚允许自己早睡半小时，把一件明天的事写下来交给「明天的你」。",
        },
        {
            "summary": "You are under a lot of pressure and feel worn out.",
            "key_emotion": "exhaustion",
            "gentle_next_step": "Go to bed half an hour earlier tonight and jot down one task for tomorrow-you to handle.",
        },
    ),
    (
        ["朋友", "同事", "老板", "父母", "家人", "分手", "吵架", "人际", "relationship", "friend", "family"],
        {
            "感受摘要": "人际关系里的一些事让你心里不太舒服。",
            "核心情绪": "困扰",
            "温暖的小建议": "用「我感到…」而不是「你总是…」来描述这件事，先理清自己的感受。",
        },
        {
            "summary": "Something in a relationship is weighing on your mind.",
            "key_emotion": "relational stress",
            "gentle_next_step": "Describe the situation using 'I feel…' instead of 'You always…' to clarify your own feelings first.",
        },
    ),
]

_DEFAULT_ZH = {
    "感受摘要": "你愿意把这些感受说出来，这本身就需要勇气。",
    "核心情绪": "复杂",
    "温暖的小建议": "用三个词形容你现在的心情，不用准确，直觉写下就好。",
}

_DEFAULT_EN = {
    "summary": "It takes courage to put these feelings into words.",
    "key_emotion": "mixed feelings",
    "gentle_next_step": "Write three words that describe your mood right now—no need to be precise.",
}


def _match_payload(query: str, lang: str) -> dict[str, str]:
    text = query.lower()
    for keywords, zh_tpl, en_tpl in _RULES:
        if any(kw.lower() in text for kw in keywords):
            return zh_tpl if lang == "zh" else en_tpl
    return _DEFAULT_ZH if lang == "zh" else _DEFAULT_EN


def is_available() -> bool:
    return True


async def stream_chat(
    query: str,
    conversation_id: str,
    user: str,
    history: Optional[list[dict[str, str]]] = None,
    **_kwargs,
) -> AsyncIterator[str]:
    conv_id = conversation_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    lang = _detect_response_language(query)
    payload = _match_payload(query, lang)
    answer = json.dumps(payload, ensure_ascii=False)

    yield sse_event(
        "message",
        conversation_id=conv_id,
        message_id=message_id,
        answer=answer,
    )
    yield sse_event(
        "message_end",
        conversation_id=conv_id,
        message_id=message_id,
    )
