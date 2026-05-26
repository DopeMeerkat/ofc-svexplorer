"""
Ollama client helper for local LLM requests.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_TIMEOUT = 120
DEBUG = False


def _post_json(url: str, payload: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Ollama request failed: {exc}") from exc

    if DEBUG:
        print("Ollama raw response:", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Ollama returned invalid JSON") from exc


def generate_ollama_response(
    prompt: str,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """
    Request a single, non-streaming response from Ollama.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
        },
    }
    response = _post_json("http://localhost:11434/api/generate", payload, timeout)
    text = response.get("response", "").strip()
    if not text:
        raise ValueError("Ollama returned an empty response")
    return text
