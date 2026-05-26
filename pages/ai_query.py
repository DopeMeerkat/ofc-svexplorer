"""
AI Query page for local LLM interaction.
"""

import json
import re

from dash import html, dcc, Input, Output, State, callback, no_update

from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE, UCONN_GRAY, uconn_styles
from utils.database import run_readonly_query
from types import SimpleNamespace

from utils.ai_query_visualizations import (
    ALLOWED_VISUALIZATION_KINDS,
    build_visualization_spec,
    render_visualization,
)
from utils.ollama_client import generate_ollama_response
from utils.openai_client import generate_openai_response


SCHEMA_SUMMARY = (
    "Schema summary:\n"
    "- genes(id, chrom, x1, x2, length, strand)\n"
    "- phenotype(family_id, part_id, bio_id, bam_id, pheno, child, proband, affected, gender, race)\n"
    "- phenotype_svs(sample, id, type, chrom, start, end, length, likelihood, methods, freq, pheno, gender)\n"
    "- background_svs(sample, id, type, chrom, start, end, length, likelihood, freq, pheno, gender, pop_code, superpop_code)\n"
    "Notes:\n"
    "- genes.x1/x2 are coordinates and length is gene length.\n"
    "- phenotype.child=1 means child, 0 means parent.\n"
    "- phenotype.pheno contains values: Normal, CL, CLP, Hypertelorism.\n"
    "- Treat phenotype as pheno != 'Normal' unless a specific pheno is requested.\n"
    "- phenotype.gender is 'M' or 'F'.\n"
    # "- bam_id (phenotype) and sample (phenotype_svs) are the person/sample identifiers.\n"
    "- phenotype_svs.sample matches phenotype.bam_id.\n"
    "- Use LOWER(pheno) when matching CL/CLP to be safe.\n"
    "- There is no table named samples; use phenotype for bam_id and pheno.\n"
    "- Chromosomes in genes are: chr1-22, chrX, chrY (see DISTINCT chrom list).\n"
    "- Default to phenotype_svs for person-level queries; use sample as the person id.\n"
    "- Avoid joins unless needed (e.g., family_id questions).\n"
    "Example queries:\n"
    "- SELECT length FROM genes WHERE id = 'FAM89B' LIMIT 1;\n"
    "- SELECT id, length FROM genes WHERE id IN ('FAM89B', 'ARGN');\n"
    "- SELECT bam_id, pheno FROM phenotype WHERE child = 1 AND LOWER(pheno) IN ('cl', 'clp') LIMIT 25;\n"
    "- SELECT bam_id, pheno FROM phenotype WHERE child = 0 AND LOWER(pheno) IN ('cl', 'clp') LIMIT 25;\n"
)

ALLOW_RAW_SQL_FALLBACK = False

def _additional_context(user_text: str) -> str:
    """
    Context.
    """
    _ = user_text
    return ""


def _build_sql_prompt(user_text: str) -> str:
    extra_context = _additional_context(user_text)
    return (
        "You are a data assistant for OFC-SV Explorer.\n"
        "Write a single SELECT-only SQLite query that answers the user question.\n"
        "Rules:\n"
        "- Output JSON only, no extra text or markdown.\n"
        "- JSON keys: sql (string), intent (string), confidence (0-1).\n"
        "- Use only SELECT statements, no writes.\n"
        "- Use only these tables: genes, phenotype, phenotype_svs, background_svs.\n"
        "- If a query is not possible, return sql as an empty string and confidence 0.0.\n\n"
        f"{SCHEMA_SUMMARY}"
        f"{extra_context}\n"
        "User question:\n"
        f"{user_text.strip()}\n"
    )


def _build_answer_prompt(user_text: str, summary: str) -> str:
    return (
        "You are a concise research assistant for OFC-SV Explorer.\n"
        "Answer the user using the database summary below.\n"
        "If the summary is empty or indicates no results, explain that clearly.\n\n"
        "- Do not include SQL or meta commentary in the response.\n"
        "- Do not add caveats about table names or assumptions.\n\n"
        "- Do not list results in the response.\n\n"
        "Database summary:\n"
        f"{summary}\n\n"
        "User question:\n"
        f"{user_text.strip()}\n"
    )


def _build_fallback_prompt(user_text: str) -> str:
    return (
        "You are a concise research assistant for OFC-SV Explorer.\n"
        "Answer the user as best as possible without running a database query.\n"
        "If the question needs data, say what specific data you would need.\n\n"
        "User question:\n"
        f"{user_text.strip()}\n"
    )


def _get_model_options():
    return [
        {"label": "Local: Qwen3 8B", "value": "ollama:qwen3:8b"},
        {"label": "OpenAI: GPT-4o Mini", "value": "openai:gpt-4o-mini"},
    ]


def _call_llm(model_value: str, prompt: str) -> str:
    if model_value == "openai:gpt-4o-mini":
        return generate_openai_response(prompt)
    return generate_ollama_response(prompt)


def _parse_json_response(raw_text: str) -> dict:
    raw = raw_text.strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            data = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return {}
    if not isinstance(data, dict):
        return {}
    return data


def _extract_gene_id_from_sql(sql_query: str) -> str | None:
    match = re.search(r"\bid\s*=\s*'([A-Za-z0-9_-]+)'", sql_query, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _summarize_rows(rows: list[dict], max_rows: int = 50) -> str:
    if not rows:
        return "No rows returned."

    columns = list(rows[0].keys())
    sample = rows[:max_rows]
    summary = {
        "row_count": len(rows),
        "columns": columns,
        "sample_rows": sample,
    }
    return json.dumps(summary, ensure_ascii=True)


def _format_results_table(rows: list[dict], max_rows: int = 50) -> str:
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


def _format_response_summary(rows: list[dict]) -> str:
    if not rows:
        return "No results found."
    return f"Query returned {len(rows)} row(s). See the result preview below."


def _build_visualization_prompt(user_text: str, rows: list[dict]) -> str:
    columns = list(rows[0].keys()) if rows else []
    allowed = ", ".join(sorted(ALLOWED_VISUALIZATION_KINDS))
    return (
        "You are a visualization selector for OFC-SV Explorer.\n"
        "Choose a visualization kind from the allowed list.\n"
        "Return JSON only, no markdown.\n\n"
        "JSON shape:\n"
        "{\n  \"visualization_kind\": \"one of the allowed values\"\n}\n\n"
        f"Allowed values: {allowed}\n"
        f"Columns: {columns}\n"
        f"Row count: {len(rows)}\n\n"
        "User question:\n"
        f"{user_text.strip()}\n"
    )


def page_layout():
    return html.Div([
        html.H2("AI Query", style={'color': UCONN_NAVY, 'marginBottom': '12px', 'fontWeight': 'bold'}),
        html.Div(
            [
                dcc.Textarea(
                    id="ai-query-input",
                    placeholder="Ask a question about genes, families, or SVs...",
                    style={
                        'width': '100%',
                        'minHeight': '120px',
                        'padding': '12px',
                        'borderRadius': '6px',
                        'border': f'1px solid {UCONN_LIGHT_BLUE}',
                        'fontSize': '15px',
                        'resize': 'vertical',
                    },
                ),
                html.Div([
                    html.Button(
                        "Submit",
                        id="ai-query-submit",
                        n_clicks=0,
                        style={
                            **uconn_styles['button'],
                            'marginTop': '10px',
                        },
                    ),
                    dcc.Dropdown(
                        id="ai-query-model",
                        options=_get_model_options(),
                        value="ollama:qwen3:8b",
                        clearable=False,
                        style={
                            'marginLeft': '12px',
                            'minWidth': '230px',
                            'fontSize': '12px',
                        },
                    ),
                    dcc.Checklist(
                        id="ai-query-show-visualization",
                        options=[{"label": "Show visualization when available", "value": "show"}],
                        value=["show"],
                        style={
                            'marginLeft': '12px',
                            'fontSize': '12px',
                        },
                    ),
                ], style={'display': 'flex', 'alignItems': 'center'}),
            ],
            style={'marginBottom': '20px'},
        ),
        dcc.Loading(
            id="ai-query-loading",
            type="default",
            children=dcc.Markdown(
                id="ai-query-output",
                style={
                    'whiteSpace': 'pre-wrap',
                    'backgroundColor': UCONN_GRAY,
                    'border': f'1px solid {UCONN_LIGHT_BLUE}',
                    'borderRadius': '6px',
                    'padding': '14px',
                    'minHeight': '140px',
                    'fontSize': '15px',
                },
            ),
        ),
        html.Div(
            id="ai-query-sql-container",
            style={
                'marginTop': '16px',
                'display': 'none',
            },
        ),
        html.Div(
            id="ai-query-visualization-container",
            style={'marginTop': '20px'},
        ),
    ], style={**uconn_styles['content'], 'maxWidth': '980px', 'margin': '40px auto 0 auto'})


@callback(
    Output("ai-query-output", "children"),
    Output("ai-query-sql-container", "children"),
    Output("ai-query-sql-container", "style"),
    Output("ai-query-visualization-container", "children"),
    Input("ai-query-submit", "n_clicks"),
    State("ai-query-input", "value"),
    State("ai-query-model", "value"),
    State("ai-query-show-visualization", "value"),
    prevent_initial_call=True,
    running=[
        (Output("ai-query-output", "children"), "", no_update),
        (Output("ai-query-sql-container", "children"), None, no_update),
        (Output("ai-query-sql-container", "style"), {'display': 'none'}, no_update),
        (Output("ai-query-visualization-container", "children"), html.Div(), no_update),
    ],
)
def handle_ai_query(n_clicks, user_text, model_value, show_visualization_values):
    _ = n_clicks
    if not user_text or not user_text.strip():
        return "Please enter a question to continue.", None, {'display': 'none'}, html.Div()

    show_visualization = bool(show_visualization_values and "show" in show_visualization_values)

    try:
        sql_prompt = _build_sql_prompt(user_text)
        raw_sql_response = _call_llm(model_value, sql_prompt)
        sql_payload = _parse_json_response(raw_sql_response)
        sql_query = (sql_payload.get("sql") or "").strip()

        if not sql_query.lower().startswith("select"):
            raise ValueError("No valid SQL generated")

        rows = run_readonly_query(sql_query, limit=5000)
        response = _format_response_summary(rows)

        result_preview = rows[:50]
        sql_block = dcc.Markdown(
            f"```sql\n{sql_query}\n```",
            style={'fontSize': '13px'},
        )
        results_block = dcc.Markdown(
            _format_results_table(result_preview, max_rows=50),
            style={'fontSize': '13px'},
        )

        sql_container = html.Div([
            html.Div(
                "Generated SQL",
                style={'fontWeight': 'bold', 'marginBottom': '6px'}
            ),
            sql_block,
            html.Div(
                "Result preview",
                style={'fontWeight': 'bold', 'margin': '12px 0 6px 0'}
            ),
            results_block,
        ], style={
            'backgroundColor': '#F7F9FC',
            'border': f'1px solid {UCONN_LIGHT_BLUE}',
            'borderRadius': '6px',
            'padding': '12px',
        })

        visualization_component = html.Div()
        if show_visualization:
            visualization_kind = "none"
            if rows:
                viz_prompt = _build_visualization_prompt(user_text, rows)
                raw_viz_response = _call_llm(model_value, viz_prompt)
                viz_payload = _parse_json_response(raw_viz_response)
                visualization_kind = (viz_payload.get("visualization_kind") or "none").strip()

            if visualization_kind not in ALLOWED_VISUALIZATION_KINDS:
                visualization_kind = "none"

            visualization_rows = rows
            gene_label = None
            if rows:
                first_row = rows[0]
                if all(key in first_row for key in ("id", "chrom", "x1", "x2")):
                    gene_label = first_row.get("id")
                    if len(rows) == 1:
                        visualization_kind = "population_igv_gene_window"
                elif visualization_kind == "none":
                    gene_id = _extract_gene_id_from_sql(sql_query)
                    if gene_id:
                        gene_rows = run_readonly_query(
                            "SELECT id, chrom, x1, x2, length, strand FROM genes WHERE id = :gene LIMIT 1",
                            params={"gene": gene_id},
                            limit=1,
                        )
                        if gene_rows:
                            visualization_rows = gene_rows
                            gene_label = gene_rows[0].get("id")
                            visualization_kind = "population_igv_gene_window"

            plan_stub = SimpleNamespace(
                intent="query",
                gene=gene_label,
                gene_a=None,
                flank_bp=0,
                visualization_kind=visualization_kind,
            )
            compiled = {"visualization_kind": visualization_kind}
            visualization_spec = build_visualization_spec(
                compiled=compiled,
                plan=plan_stub,
                rows=visualization_rows,
            )
            visualization_component = render_visualization(visualization_spec)

        return response, sql_container, {'display': 'block'}, visualization_component
    except ValueError:
        if not ALLOW_RAW_SQL_FALLBACK:
            message = (
                "I could not generate a valid SQL query for this question. "
                "Try rephrasing the request with a specific table or filter."
            )
            return message, None, {'display': 'none'}, html.Div()

        try:
            sql_prompt = _build_sql_prompt(user_text)
            raw_sql_response = _call_llm(model_value, sql_prompt)
            sql_payload = _parse_json_response(raw_sql_response)
            sql_query = (sql_payload.get("sql") or "").strip()
            if not sql_query.lower().startswith("select"):
                fallback_prompt = _build_fallback_prompt(user_text)
                response = _call_llm(model_value, fallback_prompt)
                return response, None, {'display': 'none'}, html.Div()

            rows = run_readonly_query(sql_query, limit=5000)
            response = _format_response_summary(rows)
            result_preview = rows[:50]
            sql_block = dcc.Markdown(
                f"```sql\n{sql_query}\n```",
                style={'fontSize': '13px'},
            )
            results_block = dcc.Markdown(
                _format_results_table(result_preview, max_rows=50),
                style={'fontSize': '13px'},
            )
            sql_container = html.Div([
                html.Div(
                    "Generated SQL",
                    style={'fontWeight': 'bold', 'marginBottom': '6px'}
                ),
                sql_block,
                html.Div(
                    "Result preview",
                    style={'fontWeight': 'bold', 'margin': '12px 0 6px 0'}
                ),
                results_block,
            ], style={
                'backgroundColor': '#F7F9FC',
                'border': f'1px solid {UCONN_LIGHT_BLUE}',
                'borderRadius': '6px',
                'padding': '12px',
            })
            return response, sql_container, {'display': 'block'}, html.Div()
        except Exception as fallback_exc:
            return f"Error running query: {fallback_exc}", None, {'display': 'none'}, html.Div()
    except Exception as exc:
        return f"Error generating response: {exc}", None, {'display': 'none'}, html.Div()
