"""
OFC Discovery MCP server (HTTP).

Wraps agents.tool_discovery and agents.tool_runner to expose
discovered workers and tools through the MCP interface.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from agents.tool_discovery import find_tool, load_tool_registry
from agents.tool_runner import run_tool


HOST = "127.0.0.1"
PORT = 8104
VERSION = "0.1.0"


def _summarize_tool(tool_entry: dict[str, Any]) -> dict[str, Any]:
    td = tool_entry["tool"]
    return {
        "id": td.get("id"),
        "version": td.get("version"),
        "display_name": td.get("display_name"),
        "description": td.get("description"),
        "entrypoint": td.get("entrypoint"),
        "inputs": td.get("inputs"),
        "outputs": td.get("outputs"),
        "constraints": td.get("constraints"),
    }


class MCPHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            self._send_json({"ok": False, "error": "Not found"}, status=404)
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json({"ok": False, "error": "Invalid JSON"}, status=400)
            return

        tool = payload.get("tool")
        arguments = payload.get("arguments", {}) or {}

        if tool == "health_check":
            self._send_json({"ok": True, "server": "ofc-discovery-mcp", "version": VERSION})
            return

        if tool == "list_discovered_workers":
            registry = load_tool_registry()
            workers_out = []
            for w in registry.get("workers", []):
                wd = w["worker"]
                workers_out.append({
                    "worker_id": wd.get("worker_id"),
                    "display_name": wd.get("display_name"),
                    "description": wd.get("description"),
                    "simulated": wd.get("simulated", False),
                    "resources": wd.get("resources"),
                    "tool_ids": [t["tool"].get("id") for t in w.get("tools", [])],
                })
            self._send_json({"ok": True, "workers": workers_out})
            return

        if tool == "list_discovered_tools":
            registry = load_tool_registry()
            tools_out = []
            for w in registry.get("workers", []):
                worker_id = w["worker"].get("worker_id")
                for t in w.get("tools", []):
                    summary = _summarize_tool(t)
                    summary["worker_id"] = worker_id
                    tools_out.append(summary)
            self._send_json({"ok": True, "tools": tools_out})
            return

        if tool == "get_discovered_tool":
            tool_id = arguments.get("tool_id")
            if not tool_id:
                self._send_json({"ok": False, "error": "Missing tool_id"}, status=400)
                return
            resolved = find_tool(tool_id)
            if resolved is None:
                self._send_json({"ok": False, "error": f"Tool '{tool_id}' not found"}, status=404)
                return
            self._send_json({
                "ok": True,
                "worker_id": resolved["worker"].get("worker_id"),
                "worker_dir": resolved["worker_dir"],
                "tool": resolved["tool"],
                "tool_dir": resolved["tool_dir"],
            })
            return

        if tool == "run_discovered_tool":
            tool_id = arguments.get("tool_id")
            input_path = arguments.get("input_path")
            if not tool_id:
                self._send_json({"ok": False, "error": "Missing tool_id"}, status=400)
                return
            if not input_path:
                self._send_json({"ok": False, "error": "Missing input_path"}, status=400)
                return
            parameters = arguments.get("parameters", {}) or {}
            timeout = arguments.get("timeout")
            if timeout is not None:
                timeout = int(timeout)
            result = run_tool(tool_id, input_path, parameters=parameters, timeout=timeout)
            self._send_json(result)
            return

        self._send_json({"ok": False, "error": "Unknown tool"}, status=400)


def main() -> None:
    if "MCP_TOOL_PYTHON" not in os.environ:
        os.environ["MCP_TOOL_PYTHON"] = sys.executable
    port = int(os.getenv("MCP_DISCOVERY_SERVER_PORT", str(PORT)))
    server = HTTPServer((HOST, port), MCPHandler)
    print(f"OFC Discovery MCP server listening on http://{HOST}:{port}/mcp")
    print(f"  Using tool Python: {os.environ['MCP_TOOL_PYTHON']}")
    server.serve_forever()


if __name__ == "__main__":
    main()
