"""JSON contract helpers for subprocess callers."""
from __future__ import annotations

import json


def build_response(
    *,
    intent: str,
    argv: list[str],
    stdout: str,
    exit_code: int,
    data: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build the API envelope while preserving the four-key contract."""
    payload: dict[str, object] = {
        "intent": intent,
        "argv": list(argv),
        "stdout": stdout,
        "exit_code": exit_code,
    }
    if data:
        payload["data"] = data
    return payload


def dumps_response(payload: dict[str, object]) -> str:
    """Serialize the response envelope as UTF-8 safe JSON."""
    return json.dumps(payload, ensure_ascii=False)
