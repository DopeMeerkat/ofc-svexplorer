"""
Visualization agent for MCP-enabled AI Query.
"""

from __future__ import annotations

from typing import Any

from utils.mcp_client_manager import MCPClientManager


def _infer_xy(columns: list[str]) -> tuple[str | None, str | None]:
    if len(columns) >= 2:
        return columns[0], columns[1]
    return (columns[0], None) if columns else (None, None)


def run_visualization_agent(
    question: str,
    sql: str,
    columns: list[str],
    row_count: int,
    rows: list[dict[str, Any]],
    client: MCPClientManager,
) -> dict[str, Any]:
    tool_calls = []
    sample_rows = rows[:5]
    recommendation = client.call_viz_tool(
        "recommend_visualization",
        {
            "question": question,
            "sql": sql,
            "columns": columns,
            "row_count": row_count,
            "sample_rows": sample_rows,
        },
    )
    tool_calls.append({"tool": "recommend_visualization", "arguments": {"question": question}, "result": recommendation})

    kind = recommendation.get("visualization_kind", "none")
    if kind == "bar_chart":
        x, y = _infer_xy(columns)
        spec = client.call_viz_tool(
            "build_bar_chart_spec",
            {"rows": rows[:200], "x": x, "y": y, "title": "Query result"},
        )
        tool_calls.append({"tool": "build_bar_chart_spec", "arguments": {"x": x, "y": y}, "result": spec})
        return {"spec": spec, "tool_calls": tool_calls}

    if kind == "table":
        spec = client.call_viz_tool(
            "build_table_spec",
            {"rows": rows[:200], "title": "Query result"},
        )
        tool_calls.append({"tool": "build_table_spec", "arguments": {}, "result": spec})
        return {"spec": spec, "tool_calls": tool_calls}

    if kind == "igv_gene_view" and rows:
        row = rows[0]
        spec = client.call_viz_tool(
            "build_igv_gene_view_spec",
            {
                "gene": row.get("gene") or row.get("id"),
                "chrom": row.get("chrom") or row.get("gene_chrom"),
                "start": row.get("x1") or row.get("gene_start"),
                "end": row.get("x2") or row.get("gene_end"),
                "rows": rows[:200],
            },
        )
        tool_calls.append({"tool": "build_igv_gene_view_spec", "arguments": {}, "result": spec})
        return {"spec": spec, "tool_calls": tool_calls}

    return {"spec": {"kind": "none"}, "tool_calls": tool_calls}
