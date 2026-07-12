"""
OFC DB MCP server (HTTP).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from utils.database import DB_PATH, run_readonly_query


HOST = "127.0.0.1"
PORT = 8101
VERSION = "0.1.0"

FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "attach",
    "detach",
    "reindex",
    "vacuum",
}


def _validate_sql(sql: str) -> tuple[bool, str | None]:
    if not sql or not isinstance(sql, str):
        return False, "SQL must be a non-empty string."
    stripped = sql.strip().rstrip(";")
    lowered = stripped.lower()
    if not lowered.startswith("select"):
        return False, "Only SELECT statements are allowed."
    if ";" in stripped:
        return False, "Multiple statements are not allowed."
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            return False, f"Forbidden keyword detected: {keyword}."
    return True, None


def _summarize_shape(rows: list[dict[str, Any]]) -> dict[str, Any]:
    columns = list(rows[0].keys()) if rows else []
    numeric = []
    categorical = []
    for col in columns:
        values = [row.get(col) for row in rows if row.get(col) is not None]
        if values and all(isinstance(v, (int, float)) for v in values):
            numeric.append(col)
        else:
            categorical.append(col)
    return {
        "row_count": len(rows),
        "columns": columns,
        "numeric_columns": numeric,
        "categorical_columns": categorical,
    }


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
            self._send_json({"ok": True, "server": "ofc-db-mcp", "version": VERSION})
            return

        if tool == "get_supported_query_capabilities":
            self._send_json({
                "ok": True,
                "capabilities": [
                    "gene lookup",
                    "chromosome gene listing",
                    "gene length queries",
                    "phenotype filters",
                    "child/parent filters",
                    "sample SV lookup",
                    "family membership queries",
                    "family SV queries",
                    "background cohort summaries",
                    "exon annotation queries",
                    "SV/exon overlap queries",
                    "count/distribution queries",
                ],
            })
            return

        if tool == "validate_select_sql":
            sql = arguments.get("sql", "")
            valid, reason = _validate_sql(sql)
            self._send_json({"valid": valid, "reason": reason})
            return

        if tool == "execute_readonly_sql":
            sql = arguments.get("sql", "")
            limit = int(arguments.get("limit", 500))
            valid, reason = _validate_sql(sql)
            if not valid:
                self._send_json({"ok": False, "error": reason})
                return
            try:
                rows = run_readonly_query(sql, limit=limit)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return
            columns = list(rows[0].keys()) if rows else []
            self._send_json({
                "ok": True,
                "sql": sql,
                "row_count": len(rows),
                "columns": columns,
                "rows": rows,
            })
            return

        if tool == "explain_query_plan":
            sql = arguments.get("sql", "")
            valid, reason = _validate_sql(sql)
            if not valid:
                self._send_json({"ok": False, "error": reason})
                return
            try:
                conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("EXPLAIN QUERY PLAN " + sql.strip().rstrip(";"))
                plan_rows = [dict(row) for row in cursor.fetchall()]
                conn.close()
                self._send_json({"ok": True, "plan_rows": plan_rows})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)})
            return

        if tool == "summarize_result_shape":
            rows = arguments.get("rows", []) or []
            self._send_json(_summarize_shape(rows))
            return

        self._send_json({"ok": False, "error": "Unknown tool"}, status=400)


def main() -> None:
    port = int(os.getenv("MCP_DB_SERVER_PORT", str(PORT)))
    server = HTTPServer((HOST, port), MCPHandler)
    print(f"OFC DB MCP server listening on http://{HOST}:{port}/mcp")
    server.serve_forever()


if __name__ == "__main__":
    main()
