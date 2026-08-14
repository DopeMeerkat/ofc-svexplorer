"""
Dash + Cytoscape network viewer for the palate development gene/GO network.

Reads a 3-column Edge Table (Source, InteractionType, Target) and, unless a
separate node attribute table is supplied, auto-derives node attributes
(type: gene vs GO_term) from the edge table itself.

Run:
    python network_app.py
Then open http://127.0.0.1:8050 in a browser.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact
import dash
from dash import html, dcc, dash_table, Input, Output, State
import dash_cytoscape as cyto

cyto.load_extra_layouts()  # enables dagre (true hierarchical layout), among others

# ---------------- Config ----------------
EDGES_CSV = Path("edges.csv")          # Source, InteractionType, Target
NODES_CSV = Path("nodes.csv")          # optional: id, type, label, ... (auto-generated if missing)
ANNOTATIONS_CSV = Path("go_gene_annotations.csv")  # optional: GO_ID, GeneSymbol (from parse_go_annotations.py)
DEFAULT_LAYOUT = "dagre"               # dagre | breadthfirst | cose | circle | grid | concentric
REQUIRE_NODES_CSV = True               # fail loudly if nodes.csv is missing, instead of silently
                                        # falling back to a 2-type auto-derived node table
HOST = "127.0.0.1"
PORT = 8050

HIT_COLOR = "#D62728"       # red highlight border for genes/GO terms hit by the query
DIMMED_OPACITY = 0.25       # non-hit nodes fade to this opacity when a query is active

# Fallback colors by NodeType, used if a node has no GO_Aspect value at all
# (e.g. an auto-derived node table that never had that column)
TYPE_FALLBACK_COLORS = {
    "Gene": "#4C78A8",
    "Molecular Function": "#F58518",
    "Biological Process": "#54A24B",
}

# Preferred coloring: by GO_Aspect (overrides the fallback above when present)
GO_ASPECT_COLORS = {
    "MF": "#AEC7E8",   # light blue
    "BP": "#98DF8A",   # light green
    "N/A": "#FFBB78",  # soft orange (genes)
}

# Shape by NodeType
TYPE_SHAPES = {
    "Gene": "ellipse",
    "Molecular Function": "diamond",
    "Biological Process": "hexagon",
}

# Layout presets. "dagre" gives the true left-to-right hierarchical funnel
# (genes -> molecular functions -> biological process); "cose" is the
# force-directed equivalent of Cytoscape Desktop's "Prefuse Force Directed".
LAYOUT_CONFIGS = {
    "dagre": {"name": "dagre", "rankDir": "LR", "nodeSep": 30, "rankSep": 100, "animate": True},
    "breadthfirst": {"name": "breadthfirst", "directed": True, "spacingFactor": 1.2},
    "cose": {"name": "cose", "animate": True},
    "circle": {"name": "circle"},
    "grid": {"name": "grid"},
    "concentric": {"name": "concentric"},
}

# Maps flexible/alternate column names in a user-supplied node table to the
# standard names this script uses internally.
NODE_COL_ALIASES = {
    "id": ["id", "NodeID", "node_id"],
    "label": ["label", "Label", "name"],
    "type": ["type", "NodeType", "NoteType", "node_type"],
}


# ---------------- Functions ----------------
def load_edges(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"Source", "InteractionType", "Target"}
    if not expected.issubset(df.columns):
        raise ValueError(f"Edge table must have columns {expected}, got {list(df.columns)}")
    return df


def infer_node_type(node_id: str) -> str:
    return "Molecular Function" if str(node_id).startswith("GO:") else "Gene"


def normalize_node_columns(nodes_df: pd.DataFrame) -> pd.DataFrame:
    """Rename whichever id/label/type column names are present to the
    standard names, leaving any other columns (e.g. GO_Aspect) untouched."""
    rename_map = {}
    for standard_name, aliases in NODE_COL_ALIASES.items():
        for alias in aliases:
            if alias in nodes_df.columns:
                rename_map[alias] = standard_name
                break
    nodes_df = nodes_df.rename(columns=rename_map)

    if "id" not in nodes_df.columns:
        raise ValueError(f"Could not find an id column. Columns present: {list(nodes_df.columns)}")
    if "type" not in nodes_df.columns:
        nodes_df["type"] = nodes_df["id"].map(infer_node_type)
    if "label" not in nodes_df.columns:
        nodes_df["label"] = nodes_df["id"]
    return nodes_df


def build_node_table(edges_df: pd.DataFrame, nodes_path: Path, require_nodes_csv: bool = True) -> pd.DataFrame:
    """Use the supplied node attribute table. If it's missing: raise an error
    by default (require_nodes_csv=True), since silently falling back to a
    thinner auto-derived table produces different-looking output without any
    visible warning -- confusing to debug. Set require_nodes_csv=False to
    opt back into the permissive auto-derive behavior (e.g. for quick
    exploration before a real node table exists)."""
    if nodes_path.exists():
        # keep_default_na=False so a literal "N/A" value (e.g. in GO_Aspect)
        # is kept as the string "N/A" rather than silently becoming a missing value
        nodes_df = pd.read_csv(nodes_path, keep_default_na=False)
        return normalize_node_columns(nodes_df)

    if require_nodes_csv:
        raise FileNotFoundError(
            f"{nodes_path.resolve()} not found. Either place your node attribute table there, "
            "or set REQUIRE_NODES_CSV = False in the config to run with an auto-derived "
            "(2-type: Gene/Molecular Function) node table instead."
        )

    node_ids = pd.unique(edges_df[["Source", "Target"]].values.ravel())
    nodes_df = pd.DataFrame({"id": node_ids})
    nodes_df["type"] = nodes_df["id"].map(infer_node_type)
    nodes_df["label"] = nodes_df["id"]
    return nodes_df


def build_cytoscape_elements(edges_df: pd.DataFrame, nodes_df: pd.DataFrame) -> list[dict]:
    # any columns beyond id/label/type (e.g. GO_Aspect) get passed through
    # as extra node data, useful for tooltips/filtering/styling
    extra_cols = [c for c in nodes_df.columns if c not in ("id", "label", "type")]

    node_elements = []
    for _, row in nodes_df.iterrows():
        data = {"id": row["id"], "label": row["label"], "type": row["type"]}
        for col in extra_cols:
            data[col] = row[col]
        node_elements.append({"data": data})

    edge_elements = [
        {
            "data": {
                "source": row["Source"],
                "target": row["Target"],
                "label": row["InteractionType"],
            }
        }
        for _, row in edges_df.iterrows()
    ]

    return node_elements + edge_elements


def build_stylesheet() -> list[dict]:
    # base style + fallback color by NodeType (always applies, even without GO_Aspect)
    node_style = [
        {
            "selector": f'node[type = "{node_type}"]',
            "style": {
                "background-color": color,
                "label": "data(label)",
                "font-size": "10px",
                "width": 30,
                "height": 30,
                "text-valign": "bottom",
                "text-halign": "center",
                "text-margin-y": 4,
            },
        }
        for node_type, color in TYPE_FALLBACK_COLORS.items()
    ]

    # preferred color by GO_Aspect - listed after node_style so it wins on
    # background-color for any node that has this attribute
    color_override = [
        {
            "selector": f'node[GO_Aspect = "{aspect}"]',
            "style": {"background-color": color},
        }
        for aspect, color in GO_ASPECT_COLORS.items()
    ]

    # shape by NodeType
    shape_style = [
        {
            "selector": f'node[type = "{node_type}"]',
            "style": {"shape": shape},
        }
        for node_type, shape in TYPE_SHAPES.items()
    ]

    edge_style = [
        {
            "selector": "edge",
            "style": {
                "curve-style": "bezier",
                "target-arrow-shape": "triangle",
                "target-arrow-color": "#999",
                "line-color": "#999",
                "width": 1.5,
                "label": "data(label)",
                "font-size": "8px",
                "color": "#666",
                "text-rotation": "autorotate",
                "text-margin-y": -6,
            },
        }
    ]

    return node_style + color_override + shape_style + edge_style


def load_go_annotations(path: Path) -> dict[str, set[str]]:
    """Load GO_ID -> set(gene symbols) from the annotation file produced by
    parse_go_annotations.py. Returns an empty dict if the file isn't present
    yet, so the app still runs (GO nodes just won't be hit-able by query)."""
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    return df.groupby("GO_ID")["GeneSymbol"].apply(lambda s: set(s.str.upper())).to_dict()


def parse_gene_query(text: str) -> set[str]:
    """Split free-form text (commas, whitespace, newlines) into a set of
    uppercased gene symbols."""
    if not text:
        return set()
    tokens = text.replace(",", " ").replace("\n", " ").split()
    return {t.strip().upper() for t in tokens if t.strip()}


def compute_gene_hits(
    query_genes: set[str],
    nodes_df: pd.DataFrame,
    annotations: dict[str, set[str]],
) -> dict[str, dict]:
    """For every node, determine whether the query hits it.
    Gene nodes: direct ID match. GO term nodes: overlap with annotated genes."""
    hits = {}
    for _, row in nodes_df.iterrows():
        node_id = row["id"]
        if row["type"] == "Gene":
            matched = {node_id.upper()} & query_genes
            hits[node_id] = {"hit": bool(matched), "matched_genes": matched, "total_annotated": None}
        else:
            annotated = annotations.get(node_id, set())
            matched = annotated & query_genes
            hits[node_id] = {"hit": bool(matched), "matched_genes": matched, "total_annotated": len(annotated)}
    return hits


def genes_not_in_network(
    query_genes: set[str], nodes_df: pd.DataFrame, annotations: dict[str, set[str]]
) -> set[str]:
    known_gene_ids = {gid.upper() for gid in nodes_df.loc[nodes_df["type"] == "Gene", "id"]}
    known_annotated = set().union(*annotations.values()) if annotations else set()
    return query_genes - known_gene_ids - known_annotated


def get_network_universe(nodes_df: pd.DataFrame, annotations: dict[str, set[str]]) -> set[str]:
    """All genes represented anywhere in this network: the Gene nodes plus
    every gene annotated to any GO term node. This is the background
    population used for enrichment -- NOT the whole genome."""
    gene_node_ids = {gid.upper() for gid in nodes_df.loc[nodes_df["type"] == "Gene", "id"]}
    annotated_universe = set().union(*annotations.values()) if annotations else set()
    return gene_node_ids | annotated_universe


def compute_go_enrichment(
    query_genes: set[str],
    nodes_df: pd.DataFrame,
    annotations: dict[str, set[str]],
) -> pd.DataFrame:
    """One-sided Fisher's exact test per GO term node: is the overlap between
    the query genes and this term's annotated genes bigger than expected by
    chance, given the network's own gene universe as background?

    2x2 table per term:
                      in term      not in term
        in query        k            n - k
        not in query   K - k    (N - K) - (n - k)

    N = network universe size, K = genes annotated to the term,
    n = query genes that are actually part of the network universe,
    k = query genes hitting this term.
    """
    universe = get_network_universe(nodes_df, annotations)
    N = len(universe)
    n = len(query_genes & universe)

    go_nodes = nodes_df[nodes_df["type"] != "Gene"]
    rows = []
    for _, row in go_nodes.iterrows():
        go_id = row["id"]
        annotated = annotations.get(go_id, set())
        K = len(annotated)
        k = len(annotated & query_genes)

        if N == 0 or K == 0:
            odds_ratio, p_value = float("nan"), float("nan")
        else:
            table = [[k, n - k], [K - k, (N - K) - (n - k)]]
            odds_ratio, p_value = fisher_exact(table, alternative="greater")

        rows.append({
            "GO_ID": go_id,
            "Label": row["label"],
            "annotated_in_network (K)": K,
            "hits (k)": k,
            "query_in_network (n)": n,
            "network_universe (N)": N,
            "odds_ratio": odds_ratio,
            "p_value": p_value,
        })

    result = pd.DataFrame(rows).sort_values("p_value", na_position="last").reset_index(drop=True)

    # Benjamini-Hochberg correction across the tested GO terms
    valid = result["p_value"].notna()
    m = int(valid.sum())
    result["q_value"] = np.nan
    if m > 0:
        ranks = np.arange(1, m + 1)
        q = (result.loc[valid, "p_value"].to_numpy() * m / ranks)
        # step-up monotonicity: each q_i can't exceed the next (already p-sorted ascending)
        q = np.minimum.accumulate(q[::-1])[::-1]
        result.loc[valid, "q_value"] = np.clip(q, 0, 1)

    for col in ("odds_ratio", "p_value", "q_value"):
        result[col] = result[col].round(4)

    return result


def build_app(
    elements: list[dict],
    stylesheet: list[dict],
    nodes_df: pd.DataFrame,
    annotations: dict[str, set[str]],
) -> dash.Dash:
    app = dash.Dash(__name__)

    highlight_stylesheet = stylesheet + [
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

    app.layout = html.Div(
        [
            html.H3("Palate Development Gene / GO Network"),
            html.Div(
                [
                    html.Label("Layout: "),
                    dcc.Dropdown(
                        id="layout-dropdown",
                        options=[{"label": name, "value": name} for name in LAYOUT_CONFIGS],
                        value=DEFAULT_LAYOUT,
                        clearable=False,
                        style={"width": "220px"},
                    ),
                ],
                style={"marginBottom": "10px"},
            ),
            html.Div(
                [
                    html.Label("Gene list (comma, space, or newline separated): "),
                    dcc.Textarea(
                        id="gene-query-input",
                        placeholder="e.g. TGFB3, SMAD2, PVRL1",
                        style={"width": "100%", "height": "60px"},
                    ),
                    html.Button("Highlight", id="highlight-button", n_clicks=0, style={"marginTop": "6px"}),
                    html.Button(
                        "Clear", id="clear-highlight-button", n_clicks=0,
                        style={"marginTop": "6px", "marginLeft": "6px"},
                    ),
                ],
                style={"marginBottom": "10px"},
            ),
            html.Div(
                [
                    cyto.Cytoscape(
                        id="cytoscape-network",
                        elements=elements,
                        stylesheet=highlight_stylesheet,
                        layout=LAYOUT_CONFIGS[DEFAULT_LAYOUT],
                        style={"width": "100%", "height": "650px", "border": "1px solid #ddd"},
                        clearOnUnhover=True,
                    ),
                    html.Div(
                        id="hover-info",
                        style={
                            "position": "absolute",
                            "top": "10px",
                            "right": "10px",
                            "maxWidth": "300px",
                            "backgroundColor": "rgba(255, 255, 255, 0.97)",
                            "border": "1px solid #ccc",
                            "borderRadius": "6px",
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
            html.Div(id="node-info", style={"marginTop": "10px", "fontFamily": "monospace"}),
            html.Div(id="hit-summary", style={"marginTop": "10px", "fontFamily": "monospace", "whiteSpace": "pre-wrap"}),
            html.H4("GO Term Enrichment (Fisher's exact test)", style={"marginTop": "20px"}),
            dash_table.DataTable(
                id="enrichment-table",
                columns=[
                    {"name": "GO_ID", "id": "GO_ID"},
                    {"name": "Label", "id": "Label"},
                    {"name": "K (annotated)", "id": "annotated_in_network (K)"},
                    {"name": "k (hits)", "id": "hits (k)"},
                    {"name": "n (query in network)", "id": "query_in_network (n)"},
                    {"name": "N (network universe)", "id": "network_universe (N)"},
                    {"name": "Odds ratio", "id": "odds_ratio"},
                    {"name": "p-value", "id": "p_value"},
                    {"name": "q-value (BH)", "id": "q_value"},
                ],
                data=[],
                sort_action="native",
                style_cell={"fontFamily": "monospace", "fontSize": "12px", "padding": "4px"},
                style_header={"fontWeight": "bold"},
                style_data_conditional=[
                    {
                        "if": {"filter_query": "{q_value} < 0.05", "column_id": "q_value"},
                        "color": HIT_COLOR,
                        "fontWeight": "bold",
                    }
                ],
            ),
            dcc.Store(id="query-genes-store", data=[]),
        ]
    )

    @app.callback(Output("cytoscape-network", "layout"), Input("layout-dropdown", "value"))
    def update_layout(layout_name):
        return LAYOUT_CONFIGS[layout_name]

    @app.callback(Output("node-info", "children"), Input("cytoscape-network", "tapNodeData"))
    def show_node_info(node_data):
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

    @app.callback(
        Output("cytoscape-network", "elements"),
        Output("hit-summary", "children"),
        Output("query-genes-store", "data"),
        Output("enrichment-table", "data"),
        Input("highlight-button", "n_clicks"),
        Input("clear-highlight-button", "n_clicks"),
        State("gene-query-input", "value"),
        prevent_initial_call=True,
    )
    def highlight_gene_hits(_highlight_clicks, _clear_clicks, query_text):
        triggered = dash.ctx.triggered_id
        if triggered == "clear-highlight-button":
            return elements, "Highlight cleared.", [], []

        query_genes = parse_gene_query(query_text)
        if not query_genes:
            return elements, "Enter one or more gene names and click Highlight.", [], []

        hits = compute_gene_hits(query_genes, nodes_df, annotations)

        new_elements = []
        for el in elements:
            data = el["data"]
            if "source" in data:  # edge, leave as-is
                new_elements.append(el)
                continue
            info = hits.get(data["id"], {"hit": False})
            new_elements.append({**el, "classes": "hit-node" if info["hit"] else "dimmed-node"})

        universe = get_network_universe(nodes_df, annotations)
        in_network = query_genes & universe
        summary_lines = [
            f"Query: {len(query_genes)} gene(s) -> {', '.join(sorted(query_genes))}",
            f"Network coverage: {len(in_network)}/{len(query_genes)} query genes found somewhere "
            f"in this network's {len(universe)}-gene universe ({100 * len(in_network) / len(query_genes):.0f}%)",
            "",
        ]
        hit_nodes = {nid: info for nid, info in hits.items() if info["hit"]}
        if hit_nodes:
            summary_lines.append(f"{len(hit_nodes)} node(s) lit up:")
            for nid, info in hit_nodes.items():
                if info["total_annotated"] is None:
                    summary_lines.append(f"  {nid}  (direct gene match)")
                else:
                    matched = ", ".join(sorted(info["matched_genes"]))
                    summary_lines.append(
                        f"  {nid}  ({len(info['matched_genes'])}/{info['total_annotated']} annotated genes hit: {matched})"
                    )
        else:
            summary_lines.append("No nodes matched this query.")

        not_found = genes_not_in_network(query_genes, nodes_df, annotations)
        if not_found:
            summary_lines.append("")
            summary_lines.append(f"Not found anywhere in the network: {', '.join(sorted(not_found))}")

        enrichment_df = compute_go_enrichment(query_genes, nodes_df, annotations)

        return new_elements, "\n".join(summary_lines), sorted(query_genes), enrichment_df.to_dict("records")

    @app.callback(
        Output("hover-info", "children"),
        Input("cytoscape-network", "mouseoverNodeData"),
        State("query-genes-store", "data"),
    )
    def show_hover_tooltip(node_data, current_query):
        if not node_data:
            return ""

        node_id = node_data["id"]
        header = html.Div(f"{node_data.get('label')} ({node_id})", style={"fontWeight": "bold", "marginBottom": "4px"})

        if node_data.get("type") == "Gene":
            return [header]

        annotated = sorted(annotations.get(node_id, set()))
        if not annotated:
            return [header, html.Div("No annotation data loaded for this term.", style={"color": "#888"})]

        query_set = set(current_query or [])
        gene_spans = []
        for i, gene in enumerate(annotated):
            is_hit = gene in query_set
            gene_spans.append(
                html.Span(
                    gene,
                    style={"color": HIT_COLOR, "fontWeight": "bold"} if is_hit else {},
                )
            )
            if i < len(annotated) - 1:
                gene_spans.append(html.Span(", "))

        return [
            header,
            html.Div(f"{len(annotated)} annotated gene(s):", style={"marginBottom": "2px"}),
            html.Div(gene_spans),
        ]

    return app


# ---------------- Execution ----------------
if __name__ == "__main__":
    edges_df = load_edges(EDGES_CSV)
    nodes_df = build_node_table(edges_df, NODES_CSV, require_nodes_csv=REQUIRE_NODES_CSV)

    print(f"Loaded {len(nodes_df)} nodes from {NODES_CSV.resolve()}")
    print(f"Node type counts:\n{nodes_df['type'].value_counts().to_string()}")
    if "GO_Aspect" in nodes_df.columns:
        print(f"GO_Aspect counts:\n{nodes_df['GO_Aspect'].value_counts().to_string()}")
    print()

    elements = build_cytoscape_elements(edges_df, nodes_df)
    stylesheet = build_stylesheet()
    annotations = load_go_annotations(ANNOTATIONS_CSV)

    if not annotations:
        print(
            f"Note: {ANNOTATIONS_CSV} not found. GO term nodes won't be hit-able by gene "
            "queries until you run parse_go_annotations.py. Direct gene-node matches still work."
        )

    app = build_app(elements, stylesheet, nodes_df, annotations)
    print(f"\nStarting server -- if you had a previous instance running, make sure it's stopped first.")
    app.run(host=HOST, port=PORT, debug=True)
