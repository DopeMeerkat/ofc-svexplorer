"""Overlap agent for exon-overlap questions."""

from __future__ import annotations

import re
from typing import Any

from utils.mcp_client_manager import MCPClientManager


EXON_QUERY_PATTERNS = (
    "exon overlap",
    "overlapping with an exon",
    "overlap with an exon",
    "overlap exons",
    "overlapping exons",
)


def looks_like_exon_overlap_question(question: str) -> bool:
    normalized = question.lower()
    if "sv" not in normalized and "svs" not in normalized and "structural variant" not in normalized:
        return False
    return any(pattern in normalized for pattern in EXON_QUERY_PATTERNS) or (
        "exon" in normalized and ("overlap" in normalized or "overlapping" in normalized)
    )


def _extract_chromosome(question: str) -> str | None:
    match = re.search(r"\b(?:chr(?:omosome)?\s*)?([0-9]{1,2}|x|y|m|mt)\b", question, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).upper()
    if value == "M":
        value = "MT"
    return f"chr{value}"


def _extract_sv_type(question: str) -> str | None:
    normalized = question.upper()
    for sv_type in ("DEL", "DUP", "INS", "INV", "BND"):
        if re.search(rf"\b{sv_type}\b", normalized):
            return sv_type
    type_words = {
        "DELETION": "DEL",
        "DELETIONS": "DEL",
        "DUPLICATION": "DUP",
        "DUPLICATIONS": "DUP",
        "INSERTION": "INS",
        "INSERTIONS": "INS",
        "INVERSION": "INV",
        "INVERSIONS": "INV",
    }
    for word, sv_type in type_words.items():
        if re.search(rf"\b{word}\b", normalized):
            return sv_type
    return None


def _extract_sample(question: str) -> str | None:
    match = re.search(r"\b(?:sample|person|bam)\s+([A-Za-z0-9_.-]+)\b", question, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_limit(question: str) -> int:
    match = re.search(r"\b(?:top|first|limit)\s+(\d{1,3})\b", question, re.IGNORECASE)
    if not match:
        return 100
    return max(1, min(int(match.group(1)), 500))


def _build_exon_overlap_sql(question: str) -> tuple[str, int]:
    where = []
    limit = _extract_limit(question)
    chromosome = _extract_chromosome(question)
    sv_type = _extract_sv_type(question)
    sample = _extract_sample(question)

    if chromosome:
        where.append(f"ps.chrom = '{chromosome}'")
    if sv_type:
        where.append(f"ps.type = '{sv_type}'")
    if sample:
        where.append(f"ps.sample = '{sample}'")

    where_sql = ""
    if where:
        where_sql = "WHERE " + " AND ".join(where)

    sql = f"""
        SELECT
            ps.sample AS sample_id,
            ps.id AS sv_id,
            ps.type AS sv_type,
            ps.chrom,
            ps.start AS sv_start,
            ps."end" AS sv_end,
            ps.length AS sv_length,
            e.gene_id,
            e.transcript_id,
            e.exon_number,
            e.exon_start,
            e.exon_end
        FROM phenotype_svs ps
        JOIN exons e
            ON e.chrom = ps.chrom
           AND ps.start <= e.exon_end
           AND ps."end" >= e.exon_start
        {where_sql}
        ORDER BY ps.chrom, ps.start, e.exon_start
        LIMIT {limit};
    """.strip()
    return sql, limit


def run_overlap_agent(question: str, client: MCPClientManager) -> dict[str, Any]:
    tool_calls = []
    sql, limit = _build_exon_overlap_sql(question)

    validation = client.call_db_tool("validate_select_sql", {"sql": sql})
    tool_calls.append({"tool": "validate_select_sql", "arguments": {"sql": sql}, "result": validation})
    if not validation.get("valid"):
        return {
            "ok": False,
            "error": validation.get("reason") or "SQL validation failed.",
            "tool_calls": tool_calls,
            "sql": sql,
        }

    result = client.call_db_tool("execute_readonly_sql", {"sql": sql, "limit": limit})
    tool_calls.append({"tool": "execute_readonly_sql", "arguments": {"sql": sql, "limit": limit}, "result": result})

    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error", "Overlap request failed."),
            "tool_calls": tool_calls,
            "sql": sql,
        }

    rows = result.get("rows", [])
    summary = f"Found {len(rows)} SV/exon overlap row(s) in the result preview."
    return {
        "ok": True,
        "response_summary": summary,
        "rows": rows,
        "columns": result.get("columns", list(rows[0].keys()) if rows else []),
        "sql": sql,
        "db_tool_calls": tool_calls,
        "viz_tool_calls": [],
        "overlap_tool_calls": [],
        "visualization_spec": {"kind": "table" if rows else "none"},
    }
