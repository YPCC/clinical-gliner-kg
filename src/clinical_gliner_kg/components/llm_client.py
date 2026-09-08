"""OpenAI-compatible chat completions (OpenAI, Gemini API key, vLLM, Ollama, Groq, …)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


GOOGLE_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"


def resolve_api_key(*env_names: str) -> str:
    for name in env_names:
        if not name:
            continue
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def chat_complete(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.0,
    timeout: int = 45,
) -> str:
    if not api_key:
        raise RuntimeError("LLM API key is empty")
    root = base_url.rstrip("/")
    if not root.endswith("/v1") and not root.endswith("/openai"):
        # Gemini OpenAI-compat already ends with /openai; others usually end with /v1.
        pass
    url = root + "/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": temperature}
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data: Any = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {detail}") from exc
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        raise RuntimeError(f"LLM response missing choices: {str(data)[:300]}")
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


def google_base_url(explicit: str = "") -> str:
    return (explicit or GOOGLE_OPENAI_BASE).rstrip("/") + "/"
