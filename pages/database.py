"""Database page for running preset or user-edited read-only queries."""

import json
import sqlite3
from pathlib import Path

import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html, no_update

from utils.database import DB_PATH, run_readonly_query, validate_readonly_query
from utils.styling import UCONN_LIGHT_BLUE, UCONN_NAVY, uconn_styles


QUERY_CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "database_queries.json"


def load_query_presets():
    """Load configured database queries."""
    with QUERY_CONFIG_PATH.open(encoding="utf-8") as handle:
        presets = json.load(handle)
    return {
        preset["name"]: preset
        for preset in presets
        if preset.get("name") and preset.get("query")
    }


def load_full_query_dataframe(query):
    """Execute a validated read-only query without adding a row limit."""
    safe_query = validate_readonly_query(query)
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(safe_query, conn)
    finally:
        conn.close()


def page_layout():
    presets = load_query_presets()
    return html.Div([
        html.H2("Database", style={"color": UCONN_NAVY, "marginBottom": "12px"}),
        html.P(
            "Choose a configured query or enter a custom read-only SQLite query. "
            "The table preview is limited to 5,000 rows; CSV downloads include all query results.",
            style={"marginBottom": "20px"},
        ),
        html.Label("Configured Query", style={"fontWeight": "600", "marginBottom": "6px"}),
        dcc.Dropdown(
            id="database-query-preset",
            options=[{"label": name, "value": name} for name in presets],
            placeholder="Select a configured query",
            clearable=True,
            style={"marginBottom": "10px"},
        ),
        html.Div(id="database-query-description", style={"marginBottom": "16px", "color": "#555"}),
        html.Label("Read-only SQLite Query", style={"fontWeight": "600", "marginBottom": "6px"}),
        dcc.Textarea(
            id="database-query-input",
            placeholder="SELECT ... or WITH ... SELECT ...",
            style={
                "width": "100%",
                "minHeight": "180px",
                "padding": "12px",
                "fontFamily": "monospace",
                "border": f"1px solid {UCONN_LIGHT_BLUE}",
                "borderRadius": "6px",
                "resize": "vertical",
            },
        ),
        html.Div([
            html.Button(
                "Run Query",
                id="database-query-submit",
                n_clicks=0,
                style=uconn_styles["button"],
            ),
            html.Button(
                "Download CSV",
                id="database-query-download-button",
                n_clicks=0,
                style={**uconn_styles["button"], "marginLeft": "10px"},
            ),
            dcc.Download(id="database-query-download"),
        ], style={"marginTop": "12px"}),
        dcc.Loading(
            children=html.Div([
                html.Div(id="database-query-status", style={"marginTop": "18px"}),
                html.Div(id="database-query-results", style={"marginTop": "12px"}),
            ]),
            type="default",
        ),
    ], style={**uconn_styles["content"], "maxWidth": "1400px", "margin": "30px auto"})


@callback(
    Output("database-query-input", "value"),
    Output("database-query-description", "children"),
    Input("database-query-preset", "value"),
    prevent_initial_call=True,
)
def select_query_preset(preset_name):
    presets = load_query_presets()
    preset = presets.get(preset_name)
    if not preset:
        return "", ""
    return preset["query"], preset.get("description", "")


@callback(
    Output("database-query-status", "children"),
    Output("database-query-results", "children"),
    Input("database-query-submit", "n_clicks"),
    State("database-query-input", "value"),
    prevent_initial_call=True,
)
def run_database_query(n_clicks, query):
    if not n_clicks:
        return "", html.Div()

    try:
        safe_query = validate_readonly_query(query)
        rows = run_readonly_query(safe_query, limit=5000)
    except Exception as exc:
        return html.Div(str(exc), style={"color": "#A61B1B", "fontWeight": "600"}), html.Div()

    if not rows:
        return "Query returned 0 rows.", html.Div("No results.")

    columns = list(rows[0].keys())
    return (
        f"Query returned {len(rows):,} row(s).",
        dash_table.DataTable(
            data=rows,
            columns=[{"name": column, "id": column} for column in columns],
            page_size=25,
            sort_action="native",
            filter_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "7px", "maxWidth": "360px"},
            style_header={"backgroundColor": UCONN_LIGHT_BLUE, "fontWeight": "bold"},
        ),
    )


@callback(
    Output("database-query-download", "data"),
    Input("database-query-download-button", "n_clicks"),
    State("database-query-input", "value"),
    prevent_initial_call=True,
)
def download_database_query(n_clicks, query):
    if not n_clicks:
        return no_update

    try:
        dataframe = load_full_query_dataframe(query)
    except Exception:
        return no_update

    return dcc.send_data_frame(dataframe.to_csv, "database_query_results.csv", index=False)
