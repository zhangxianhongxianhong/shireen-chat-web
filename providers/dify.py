import json
import os
from typing import AsyncIterator

import httpx
from fastapi import HTTPException

from providers.sse import sse_event

DIFY_API_BASE = os.getenv("DIFY_API_BASE", "https://api.dify.ai/v1")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")


def _headers() -> dict[str, str]:
    if not DIFY_API_KEY:
        raise HTTPException(status_code=500, detail="DIFY_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
    }


async def stream_chat(
    query: str,
    conversation_id: str,
    user: str,
    inputs: dict,
    files: list[dict],
) -> AsyncIterator[str]:
    payload = {
        "inputs": inputs,
        "query": query,
        "response_mode": "streaming",
        "conversation_id": conversation_id,
        "user": user,
        "files": files,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        async with client.stream(
            "POST",
            f"{DIFY_API_BASE}/chat-messages",
            headers=_headers(),
            json=payload,
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                error_detail = body.decode("utf-8", errors="replace")
                try:
                    error_json = json.loads(error_detail)
                    error_detail = error_json.get("message", error_detail)
                except json.JSONDecodeError:
                    pass
                yield sse_event("error", message=error_detail)
                return

            async for chunk in response.aiter_bytes():
                if chunk:
                    yield chunk.decode("utf-8", errors="replace")
