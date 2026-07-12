"""Local genomic overlap engine used by the overlap MCP server.

The engine downloads hg38 RefSeq annotations from UCSC once, preserves exon
intervals per gene, and exposes deterministic interval annotation helpers.
"""

from __future__ import annotations

import io
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import requests


SCRIPT_DIR = Path(__file__).parent.resolve()
CACHE_FILE = SCRIPT_DIR / "hg38_refseq_gene_exons.parquet"
UCSC_TABLE_URL = (
    "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/ncbiRefSeqCurated.txt.gz"
)

UCSC_COL_NAMES = [
    "bin",
    "name",
    "chrom",
    "strand",
    "txStart",
    "txEnd",
    "cdsStart",
    "cdsEnd",
    "exonCount",
    "exonStarts",
    "exonEnds",
    "score",
    "name2",
    "cdsStartStat",
    "cdsEndStat",
    "exonFrames",
]

STANDARD_CHROMS = {f"chr{i}" for i in list(range(1, 23)) + ["X", "Y", "M"]}

REQUIRED_COLUMNS = {
    "gene_name",
    "gene_chrom",
    "direction",
    "gene_start",
    "gene_end",
    "gene_length",
    "exon_count",
    "exons_json",
}


def _parse_int_list(raw_value: Any) -> list[int]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [int(value) for value in raw_value if str(value).strip()]
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


def _prepare_annotation_frame(raw: pd.DataFrame) -> pd.DataFrame:
    columns = ["name2", "chrom", "strand", "txStart", "txEnd", "exonStarts", "exonEnds"]
    frame = raw[columns].copy()
    frame.rename(
        columns={
            "name2": "gene_name",
            "chrom": "gene_chrom",
            "strand": "direction",
            "txStart": "gene_start",
            "txEnd": "gene_end",
        },
        inplace=True,
    )

    records: list[dict[str, Any]] = []
    grouped = frame.groupby(["gene_name", "gene_chrom", "direction"], sort=False)
    for (gene_name, gene_chrom, direction), group in grouped:
        gene_start = int(group["gene_start"].min())
        gene_end = int(group["gene_end"].max())
        exon_intervals: list[tuple[int, int]] = []
        for row in group.itertuples(index=False):
            starts = _parse_int_list(row.exonStarts)
            ends = _parse_int_list(row.exonEnds)
            exon_intervals.extend((int(start), int(end)) for start, end in zip(starts, ends) if int(end) > int(start))
        merged_exons = _merge_intervals(exon_intervals)
        records.append(
            {
                "gene_name": gene_name,
                "gene_chrom": gene_chrom,
                "direction": direction,
                "gene_start": gene_start,
                "gene_end": gene_end,
                "gene_length": gene_end - gene_start,
                "exon_count": len(merged_exons),
                "exons_json": json.dumps(merged_exons),
            }
        )

    annotated = pd.DataFrame(records)
    if not annotated.empty:
        annotated = annotated[annotated["gene_chrom"].isin(STANDARD_CHROMS)].copy()
        annotated.sort_values(["gene_chrom", "gene_start", "gene_end", "gene_name"], inplace=True)
        annotated.reset_index(drop=True, inplace=True)
    return annotated


def download_and_cache_annotations() -> pd.DataFrame:
    response = requests.get(UCSC_TABLE_URL, timeout=180, stream=True)
    response.raise_for_status()

    raw = pd.read_csv(
        io.BytesIO(response.content),
        sep="\t",
        header=None,
        names=UCSC_COL_NAMES,
        compression="gzip",
        low_memory=False,
    )
    annotations = _prepare_annotation_frame(raw)
    annotations.to_parquet(CACHE_FILE, index=False)
    return annotations


def load_annotations(refresh: bool = False) -> pd.DataFrame:
    if not refresh and CACHE_FILE.exists():
        cached = pd.read_parquet(CACHE_FILE)
        if REQUIRED_COLUMNS.issubset(set(cached.columns)):
            return cached
    return download_and_cache_annotations()


def build_chrom_index(annotations: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    chrom_index: dict[str, list[dict[str, Any]]] = {}
    for row in annotations.itertuples(index=False):
        chrom_index.setdefault(row.gene_chrom, []).append(
            {
                "gene_name": row.gene_name,
                "gene_chrom": row.gene_chrom,
                "direction": row.direction,
                "gene_start": int(row.gene_start),
                "gene_end": int(row.gene_end),
                "gene_length": int(row.gene_length),
                "exon_count": int(row.exon_count),
                "exons": json.loads(row.exons_json) if isinstance(row.exons_json, str) else list(row.exons_json or []),
            }
        )

    for chrom in chrom_index:
        chrom_index[chrom].sort(key=lambda item: (item["gene_start"], item["gene_end"], item["gene_name"]))
    return chrom_index


@lru_cache(maxsize=2)
def get_chrom_index(refresh: bool = False) -> dict[str, list[dict[str, Any]]]:
    annotations = load_annotations(refresh=refresh)
    return build_chrom_index(annotations)


def classify_interval(
    chrom: str,
    start: int,
    end: int,
    chrom_index: dict[str, list[dict[str, Any]]],
    margin: int = 2000,
) -> list[dict[str, Any]]:
    genes = chrom_index.get(chrom, [])
    matches: list[dict[str, Any]] = []

    for gene in genes:
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
