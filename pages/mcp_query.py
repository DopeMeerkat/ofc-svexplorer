"""
MCP Query page — upload or default dataset, get LLM tool recommendations,
and execute tools through the discovery MCP server.
"""

from __future__ import annotations

import base64
import io
import json
import os
import pathlib
import uuid

import pandas as pd
from dash import html, dcc, Input, Output, State, callback, no_update

from agents.mcp_query_agent import recommend_tools, run_discovered_tool
from utils.mcp_client_manager import MCPClientManager
from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE, UCONN_GRAY, uconn_styles

DEFAULT_CSV_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "sample_sv_phenotypes.csv"
UPLOAD_DIR = pathlib.Path(__file__).resolve().parent.parent / "discovered_workers" / "uploads"
MODEL_OPTIONS = [
    {"label": "Local: Qwen3 8B", "value": "ollama:qwen3:8b"},
]


def _model_value():
    return MODEL_OPTIONS[0]["value"]


def _read_csv_columns(file_path: str) -> list[str]:
    try:
        df = pd.read_csv(file_path, nrows=0)
        return list(df.columns)
    except Exception:
        return []


def page_layout():
    return html.Div([
        html.H2("MCP Query", style={'color': UCONN_NAVY, 'marginBottom': '12px', 'fontWeight': 'bold'}),
        html.Div([
            dcc.Textarea(
                id="mcp-query-instructions",
                placeholder='Describe your analysis goal, e.g. "Find which genes best predict phenotype"',
                style={
                    'width': '100%',
                    'minHeight': '100px',
                    'padding': '12px',
                    'borderRadius': '6px',
                    'border': f'1px solid {UCONN_LIGHT_BLUE}',
                    'fontSize': '15px',
                    'resize': 'vertical',
                },
            ),
        ], style={'marginBottom': '16px'}),
        html.Div([
            html.Label("Data Source", style={'fontWeight': 'bold', 'marginBottom': '6px', 'display': 'block'}),
            dcc.RadioItems(
                id="mcp-query-data-source",
                options=[
                    {"label": " Default dataset (sample_sv_phenotypes.csv)", "value": "default"},
                    {"label": " Upload CSV", "value": "upload"},
                ],
                value="default",
                inline=True,
                inputStyle={'marginRight': '6px'},
                labelStyle={'marginRight': '24px', 'cursor': 'pointer'},
            ),
        ], style={'marginBottom': '14px'}),
        html.Div(
            dcc.Upload(
                id="mcp-query-upload",
                children=html.Div([
                    "Drag and Drop or ",
                    html.A("Select CSV File", style={'fontWeight': 'bold', 'color': UCONN_NAVY}),
                ]),
                style={
                    'width': '100%', 'height': '60px', 'lineHeight': '60px',
                    'borderWidth': '2px', 'borderStyle': 'dashed', 'borderRadius': '8px',
                    'textAlign': 'center', 'margin': '0 0 14px 0',
                    'backgroundColor': '#fafafa', 'cursor': 'pointer',
                },
                multiple=False,
            ),
            id="mcp-query-upload-container",
            style={'display': 'none'},
        ),
        html.Div([
            html.Label("Target Column", style={'fontWeight': 'bold', 'marginBottom': '6px', 'display': 'block'}),
            dcc.Dropdown(
                id="mcp-query-target-column",
                placeholder="Select target column...",
                clearable=False,
                style={'maxWidth': '360px'},
            ),
        ], style={'marginBottom': '16px'}),
        html.Div([
            html.Button(
                "Recommend Tools",
                id="mcp-query-recommend-btn",
                n_clicks=0,
                style={**uconn_styles['button'], 'marginRight': '12px'},
            ),
            dcc.Dropdown(
                id="mcp-query-model",
                options=MODEL_OPTIONS,
                value=_model_value(),
                clearable=False,
                style={'minWidth': '200px', 'fontSize': '12px', 'display': 'inline-block'},
            ),
        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '16px'}),
        dcc.Loading(
            id="mcp-query-loading",
            type="default",
            children=html.Div(id="mcp-query-output", style={'minHeight': '60px'}),
        ),
        html.Div(id="mcp-query-run-section", style={'display': 'none'}, children=[
            html.Hr(style={'margin': '20px 0'}),
            html.H4("Run Tool", style={'color': UCONN_NAVY, 'marginBottom': '10px'}),
            html.Div([
                dcc.Dropdown(
                    id="mcp-query-tool-select",
                    placeholder="Select a tool to run...",
                    clearable=False,
                    style={'minWidth': '300px', 'display': 'inline-block'},
                ),
                html.Button(
                    "Run Tool",
                    id="mcp-query-run-btn",
                    n_clicks=0,
                    style={**uconn_styles['button'], 'marginLeft': '12px'},
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '16px'}),
            dcc.Loading(
                id="mcp-query-run-loading",
                type="default",
                children=html.Div(id="mcp-query-run-output"),
            ),
        ]),
        dcc.Store(id="mcp-query-input-path"),
        dcc.Store(id="mcp-query-columns"),
        dcc.Store(id="mcp-query-tools"),
    ], style={**uconn_styles['content'], 'maxWidth': '980px', 'margin': '40px auto 0 auto'})


def _save_uploaded_csv(contents: str, filename: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)
    safe_name = pathlib.Path(filename).stem
    uid = uuid.uuid4().hex[:8]
    dest = UPLOAD_DIR / f"{safe_name}_{uid}.csv"
    dest.write_bytes(decoded)
    return str(dest)


@callback(
    Output("mcp-query-input-path", "data"),
    Output("mcp-query-columns", "data"),
    Output("mcp-query-target-column", "options"),
    Output("mcp-query-target-column", "value"),
    Output("mcp-query-upload-container", "style"),
    Input("mcp-query-data-source", "value"),
    Input("mcp-query-upload", "contents"),
    State("mcp-query-upload", "filename"),
    prevent_initial_call=False,
)
def update_data_source(data_source, upload_contents, upload_filename):
    if data_source == "default":
        csv_path = str(DEFAULT_CSV_PATH)
        if not os.path.isfile(csv_path):
            return None, [], [], None, {'display': 'none'}
        columns = _read_csv_columns(csv_path)
        options = [{"label": c, "value": c} for c in columns]
        default_target = columns[-1] if columns else None
        return csv_path, columns, options, default_target, {'display': 'none'}

    if data_source == "upload" and upload_contents and upload_filename:
        csv_path = _save_uploaded_csv(upload_contents, upload_filename)
        columns = _read_csv_columns(csv_path)
        options = [{"label": c, "value": c} for c in columns]
        default_target = columns[-1] if columns else None
        return csv_path, columns, options, default_target, {'display': 'block'}

    return no_update, [], [], None, {'display': 'block'}


@callback(
    Output("mcp-query-output", "children"),
    Output("mcp-query-run-section", "style"),
    Output("mcp-query-tool-select", "options"),
    Output("mcp-query-tool-select", "value"),
    Output("mcp-query-tools", "data"),
    Input("mcp-query-recommend-btn", "n_clicks"),
    State("mcp-query-instructions", "value"),
    State("mcp-query-columns", "data"),
    State("mcp-query-input-path", "data"),
    State("mcp-query-model", "value"),
    prevent_initial_call=True,
)
def handle_recommend(n_clicks, instructions, columns, input_path, model):
    _ = n_clicks
    if not instructions or not instructions.strip():
        return "Please enter instructions first.", {'display': 'none'}, [], None, None

    if not input_path:
        return "Please select a data source first.", {'display': 'none'}, [], None, None

    if not os.path.isfile(input_path):
        return f"Input file not found: {input_path}", {'display': 'none'}, [], None, None

    df = pd.read_csv(input_path)
    row_count = len(df)

    ok, result = recommend_tools(
        instructions=instructions.strip(),
        columns=columns or [],
        row_count=row_count,
        model=model,
    )

    if not ok:
        return html.Div([
            html.H4("Recommendation failed", style={'color': '#A61B1B', 'marginBottom': '8px'}),
            html.Pre(str(result), style={
                'backgroundColor': '#FEE',
                'border': '1px solid #E88',
                'borderRadius': '6px',
                'padding': '10px',
                'overflowX': 'auto',
            }),
        ]), {'display': 'none'}, [], None, None

    recs = result
    client = MCPClientManager()
    tools_result = client.call_discovery_tool("list_discovered_tools", {})
    all_tools = tools_result.get("tools", [])

    rec_tools = [t for t in all_tools if t.get("id") in recs]
    tool_options = [{"label": f"{t.get('display_name', t['id'])} ({t['id']})", "value": t["id"]} for t in rec_tools]

    rec_md_lines = []
    for rt in rec_tools:
        tid = rt.get("id", "?")
        name = rt.get("display_name", tid)
        desc = rt.get("description", "")
        inputs = list(rt.get("inputs", {}).keys())
        rec_md_lines.append(f"- **{name}** (`{tid}`): {desc}")
    rec_md = "\n".join(rec_md_lines) if rec_md_lines else "*No compatible tools found.*"

    output = html.Div([
        html.H4("Recommended Tools", style={'color': UCONN_NAVY, 'marginBottom': '10px'}),
        dcc.Markdown(rec_md, style={
            'backgroundColor': UCONN_GRAY,
            'border': f'1px solid {UCONN_LIGHT_BLUE}',
            'borderRadius': '6px',
            'padding': '14px',
            'fontSize': '15px',
        }),
    ])

    show_run = {'display': 'block'} if tool_options else {'display': 'none'}
    default_tool = tool_options[0]["value"] if tool_options else None
    return output, show_run, tool_options, default_tool, recs


@callback(
    Output("mcp-query-run-output", "children"),
    Input("mcp-query-run-btn", "n_clicks"),
    State("mcp-query-tool-select", "value"),
    State("mcp-query-input-path", "data"),
    State("mcp-query-target-column", "value"),
    prevent_initial_call=True,
)
def handle_run_tool(n_clicks, tool_id, input_path, target_column):
    _ = n_clicks
    if not tool_id:
        return "Please select a tool to run."

    if not input_path or not os.path.isfile(input_path):
        return "Input file not found. Please re-select your data source."

    parameters = {}
    if target_column:
        parameters["target_column"] = target_column

    result = run_discovered_tool(tool_id, input_path, parameters=parameters)

    if not result.get("ok"):
        return html.Div([
            html.H4("Tool execution failed", style={'color': '#A61B1B', 'marginBottom': '8px'}),
            html.Pre(
                json.dumps(result, indent=2, default=str),
                style={
                    'backgroundColor': '#FEE',
                    'border': '1px solid #E88',
                    'borderRadius': '6px',
                    'padding': '10px',
                    'overflowX': 'auto',
                    'maxHeight': '400px',
                },
            ),
        ])

    output_dir = result.get("output_dir", "")
    stdout_path = result.get("stdout_path", "")
    stderr_path = result.get("stderr_path", "")
    metrics = result.get("metrics", {})

    children = [
        html.H4("Tool Results", style={'color': UCONN_NAVY, 'marginBottom': '10px'}),
        html.Div([
            html.Span("Status: ", style={'fontWeight': 'bold'}),
            html.Span("Completed", style={'color': '#1B7A1B', 'fontWeight': 'bold'}),
        ], style={'marginBottom': '8px'}),
    ]

    if metrics:
        metrics_display = {k: v for k, v in metrics.items() if k != "top_features"}
        children.append(html.Div([
            html.H5("Metrics", style={'color': UCONN_NAVY, 'marginBottom': '6px', 'marginTop': '14px'}),
            html.Pre(
                json.dumps(metrics_display, indent=2, default=str),
                style={
                    'backgroundColor': '#F0F4F8',
                    'border': f'1px solid {UCONN_LIGHT_BLUE}',
                    'borderRadius': '6px',
                    'padding': '10px',
                    'overflowX': 'auto',
                    'fontSize': '13px',
                },
            ),
        ]))

        top = metrics.get("top_features")
        if top:
            import pandas as pd
            top_df = pd.DataFrame(top)
            children.append(html.Div([
                html.H5("Top Features", style={'color': UCONN_NAVY, 'marginBottom': '6px', 'marginTop': '14px'}),
                dcc.Markdown(top_df.to_markdown(index=False), style={
                    'overflowX': 'auto',
                    'whiteSpace': 'nowrap',
                    'fontFamily': 'monospace',
                    'fontSize': '13px',
                }),
            ]))

    if stdout_path and os.path.isfile(stdout_path):
        text = open(stdout_path).read().strip()
        if text:
            children.append(html.Div([
                html.H5("Standard Output", style={'color': UCONN_NAVY, 'marginBottom': '6px', 'marginTop': '14px'}),
                html.Pre(text, style={
                    'backgroundColor': UCONN_GRAY,
                    'border': f'1px solid {UCONN_LIGHT_BLUE}',
                    'borderRadius': '6px',
                    'padding': '10px',
                    'overflowX': 'auto',
                    'fontSize': '13px',
                    'maxHeight': '300px',
                }),
            ]))

    plot_json = os.path.join(output_dir, "plot.json")
    if os.path.isfile(plot_json):
        try:
            with open(plot_json) as f:
                plot_data = json.load(f)
            children.append(html.Div([
                dcc.Graph(
                    figure=plot_data,
                    style={'height': 'auto', 'marginTop': '14px', 'marginBottom': '10px'},
                    config={'displayModeBar': True, 'scrollZoom': True},
                ),
            ]))
        except Exception:
            pass

    result_csv = os.path.join(output_dir, "results.csv")
    feature_ranking = os.path.join(output_dir, "feature_ranking.csv")
    feature_importance = os.path.join(output_dir, "feature_importance.csv")

    for csv_path, label in [
        (result_csv, "Results Preview"),
        (feature_ranking, "Feature Ranking"),
        (feature_importance, "Feature Importance"),
    ]:
        if os.path.isfile(csv_path):
            try:
                df = pd.read_csv(csv_path)
                children.append(html.Div([
                    html.H5(label, style={'color': UCONN_NAVY, 'marginBottom': '6px', 'marginTop': '14px'}),
                    dcc.Markdown(df.head(20).to_markdown(index=False), style={
                        'overflowX': 'auto',
                        'whiteSpace': 'nowrap',
                        'fontFamily': 'monospace',
                        'fontSize': '13px',
                    }),
                ]))
            except Exception:
                pass

    return html.Div(children, style={
        'backgroundColor': '#F7F9FC',
        'border': f'1px solid {UCONN_LIGHT_BLUE}',
        'borderRadius': '6px',
        'padding': '14px',
    })
