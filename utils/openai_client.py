"""
OpenAI client helper for chat completions.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 120
DEFAULT_KEY_PATH = "api_key.txt"


def _load_api_key(key_path: str) -> str:
    if not os.path.exists(key_path):
        raise FileNotFoundError(
            f"OpenAI key file not found at {key_path}."
        )
    with open(key_path, "r", encoding="utf-8") as handle:
        key = handle.read().strip()
    if not key:
        raise ValueError("OpenAI key file is empty")
    return key


def _post_json(url: str, payload: dict, api_key: str, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise ConnectionError(f"OpenAI request failed: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI returned invalid JSON") from exc


def generate_openai_response(
    prompt: str,
    model: str = DEFAULT_OPENAI_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
    key_path: str = DEFAULT_KEY_PATH,
) -> str:
    """
    Request a single response from OpenAI Chat Completions API.
    """
    api_key = _load_api_key(key_path)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise research assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    response = _post_json("https://api.openai.com/v1/chat/completions", payload, api_key, timeout)
    choices = response.get("choices", [])
    if not choices:
        raise ValueError("OpenAI returned no choices")
    message = choices[0].get("message", {})
    content = message.get("content", "").strip()
    if not content:
        raise ValueError("OpenAI returned an empty response")
    return content
