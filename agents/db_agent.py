"""
DB agent for MCP-enabled AI Query.
"""

from __future__ import annotations

import json
from typing import Any

from utils.mcp_client_manager import MCPClientManager
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
    "- phenotype_svs.sample matches phenotype.bam_id.\n"
    "- Use LOWER(pheno) when matching CL/CLP to be safe.\n"
    "- There is no table named samples; use phenotype for bam_id and pheno.\n"
    "- Chromosomes in genes are: chr1-22, chrX, chrY (see DISTINCT chrom list).\n"
    "- Default to phenotype_svs for person-level queries; use sample as the person id.\n"
    "- Avoid joins unless needed (e.g., family_id questions).\n"
)


def _build_sql_prompt(user_text: str) -> str:
    return (
        "You are a data assistant for OFC-SV Explorer.\n"
        "Write a single SELECT-only SQLite query that answers the user question.\n"
        "Rules:\n"
        "- Output JSON only, no extra text or markdown.\n"
        "- JSON keys: sql (string).\n"
        "- Use only SELECT statements, no writes.\n"
        "- Use only these tables: genes, phenotype, phenotype_svs, background_svs.\n"
        "- If a query is not possible, return sql as an empty string.\n\n"
        f"{SCHEMA_SUMMARY}"
        "User question:\n"
        f"{user_text.strip()}\n"
    )


def _call_llm(model_value: str, prompt: str) -> str:
    if model_value == "openai:gpt-4o-mini":
        return generate_openai_response(prompt)
    return generate_ollama_response(prompt)


def _parse_json_response(raw_text: str) -> dict[str, Any]:
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


def run_db_agent(user_text: str, model_value: str, client: MCPClientManager) -> dict[str, Any]:
    tool_calls = []
    prompt = _build_sql_prompt(user_text)
    raw_sql = _call_llm(model_value, prompt)
    payload = _parse_json_response(raw_sql)
    sql = (payload.get("sql") or "").strip()

    if not sql:
        return {"ok": False, "error": "No SQL returned by model.", "tool_calls": tool_calls}

    validation = client.call_db_tool("validate_select_sql", {"sql": sql})
    tool_calls.append({"tool": "validate_select_sql", "arguments": {"sql": sql}, "result": validation})
    if not validation.get("valid"):
        reason = validation.get("reason") or "SQL validation failed."
        return {"ok": False, "error": reason, "tool_calls": tool_calls, "sql": sql}

    exec_result = client.call_db_tool("execute_readonly_sql", {"sql": sql, "limit": 500})
    tool_calls.append({"tool": "execute_readonly_sql", "arguments": {"sql": sql, "limit": 500}, "result": exec_result})

    if not exec_result.get("ok"):
        return {"ok": False, "error": exec_result.get("error", "Execution failed."), "tool_calls": tool_calls, "sql": sql}

    return {
        "ok": True,
        "sql": sql,
        "row_count": exec_result.get("row_count", 0),
        "columns": exec_result.get("columns", []),
        "rows": exec_result.get("rows", []),
        "tool_calls": tool_calls,
    }
