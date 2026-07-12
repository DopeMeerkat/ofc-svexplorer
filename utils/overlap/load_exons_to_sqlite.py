#!/usr/bin/env python3
"""
Load hg38 RefSeq exon annotations from parquet into the OFC SQLite database.

Default DB:
    /data/cellvar.db/cellvar.db

Expected input:
    hg38_refseq_exons.parquet

The script tries to handle several likely column naming conventions, such as:
    gene, gene_id, name2, geneSymbol
    transcript_id, transcript, name
    chrom, chromosome
    exon_start, start, txStart
    exon_end, end, txEnd
    exon_number, exon_idx
    strand

Usage:
    python scripts/load_exons_to_sqlite.py \
        --exons-parquet hg38_refseq_exons.parquet

Optional:
    python scripts/load_exons_to_sqlite.py \
        --exons-parquet hg38_refseq_exons.parquet \
        --db-path /data/cellvar.db/cellvar.db \
        --replace
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd


DEFAULT_DB_PATH = "/data/cellvar.db/cellvar.db"


def find_col(df: pd.DataFrame, candidates: list[str], required: bool = True) -> Optional[str]:
    """Find the first matching column, case-insensitive."""
    lower_to_original = {c.lower(): c for c in df.columns}

    for cand in candidates:
        if cand.lower() in lower_to_original:
            return lower_to_original[cand.lower()]

    if required:
        raise ValueError(
            f"Could not find required column. Tried: {candidates}. "
            f"Available columns: {list(df.columns)}"
        )

    return None


def normalize_chrom(chrom: object) -> str:
    """Normalize chromosome names to chr-prefixed format."""
    value = str(chrom).strip()
    if not value:
        return value
    if value.startswith("chr"):
        return value
    return f"chr{value}"


def clean_str(value: object) -> Optional[str]:
    """Normalize nullable string fields."""
    if pd.isna(value):
        return None
    value = str(value).strip()
    return value if value else None


def load_exons_dataframe(exons_parquet: str) -> pd.DataFrame:
    """Load and normalize exon annotation parquet into a standard dataframe."""
    path = Path(exons_parquet)
    if not path.exists():
        raise FileNotFoundError(f"Exon parquet file not found: {path}")

    df = pd.read_parquet(path)

    print("Loaded parquet:", path)
    print("Input columns:", list(df.columns))
    print("Input rows:", len(df))

    gene_col = find_col(
        df,
        [
            "gene_id",
            "gene",
            "gene_name",
            "geneSymbol",
            "gene_symbol",
            "name2",
        ],
        required=True,
    )

    transcript_col = find_col(
        df,
        [
            "transcript_id",
            "transcript",
            "tx_id",
            "name",
            "refseq_id",
            "mrnaAcc",
        ],
        required=False,
    )

    chrom_col = find_col(
        df,
        ["chrom", "chromosome", "chr", "exon_chrom"],
        required=True,
    )

    start_col = find_col(
        df,
        [
            "exon_start",
            "exonStart",
            "start",
            "chromStart",
        ],
        required=True,
    )

    end_col = find_col(
        df,
        [
            "exon_end",
            "exonEnd",
            "end",
            "chromEnd",
        ],
        required=True,
    )

    exon_number_col = find_col(
        df,
        [
            "exon_number",
            "exonNumber",
            "exon_idx",
            "exonIndex",
            "exon_rank",
            "rank",
        ],
        required=False,
    )

    strand_col = find_col(
        df,
        ["strand", "direction"],
        required=False,
    )

    source_col = find_col(
        df,
        ["source"],
        required=False,
    )

    out = pd.DataFrame()
    out["gene_id"] = df[gene_col].map(clean_str)
    out["transcript_id"] = df[transcript_col].map(clean_str) if transcript_col else None
    out["chrom"] = df[chrom_col].map(normalize_chrom)

    out["exon_start"] = pd.to_numeric(df[start_col], errors="coerce").astype("Int64")
    out["exon_end"] = pd.to_numeric(df[end_col], errors="coerce").astype("Int64")

    if exon_number_col:
        out["exon_number"] = pd.to_numeric(df[exon_number_col], errors="coerce").astype("Int64")
    else:
        out["exon_number"] = pd.Series([pd.NA] * len(out), dtype="Int64")

    out["strand"] = df[strand_col].map(clean_str) if strand_col else None
    out["source"] = df[source_col].map(clean_str) if source_col else "hg38_refseq_exons.parquet"

    # Drop invalid rows.
    before = len(out)
    out = out.dropna(subset=["gene_id", "chrom", "exon_start", "exon_end"])
    out = out[out["exon_end"] > out["exon_start"]]
    after = len(out)

    if before != after:
        print(f"Dropped {before - after} invalid exon rows.")

    # Convert pandas nullable ints to normal Python values for sqlite.
    out["exon_start"] = out["exon_start"].astype(int)
    out["exon_end"] = out["exon_end"].astype(int)
    out["exon_number"] = out["exon_number"].astype(object).where(out["exon_number"].notna(), None)

    # Create a stable exon_id.
    def make_exon_id(row: pd.Series) -> str:
        tx = row["transcript_id"] or "NA"
        exon_num = row["exon_number"] if row["exon_number"] is not None else "NA"
        return (
            f"{row['gene_id']}|{tx}|exon_{exon_num}|"
            f"{row['chrom']}:{row['exon_start']}-{row['exon_end']}"
        )

    out["exon_id"] = out.apply(make_exon_id, axis=1)

    # Reorder columns.
    out = out[
        [
            "exon_id",
            "gene_id",
            "transcript_id",
            "chrom",
            "exon_start",
            "exon_end",
            "exon_number",
            "strand",
            "source",
        ]
    ]

    # Drop exact duplicates.
    before = len(out)
    out = out.drop_duplicates()
    after = len(out)
    if before != after:
        print(f"Dropped {before - after} duplicate exon rows.")

    print("Normalized exon rows:", len(out))
    return out


def create_schema(conn: sqlite3.Connection, replace: bool = False) -> None:
    """Create exon-related tables."""
    cur = conn.cursor()

    if replace:
        cur.execute("DROP TABLE IF EXISTS gene_exon_regions")
        cur.execute("DROP TABLE IF EXISTS exons")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS exons (
            exon_id TEXT PRIMARY KEY,
            gene_id TEXT NOT NULL,
            transcript_id TEXT,
            chrom TEXT NOT NULL,
            exon_start INTEGER NOT NULL,
            exon_end INTEGER NOT NULL,
            exon_number INTEGER,
            strand TEXT,
            source TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gene_exon_regions (
            region_id TEXT PRIMARY KEY,
            gene_id TEXT NOT NULL,
            chrom TEXT NOT NULL,
            region_start INTEGER NOT NULL,
            region_end INTEGER NOT NULL,
            strand TEXT,
            source TEXT
        );
        """
    )

    conn.commit()


def insert_exons(conn: sqlite3.Connection, exons: pd.DataFrame) -> None:
    """Insert exons into SQLite."""
    rows = list(exons.itertuples(index=False, name=None))

    conn.executemany(
        """
        INSERT OR REPLACE INTO exons (
            exon_id,
            gene_id,
            transcript_id,
            chrom,
            exon_start,
            exon_end,
            exon_number,
            strand,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        rows,
    )
    conn.commit()


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping/adjacent intervals."""
    if not intervals:
        return []

    intervals = sorted(intervals)
    merged = [intervals[0]]

    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def build_gene_exon_regions(conn: sqlite3.Connection, exons: pd.DataFrame) -> None:
    """
    Build merged non-overlapping exon regions per gene/chrom/strand.

    This is useful for default user-facing queries like:
        "SVs in exon regions of DOT1L"

    It avoids duplicate rows from multiple transcripts sharing similar exon intervals.
    """
    region_rows = []

    grouped = exons.groupby(["gene_id", "chrom", "strand"], dropna=False)

    for (gene_id, chrom, strand), group in grouped:
        intervals = list(zip(group["exon_start"].astype(int), group["exon_end"].astype(int)))
        merged = merge_intervals(intervals)

        for idx, (start, end) in enumerate(merged, start=1):
            strand_value = None if pd.isna(strand) else strand
            region_id = f"{gene_id}|merged_exon_region_{idx}|{chrom}:{start}-{end}"
            region_rows.append(
                (
                    region_id,
                    gene_id,
                    chrom,
                    start,
                    end,
                    strand_value,
                    "hg38_refseq_exons_merged",
                )
            )

    conn.execute("DELETE FROM gene_exon_regions;")
    conn.executemany(
        """
        INSERT OR REPLACE INTO gene_exon_regions (
            region_id,
            gene_id,
            chrom,
            region_start,
            region_end,
            strand,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        region_rows,
    )
    conn.commit()

    print("Merged gene exon regions:", len(region_rows))


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create useful indexes for exon lookup and overlap queries."""
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_exons_gene
        ON exons(gene_id);

        CREATE INDEX IF NOT EXISTS idx_exons_transcript
        ON exons(transcript_id);

        CREATE INDEX IF NOT EXISTS idx_exons_chrom_start_end
        ON exons(chrom, exon_start, exon_end);

        CREATE INDEX IF NOT EXISTS idx_gene_exon_regions_gene
        ON gene_exon_regions(gene_id);

        CREATE INDEX IF NOT EXISTS idx_gene_exon_regions_chrom_start_end
        ON gene_exon_regions(chrom, region_start, region_end);

        CREATE INDEX IF NOT EXISTS idx_phenotype_svs_chrom_start_end
        ON phenotype_svs(chrom, start, "end");

        ANALYZE;
        """
    )

    conn.commit()


def sanity_checks(conn: sqlite3.Connection) -> None:
    """Print a few sanity checks."""
    cur = conn.cursor()

    print("\nSanity checks:")

    for table in ["exons", "gene_exon_regions"]:
        count = cur.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
        print(f"  {table}: {count:,} rows")

    dot1l_exons = cur.execute(
        """
        SELECT gene_id, transcript_id, chrom, exon_start, exon_end, exon_number, strand
        FROM exons
        WHERE gene_id = 'DOT1L'
        ORDER BY chrom, exon_start
        LIMIT 10;
        """
    ).fetchall()

    print("\nFirst DOT1L exon rows:")
    for row in dot1l_exons:
        print(" ", row)

    dot1l_regions = cur.execute(
        """
        SELECT gene_id, chrom, region_start, region_end, strand
        FROM gene_exon_regions
        WHERE gene_id = 'DOT1L'
        ORDER BY chrom, region_start
        LIMIT 10;
        """
    ).fetchall()

    print("\nFirst DOT1L merged exon regions:")
    for row in dot1l_regions:
        print(" ", row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exons-parquet",
        default="hg38_refseq_exons.parquet",
        help="Path to hg38 RefSeq exon parquet file.",
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to SQLite database.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop and recreate exons/gene_exon_regions tables.",
    )

    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")

    exons = load_exons_dataframe(args.exons_parquet)

    conn = sqlite3.connect(db_path)
    try:
        create_schema(conn, replace=args.replace)
        insert_exons(conn, exons)
        build_gene_exon_regions(conn, exons)
        create_indexes(conn)
        sanity_checks(conn)
    finally:
        conn.close()

    print("\nDone.")


if __name__ == "__main__":
    main()