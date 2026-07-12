"""
Genomic Coordinate Overlap Annotator
-------------------------------------
Reads an input CSV with columns (chrom, start, end, ...other columns...)
and annotates each row with overlapping hg38 genes (±2kb margin).

Output columns added:
  gene_name, gene_chrom, gene_start, gene_end, gene_length,
  direction, before, after

The hg38 gene annotation table is downloaded once from UCSC and cached
locally as hg38_refseq_genes.parquet (same directory as this script).
On subsequent runs the cached file is used automatically.
To force a fresh download, delete or pass --refresh-cache.

Usage:
  python genomic_overlap.py --input input.csv --output output.csv
  python genomic_overlap.py --input input.csv --output output.csv --margin 2000
  python genomic_overlap.py --input input.csv --output output.csv --refresh-cache
"""

import argparse
import sys
import os
import pandas as pd
import requests
import io
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR  = Path(__file__).parent.resolve()
CACHE_FILE  = SCRIPT_DIR / "hg38_refseq_genes.parquet"

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
# 1. Gene annotation: download + cache
# ---------------------------------------------------------------------------

def download_and_cache_genes() -> pd.DataFrame:
    """Download ncbiRefSeqCurated from UCSC, collapse transcripts, and cache."""
    print(f"Downloading hg38 RefSeq gene annotations from UCSC ...", flush=True)
    try:
        resp = requests.get(UCSC_TABLE_URL, timeout=180, stream=True)
        resp.raise_for_status()
    except Exception as exc:
        print(f"ERROR fetching gene annotations: {exc}", file=sys.stderr)
        sys.exit(1)

    raw = pd.read_csv(
        io.BytesIO(resp.content),
        sep="\t",
        header=None,
        names=UCSC_COL_NAMES,
        compression="gzip",
        low_memory=False,
    )

    df = raw[["name2", "chrom", "strand", "txStart", "txEnd"]].copy()
    df.rename(columns={
        "name2":   "gene_name",
        "strand":  "direction",
        "txStart": "gene_start",
        "txEnd":   "gene_end",
    }, inplace=True)

    # Collapse multiple transcripts → single span per gene + chrom + strand
    df = (
        df.groupby(["gene_name", "chrom", "direction"], as_index=False)
          .agg(gene_start=("gene_start", "min"), gene_end=("gene_end", "max"))
    )

    # Standard chromosomes only
    df = df[df["chrom"].isin(STANDARD_CHROMS)].copy()
    df["gene_length"] = df["gene_end"] - df["gene_start"]

    # Save cache
    df.to_parquet(CACHE_FILE, index=False)
    print(f"  {len(df):,} gene records cached to: {CACHE_FILE}", flush=True)
    return df


def load_genes(refresh: bool = False) -> pd.DataFrame:
    """Return gene annotation DataFrame, using local cache when available."""
    if not refresh and CACHE_FILE.exists():
        print(f"Using cached gene annotations: {CACHE_FILE}", flush=True)
        df = pd.read_parquet(CACHE_FILE)
        print(f"  {len(df):,} gene records loaded.", flush=True)
        return df
    return download_and_cache_genes()


# ---------------------------------------------------------------------------
# 2. Build per-chromosome interval index
# ---------------------------------------------------------------------------

def build_chrom_index(genes: pd.DataFrame) -> dict:
    """dict: chrom -> list of gene dicts sorted by gene_start."""
    index = defaultdict(list)
    for row in genes.itertuples(index=False):
        index[row.chrom].append({
            "gene_name":   row.gene_name,
            "gene_chrom":  row.chrom,
            "gene_start":  row.gene_start,
            "gene_end":    row.gene_end,
            "gene_length": row.gene_length,
            "direction":   row.direction,
        })
    for chrom in index:
        index[chrom].sort(key=lambda g: g["gene_start"])
    return dict(index)


# ---------------------------------------------------------------------------
# 3. Overlap logic with ±margin
# ---------------------------------------------------------------------------

def find_overlapping_genes(
    chrom: str,
    start: int,
    end: int,
    chrom_index: dict,
    margin: int = 2000,
) -> list:
    """
    Find all genes on `chrom` whose extended region
    [gene_start - margin, gene_end + margin] overlaps [start, end].

    Strand-aware definitions
    ------------------------
    For a + strand gene:
      'before' (upstream)   = the margin on the LOW-coordinate  side (gene_start - margin)
      'after'  (downstream) = the margin on the HIGH-coordinate side (gene_end   + margin)

    For a - strand gene:
      'before' (upstream)   = the margin on the HIGH-coordinate side (gene_end   + margin)
      'after'  (downstream) = the margin on the LOW-coordinate  side (gene_start - margin)

    before = "Yes"  →  query overlaps the upstream   margin window for this gene's strand
    after  = "Yes"  →  query overlaps the downstream margin window for this gene's strand
    """
    genes   = chrom_index.get(chrom, [])
    results = []

    for gene in genes:
        g_start   = gene["gene_start"]
        g_end     = gene["gene_end"]
        strand    = gene["direction"]
        ext_start = g_start - margin
        ext_end   = g_end   + margin

        # Skip if no overlap with the fully extended region
        if start > ext_end or end < ext_start:
            continue

        # Low-coord margin window:  [g_start - margin, g_start)
        # High-coord margin window: (g_end,             g_end + margin]
        overlaps_low_margin  = (start < g_start) and (end > ext_start)
        overlaps_high_margin = (end   > g_end)   and (start < ext_end)

        if strand == "+":
            before = "Yes" if overlaps_low_margin  else "No"
            after  = "Yes" if overlaps_high_margin else "No"
        else:
            # "-" strand (or any non-"+" strand): upstream is the high-coord side
            before = "Yes" if overlaps_high_margin else "No"
            after  = "Yes" if overlaps_low_margin  else "No"

        results.append({**gene, "before": before, "after": after})

    return results


# ---------------------------------------------------------------------------
# 4. Main pipeline
# ---------------------------------------------------------------------------

def run(input_path: str, output_path: str, margin: int = 2000, refresh: bool = False) -> None:
    # Load input
    print(f"Reading input file: {input_path}", flush=True)
    input_df = pd.read_csv(input_path)

    for col in ("chrom", "start", "end"):
        if col not in input_df.columns:
            print(f"ERROR: input CSV must contain a '{col}' column.", file=sys.stderr)
            sys.exit(1)

    input_df["start"] = input_df["start"].astype(int)
    input_df["end"]   = input_df["end"].astype(int)
    # Add query_length derived from input coordinates
    input_df["query_length"] = input_df["end"] - input_df["start"]
    print(f"  {len(input_df):,} input rows loaded.", flush=True)

    # Load gene annotations (cached or fresh)
    genes_df  = load_genes(refresh=refresh)
    chrom_idx = build_chrom_index(genes_df)

    # Annotate
    print(f"Annotating with ±{margin:,} bp margin ...", flush=True)
    # query_length comes first, then gene annotation columns
    annotation_cols = [
        "query_length",
        "gene_name", "gene_chrom", "gene_start", "gene_end",
        "gene_length", "direction", "before", "after"
    ]
    output_rows = []

    for _, row in input_df.iterrows():
        hits = find_overlapping_genes(
            chrom=str(row["chrom"]),
            start=int(row["start"]),
            end=int(row["end"]),
            chrom_index=chrom_idx,
            margin=margin,
        )
        for hit in hits:
            out = row.to_dict()
            for col in annotation_cols:
                # query_length is already in `out` from input_df; gene cols come from hit
                if col != "query_length":
                    out[col] = hit.get(col, "")
            output_rows.append(out)

    if not output_rows:
        print("No overlaps found. Output file will be empty.", flush=True)
        pd.DataFrame(columns=list(input_df.columns) + annotation_cols).to_csv(
            output_path, index=False
        )
        return

    out_df = pd.DataFrame(output_rows)
    # Original input cols (excluding query_length which we appended), then annotation cols
    orig_cols  = [c for c in input_df.columns if c != "query_length"]
    final_cols = orig_cols + annotation_cols
    out_df[final_cols].to_csv(output_path, index=False)
    print(f"Done. {len(out_df):,} annotated rows written to: {output_path}", flush=True)


# ---------------------------------------------------------------------------
# 5. CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Annotate genomic intervals with overlapping hg38 genes (±2kb margin)."
    )
    parser.add_argument("--input",  "-i", required=True,
                        help="Input CSV with columns: chrom, start, end [, ...]")
    parser.add_argument("--output", "-o", required=True,
                        help="Output annotated CSV path")
    parser.add_argument("--margin", "-m", type=int, default=2000,
                        help="Margin (bp) added before/after each gene (default: 2000)")
    parser.add_argument("--refresh-cache", action="store_true",
                        help="Force re-download of gene annotations even if cache exists")
    args = parser.parse_args()
    run(args.input, args.output, args.margin, args.refresh_cache)
