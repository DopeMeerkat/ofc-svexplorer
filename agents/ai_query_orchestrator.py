"""
AI Query orchestrator for MCP-enabled flow.
"""

from __future__ import annotations

from typing import Any

from agents.db_agent import run_db_agent
from agents.visualization_agent import run_visualization_agent
from utils.mcp_client_manager import MCPClientManager


def handle_ai_query_with_mcp(user_text: str, model_value: str, show_visualization: bool) -> dict[str, Any]:
    client = MCPClientManager()
    db_result = run_db_agent(user_text, model_value, client)
    if not db_result.get("ok"):
        return {
            "ok": False,
            "error": db_result.get("error", "Database request failed."),
            "db_tool_calls": db_result.get("tool_calls", []),
        }

    rows = db_result.get("rows", [])
    summary = f"Query returned {len(rows)} row(s). See the result preview below." if rows else "No results found."

    viz_spec = {"kind": "none"}
    viz_calls = []
    if show_visualization:
        viz_result = run_visualization_agent(
            user_text,
            db_result.get("sql", ""),
            db_result.get("columns", []),
            db_result.get("row_count", 0),
            rows,
            client,
        )
        viz_spec = viz_result.get("spec", {"kind": "none"})
        viz_calls = viz_result.get("tool_calls", [])

    return {
        "ok": True,
        "response_summary": summary,
        "sql": db_result.get("sql", ""),
        "rows": rows,
        "columns": db_result.get("columns", []),
        "db_tool_calls": db_result.get("tool_calls", []),
        "viz_tool_calls": viz_calls,
        "visualization_spec": viz_spec,
    }
