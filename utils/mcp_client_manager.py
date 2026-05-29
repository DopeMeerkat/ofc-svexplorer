"""
Minimal MCP HTTP client manager.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_TIMEOUT = 30
DEFAULT_DB_URL = "http://127.0.0.1:8101/mcp"
DEFAULT_VIZ_URL = "http://127.0.0.1:8102/mcp"


def _post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
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
        return {"ok": False, "error": f"MCP request failed: {exc}"}

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"MCP returned invalid JSON: {exc}"}


class MCPClientManager:
    def __init__(self) -> None:
        self.db_url = os.getenv("MCP_DB_SERVER_URL", DEFAULT_DB_URL)
        self.viz_url = os.getenv("MCP_VIZ_SERVER_URL", DEFAULT_VIZ_URL)
        self.timeout = int(os.getenv("MCP_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT)))

    def call_db_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {"tool": tool_name, "arguments": arguments}
        return _post_json(self.db_url, payload, self.timeout)

    def call_viz_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {"tool": tool_name, "arguments": arguments}
        return _post_json(self.viz_url, payload, self.timeout)
