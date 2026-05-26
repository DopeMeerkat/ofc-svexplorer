"""
Visualization helpers for AI Query results.
"""

from __future__ import annotations

from typing import Any, Optional

import plotly.express as px
from dash import dcc, html
import dash_bio as dashbio

from utils.database import get_tracks_for_genome

ALLOWED_VISUALIZATION_KINDS = {
    "none",
    "bar_chart",
    "pie_chart",
    "histogram",
    "scatter_plot",
    "igv_gene_window",
    "family_igv_compare",
    "population_igv_gene_window",
}

try:
    from pydantic import BaseModel
    _HAS_PYDANTIC = True
except ImportError:  # pragma: no cover - fallback when pydantic is unavailable
    BaseModel = object
    _HAS_PYDANTIC = False


if _HAS_PYDANTIC:

    class VisualizationSpec(BaseModel):
        enabled: bool = False
        kind: str = "none"
        title: Optional[str] = None
        x: Optional[str] = None
        y: Optional[str] = None
        color: Optional[str] = None
        gene: Optional[str] = None
        chrom: Optional[str] = None
        start: Optional[int] = None
        end: Optional[int] = None
        rows: Optional[list[dict[str, Any]]] = None

else:

    class VisualizationSpec:
        def __init__(
            self,
            enabled: bool = False,
            kind: str = "none",
            title: Optional[str] = None,
            x: Optional[str] = None,
            y: Optional[str] = None,
            color: Optional[str] = None,
            gene: Optional[str] = None,
            chrom: Optional[str] = None,
            start: Optional[int] = None,
            end: Optional[int] = None,
            rows: Optional[list[dict[str, Any]]] = None,
        ) -> None:
            self.enabled = enabled
            self.kind = kind
            self.title = title
            self.x = x
            self.y = y
            self.color = color
            self.gene = gene
            self.chrom = chrom
            self.start = start
            self.end = end
            self.rows = rows


def infer_title(plan) -> str:
    if getattr(plan, "intent", None):
        return plan.intent.replace("_", " ").title()
    return "Query Visualization"


def _resolve_gene_label(plan, row: dict[str, Any]) -> str | None:
    if getattr(plan, "gene", None):
        return plan.gene
    if row.get("gene_id"):
        return row.get("gene_id")
    if row.get("id"):
        return row.get("id")
    return None


def _extract_gene_window(rows: list[dict[str, Any]], flank_bp: int) -> tuple[str, int, int] | None:
    if not rows:
        return None
    row = rows[0]
    if "gene_chrom" in row and "gene_start" in row and "gene_end" in row:
        chrom = row.get("gene_chrom")
        start = row.get("gene_start")
        end = row.get("gene_end")
    elif "chrom" in row and "x1" in row and "x2" in row:
        chrom = row.get("chrom")
        start = row.get("x1")
        end = row.get("x2")
    else:
        return None

    if chrom is None or start is None or end is None:
        return None

    start = int(start)
    end = int(end)
    start = max(0, start - int(flank_bp or 0))
    end = end + int(flank_bp or 0)
    return chrom, start, end


def _select_visualization_kind(compiled, plan) -> str:
    plan_kind = getattr(plan, "visualization_kind", None)
    if plan_kind in ALLOWED_VISUALIZATION_KINDS and plan_kind != "none":
        return plan_kind
    return compiled.get("visualization_kind", "none")


def build_visualization_spec(compiled, plan, rows):
    kind = _select_visualization_kind(compiled, plan)

    if not rows:
        return VisualizationSpec(enabled=False, kind="none")

    if kind == "bar_chart":
        columns = list(rows[0].keys())
        return VisualizationSpec(
            enabled=True,
            kind="bar_chart",
            title=infer_title(plan),
            x=columns[0] if columns else None,
            y=columns[1] if len(columns) > 1 else None,
            rows=rows,
        )

    if kind in {"igv_gene_window", "family_igv_compare", "population_igv_gene_window"}:
        window = _extract_gene_window(rows, getattr(plan, "flank_bp", 0))
        if not window:
            return VisualizationSpec(enabled=False, kind="none")
        chrom, start, end = window
        gene_label = _resolve_gene_label(plan, rows[0])
        title_prefix = "SVs near"
        if kind == "family_igv_compare":
            title_prefix = "Family SVs near"
        title = f"{title_prefix} {gene_label}" if gene_label else "Gene window"
        return VisualizationSpec(
            enabled=True,
            kind=kind,
            title=title,
            gene=gene_label,
            chrom=chrom,
            start=start,
            end=end,
            rows=rows,
        )

    if kind == "none" and (getattr(plan, "gene", None) or getattr(plan, "gene_a", None)):
        window = _extract_gene_window(rows, getattr(plan, "flank_bp", 0))
        if window:
            chrom, start, end = window
            gene_label = _resolve_gene_label(plan, rows[0])
            return VisualizationSpec(
                enabled=True,
                kind="population_igv_gene_window",
                title=f"SVs near {gene_label}" if gene_label else "Gene window",
                gene=gene_label,
                chrom=chrom,
                start=start,
                end=end,
                rows=rows,
            )

    return VisualizationSpec(enabled=False, kind="none")


def render_visualization(spec: VisualizationSpec):
    if not spec or not spec.enabled:
        return html.Div()

    if spec.kind == "bar_chart":
        return render_bar_chart(spec)

    if spec.kind == "pie_chart":
        return render_pie_chart(spec)

    if spec.kind == "histogram":
        return render_histogram(spec)

    if spec.kind == "scatter_plot":
        return render_scatter_plot(spec)

    if spec.kind == "igv_gene_window":
        return render_igv_gene_window(spec)

    if spec.kind == "family_igv_compare":
        return render_family_igv_compare(spec)

    if spec.kind == "population_igv_gene_window":
        return render_population_igv_gene_window(spec)

    return html.Div()


def render_bar_chart(spec: VisualizationSpec):
    if not spec.rows or not spec.x or not spec.y:
        return html.Div()

    fig = px.bar(spec.rows, x=spec.x, y=spec.y, title=spec.title)
    return dcc.Graph(figure=fig)


def render_pie_chart(spec: VisualizationSpec):
    if not spec.rows or not spec.x or not spec.y:
        return html.Div()

    fig = px.pie(spec.rows, names=spec.x, values=spec.y, title=spec.title)
    return dcc.Graph(figure=fig)


def render_histogram(spec: VisualizationSpec):
    if not spec.rows or not spec.x:
        return html.Div()

    fig = px.histogram(spec.rows, x=spec.x, title=spec.title)
    return dcc.Graph(figure=fig)


def render_scatter_plot(spec: VisualizationSpec):
    if not spec.rows or not spec.x or not spec.y:
        return html.Div()

    fig = px.scatter(spec.rows, x=spec.x, y=spec.y, title=spec.title)
    return dcc.Graph(figure=fig)


def _build_igv_locus(spec: VisualizationSpec) -> str | None:
    if not spec.chrom:
        return None
    if spec.start is not None and spec.end is not None:
        return f"{spec.chrom}:{spec.start}-{spec.end}"
    return spec.chrom


def render_igv_gene_window(spec: VisualizationSpec):
    locus = _build_igv_locus(spec)
    if not locus:
        return html.Div("No locus available for IGV.")

    tracks = get_tracks_for_genome(spec.chrom, include_interactions=False)
    return dashbio.Igv(
        id="ai-query-igv",
        genome="hg38",
        locus=locus,
        tracks=tracks,
        style={"height": "650px", "width": "100%"},
    )


def render_family_igv_compare(spec: VisualizationSpec):
    locus = _build_igv_locus(spec)
    if not locus:
        return html.Div("No locus available for IGV.")

    tracks = get_tracks_for_genome(spec.chrom, include_interactions=False)
    return dashbio.Igv(
        id="ai-query-family-igv",
        genome="hg38",
        locus=locus,
        tracks=tracks,
        style={"height": "650px", "width": "100%"},
    )


def render_population_igv_gene_window(spec: VisualizationSpec):
    locus = _build_igv_locus(spec)
    if not locus:
        return html.Div("No locus available for IGV.")

    tracks = get_tracks_for_genome(spec.chrom, include_interactions=False)
    try:
        from pages.population_svs import create_population_tracks
        population_tracks = create_population_tracks(spec.chrom)
    except Exception:
        population_tracks = []

    return dashbio.Igv(
        id="ai-query-population-igv",
        genome="hg38",
        locus=locus,
        tracks=tracks + population_tracks,
        style={"height": "650px", "width": "100%"},
    )
