"""
Genomic Coordinate Exon Overlap Annotator
-----------------------------------------
Reads an input CSV with columns (chrom, start, end, ...other columns...)
and annotates each row with overlapping hg38 RefSeq exons.

Output columns added:
  query_length,
  gene_name, transcript_id, exon_chrom, exon_number,
  exon_start, exon_end, exon_length,
  direction, overlap_bp, exon_overlap, before, after

By default, this checks exact exon overlap only. Use --margin if you also
want intervals near an exon to be reported.

Usage:
  python exon_overlap.py --input input.csv --output output.csv
  python exon_overlap.py --input input.csv --output output.csv --margin 2000
  python exon_overlap.py --input input.csv --output output.csv --refresh-cache
"""

import argparse
import sys
import pandas as pd
import requests
import io
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent.resolve()
CACHE_FILE = SCRIPT_DIR / "hg38_refseq_exons.parquet"

UCSC_TABLE_URL = (
    "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/ncbiRefSeqCurated.txt.gz"
)

UCSC_COL_NAMES = [
    "bin", "name", "chrom", "strand", "txStart", "txEnd",
    "cdsStart", "cdsEnd", "exonCount", "exonStarts", "exonEnds",
    "score", "name2", "cdsStartStat", "cdsEndStat", "exonFrames"
]

STANDARD_CHROMS = {f"chr{i}" for i in list(range(1, 23)) + ["X", "Y", "M"]}


# ---------------------------------------------------------------------------
# 1. Exon annotation: download + cache
# ---------------------------------------------------------------------------

def parse_ucsc_int_list(value: str) -> list[int]:
    """Parse UCSC comma-separated coordinate lists like '100,200,300,'."""
    return [int(x) for x in str(value).strip().rstrip(",").split(",") if x != ""]


def download_and_cache_exons() -> pd.DataFrame:
    """Download ncbiRefSeqCurated from UCSC, expand transcripts into exons, and cache."""
    print("Downloading hg38 RefSeq exon annotations from UCSC ...", flush=True)
    try:
        resp = requests.get(UCSC_TABLE_URL, timeout=180, stream=True)
        resp.raise_for_status()
    except Exception as exc:
        print(f"ERROR fetching exon annotations: {exc}", file=sys.stderr)
        sys.exit(1)

    raw = pd.read_csv(
        io.BytesIO(resp.content),
        sep="\t",
        header=None,
        names=UCSC_COL_NAMES,
        compression="gzip",
        low_memory=False,
    )

    raw = raw[raw["chrom"].isin(STANDARD_CHROMS)].copy()

    exon_rows = []
    for row in raw[["name", "name2", "chrom", "strand", "exonCount", "exonStarts", "exonEnds"]].itertuples(index=False):
        transcript_id = row.name
        gene_name = row.name2
        chrom = row.chrom
        strand = row.strand
        starts = parse_ucsc_int_list(row.exonStarts)
        ends = parse_ucsc_int_list(row.exonEnds)

        if len(starts) != len(ends):
            continue

        for coord_index, (exon_start, exon_end) in enumerate(zip(starts, ends), start=1):
            # UCSC exon starts/ends are stored in ascending coordinate order.
            # For negative-strand transcripts, biological exon numbering is reversed.
            if strand == "-":
                exon_number = len(starts) - coord_index + 1
            else:
                exon_number = coord_index

            exon_rows.append({
                "gene_name": gene_name,
                "transcript_id": transcript_id,
                "exon_chrom": chrom,
                "exon_number": exon_number,
                "exon_start": int(exon_start),
                "exon_end": int(exon_end),
                "exon_length": int(exon_end) - int(exon_start),
                "direction": strand,
            })

    df = pd.DataFrame(exon_rows)
    df = df.drop_duplicates().reset_index(drop=True)

    df.to_parquet(CACHE_FILE, index=False)
    print(f"  {len(df):,} exon records cached to: {CACHE_FILE}", flush=True)
    return df


def load_exons(refresh: bool = False) -> pd.DataFrame:
    """Return exon annotation DataFrame, using local cache when available."""
    if not refresh and CACHE_FILE.exists():
        print(f"Using cached exon annotations: {CACHE_FILE}", flush=True)
        df = pd.read_parquet(CACHE_FILE)
        print(f"  {len(df):,} exon records loaded.", flush=True)
        return df
    return download_and_cache_exons()


# ---------------------------------------------------------------------------
# 2. Build per-chromosome interval index
# ---------------------------------------------------------------------------

def build_chrom_index(exons: pd.DataFrame) -> dict:
    """dict: chrom -> list of exon dicts sorted by exon_start."""
    index = defaultdict(list)
    for row in exons.itertuples(index=False):
        index[row.exon_chrom].append({
            "gene_name": row.gene_name,
            "transcript_id": row.transcript_id,
            "exon_chrom": row.exon_chrom,
            "exon_number": row.exon_number,
            "exon_start": row.exon_start,
            "exon_end": row.exon_end,
            "exon_length": row.exon_length,
            "direction": row.direction,
        })
    for chrom in index:
        index[chrom].sort(key=lambda e: e["exon_start"])
    return dict(index)


# ---------------------------------------------------------------------------
# 3. Exon overlap logic
# ---------------------------------------------------------------------------

def find_overlapping_exons(
    chrom: str,
    start: int,
    end: int,
    chrom_index: dict,
    margin: int = 0,
) -> list:
    """
    Find all exons on `chrom` whose extended region
    [exon_start - margin, exon_end + margin] overlaps [start, end].

    If margin is 0, this only reports true exon overlaps.
    If margin is >0, this also reports intervals that touch the margin around an exon.

    before/after are strand-aware, matching the gene-overlap script's idea:
      + strand: before is low-coordinate side, after is high-coordinate side
      - strand: before is high-coordinate side, after is low-coordinate side
    """
    exons = chrom_index.get(chrom, [])
    results = []

    for exon in exons:
        e_start = exon["exon_start"]
        e_end = exon["exon_end"]
        strand = exon["direction"]
        ext_start = e_start - margin
        ext_end = e_end + margin

        # Half-open interval overlap check: [start, end) overlaps [ext_start, ext_end)
        if start >= ext_end or end <= ext_start:
            continue

        overlap_start = max(start, e_start)
        overlap_end = min(end, e_end)
        overlap_bp = max(0, overlap_end - overlap_start)
        exon_overlap = "Yes" if overlap_bp > 0 else "No"

        # Margin windows around the exon. These only matter when margin > 0.
        overlaps_low_margin = margin > 0 and (start < e_start) and (end > ext_start)
        overlaps_high_margin = margin > 0 and (end > e_end) and (start < ext_end)

        if strand == "+":
            before = "Yes" if overlaps_low_margin else "No"
            after = "Yes" if overlaps_high_margin else "No"
        else:
            before = "Yes" if overlaps_high_margin else "No"
            after = "Yes" if overlaps_low_margin else "No"

        results.append({
            **exon,
            "overlap_bp": overlap_bp,
            "exon_overlap": exon_overlap,
            "before": before,
            "after": after,
        })

    return results


# ---------------------------------------------------------------------------
# 4. Main pipeline
# ---------------------------------------------------------------------------

def run(input_path: str, output_path: str, margin: int = 0, refresh: bool = False) -> None:
    print(f"Reading input file: {input_path}", flush=True)
    input_df = pd.read_csv(input_path)

    for col in ("chrom", "start", "end"):
        if col not in input_df.columns:
            print(f"ERROR: input CSV must contain a '{col}' column.", file=sys.stderr)
            sys.exit(1)

    input_df["start"] = input_df["start"].astype(int)
    input_df["end"] = input_df["end"].astype(int)
    input_df["query_length"] = input_df["end"] - input_df["start"]
    print(f"  {len(input_df):,} input rows loaded.", flush=True)

    exons_df = load_exons(refresh=refresh)
    chrom_idx = build_chrom_index(exons_df)

    print(f"Annotating exon overlaps with ±{margin:,} bp margin ...", flush=True)
    annotation_cols = [
        "query_length",
        "gene_name", "transcript_id", "exon_chrom", "exon_number",
        "exon_start", "exon_end", "exon_length",
        "direction", "overlap_bp", "exon_overlap", "before", "after",
    ]
    output_rows = []

    for _, row in input_df.iterrows():
        hits = find_overlapping_exons(
            chrom=str(row["chrom"]),
            start=int(row["start"]),
            end=int(row["end"]),
            chrom_index=chrom_idx,
            margin=margin,
        )
        for hit in hits:
            out = row.to_dict()
            for col in annotation_cols:
                if col != "query_length":
                    out[col] = hit.get(col, "")
            output_rows.append(out)

    orig_cols = [c for c in input_df.columns if c != "query_length"]
    final_cols = orig_cols + annotation_cols

    if not output_rows:
        print("No exon overlaps found. Output file will be empty.", flush=True)
        pd.DataFrame(columns=final_cols).to_csv(output_path, index=False)
        return

    out_df = pd.DataFrame(output_rows)
    out_df[final_cols].to_csv(output_path, index=False)
    print(f"Done. {len(out_df):,} annotated rows written to: {output_path}", flush=True)


# ---------------------------------------------------------------------------
# 5. CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Annotate genomic intervals with overlapping hg38 RefSeq exons."
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input CSV with columns: chrom, start, end [, ...]")
    parser.add_argument("--output", "-o", required=True,
                        help="Output annotated CSV path")
    parser.add_argument("--margin", "-m", type=int, default=0,
                        help="Margin in bp added before/after each exon. Default is 0 for exact exon overlap.")
    parser.add_argument("--refresh-cache", action="store_true",
                        help="Force re-download of exon annotations even if cache exists")
    args = parser.parse_args()
    run(args.input, args.output, args.margin, args.refresh_cache)
