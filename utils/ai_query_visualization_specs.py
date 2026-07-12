"""
Render MCP visualization specs into Dash components.
"""

from __future__ import annotations

from typing import Any

import plotly.express as px
from dash import dcc, html
import dash_bio as dashbio

from app import build_local_igv_reference
from utils.database import get_tracks_for_genome


def _format_table(rows: list[dict[str, Any]], max_rows: int = 50) -> str:
    if not rows:
        return "No results."

    columns = list(rows[0].keys())
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines = [header, separator]

    for row in rows[:max_rows]:
        values = [str(row.get(col, "")) for col in columns]
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def render_visualization_spec(spec: dict[str, Any]):
    if not spec or spec.get("kind") in (None, "none"):
        return html.Div()

    kind = spec.get("kind")
    if kind == "bar_chart":
        rows = spec.get("rows") or []
        if not rows:
            return html.Div()
        fig = px.bar(rows, x=spec.get("x"), y=spec.get("y"), title=spec.get("title"))
        return dcc.Graph(figure=fig)

    if kind == "table":
        rows = spec.get("rows") or []
        table_md = _format_table(rows)
        return dcc.Markdown(table_md, style={"fontSize": "13px"})

    if kind == "igv_gene_view":
        locus = spec.get("locus")
        chrom = spec.get("chrom")
        if not locus or not chrom:
            return html.Div("No locus available for IGV.")
        tracks = get_tracks_for_genome(chrom)
        return dashbio.Igv(
            id="ai-query-mcp-igv",
            reference=build_local_igv_reference(chrom),
            locus=locus,
            tracks=tracks,
            style={"height": "650px", "width": "100%"},
        )

    return html.Div()
