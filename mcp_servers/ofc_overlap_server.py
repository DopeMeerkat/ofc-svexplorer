"""OFC overlap MCP server (HTTP)."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from utils.overlap.overlap_engine_stdlib import annotate_queries, count_svs_overlapping_exons


HOST = "127.0.0.1"
PORT = 8103
VERSION = "0.1.0"

SUPPORTED_RULES = [
    "gene_body_overlap",
    "exon_overlap",
    "within_gene_without_exon",
    "upstream_margin_overlap",
    "downstream_margin_overlap",
]


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
            self._send_json({"ok": True, "server": "ofc-overlap-mcp", "version": VERSION})
            return

        if tool == "get_supported_overlap_rules":
            self._send_json({"ok": True, "rules": SUPPORTED_RULES})
            return

        if tool == "annotate_overlap":
            queries = arguments.get("queries", []) or []
            margin = int(arguments.get("margin", 2000))
            emit_unmatched_rows = bool(arguments.get("emit_unmatched_rows", False))
            refresh_cache = bool(arguments.get("refresh_cache", False))
            try:
                result = annotate_queries(
                    queries=queries,
                    margin=margin,
                    refresh_cache=refresh_cache,
                    emit_unmatched_rows=emit_unmatched_rows,
                )
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return
            self._send_json(result)
            return

        if tool == "count_svs_overlapping_exons":
            try:
                result = count_svs_overlapping_exons(
                    table_name=arguments.get("table_name", "phenotype_svs"),
                    chromosome=arguments.get("chromosome"),
                    sample=arguments.get("sample"),
                    sv_type=arguments.get("sv_type"),
                    phenotype=arguments.get("phenotype"),
                    margin=int(arguments.get("margin", 0)),
                    refresh_cache=bool(arguments.get("refresh_cache", False)),
                )
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return
            self._send_json(result)
            return

        self._send_json({"ok": False, "error": "Unknown tool"}, status=400)


def main() -> None:
    port = int(os.getenv("MCP_OVERLAP_SERVER_PORT", str(PORT)))
    server = HTTPServer((HOST, port), MCPHandler)
    print(f"OFC Overlap MCP server listening on http://{HOST}:{port}/mcp")
    server.serve_forever()


if __name__ == "__main__":
    main()
