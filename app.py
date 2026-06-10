import os
import uuid
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from providers import router

CHAT_PROVIDER = os.getenv("CHAT_PROVIDER", "qwen").lower()

app = FastAPI(title="Chat Proxy", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatFile(BaseModel):
    type: str = "image"
    transfer_method: str = "remote_url"
    url: str


class ChatMessage(BaseModel):
    role: str
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=800)
    conversation_id: str = ""
    user: str = ""
    history: list[ChatMessage] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    files: list[ChatFile] = Field(default_factory=list)


def _is_configured() -> bool:
    if CHAT_PROVIDER == "dify":
        return bool(os.getenv("DIFY_API_KEY"))
    return bool(os.getenv("QWEN_API_KEY"))


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "provider": CHAT_PROVIDER,
        "configured": _is_configured(),
    }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    user_id = request.user or f"user-{uuid.uuid4().hex[:12]}"

    stream = router.stream_chat(
        query=request.query,
        conversation_id=request.conversation_id,
        user=user_id,
        history=[m.model_dump() for m in request.history],
        inputs=request.inputs,
        files=[f.model_dump() for f in request.files],
    )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
