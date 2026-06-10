import json
from typing import Any


def sse_event(event: str, **fields: Any) -> str:
    payload = {"event": event, **fields}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
