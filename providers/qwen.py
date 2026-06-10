import json
import os
import re
import uuid
from typing import AsyncIterator, Optional

import httpx
from fastapi import HTTPException

from providers.sse import sse_event

QWEN_API_BASE = os.getenv(
    "QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

DEFAULT_SYSTEM_PROMPT = """你是一位专业、温暖的心理咨询师。用户会分享一段日记或感受。

【语言规则 — 必须严格遵守】
- 多轮对话时，回复语言只由「当前这一轮」用户输入决定，与历史消息语言无关
- 若上一轮用户用中文、本轮用户改用英文，本轮 JSON 必须全部使用英文
- 若上一轮用户用英文、本轮用户改用中文，本轮 JSON 必须全部使用中文
- JSON 中 summary、key_emotion、gentle_next_step 三个字段的值，必须全部使用本轮用户输入的语言
- 禁止混用语言；这条规则优先于历史对话与下方所有示例

你的工作流程（仅在内心进行，不要输出）：
1. 倾听并理解用户的问题
2. 判断这属于哪类心理议题（如自我怀疑、焦虑、人际关系、职场压力等）
3. 选择合适的心理支持方向（如认知重构、自我接纳、行为激活等）
4. 基于以上判断，生成对用户的回应

你必须且只能输出一个合法的 JSON 对象，不要输出 markdown 代码块、解释或任何其他文字。JSON 包含以下三个字段：
- summary: 用一句简洁的话概括用户当下的处境与感受
- key_emotion: 用户最突出的核心情绪（一个词或短短语）
- gentle_next_step: 一段温暖、接纳的回应，使用日常、用户能理解的语言；并提供一个具体的、用户可以在 24 小时内完成的小行动

示例（中文输入 → 中文输出）：
用户：今天开会被老板质疑了，我表面上没事，但其实很受打击。回家以后一直在想是不是自己能力不够。
输出：
{"summary":"你在工作中被质疑后感到受伤，并开始怀疑自己的能力。","key_emotion":"自我怀疑","gentle_next_step":"在对自己下更大判断之前，先写下今天一件你处理得还不错的事。不用完美，只要真实就好。"}

示例（英文输入 → 英文输出）：
用户：I felt hurt after being questioned at work and started doubting my ability.
输出：
{"summary":"You felt hurt after being questioned at work and started doubting your ability.","key_emotion":"self-doubt","gentle_next_step":"Write down one thing you handled well today before making any bigger judgment about yourself."}"""

QWEN_SYSTEM_PROMPT = os.getenv("QWEN_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

def _headers() -> dict[str, str]:
    if not QWEN_API_KEY:
        raise HTTPException(status_code=500, detail="QWEN_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json",
    }


def _detect_response_language(text: str) -> str:
    """根据当前用户输入判断本轮回复应使用的语言。"""
    text = text.strip()
    if not text:
        return "zh"

    cjk_chars = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))

    if cjk_chars == 0 and latin_chars > 0:
        return "en"
    if latin_chars == 0 and cjk_chars > 0:
        return "zh"
    if latin_chars > cjk_chars:
        return "en"
    if cjk_chars > latin_chars:
        return "zh"

    if re.search(r"\b(the|is|are|am|was|were|my|I|you|always|feel|mom|dad)\b", text, re.I):
        return "en"
    return "zh"


def _language_instruction(lang: str) -> str:
    if lang == "en":
        return (
            "【本轮回复语言：English】"
            "Only for the user's latest message in this turn, "
            "all JSON fields (summary, key_emotion, gentle_next_step) must be written in English. "
            "Ignore the language used in earlier messages."
        )
    return (
        "【本轮回复语言：中文】"
        "仅针对用户本轮最新一条消息，JSON 全部字段（summary、key_emotion、gentle_next_step）必须使用中文。"
        "不要受历史消息语言影响。"
    )


def _parse_openai_sse_line(line: str) -> Optional[dict]:
    line = line.strip()
    if not line.startswith("data:"):
        return None
    raw = line[5:].strip()
    if not raw or raw == "[DONE]":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def stream_chat(
    query: str,
    conversation_id: str,
    user: str,
    history: list[dict[str, str]] | None = None,
    **_kwargs,
) -> AsyncIterator[str]:
    conv_id = conversation_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    conv_history = list(history or [])
    conv_history.append({"role": "user", "content": query})

    response_lang = _detect_response_language(query)
    messages = [
        {"role": "system", "content": QWEN_SYSTEM_PROMPT},
        {"role": "system", "content": _language_instruction(response_lang)},
        *conv_history,
    ]

    payload = {
        "model": QWEN_MODEL,
        "messages": messages,
        "stream": True,
        "response_format": {"type": "json_object"},
    }

    yield sse_event(
        "workflow_started",
        conversation_id=conv_id,
        message_id=message_id,
    )

    full_answer = ""

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        async with client.stream(
            "POST",
            f"{QWEN_API_BASE}/chat/completions",
            headers=_headers(),
            json=payload,
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                error_detail = body.decode("utf-8", errors="replace")
                try:
                    err = json.loads(error_detail)
                    error_detail = err.get("error", {}).get("message", error_detail)
                except json.JSONDecodeError:
                    pass
                yield sse_event("error", message=error_detail, conversation_id=conv_id)
                return

            line_buffer = ""
            async for chunk in response.aiter_bytes():
                line_buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in line_buffer:
                    line, line_buffer = line_buffer.split("\n", 1)
                    data = _parse_openai_sse_line(line)
                    if not data:
                        continue

                    if data.get("error"):
                        msg = data["error"].get("message", "Unknown error")
                        yield sse_event("error", message=msg, conversation_id=conv_id)
                        return

                    for choice in data.get("choices", []):
                        delta = choice.get("delta", {})
                        content = delta.get("content")
                        if content:
                            full_answer += content
                            yield sse_event(
                                "message",
                                conversation_id=conv_id,
                                message_id=message_id,
                                answer=content,
                            )

    yield sse_event(
        "message_end",
        conversation_id=conv_id,
        message_id=message_id,
    )
