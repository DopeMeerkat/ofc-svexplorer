"""Case Study page for curated gene-level examples.

Content is loaded from the committed local ``case_studies/`` folder managed by
``utils.case_studies``. A hard-coded TET3 fallback is provided as "TET3-local"
for when no case-study files are available.
"""

import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlencode

import pandas as pd
from dash import Input, Output, callback, dash_table, dcc, html, no_update

from utils import case_studies
from utils.curated_table import CURATED_TABLE_PATH, curated_table_footnote_lines
from utils.database import DB_PATH
from utils.styling import UCONN_LIGHT_BLUE, UCONN_NAVY, page_title_style, uconn_styles


FALLBACK_CASE_ID = "TET3-local"
CURATED_GENE_TABLE = Path(__file__).resolve().parents[1] / CURATED_TABLE_PATH

SECTION_HEADING_STYLE = {
    "color": UCONN_NAVY,
    "fontSize": "18px",
    "fontWeight": "600",
    "margin": "0 0 12px 0",
}


def _yes_no(count):
    return "Yes" if int(count or 0) > 0 else "No"


def _load_tet3_supporting_data():
    """Return aggregate-only supporting evidence for the TET3 fallback."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        rows = pd.read_sql_query(
            """
            WITH tet3 AS (
                SELECT chrom, CAST(x1 AS INT) AS start, CAST(x2 AS INT) AS end
                FROM genes
                WHERE UPPER(id) = 'TET3'
            ),
            tet3_svs AS (
                SELECT ps.*
                FROM phenotype_svs ps
                JOIN tet3 g ON ps.chrom = g.chrom
                    AND ps.start <= g.end
                    AND ps."end" >= g.start
                WHERE CAST(COALESCE(ps.freq, 0) AS REAL) <= 0.01
            )
            SELECT 'Overlapping with exons' AS evidence, COUNT(*) AS overlap_count, COUNT(DISTINCT ps.id) AS distinct_svs
            FROM tet3_svs ps
            JOIN exons e ON e.chrom = ps.chrom
                AND ps.start <= e.exon_end
                AND ps."end" >= e.exon_start
            UNION ALL
            SELECT 'Overlapping with enhancer candidates', COUNT(*), COUNT(DISTINCT ps.id)
            FROM tet3_svs ps
            JOIN active_enhancer_candidates c ON c.chrom = ps.chrom
                AND ps.start <= c.end
                AND ps."end" >= c.start
            UNION ALL
            SELECT 'Overlapping with promoter candidates', COUNT(*), COUNT(DISTINCT ps.id)
            FROM tet3_svs ps
            JOIN promoter_candidates c ON c.chrom = ps.chrom
                AND ps.start <= c.end
                AND ps."end" >= c.start
            """,
            conn,
        )
    finally:
        conn.close()

    evidence_rows = [
        {"Evidence": row["evidence"], "Finding": _yes_no(row["overlap_count"])}
        for _, row in rows.iterrows()
    ]
    expression_finding = _load_tet3_expression_finding()
    evidence_rows.append({"Evidence": "Gene expression data (NCC E13.5)", "Finding": expression_finding})
    return pd.DataFrame(evidence_rows)


def _load_tet3_expression_finding():
    if not CURATED_GENE_TABLE.is_file():
        return "Not available"

    table = pd.read_csv(CURATED_GENE_TABLE)
    row = table[table["Gene"].astype(str).str.upper() == "TET3"]
    expression_column = next((column for column in table.columns if str(column).startswith("NCC_13.5")), None)
    if row.empty or not expression_column:
        return "Not available"

    value = pd.to_numeric(row.iloc[0][expression_column], errors="coerce")
    if pd.isna(value):
        return "Not available"
    if value >= 7:
        return f"Highly expressed (NCC E13.5 = {value:.2f})"
    return f"Detected (NCC E13.5 = {value:.2f})"


def _section(title, children):
    return html.Div([
        html.H3(title, style=SECTION_HEADING_STYLE),
        *children,
    ], style={"marginBottom": "26px"})


def _supporting_data_table():
    try:
        data = _load_tet3_supporting_data()
    except Exception as exc:
        return html.Div(f"Could not load supporting data: {exc}", style={"color": "#A61B1B", "fontWeight": "600"})

    return dash_table.DataTable(
        data=data.to_dict("records"),
        columns=[{"name": column, "id": column} for column in data.columns],
        page_size=10,
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "9px", "fontSize": "14px"},
        style_header={"backgroundColor": UCONN_LIGHT_BLUE, "fontWeight": "bold", "color": UCONN_NAVY},
        style_data_conditional=[
            {"if": {"filter_query": "{Finding} = Yes", "column_id": "Finding"}, "fontWeight": "700", "color": "#166534"},
            {"if": {"filter_query": "{Finding} = No", "column_id": "Finding"}, "fontWeight": "700", "color": "#991B1B"},
        ],
    )


def _case_study_options():
    """Dropdown options from the JSON cache, plus the built-in fallback."""
    options = [{"label": study["title"], "value": study["id"]} for study in case_studies.list_case_studies()]
    options.append({"label": FALLBACK_CASE_ID, "value": FALLBACK_CASE_ID})
    return options


def _case_study_summary_table():
    """Render the curated 41-gene summary table from SUMMARY.csv, if present."""
    summary = case_studies.load_case_study_summary()
    if summary is None:
        return html.Div("No case study summary table is available.", style={"color": "#A61B1B", "fontWeight": "600"})
    columns = [{"name": column, "id": column} for column in summary["columns"]]
    return html.Div([
        dash_table.DataTable(
            id="case-study-summary-table",
            data=summary["rows"],
            columns=columns,
            page_size=10,
            sort_action="native",
            filter_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "9px", "fontSize": "14px", "whiteSpace": "normal"},
            style_data={"cursor": "pointer"},
            style_header={"backgroundColor": UCONN_LIGHT_BLUE, "fontWeight": "bold", "color": UCONN_NAVY},
        ),
        html.Div([
            html.P(line, style={"margin": "2px 0"})
            for line in curated_table_footnote_lines()
        ], style={"fontSize": "12px", "color": "#4B5563", "lineHeight": "1.45", "marginTop": "10px"}),
    ])


def _case_id_from_gene_value(value):
    """Map summary-table gene labels like 'KDM8 (JMJD5)' to JSON case IDs."""
    text = str(value or "").strip()
    if not text:
        return None
    case_id = text.split("(", 1)[0].strip().split()[0]
    known_ids = {study["id"] for study in case_studies.list_case_studies()}
    return case_id if case_id in known_ids else None


def _default_case_id(search=None):
    query = parse_qs((search or "").lstrip("?"))
    requested = query.get("case", [""])[0]
    if requested and case_studies.load_case_study(requested):
        return requested
    for study in case_studies.list_case_studies():
        if study["id"] == "TET3":
            return "TET3"
    return FALLBACK_CASE_ID


def _default_tab(search=None):
    query = parse_qs((search or "").lstrip("?"))
    tab = query.get("tab", [""])[0]
    if tab in {"summary", "case-studies"}:
        return tab
    if query.get("case"):
        return "case-studies"
    return "summary"


def _cache_warning():
    problems = case_studies.invalid_study_files()
    if not problems:
        return html.Div()
    details = "; ".join(f"{name}: {reason}" for name, reason in problems)
    return html.Div(
        f"Warning: {len(problems)} case study file(s) could not be loaded ({details}). "
        "Fix the JSON so the case study appears in the dropdown.",
        style={"color": "#92400E", "fontWeight": "600", "margin": "0 0 12px 0"},
    )


def page_layout(search=None):
    return html.Div([
        html.H2("Case Study", style=page_title_style),
        dcc.Tabs(
            id="case-study-tabs",
            value=_default_tab(search),
            children=[
                dcc.Tab(
                    label="Summary Table",
                    value="summary",
                    children=html.Div(id="case-study-summary", children=_case_study_summary_table(), style={"paddingTop": "22px"}),
                ),
                dcc.Tab(
                    label="Case Studies",
                    value="case-studies",
                    children=html.Div([
                        html.Div([
                            html.Label("Select case study", style={"fontWeight": "600", "color": UCONN_NAVY, "marginRight": "12px"}),
                            dcc.Dropdown(
                                id="case-study-selector",
                                options=_case_study_options(),
                                value=_default_case_id(search),
                                clearable=False,
                                optionHeight=48,
                                style={"width": "380px", "display": "inline-block", "verticalAlign": "middle", "lineHeight": "24px"},
                            ),
                        ], style={
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "12px",
                            "flexWrap": "wrap",
                            "marginBottom": "10px",
                            "paddingBottom": "14px",
                        }),
                        html.Div(id="case-study-cache-warning", children=_cache_warning()),
                        html.Div(id="case-study-content"),
                    ], style={"paddingTop": "22px"}),
                ),
            ],
            colors={"border": UCONN_LIGHT_BLUE, "primary": UCONN_NAVY, "background": "#FFFFFF"},
        ),
    ], style={**uconn_styles["content"], "maxWidth": "1100px", "margin": "30px auto"})


def _paragraph_children(item):
    """Render a JSON paragraph item (string or {text, links, suffix})."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        parts = []
        if item.get("text"):
            parts.append(item["text"])
        for link in item.get("links", []) or []:
            parts.append(dcc.Link(
                link.get("label", ""),
                href=link.get("href", ""),
                style={"fontWeight": "700", "color": UCONN_NAVY},
            ))
        if item.get("suffix"):
            parts.append(item["suffix"])
        return parts
    return str(item)


def _table_from_json(table):
    columns = [
        {"name": column.get("name", column.get("id", "")), "id": column.get("id", column.get("name", ""))}
        for column in (table.get("columns", []) or [])
    ]
    return dash_table.DataTable(
        data=table.get("rows", []) or [],
        columns=columns,
        page_size=10,
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "9px", "fontSize": "14px"},
        style_header={"backgroundColor": UCONN_LIGHT_BLUE, "fontWeight": "bold", "color": UCONN_NAVY},
        style_data_conditional=[
            {"if": {"filter_query": "{Finding} = Yes", "column_id": "Finding"}, "fontWeight": "700", "color": "#166534"},
            {"if": {"filter_query": "{Finding} = No", "column_id": "Finding"}, "fontWeight": "700", "color": "#991B1B"},
        ],
    )


def _render_from_json(data):
    section_children = []
    for section in data.get("sections", []):
        children = []
        for item in section.get("paragraphs", []) or []:
            children.append(html.P(
                _paragraph_children(item),
                style={"lineHeight": "1.65", "margin": "0 0 10px 0"},
            ))
        table = section.get("table")
        if table:
            children.append(html.Div(_table_from_json(table), style={"marginTop": "12px"}))
        section_children.append(_section(section.get("heading", "Untitled"), children))
    return html.Div(section_children)


def _render_local_tet3():
    """Built-in fallback rendered when no cached JSON content is available."""
    pathway_query = urlencode({"genes": "TET3,SNAI1,CDH1,PITX2"})

    return html.Div([
        _section("Function", [
            html.P(
                "TET3 is responsible for converting 5-methylcytosine (5mC) to "
                "5-hydroxymethylcytosine (5hmC), which is responsible for initiating "
                "active DNA demethylation [Ketchum et al., 2024].",
                style={"lineHeight": "1.65", "margin": "0"},
            ),
        ]),
        _section("IGV", [
            html.P([
                "Rare SVs in the cohort overlap the TET3 locus and supporting regulatory annotations. ",
                dcc.Link("Open TET3 in IGV", href="/population?gene=TET3", style={"fontWeight": "700", "color": UCONN_NAVY}),
                ".",
            ], style={"lineHeight": "1.65", "margin": "0"}),
        ]),
        _section("Literature", [
            html.P(
                "When TET3 is compromised, downstream signaling required for neural crest cell "
                "differentiation and pharyngeal cartilage formation is impaired, which can lead "
                "to craniofacial malformations like cleft lip and palate [Chen et al., 2023, "
                "Wang et al., 2024].",
                style={"lineHeight": "1.65", "margin": "0"},
            ),
        ]),
        _section("Pathway", [
            html.P([
                "The pathway view places TET3 in the context of co-occurring genes and developmental regulatory biology. ",
                dcc.Link(
                    "Open pathway view for TET3, SNAI1, CDH1, and PITX2",
                    href=f"/pathway?{pathway_query}",
                    style={"fontWeight": "700", "color": UCONN_NAVY},
                ),
                ". The network highlights developmental enhancer context through the TET-SNAIL4-BMP axis.",
            ], style={"lineHeight": "1.65", "margin": "0"}),
        ]),
        _section("Supporting Data", [
            html.P(
                "Curated supporting evidence is summarized below for review.",
                style={"lineHeight": "1.65", "margin": "0 0 12px 0"},
            ),
            _supporting_data_table(),
        ]),
    ])


@callback(
    Output("case-study-tabs", "value"),
    Output("case-study-selector", "value"),
    Input("case-study-summary-table", "active_cell"),
    Input("case-study-summary-table", "data"),
    prevent_initial_call=True,
)
def _open_case_from_summary_row(active_cell, rows):
    if not active_cell or not rows:
        return no_update, no_update
    row_index = active_cell.get("row")
    if row_index is None or row_index >= len(rows):
        return no_update, no_update
    case_id = _case_id_from_gene_value(rows[row_index].get("Gene"))
    if not case_id:
        return no_update, no_update
    return "case-studies", case_id


@callback(
    Output("case-study-content", "children"),
    Input("case-study-selector", "value"),
)
def _render_selected_case(case_id):
    if not case_id:
        case_id = FALLBACK_CASE_ID
    if case_id == FALLBACK_CASE_ID:
        return _render_local_tet3()

    data = case_studies.load_case_study(case_id)
    if data is None:
        return html.Div(
            f"Could not load case study '{case_id}'. "
            f"Check that a file named '{case_id}.json' is in the case study folder.",
            style={"color": "#A61B1B", "fontWeight": "600"},
        )
    return _render_from_json(data)
