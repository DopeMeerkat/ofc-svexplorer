#!/usr/bin/env python3
"""
Extract low-frequency structural variants from the CellVar SQLite database.

Output CSV format:
    id,type,chrom,start,end

Default behavior:
    - Reads from /data/cellvar.db/cellvar.db
    - Uses both phenotype_svs and background_svs
    - Keeps SVs where freq < 0.02
    - De-duplicates repeated sample-level rows into one row per SV interval

Examples:
    python extract_low_freq_svs.py
    python extract_low_freq_svs.py --output low_freq_svs.csv
    python extract_low_freq_svs.py --table phenotype_svs --output low_freq_phenotype_svs.csv
    python extract_low_freq_svs.py --max-freq 0.01 --output low_freq_svs_001.csv
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd


DEFAULT_DB_PATH = "/data/cellvar.db/cellvar.db"
DEFAULT_OUTPUT = "low_freq_svs.csv"
VALID_TABLES = {"phenotype_svs", "background_svs", "both"}
OUTPUT_COLUMNS = ["id", "type", "chrom", "start", "end"]


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Return True if table_name exists in the SQLite database."""
    query = """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
    """
    return conn.execute(query, (table_name,)).fetchone() is not None


def build_query(table_mode: str, max_freq: float) -> tuple[str, tuple]:
    """
    Build SQL query and parameters.

    SQLite allows a column named end, but because it can be awkward in SQL,
    the query quotes it as "end".
    """
    per_table_query = """
        SELECT DISTINCT
            id,
            type,
            chrom,
            start,
            "end" AS "end"
        FROM {table_name}
        WHERE freq IS NOT NULL
          AND CAST(freq AS REAL) < ?
    """

    if table_mode == "both":
        query = f"""
            SELECT DISTINCT id, type, chrom, start, "end"
            FROM (
                {per_table_query.format(table_name="phenotype_svs")}
                UNION
                {per_table_query.format(table_name="background_svs")}
            )
            ORDER BY
                CASE
                    WHEN chrom = 'chrX' THEN 23
                    WHEN chrom = 'chrY' THEN 24
                    WHEN chrom = 'chrM' THEN 25
                    WHEN chrom GLOB 'chr[0-9]*' THEN CAST(SUBSTR(chrom, 4) AS INTEGER)
                    ELSE 999
                END,
                chrom,
                start,
                "end",
                id
        """
        params = (max_freq, max_freq)
    else:
        query = f"""
            {per_table_query.format(table_name=table_mode)}
            ORDER BY
                CASE
                    WHEN chrom = 'chrX' THEN 23
                    WHEN chrom = 'chrY' THEN 24
                    WHEN chrom = 'chrM' THEN 25
                    WHEN chrom GLOB 'chr[0-9]*' THEN CAST(SUBSTR(chrom, 4) AS INTEGER)
                    ELSE 999
                END,
                chrom,
                start,
                "end",
                id
        """
        params = (max_freq,)

    return query, params


def extract_low_freq_svs(
    db_path: str,
    output_path: str,
    max_freq: float,
    table_mode: str,
) -> None:
    db = Path(db_path)
    if not db.exists():
        print(f"ERROR: database not found: {db}", file=sys.stderr)
        sys.exit(1)

    if table_mode not in VALID_TABLES:
        print(
            f"ERROR: --table must be one of: {', '.join(sorted(VALID_TABLES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        needed_tables = ["phenotype_svs", "background_svs"] if table_mode == "both" else [table_mode]
        missing = [name for name in needed_tables if not table_exists(conn, name)]
        if missing:
            print(f"ERROR: missing table(s): {', '.join(missing)}", file=sys.stderr)
            sys.exit(1)

        query, params = build_query(table_mode, max_freq)
        df = pd.read_sql_query(query, conn, params=params)

    # Guarantee exact output column order and no extra columns.
    df = df[OUTPUT_COLUMNS]

    # Defensive cleanup in case equivalent rows came through with odd typing.
    df["start"] = df["start"].astype(int)
    df["end"] = df["end"].astype(int)
    df = df.drop_duplicates(subset=OUTPUT_COLUMNS)

    df.to_csv(output_path, index=False)
    print(f"Wrote {len(df):,} unique SVs with freq < {max_freq:g} to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract SVs with freq less than a threshold from the CellVar SQLite database."
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database. Default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=0.02,
        help="Frequency cutoff. Keeps rows where freq < this value. Default: 0.02",
    )
    parser.add_argument(
        "--table",
        choices=sorted(VALID_TABLES),
        default="both",
        help="Which SV table to read from. Default: both",
    )

    args = parser.parse_args()
    extract_low_freq_svs(
        db_path=args.db,
        output_path=args.output,
        max_freq=args.max_freq,
        table_mode=args.table,
    )


if __name__ == "__main__":
    main()
