"""
Pathway diagram page.
"""

import base64
import io
import re
from pathlib import Path
from urllib.parse import parse_qs

import dash
import pandas as pd
from dash import ALL, Input, Output, State, callback, dcc, html, no_update
import dash_cytoscape as cyto

from pathway.network_app_rel import (
    DEFAULT_LAYOUT,
    HIT_COLOR,
    LAYOUT_CONFIGS,
    build_stylesheet,
    compute_gene_hits,
    genes_not_in_network,
    get_network_universe,
    load_go_annotations,
    parse_gene_query,
)
from utils import pathway_networks
from utils.styling import UCONN_GRAY, UCONN_LIGHT_BLUE, UCONN_NAVY, muted_text_style, page_title_style


cyto.load_extra_layouts()

PATHWAY_DIR = Path(__file__).resolve().parents[1] / "pathway"
ANNOTATIONS_CSV = PATHWAY_DIR / "go_gene_annotations.csv"

DIMMED_OPACITY = 0.25

ANNOTATIONS = load_go_annotations(ANNOTATIONS_CSV)


_NETWORK_CACHE: dict[str, dict] = {}


def _versions() -> list[dict]:
    return pathway_networks.list_versions()


def _version_choices() -> list[dict]:
    """Return the publication-facing network choices in display order."""
    versions = {v["id"]: v for v in _versions()}
    ordered = [
        ("Baseline", "Baseline"),
        ("Extended2", "Extended"),
        ("Extended1", "Extended"),
        ("CaseStudy6", "Case Study 6"),
    ]
    choices = []
    used_labels = set()
    for version_id, label in ordered:
        if version_id in versions and label not in used_labels:
            choices.append({"id": version_id, "label": label})
            used_labels.add(label)
    return choices


def _default_version_id() -> str | None:
    choices = _version_choices()
    return choices[0]["id"] if choices else None


def _default_visible_networks() -> list[str]:
    return [choice["id"] for choice in _version_choices() if choice["label"] != "Case Study 6"]


def _network(version_id: str | None = None) -> dict:
    version_id = version_id or _default_version_id()
    if version_id not in _NETWORK_CACHE:
        _NETWORK_CACHE[version_id] = pathway_networks.load_version(version_id)
    return _NETWORK_CACHE[version_id]


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


def _genes_from_search(search: str | None) -> set[str]:
    if not search:
        return set()
    query = parse_qs(search.lstrip("?"))
    raw_values = query.get("gene", []) + query.get("genes", [])
    return parse_gene_query(" ".join(raw_values))


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


def _network_panel(choice: dict, query_genes=None, layout_name=DEFAULT_LAYOUT, visible=True) -> html.Div:
    """Build one self-contained network panel for a version choice."""
    version_id = choice["id"]
    network = _network(version_id)
    query_genes = set(query_genes or [])
    elements = _build_highlighted_elements(query_genes, version_id) if query_genes else (network["elements"] if network else [])
    layout = {
        **LAYOUT_CONFIGS.get(layout_name, LAYOUT_CONFIGS[DEFAULT_LAYOUT]),
        "fit": True,
        "padding": 30,
    }
    return html.Div(
        [
            html.H3(
                choice["label"],
                style={"color": UCONN_NAVY, "fontWeight": "bold", "textAlign": "center", "marginBottom": "8px"},
            ),
            html.Div(
                [
                    cyto.Cytoscape(
                        id={"type": "pathway-network", "index": version_id},
                        elements=elements,
                        stylesheet=BASE_STYLESHEET,
                        layout=layout,
                        style={"width": "100%", "height": "600px", "border": f"1px solid {UCONN_NAVY}"},
                    ),
                    html.Div(
                        id={"type": "pathway-hover-info", "index": version_id},
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
            html.Div(id={"type": "pathway-node-info", "index": version_id}, style={"marginTop": "10px", "fontFamily": "monospace"}),
            html.Div(
                id={"type": "pathway-hit-summary", "index": version_id},
                style={"marginTop": "10px", "fontFamily": "monospace", "whiteSpace": "pre-wrap"},
            ),
        ],
        id={"type": "pathway-panel", "index": version_id},
        style={"flex": "1 1 460px", "minWidth": "420px", "display": "block" if visible else "none"},
    )


def _network_panels(versions, query_genes=None, layout_name=DEFAULT_LAYOUT, selected_versions=None):
    selected = set(selected_versions) if selected_versions is not None else set(_default_visible_networks())
    return [
        _network_panel(
            choice,
            query_genes=query_genes,
            layout_name=layout_name,
            visible=choice["id"] in selected,
        )
        for choice in versions
    ]


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


def _build_highlighted_elements(query_genes: set[str], version_id: str | None) -> list[dict]:
    network = _network(version_id)
    hits = compute_gene_hits(query_genes, network["nodes"], ANNOTATIONS)
    highlighted = []
    for element in network["elements"]:
        data = element["data"]
        if "source" in data:
            highlighted.append(element)
            continue
        info = hits.get(data["id"], {"hit": False})
        highlighted.append({**element, "classes": "hit-node" if info["hit"] else "dimmed-node"})
    return highlighted


def _build_summary(query_genes: set[str], version_id: str | None) -> str:
    network = _network(version_id)
    hits = compute_gene_hits(query_genes, network["nodes"], ANNOTATIONS)
    universe = get_network_universe(network["nodes"], ANNOTATIONS)
    in_network = query_genes & universe
    coverage = 100 * len(in_network) / len(query_genes) if query_genes else 0
    label = network["version"]["label"]

    lines = [
        f"Network: {label}",
        f"Query: {len(query_genes)} gene(s) -> {', '.join(sorted(query_genes))}",
        f"Network coverage: {len(in_network)}/{len(query_genes)} query genes found in this network's {len(universe)}-gene universe ({coverage:.0f}%)",
        "",
    ]

    hit_nodes = {node_id: info for node_id, info in hits.items() if info["hit"]}
    if hit_nodes:
        lines.append(f"{len(hit_nodes)} matching node(s):")
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

    not_found = genes_not_in_network(query_genes, network["nodes"], ANNOTATIONS)
    if not_found:
        lines.extend(["", f"Not found anywhere in the network: {', '.join(sorted(not_found))}"])

    return "\n".join(lines)


def page_layout(search=None):
    initial_genes = _genes_from_search(search)
    initial_gene_text = ", ".join(sorted(initial_genes)) if initial_genes else "TP63, IRF6, GRHL3, HDAC3, EZH2"
    versions = _version_choices()

    return html.Div(
        [
            html.H2("Pathway", style=page_title_style),
            html.P(
                "Compare queried genes against curated baseline and extended palatogenesis network models. Highlighting shows direct gene matches and ontology/pathway terms annotated to the submitted gene set.",
                style=muted_text_style,
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Gene list", style={"fontWeight": "600", "color": UCONN_NAVY}),
                            dcc.Textarea(
                                id="pathway-gene-input",
                                value=initial_gene_text,
                                placeholder="TP63, IRF6, GRHL3, HDAC3, EZH2",
                                style={"width": "100%", "height": "80px", "marginTop": "6px"},
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
                                    "padding": "26px 16px",
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
                style={"display": "flex", "gap": "18px", "flexWrap": "wrap", "alignItems": "flex-end", "marginBottom": "12px"},
            ),
            html.Div(
                [
                    html.Button("Highlight genes", id="pathway-highlight-button", n_clicks=0, style=_button_style()),
                    html.Button(
                        "Clear",
                        id="pathway-clear-button",
                        n_clicks=0,
                        style={**_button_style(UCONN_GRAY), "marginLeft": "8px"},
                    ),
                    html.Span(
                        "Layout",
                        style={"fontWeight": "600", "color": UCONN_NAVY, "marginLeft": "16px", "marginRight": "8px"},
                    ),
                    dcc.Dropdown(
                        id="pathway-layout-dropdown",
                        options=[{"label": name, "value": name} for name in LAYOUT_CONFIGS],
                        value=DEFAULT_LAYOUT,
                        clearable=False,
                        style={"width": "220px", "display": "inline-block", "verticalAlign": "middle"},
                    ),
                    html.Button(
                        "Reset view",
                        id="pathway-reset-view-button",
                        n_clicks=0,
                        style={**_button_style(UCONN_LIGHT_BLUE), "marginLeft": "8px", "color": UCONN_NAVY},
                    ),
                    html.Span(
                        "Network",
                        style={"fontWeight": "600", "color": UCONN_NAVY, "marginLeft": "16px", "marginRight": "8px"},
                    ),
                    dcc.Checklist(
                        id="pathway-network-display",
                        options=[{"label": choice["label"], "value": choice["id"]} for choice in versions],
                        value=_default_visible_networks(),
                        inline=True,
                        labelStyle={"marginRight": "12px", "cursor": "pointer"},
                        inputStyle={"marginRight": "5px"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "14px", "flexWrap": "wrap", "gap": "6px"},
            ),
            html.Div(
                _network_panels(versions),
                id="pathway-network-panels",
                style={"display": "flex", "gap": "18px", "flexWrap": "wrap", "alignItems": "flex-start"},
            ),
            dcc.Store(id="pathway-upload-genes-store", data=[]),
            dcc.Store(id="pathway-query-genes-store", data=[]),
        ],
        style={"padding": "20px"},
    )


@callback(Output({"type": "pathway-network", "index": ALL}, "layout"), Input("pathway-layout-dropdown", "value"))
def update_pathway_layout(layout_name):
    cfg = {
        **LAYOUT_CONFIGS.get(layout_name, LAYOUT_CONFIGS[DEFAULT_LAYOUT]),
        "fit": True,
        "padding": 30,
        "animate": True,
    }
    return [cfg for _ in _version_choices()]


@callback(
    Output("pathway-network-panels", "children"),
    Input("pathway-reset-view-button", "n_clicks"),
    State("pathway-query-genes-store", "data"),
    State("pathway-layout-dropdown", "value"),
    State("pathway-network-display", "value"),
    prevent_initial_call=True,
)
def reset_pathway_network_panels(n_clicks, current_query_genes, layout_name, selected_versions):
    if not n_clicks:
        return no_update
    return _network_panels(
        _version_choices(),
        query_genes=set(current_query_genes or []),
        layout_name=layout_name or DEFAULT_LAYOUT,
        selected_versions=selected_versions,
    )


@callback(Output({"type": "pathway-panel", "index": ALL}, "style"), Input("pathway-network-display", "value"))
def update_pathway_panel_display(selected_versions):
    selected = set(selected_versions or [])
    styles = []
    for choice in _version_choices():
        visible = choice["id"] in selected
        styles.append({"flex": "1 1 460px", "minWidth": "420px", "display": "block" if visible else "none"})
    return styles


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


@callback(Output({"type": "pathway-node-info", "index": ALL}, "children"), Input({"type": "pathway-network", "index": ALL}, "tapNodeData"))
def show_pathway_node_info(node_datas):
    if not node_datas:
        return [no_update] * len(_version_choices())
    results = []
    for node_data in node_datas or []:
        if not node_data:
            results.append("Click a node to see its details.")
            continue
        parts = [
            f"ID: {node_data.get('id')}",
            f"Label: {node_data.get('label')}",
            f"Type: {node_data.get('type')}",
        ]
        if node_data.get("GO_Aspect") and node_data.get("GO_Aspect") != "N/A":
            parts.append(f"GO_Aspect: {node_data.get('GO_Aspect')}")
        results.append(" | ".join(parts))
    return results


@callback(
    Output({"type": "pathway-network", "index": ALL}, "elements"),
    Output({"type": "pathway-hit-summary", "index": ALL}, "children"),
    Output("pathway-query-genes-store", "data"),
    Input("pathway-highlight-button", "n_clicks"),
    Input("pathway-clear-button", "n_clicks"),
    Input("url", "search"),
    State("pathway-gene-input", "value"),
    State("pathway-upload-genes-store", "data"),
    State("pathway-query-genes-store", "data"),
    prevent_initial_call=False,
)
def highlight_pathway_gene_hits(
    _highlight_clicks,
    _clear_clicks,
    search,
    query_text,
    uploaded_genes,
    current_query_genes,
):
    choices = _version_choices()
    base_elements = [_network(c["id"])["elements"] for c in choices]

    if dash.ctx.triggered_id == "pathway-clear-button":
        return base_elements, ["Highlight cleared."] * len(choices), []

    url_genes = _genes_from_search(search)
    query_genes = (url_genes or parse_gene_query(query_text)) | set(uploaded_genes or [])

    if not _highlight_clicks and not url_genes:
        return [no_update] * len(choices), [no_update] * len(choices), no_update

    if not query_genes:
        msg = "Enter gene names or upload a CSV containing gene symbols."
        return base_elements, [msg] * len(choices), []

    return (
        [_build_highlighted_elements(query_genes, c["id"]) for c in choices],
        [_build_summary(query_genes, c["id"]) for c in choices],
        sorted(query_genes),
    )


@callback(
    Output({"type": "pathway-hover-info", "index": ALL}, "children"),
    Input({"type": "pathway-network", "index": ALL}, "mouseoverNodeData"),
    State("pathway-query-genes-store", "data"),
)
def show_pathway_hover_tooltip(node_datas, current_query):
    if not node_datas:
        return [""] * len(_version_choices())

    results = []
    for node_data in node_datas or []:
        results.append(_hover_content(node_data, current_query))
    return results


def _hover_content(node_data, current_query):
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
