"""
OFC Visualization MCP server (HTTP).
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


HOST = "127.0.0.1"
PORT = 8102
VERSION = "0.1.0"

SUPPORTED_VISUALIZATIONS = [
    "none",
    "table",
    "bar_chart",
    "pie_chart",
    "histogram",
    "scatter_plot",
    "igv_gene_view",
]


def _recommend_visualization(columns: list[str], row_count: int, sample_rows: list[dict[str, Any]]):
    if row_count == 0:
        return "none", 0.2, "No rows returned."
    if columns and {"chrom", "x1", "x2"}.issubset(set(columns)):
        return "igv_gene_view", 0.7, "Gene coordinates available."
    if len(columns) == 2 and row_count > 1:
        return "bar_chart", 0.7, "Two-column grouped result."
    if len(columns) == 1:
        return "table", 0.6, "Single-column result."
    if row_count <= 5:
        return "table", 0.5, "Small result set."
    return "table", 0.4, "No clear chart shape."


class MCPHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
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
            self._send_json({"ok": True, "server": "ofc-viz-mcp", "version": VERSION})
            return

        if tool == "get_supported_visualizations":
            self._send_json({"ok": True, "visualizations": SUPPORTED_VISUALIZATIONS})
            return

        if tool == "recommend_visualization":
            columns = arguments.get("columns", []) or []
            row_count = int(arguments.get("row_count", 0))
            sample_rows = arguments.get("sample_rows", []) or []
            kind, confidence, reason = _recommend_visualization(columns, row_count, sample_rows)
            self._send_json({"visualization_kind": kind, "confidence": confidence, "reason": reason})
            return

        if tool == "build_bar_chart_spec":
            rows = arguments.get("rows", []) or []
            self._send_json({
                "kind": "bar_chart",
                "title": arguments.get("title"),
                "x": arguments.get("x"),
                "y": arguments.get("y"),
                "rows": rows,
            })
            return

        if tool == "build_table_spec":
            rows = arguments.get("rows", []) or []
            self._send_json({
                "kind": "table",
                "title": arguments.get("title"),
                "rows": rows,
            })
            return

        if tool == "build_igv_gene_view_spec":
            gene = arguments.get("gene")
            chrom = arguments.get("chrom")
            start = arguments.get("start")
            end = arguments.get("end")
            if not all([gene, chrom, start, end]):
                self._send_json({"ok": False, "error": "Missing gene coordinates."})
                return
            locus = f"{chrom}:{start}-{end}"
            self._send_json({
                "kind": "igv_gene_view",
                "title": f"{gene} view",
                "gene": gene,
                "locus": locus,
                "chrom": chrom,
                "start": start,
                "end": end,
                "rows": arguments.get("rows", []),
            })
            return

        self._send_json({"ok": False, "error": "Unknown tool"}, status=400)


def main() -> None:
    port = int(os.getenv("MCP_VIZ_SERVER_PORT", str(PORT)))
    server = HTTPServer((HOST, port), MCPHandler)
    print(f"OFC Visualization MCP server listening on http://{HOST}:{port}/mcp")
    server.serve_forever()


if __name__ == "__main__":
    main()
