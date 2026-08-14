"""Import embryo no-cleft enhancer cCRE BED annotations into cellvar.db.

The source BED is expected to have 11 columns:
chrom, start, end, name, score, strand, thick_start, thick_end, item_rgb,
ccre_type, source.

Only enhancer/promoter-like cCRE classes used by the enhancer notebook are
kept: dELS, pELS, and PLS. Target genes are populated from the 3D chromatin
gene-link file by joining on cCRE ID.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from utils.database import DB_PATH


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BED_PATH = PROJECT_ROOT / "assets" / "embryo.noccl.cCREs.bed"
DEFAULT_LINKS_PATH = PROJECT_ROOT / "assets" / "V4-hg38.Gene-Links.3D-Chromatin.txt"
TABLE_NAME = "noccl_cCREs"
BED_COLUMNS = 11
TARGET_CLASSES = {"dELS", "pELS", "PLS"}


def _int_or_none(value: str):
    value = str(value).strip()
    return int(value) if value else None


def _parse_bed_row(row: list[str], line_number: int) -> tuple:
    if len(row) < BED_COLUMNS:
        raise ValueError(f"Line {line_number} has {len(row)} columns; expected at least {BED_COLUMNS}")
    return (
        row[0],
        _int_or_none(row[1]),
        _int_or_none(row[2]),
        row[3],
        _int_or_none(row[4]),
        row[5],
        _int_or_none(row[6]),
        _int_or_none(row[7]),
        row[8],
        row[9],
        row[10],
        None,
    )


def _create_table(conn: sqlite3.Connection) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            chrom TEXT NOT NULL,
            start INTEGER NOT NULL,
            "end" INTEGER NOT NULL,
            ccre_id TEXT NOT NULL,
            score INTEGER,
            strand TEXT,
            thick_start INTEGER,
            thick_end INTEGER,
            item_rgb TEXT,
            ccre_type TEXT,
            source TEXT,
            targets TEXT
        )
    """)


def _ensure_targets_column(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({TABLE_NAME})")}
    if "targets" not in columns:
        conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN targets TEXT")


def _create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_locus ON {TABLE_NAME}(chrom, start, \"end\")")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_type ON {TABLE_NAME}(ccre_type)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_id ON {TABLE_NAME}(ccre_id)")


def _load_targets_for_ccres(links_path: Path, ccre_ids: set[str]) -> dict[str, str]:
    """Stream the large 3D chromatin link file and collect target genes."""
    if not links_path.is_file():
        raise FileNotFoundError(f"3D chromatin gene-link file not found: {links_path}")

    targets: dict[str, set[str]] = {}
    with links_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) < 3:
                continue
            ccre_id = row[0].strip()
            if ccre_id not in ccre_ids:
                continue
            gene = row[2].strip()
            if gene and gene.upper() != "NA":
                targets.setdefault(ccre_id, set()).add(gene)
    return {ccre_id: ", ".join(sorted(genes)) for ccre_id, genes in targets.items()}


def _populate_targets(conn: sqlite3.Connection, links_path: Path, batch_size: int = 10000) -> int:
    ccre_ids = {
        row[0]
        for row in conn.execute(f"SELECT DISTINCT ccre_id FROM {TABLE_NAME}")
        if row[0]
    }
    if not ccre_ids:
        return 0

    target_map = _load_targets_for_ccres(links_path, ccre_ids)
    conn.execute(f"UPDATE {TABLE_NAME} SET targets = NULL")

    updates = [(targets, ccre_id) for ccre_id, targets in target_map.items()]
    for index in range(0, len(updates), batch_size):
        conn.executemany(
            f"UPDATE {TABLE_NAME} SET targets = ? WHERE ccre_id = ?",
            updates[index:index + batch_size],
        )
    return len(updates)


def update_existing_table(db_path: str, links_path: Path, batch_size: int = 10000) -> tuple[int, int]:
    """Trim existing table to target classes and populate target genes."""
    conn = sqlite3.connect(db_path)
    try:
        _create_table(conn)
        _ensure_targets_column(conn)
        placeholders = ", ".join("?" for _ in TARGET_CLASSES)
        conn.execute(
            f"DELETE FROM {TABLE_NAME} WHERE ccre_type NOT IN ({placeholders})",
            tuple(sorted(TARGET_CLASSES)),
        )
        remaining = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
        targeted = _populate_targets(conn, links_path, batch_size=batch_size)
        _create_indexes(conn)
        conn.commit()
        return int(remaining), int(targeted)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def import_bed(
    db_path: str,
    bed_path: Path,
    links_path: Path,
    replace: bool = True,
    batch_size: int = 10000,
) -> tuple[int, int]:
    if not bed_path.is_file():
        raise FileNotFoundError(f"BED file not found: {bed_path}")

    conn = sqlite3.connect(db_path)
    try:
        _create_table(conn)
        _ensure_targets_column(conn)
        if replace:
            conn.execute(f"DELETE FROM {TABLE_NAME}")

        insert_sql = f"""
            INSERT INTO {TABLE_NAME} (
                chrom, start, "end", ccre_id, score, strand, thick_start,
                thick_end, item_rgb, ccre_type, source, targets
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        imported = 0
        batch = []
        with bed_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle, delimiter="\t")
            for line_number, row in enumerate(reader, start=1):
                if not row or row[0].startswith("#"):
                    continue
                if len(row) >= BED_COLUMNS and row[9] not in TARGET_CLASSES:
                    continue
                batch.append(_parse_bed_row(row, line_number))
                if len(batch) >= batch_size:
                    conn.executemany(insert_sql, batch)
                    imported += len(batch)
                    batch.clear()
            if batch:
                conn.executemany(insert_sql, batch)
                imported += len(batch)

        targeted = _populate_targets(conn, links_path, batch_size=batch_size)
        _create_indexes(conn)
        conn.commit()
        return imported, targeted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import embryo no-cleft cCRE BED annotations into SQLite.")
    parser.add_argument("--db-path", default=DB_PATH, help="SQLite database path")
    parser.add_argument("--bed-path", default=str(DEFAULT_BED_PATH), help="Path to embryo.noccl.cCREs.bed")
    parser.add_argument("--links-path", default=str(DEFAULT_LINKS_PATH), help="Path to V4-hg38.Gene-Links.3D-Chromatin.txt")
    parser.add_argument("--append", action="store_true", help="Append rows instead of replacing the existing table contents")
    parser.add_argument("--update-existing", action="store_true", help="Trim/populate an existing noccl_cCREs table without reimporting the BED")
    parser.add_argument("--batch-size", type=int, default=10000, help="Rows inserted per batch")
    args = parser.parse_args()

    if args.update_existing:
        remaining, targeted = update_existing_table(
            db_path=args.db_path,
            links_path=Path(args.links_path),
            batch_size=args.batch_size,
        )
        print(f"Trimmed {TABLE_NAME} to {remaining:,} enhancer rows")
        print(f"Populated targets for {targeted:,} cCRE IDs")
    else:
        imported, targeted = import_bed(
            db_path=args.db_path,
            bed_path=Path(args.bed_path),
            links_path=Path(args.links_path),
            replace=not args.append,
            batch_size=args.batch_size,
        )
        print(f"Imported {imported:,} enhancer rows into {TABLE_NAME}")
        print(f"Populated targets for {targeted:,} cCRE IDs")


if __name__ == "__main__":
    main()
