"""Standard-library overlap engine for the overlap MCP server."""

from __future__ import annotations

import bisect
import csv
import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import sqlite3

try:
    from utils.database import DB_PATH as DEFAULT_DB_PATH
except Exception:  # pragma: no cover - safe fallback if utils.database is unavailable
    DEFAULT_DB_PATH = "/data/cellvar.db/cellvar.db"


SCRIPT_DIR = Path(__file__).parent.resolve()
CACHE_FILE = SCRIPT_DIR / "hg38_refseq_gene_exons.json"
UCSC_TABLE_URL = (
    "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/ncbiRefSeqCurated.txt.gz"
)
DB_PATH = DEFAULT_DB_PATH

STANDARD_CHROMS = {f"chr{i}" for i in list(range(1, 23)) + ["X", "Y", "M"]}
REQUIRED_COLUMNS = {
    "gene_name",
    "gene_chrom",
    "direction",
    "gene_start",
    "gene_end",
    "gene_length",
    "exon_count",
    "exons",
}


def _parse_int_list(raw_value: Any) -> list[int]:
    if raw_value is None:
        return []
    text = str(raw_value).strip().rstrip(",")
    if not text:
        return []
    return [int(value) for value in text.split(",") if str(value).strip()]


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    ordered = sorted((int(start), int(end)) for start, end in intervals if int(end) > int(start))
    merged: list[tuple[int, int]] = []
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = start, end
    merged.append((current_start, current_end))
    return merged


def _overlaps(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return int(start_a) < int(end_b) and int(end_a) > int(start_b)


def _primary_overlap_type(overlap_types: list[str]) -> str:
    priority = ["exon", "within_gene_without_exon", "gene_body", "upstream_margin", "downstream_margin"]
    for overlap_type in priority:
        if overlap_type in overlap_types:
            return overlap_type
    return "none"


def _load_cached_annotations() -> list[dict[str, Any]]:
    if not CACHE_FILE.exists():
        return []
    with CACHE_FILE.open("r", encoding="utf-8") as handle:
        cached = json.load(handle)
    if not isinstance(cached, list):
        return []
    return cached


def _save_cached_annotations(records: list[dict[str, Any]]) -> None:
    with CACHE_FILE.open("w", encoding="utf-8") as handle:
        json.dump(records, handle)


def _prepare_annotation_records() -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    with urlopen(UCSC_TABLE_URL, timeout=180) as response:
        with gzip.GzipFile(fileobj=response) as gz_handle:
            text_handle = gz_handle.read().decode("utf-8")

    reader = csv.reader(text_handle.splitlines(), delimiter="\t")
    for row in reader:
        if len(row) < 16:
            continue
        chrom = row[2]
        if chrom not in STANDARD_CHROMS:
            continue
        direction = row[3]
        gene_name = row[12].strip()
        if not gene_name:
            continue
        gene_start = int(row[4])
        gene_end = int(row[5])
        exon_starts = _parse_int_list(row[10])
        exon_ends = _parse_int_list(row[11])
        exon_intervals = [(start, end) for start, end in zip(exon_starts, exon_ends) if int(end) > int(start)]

        key = (gene_name, chrom, direction)
        record = grouped.setdefault(
            key,
            {
                "gene_name": gene_name,
                "gene_chrom": chrom,
                "direction": direction,
                "gene_start": gene_start,
                "gene_end": gene_end,
                "exon_intervals": [],
            },
        )
        record["gene_start"] = min(int(record["gene_start"]), gene_start)
        record["gene_end"] = max(int(record["gene_end"]), gene_end)
        record["exon_intervals"].extend(exon_intervals)

    records: list[dict[str, Any]] = []
    for record in grouped.values():
        merged_exons = _merge_intervals(record["exon_intervals"])
        records.append(
            {
                "gene_name": record["gene_name"],
                "gene_chrom": record["gene_chrom"],
                "direction": record["direction"],
                "gene_start": int(record["gene_start"]),
                "gene_end": int(record["gene_end"]),
                "gene_length": int(record["gene_end"]) - int(record["gene_start"]),
                "exon_count": len(merged_exons),
                "exons": merged_exons,
            }
        )

    records.sort(key=lambda item: (item["gene_chrom"], item["gene_start"], item["gene_end"], item["gene_name"]))
    return records


def load_annotations(refresh: bool = False) -> list[dict[str, Any]]:
    if not refresh:
        cached = _load_cached_annotations()
        if cached and REQUIRED_COLUMNS.issubset(set(cached[0].keys())):
            return cached
    records = _prepare_annotation_records()
    _save_cached_annotations(records)
    return records


def build_chrom_index(annotations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    chrom_index: dict[str, list[dict[str, Any]]] = {}
    for record in annotations:
        chrom_index.setdefault(record["gene_chrom"], []).append(record)
    for chrom in chrom_index:
        chrom_index[chrom].sort(key=lambda item: (item["gene_start"], item["gene_end"], item["gene_name"]))
    return chrom_index


def build_exon_index(annotations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    exon_index: dict[str, dict[str, Any]] = {}
    exon_intervals_by_chrom: dict[str, list[tuple[int, int]]] = {}
    for record in annotations:
        chrom = record["gene_chrom"]
        exon_intervals_by_chrom.setdefault(chrom, []).extend(record.get("exons", []))

    for chrom, intervals in exon_intervals_by_chrom.items():
        merged = _merge_intervals(intervals)
        starts = [interval[0] for interval in merged]
        exon_index[chrom] = {"intervals": merged, "starts": starts}

    return exon_index


@lru_cache(maxsize=2)
def get_chrom_index(refresh: bool = False) -> dict[str, list[dict[str, Any]]]:
    return build_chrom_index(load_annotations(refresh=refresh))


@lru_cache(maxsize=2)
def get_exon_index(refresh: bool = False) -> dict[str, dict[str, Any]]:
    return build_exon_index(load_annotations(refresh=refresh))


def classify_interval(
    chrom: str,
    start: int,
    end: int,
    chrom_index: dict[str, list[dict[str, Any]]],
    margin: int = 2000,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for gene in chrom_index.get(chrom, []):
        gene_start = int(gene["gene_start"])
        gene_end = int(gene["gene_end"])
        direction = gene["direction"]
        exon_intervals = gene.get("exons", [])

        if not _overlaps(start, end, gene_start - margin, gene_end + margin):
            continue

        gene_body_overlap = _overlaps(start, end, gene_start, gene_end)
        exon_overlap = any(_overlaps(start, end, int(exon_start), int(exon_end)) for exon_start, exon_end in exon_intervals)
        within_gene_without_exon = gene_body_overlap and not exon_overlap
        upstream_margin_overlap = False
        downstream_margin_overlap = False

        if not gene_body_overlap:
            low_margin_overlap = _overlaps(start, end, gene_start - margin, gene_start)
            high_margin_overlap = _overlaps(start, end, gene_end, gene_end + margin)
            if direction == "+":
                upstream_margin_overlap = low_margin_overlap
                downstream_margin_overlap = high_margin_overlap
            else:
                upstream_margin_overlap = high_margin_overlap
                downstream_margin_overlap = low_margin_overlap

        overlap_types: list[str] = []
        if exon_overlap:
            overlap_types.append("exon")
        if within_gene_without_exon:
            overlap_types.append("within_gene_without_exon")
        elif gene_body_overlap:
            overlap_types.append("gene_body")
        if upstream_margin_overlap:
            overlap_types.append("upstream_margin")
        if downstream_margin_overlap:
            overlap_types.append("downstream_margin")

        matches.append(
            {
                **gene,
                "query_chrom": chrom,
                "query_start": int(start),
                "query_end": int(end),
                "gene_body_overlap": gene_body_overlap,
                "exon_overlap": exon_overlap,
                "within_gene_without_exon": within_gene_without_exon,
                "upstream_margin_overlap": upstream_margin_overlap,
                "downstream_margin_overlap": downstream_margin_overlap,
                "overlap_types": overlap_types,
                "primary_overlap_type": _primary_overlap_type(overlap_types),
            }
        )

    return matches


def _has_exon_overlap(
    chrom: str,
    start: int,
    end: int,
    exon_index: dict[str, dict[str, Any]],
    margin: int = 0,
) -> bool:
    entry = exon_index.get(chrom)
    if not entry:
        return False
    intervals = entry.get("intervals", [])
    starts = entry.get("starts", [])
    if not intervals:
        return False
    extended_start = start - margin
    extended_end = end + margin
    pos = bisect.bisect_right(starts, extended_end) - 1
    if pos < 0:
        return False
    interval_start, interval_end = intervals[pos]
    return extended_start < interval_end and extended_end > interval_start


def annotate_queries(
    queries: list[dict[str, Any]],
    margin: int = 2000,
    refresh_cache: bool = False,
    emit_unmatched_rows: bool = False,
) -> dict[str, Any]:
    chrom_index = get_chrom_index(refresh=refresh_cache)
    rows: list[dict[str, Any]] = []
    summary = {
        "query_count": 0,
        "matched_query_count": 0,
        "unmatched_query_count": 0,
        "match_count": 0,
        "primary_overlap_type_counts": {},
    }

    for index, raw_query in enumerate(queries):
        if not isinstance(raw_query, dict):
            raise ValueError(f"Query at index {index} must be an object with chrom/start/end fields.")
        if "chrom" not in raw_query or "start" not in raw_query or "end" not in raw_query:
            raise ValueError(f"Query at index {index} must include chrom, start, and end.")

        chrom = str(raw_query["chrom"])
        start = int(raw_query["start"])
        end = int(raw_query["end"])
        if end < start:
            start, end = end, start

        matches = classify_interval(chrom, start, end, chrom_index, margin=margin)
        summary["query_count"] += 1

        if matches:
            summary["matched_query_count"] += 1
            summary["match_count"] += len(matches)
            for match in matches:
                primary = match["primary_overlap_type"]
                summary["primary_overlap_type_counts"][primary] = summary["primary_overlap_type_counts"].get(primary, 0) + 1
                row = dict(raw_query)
                row.update(match)
                row["query_index"] = index
                rows.append(row)
        else:
            summary["unmatched_query_count"] += 1
            if emit_unmatched_rows:
                row = dict(raw_query)
                row.update(
                    {
                        "query_index": index,
                        "query_chrom": chrom,
                        "query_start": start,
                        "query_end": end,
                        "gene_name": None,
                        "gene_chrom": None,
                        "direction": None,
                        "gene_start": None,
                        "gene_end": None,
                        "gene_length": None,
                        "exon_count": 0,
                        "exons": [],
                        "gene_body_overlap": False,
                        "exon_overlap": False,
                        "within_gene_without_exon": False,
                        "upstream_margin_overlap": False,
                        "downstream_margin_overlap": False,
                        "overlap_types": [],
                        "primary_overlap_type": "none",
                    }
                )
                rows.append(row)

    rows.sort(key=lambda item: (item.get("query_index", 0), item.get("gene_start") is None, item.get("gene_start") or 0, item.get("gene_name") or ""))
    return {
        "ok": True,
        "margin": int(margin),
        "cache_file": str(CACHE_FILE),
        "summary": summary,
        "row_count": len(rows),
        "rows": rows,
    }


def count_svs_overlapping_exons(
    table_name: str = "phenotype_svs",
    chromosome: str | None = None,
    sample: str | None = None,
    sv_type: str | None = None,
    phenotype: str | None = None,
    margin: int = 0,
    refresh_cache: bool = False,
    batch_size: int = 5000,
) -> dict[str, Any]:
    if table_name not in {"phenotype_svs", "background_svs"}:
        raise ValueError("table_name must be phenotype_svs or background_svs")

    exon_index = get_exon_index(refresh=refresh_cache)
    where_clauses = []
    params: list[Any] = []
    if chromosome:
        where_clauses.append("chrom = ?")
        params.append(chromosome)
    if sample:
        where_clauses.append("sample = ?")
        params.append(sample)
    if sv_type:
        where_clauses.append("type = ?")
        params.append(sv_type)
    if phenotype:
        where_clauses.append("LOWER(pheno) = LOWER(?)")
        params.append(phenotype)

    query = f"SELECT sample, id AS sv_id, type AS sv_type, chrom, start, \"end\" AS sv_end FROM {table_name}"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY chrom, start"

    matched_rows: list[dict[str, Any]] = []
    total_rows = 0
    distinct_sv_ids: set[str] = set()
    exon_match_count = 0
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        while True:
            batch = cursor.fetchmany(batch_size)
            if not batch:
                break
            for row in batch:
                total_rows += 1
                chrom = row["chrom"]
                start = int(row["start"])
                end = int(row["sv_end"])
                if _has_exon_overlap(chrom, start, end, exon_index, margin=margin):
                    exon_match_count += 1
                    sv_id = str(row["sv_id"])
                    distinct_sv_ids.add(sv_id)
                    matched_rows.append(
                        {
                            "sample": row["sample"],
                            "sv_id": sv_id,
                            "sv_type": row["sv_type"],
                            "chrom": chrom,
                            "start": start,
                            "end": end,
                            "exon_overlap": True,
                        }
                    )
    finally:
        conn.close()

    return {
        "ok": True,
        "table_name": table_name,
        "chromosome": chromosome,
        "sample": sample,
        "sv_type": sv_type,
        "phenotype": phenotype,
        "margin": int(margin),
        "query_row_count": total_rows,
        "matching_sv_count": len(distinct_sv_ids),
        "matching_overlap_row_count": exon_match_count,
        "rows": matched_rows[:500],
        "summary": {
            "table_name": table_name,
            "query_row_count": total_rows,
            "matching_sv_count": len(distinct_sv_ids),
            "matching_overlap_row_count": exon_match_count,
            "exon_overlap_count": len(distinct_sv_ids),
        },
    }
