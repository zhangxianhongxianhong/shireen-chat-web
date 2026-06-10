import json
import os
import re
import uuid
from typing import Any, AsyncIterator, Callable, Optional

from providers import dify, qwen, template
from providers.sse import sse_event

CHAT_PROVIDER = os.getenv("CHAT_PROVIDER", "qwen").lower()
ENABLE_PROVIDER_FALLBACK = os.getenv("ENABLE_PROVIDER_FALLBACK", "true").lower() == "true"


def _qwen_configured() -> bool:
    return bool(os.getenv("QWEN_API_KEY"))


def _dify_configured() -> bool:
    return bool(os.getenv("DIFY_API_KEY"))


def _parse_sse_chunk(chunk: str) -> Optional[dict[str, Any]]:
    for line in chunk.split("\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if not raw:
            continue
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return None


def _classify_error(message: str) -> str:
    text = message.lower()
    if any(k in text for k in ("quota", "insufficient", "余额", "配额", "exceeded", "limit")):
        return "quota"
    if any(k in text for k in ("timeout", "timed out", "超时")):
        return "timeout"
    if any(k in text for k in ("network", "connect", "connection", "网络", "连接")):
        return "network"
    return "api"


def _fallback_notice(reason: str, lang: str) -> str:
    notices_zh = {
        "quota": "AI 服务额度暂时不足，已切换为简化回复模式。",
        "timeout": "AI 响应超时，已切换为简化回复模式。",
        "network": "网络不太稳定，已切换为简化回复模式。",
        "api": "AI 服务暂时不可用，已切换为简化回复模式。",
        "unconfigured": "AI 服务未配置，已使用简化回复模式。",
    }
    notices_en = {
        "quota": "AI quota is temporarily unavailable. Switched to simplified replies.",
        "timeout": "AI response timed out. Switched to simplified replies.",
        "network": "Network is unstable. Switched to simplified replies.",
        "api": "AI service is temporarily unavailable. Switched to simplified replies.",
        "unconfigured": "AI is not configured. Using simplified replies.",
    }
    notices = notices_zh if lang == "zh" else notices_en
    return notices.get(reason, notices["api"])


async def _stream_provider(
    stream_fn: Callable[..., AsyncIterator[str]],
    kwargs: dict[str, Any],
) -> tuple[bool, Optional[str], list[str]]:
    chunks: list[str] = []
    has_message = False
    error_reason: Optional[str] = None

    async for chunk in stream_fn(**kwargs):
        event = _parse_sse_chunk(chunk)
        if event:
            name = event.get("event")
            if name == "message" and event.get("answer"):
                has_message = True
            elif name == "error" and not has_message:
                error_reason = _classify_error(event.get("message", ""))
                return False, error_reason, chunks
        chunks.append(chunk)

    if has_message:
        return True, None, chunks
    return False, "api", chunks


async def stream_chat(
    query: str,
    conversation_id: str,
    user: str,
    history: Optional[list[dict[str, str]]] = None,
    inputs: Optional[dict] = None,
    files: Optional[list[dict]] = None,
    **_kwargs,
) -> AsyncIterator[str]:
    conv_id = conversation_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    lang = "zh" if re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", query) else "en"

    base_kwargs = {
        "query": query,
        "conversation_id": conv_id,
        "user": user,
        "history": history,
    }
    dify_kwargs = {
        **base_kwargs,
        "inputs": inputs or {},
        "files": files or [],
    }

    # Dify 使用自有 SSE 格式，不做链式降级解析
    if CHAT_PROVIDER == "dify" and _dify_configured():
        async for chunk in dify.stream_chat(**dify_kwargs):
            yield chunk
        return

    last_reason = "unconfigured"

    if _qwen_configured():
        ok, reason, chunks = await _stream_provider(qwen.stream_chat, base_kwargs)
        if ok:
            for chunk in chunks:
                yield chunk
            return
        last_reason = reason or "api"
    else:
        last_reason = "unconfigured"

    if not ENABLE_PROVIDER_FALLBACK:
        yield sse_event(
            "workflow_started",
            conversation_id=conv_id,
            message_id=message_id,
        )
        yield sse_event(
            "error",
            conversation_id=conv_id,
            message=_fallback_notice(last_reason, lang),
            code=last_reason,
        )
        return

    yield sse_event(
        "workflow_started",
        conversation_id=conv_id,
        message_id=message_id,
    )
    yield sse_event(
        "provider_fallback",
        conversation_id=conv_id,
        message_id=message_id,
        mode="template",
        reason=last_reason,
        notice=_fallback_notice(last_reason, lang),
    )
    async for chunk in template.stream_chat(**base_kwargs):
        yield chunk
