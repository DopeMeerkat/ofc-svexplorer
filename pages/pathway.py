"""
Pathway diagram and GO enrichment page.
"""

import base64
import io
import re
from pathlib import Path

import dash
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html
import dash_cytoscape as cyto

from pathway.network_app_rel import (
    DEFAULT_LAYOUT,
    HIT_COLOR,
    LAYOUT_CONFIGS,
    build_cytoscape_elements,
    build_node_table,
    build_stylesheet,
    compute_gene_hits,
    compute_go_enrichment,
    genes_not_in_network,
    get_network_universe,
    load_edges,
    load_go_annotations,
    parse_gene_query,
)
from utils.styling import UCONN_GRAY, UCONN_LIGHT_BLUE, UCONN_NAVY


cyto.load_extra_layouts()

PATHWAY_DIR = Path(__file__).resolve().parents[1] / "pathway"
EDGES_CSV = PATHWAY_DIR / "edges_e.csv"
NODES_CSV = PATHWAY_DIR / "nodes_e.csv"
ANNOTATIONS_CSV = PATHWAY_DIR / "go_gene_annotations.csv"

DIMMED_OPACITY = 0.25

EDGES_DF = load_edges(EDGES_CSV)
NODES_DF = build_node_table(EDGES_DF, NODES_CSV, require_nodes_csv=True)
ANNOTATIONS = load_go_annotations(ANNOTATIONS_CSV)
BASE_ELEMENTS = build_cytoscape_elements(EDGES_DF, NODES_DF)
BASE_STYLESHEET = build_stylesheet() + [
    {
        "selector": ".hit-node",
        "style": {
            "border-width": 4,
            "border-color": HIT_COLOR,
            "border-style": "solid",
            "z-index": 9999,
        },
    },
    {
        "selector": ".dimmed-node",
        "style": {"opacity": DIMMED_OPACITY},
    },
]


def _button_style(background_color=UCONN_NAVY):
    return {
        "backgroundColor": background_color,
        "color": "white",
        "border": "none",
        "padding": "9px 14px",
        "borderRadius": "4px",
        "cursor": "pointer",
        "fontWeight": "600",
    }


def _extract_genes_from_upload(contents: str) -> tuple[set[str], str | None]:
    if not contents:
        return set(), None

    try:
        _, encoded = contents.split(",", 1)
        decoded = base64.b64decode(encoded).decode("utf-8-sig")
    except Exception as exc:
        return set(), f"Could not read uploaded CSV: {exc}"

    try:
        df = pd.read_csv(io.StringIO(decoded))
    except Exception as exc:
        return set(), f"Could not parse uploaded CSV: {exc}"

    if df.empty and not df.columns.empty:
        raw_tokens = parse_gene_query(" ".join(str(col) for col in df.columns))
        return raw_tokens, None

    gene_column = None
    preferred_names = {"gene", "genes", "gene_symbol", "genesymbol", "symbol"}
    for column in df.columns:
        normalized = re.sub(r"[^a-z0-9]", "", str(column).lower())
        if normalized in preferred_names:
            gene_column = column
            break

    if gene_column is None:
        gene_column = df.columns[0]
        genes = parse_gene_query(" ".join(df[gene_column].dropna().astype(str)))
        first_header = str(gene_column).strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", first_header):
            genes |= parse_gene_query(first_header)
        return genes, None

    return parse_gene_query(" ".join(df[gene_column].dropna().astype(str))), None


def _build_highlighted_elements(query_genes: set[str]) -> list[dict]:
    hits = compute_gene_hits(query_genes, NODES_DF, ANNOTATIONS)
    highlighted = []
    for element in BASE_ELEMENTS:
        data = element["data"]
        if "source" in data:
            highlighted.append(element)
            continue
        info = hits.get(data["id"], {"hit": False})
        highlighted.append({**element, "classes": "hit-node" if info["hit"] else "dimmed-node"})
    return highlighted


def _build_summary(query_genes: set[str]) -> str:
    hits = compute_gene_hits(query_genes, NODES_DF, ANNOTATIONS)
    universe = get_network_universe(NODES_DF, ANNOTATIONS)
    in_network = query_genes & universe
    coverage = 100 * len(in_network) / len(query_genes) if query_genes else 0

    lines = [
        f"Query: {len(query_genes)} gene(s) -> {', '.join(sorted(query_genes))}",
        f"Network coverage: {len(in_network)}/{len(query_genes)} query genes found in this network's {len(universe)}-gene universe ({coverage:.0f}%)",
        "",
    ]

    hit_nodes = {node_id: info for node_id, info in hits.items() if info["hit"]}
    if hit_nodes:
        lines.append(f"{len(hit_nodes)} node(s) lit up:")
        for node_id, info in hit_nodes.items():
            if info["total_annotated"] is None:
                lines.append(f"  {node_id}  (direct gene match)")
            else:
                matched = ", ".join(sorted(info["matched_genes"]))
                lines.append(
                    f"  {node_id}  ({len(info['matched_genes'])}/{info['total_annotated']} annotated genes hit: {matched})"
                )
    else:
        lines.append("No nodes matched this query.")

    not_found = genes_not_in_network(query_genes, NODES_DF, ANNOTATIONS)
    if not_found:
        lines.extend(["", f"Not found anywhere in the network: {', '.join(sorted(not_found))}"])

    return "\n".join(lines)


def page_layout():
    return html.Div(
        [
            html.H2(
                "Pathway",
                style={"color": UCONN_NAVY, "marginBottom": "12px", "fontWeight": "bold"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Gene list", style={"fontWeight": "600", "color": UCONN_NAVY}),
                            dcc.Textarea(
                                id="pathway-gene-input",
                                value="TP63, IRF6, GRHL3, HDAC3, EZH2",
                                placeholder="TP63, IRF6, GRHL3, HDAC3, EZH2",
                                style={"width": "100%", "height": "84px", "marginTop": "6px"},
                            ),
                        ],
                        style={"flex": "1 1 440px"},
                    ),
                    html.Div(
                        [
                            html.Label("Upload CSV", style={"fontWeight": "600", "color": UCONN_NAVY}),
                            dcc.Upload(
                                id="pathway-gene-upload",
                                children=html.Div(["Drag and drop or select a .csv"]),
                                accept=".csv,text/csv",
                                multiple=False,
                                style={
                                    "border": f"1px dashed {UCONN_LIGHT_BLUE}",
                                    "padding": "18px",
                                    "marginTop": "6px",
                                    "textAlign": "center",
                                    "backgroundColor": "#f8fbfd",
                                },
                            ),
                            html.Div(id="pathway-upload-status", style={"fontSize": "13px", "marginTop": "8px"}),
                        ],
                        style={"flex": "1 1 320px"},
                    ),
                ],
                style={"display": "flex", "gap": "18px", "flexWrap": "wrap", "marginBottom": "12px"},
            ),
            html.Div(
                [
                    html.Button("Analyze", id="pathway-highlight-button", n_clicks=0, style=_button_style()),
                    html.Button(
                        "Clear",
                        id="pathway-clear-button",
                        n_clicks=0,
                        style={**_button_style(UCONN_GRAY), "marginLeft": "8px"},
                    ),
                    dcc.Dropdown(
                        id="pathway-layout-dropdown",
                        options=[{"label": name, "value": name} for name in LAYOUT_CONFIGS],
                        value=DEFAULT_LAYOUT,
                        clearable=False,
                        style={"width": "220px", "display": "inline-block", "marginLeft": "16px", "verticalAlign": "middle"},
                    ),
                ],
                style={"marginBottom": "12px"},
            ),
            html.Div(
                [
                    cyto.Cytoscape(
                        id="pathway-network",
                        elements=BASE_ELEMENTS,
                        stylesheet=BASE_STYLESHEET,
                        layout=LAYOUT_CONFIGS[DEFAULT_LAYOUT],
                        style={"width": "100%", "height": "650px", "border": f"1px solid {UCONN_NAVY}"},
                    ),
                    html.Div(
                        id="pathway-hover-info",
                        style={
                            "position": "absolute",
                            "top": "10px",
                            "right": "10px",
                            "maxWidth": "320px",
                            "backgroundColor": "rgba(255, 255, 255, 0.97)",
                            "border": "1px solid #ccc",
                            "padding": "8px 10px",
                            "fontSize": "12px",
                            "fontFamily": "monospace",
                            "boxShadow": "0 2px 6px rgba(0,0,0,0.15)",
                            "pointerEvents": "none",
                        },
                    ),
                ],
                style={"position": "relative"},
            ),
            html.Div(id="pathway-node-info", style={"marginTop": "10px", "fontFamily": "monospace"}),
            html.Div(
                id="pathway-hit-summary",
                style={"marginTop": "10px", "fontFamily": "monospace", "whiteSpace": "pre-wrap"},
            ),
            html.H3("GO Term Enrichment", style={"color": UCONN_NAVY, "marginTop": "24px"}),
            dash_table.DataTable(
                id="pathway-enrichment-table",
                columns=[
                    {"name": "GO_ID", "id": "GO_ID"},
                    {"name": "Label", "id": "Label"},
                    {"name": "K", "id": "annotated_in_network (K)"},
                    {"name": "k", "id": "hits (k)"},
                    {"name": "n", "id": "query_in_network (n)"},
                    {"name": "N", "id": "network_universe (N)"},
                    {"name": "Odds ratio", "id": "odds_ratio"},
                    {"name": "p-value", "id": "p_value"},
                    {"name": "q-value", "id": "q_value"},
                ],
                data=[],
                sort_action="native",
                page_size=15,
                style_cell={"fontFamily": "monospace", "fontSize": "12px", "padding": "5px", "textAlign": "left"},
                style_header={"fontWeight": "bold", "backgroundColor": "#f1f5f9"},
                style_table={"overflowX": "auto"},
                style_data_conditional=[
                    {
                        "if": {"filter_query": "{q_value} < 0.05", "column_id": "q_value"},
                        "color": HIT_COLOR,
                        "fontWeight": "bold",
                    }
                ],
            ),
            dcc.Store(id="pathway-upload-genes-store", data=[]),
            dcc.Store(id="pathway-query-genes-store", data=[]),
        ],
        style={"padding": "20px"},
    )


@callback(Output("pathway-network", "layout"), Input("pathway-layout-dropdown", "value"))
def update_pathway_layout(layout_name):
    return LAYOUT_CONFIGS.get(layout_name, LAYOUT_CONFIGS[DEFAULT_LAYOUT])


@callback(
    Output("pathway-upload-genes-store", "data"),
    Output("pathway-upload-status", "children"),
    Input("pathway-gene-upload", "contents"),
    State("pathway-gene-upload", "filename"),
    prevent_initial_call=True,
)
def parse_uploaded_gene_csv(contents, filename):
    genes, error = _extract_genes_from_upload(contents)
    if error:
        return [], html.Span(error, style={"color": "#b91c1c"})
    if not genes:
        return [], html.Span("No gene symbols found in uploaded CSV.", style={"color": "#b91c1c"})
    return sorted(genes), html.Span(f"Loaded {len(genes)} gene(s) from {filename}.", style={"color": UCONN_NAVY})


@callback(Output("pathway-node-info", "children"), Input("pathway-network", "tapNodeData"))
def show_pathway_node_info(node_data):
    if not node_data:
        return "Click a node to see its details."
    parts = [
        f"ID: {node_data.get('id')}",
        f"Label: {node_data.get('label')}",
        f"Type: {node_data.get('type')}",
    ]
    if node_data.get("GO_Aspect") and node_data.get("GO_Aspect") != "N/A":
        parts.append(f"GO_Aspect: {node_data.get('GO_Aspect')}")
    return " | ".join(parts)


@callback(
    Output("pathway-network", "elements"),
    Output("pathway-hit-summary", "children"),
    Output("pathway-query-genes-store", "data"),
    Output("pathway-enrichment-table", "data"),
    Input("pathway-highlight-button", "n_clicks"),
    Input("pathway-clear-button", "n_clicks"),
    State("pathway-gene-input", "value"),
    State("pathway-upload-genes-store", "data"),
    prevent_initial_call=True,
)
def highlight_pathway_gene_hits(_highlight_clicks, _clear_clicks, query_text, uploaded_genes):
    if dash.ctx.triggered_id == "pathway-clear-button":
        return BASE_ELEMENTS, "Highlight cleared.", [], []

    query_genes = parse_gene_query(query_text) | set(uploaded_genes or [])
    if not query_genes:
        return BASE_ELEMENTS, "Enter gene names or upload a CSV containing gene symbols.", [], []

    enrichment_df = compute_go_enrichment(query_genes, NODES_DF, ANNOTATIONS)
    return (
        _build_highlighted_elements(query_genes),
        _build_summary(query_genes),
        sorted(query_genes),
        enrichment_df.to_dict("records"),
    )


@callback(
    Output("pathway-hover-info", "children"),
    Input("pathway-network", "mouseoverNodeData"),
    State("pathway-query-genes-store", "data"),
)
def show_pathway_hover_tooltip(node_data, current_query):
    if not node_data:
        return ""

    node_id = node_data["id"]
    header = html.Div(f"{node_data.get('label')} ({node_id})", style={"fontWeight": "bold", "marginBottom": "4px"})

    if node_data.get("type") == "Gene":
        return [header]

    annotated = sorted(ANNOTATIONS.get(node_id, set()))
    if not annotated:
        return [header, html.Div("No annotation data loaded for this term.", style={"color": "#888"})]

    query_set = set(current_query or [])
    gene_spans = []
    for index, gene in enumerate(annotated):
        is_hit = gene in query_set
        gene_spans.append(html.Span(gene, style={"color": HIT_COLOR, "fontWeight": "bold"} if is_hit else {}))
        if index < len(annotated) - 1:
            gene_spans.append(html.Span(", "))

    return [
        header,
        html.Div(f"{len(annotated)} annotated gene(s):", style={"marginBottom": "2px"}),
        html.Div(gene_spans),
    ]
