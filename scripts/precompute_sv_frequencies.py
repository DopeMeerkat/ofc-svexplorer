"""Precompute SV counts and frequencies directly in the SQLite SV tables.

The existing ``freq`` column is left untouched. New columns are added only when
missing, then populated by SV id using distinct-sample counts.
"""

from __future__ import annotations

import argparse
import sqlite3

from utils.database import DB_PATH


PHENOTYPE_COLUMNS = {
    "count_all": "INTEGER",
    "freq_all": "REAL",
    "count_mother": "INTEGER",
    "freq_mother": "REAL",
    "count_father": "INTEGER",
    "freq_father": "REAL",
    "count_child": "INTEGER",
    "freq_child": "REAL",
}

BACKGROUND_COLUMNS = {
    "count_background": "INTEGER",
    "freq_background": "REAL",
}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _add_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = _columns(conn, table)
    for column, column_type in columns.items():
        if column not in existing:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {column_type}')


def _denominators(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "all": int(conn.execute("SELECT COUNT(DISTINCT bam_id) FROM phenotype").fetchone()[0] or 0),
        "mother": int(conn.execute("SELECT COUNT(DISTINCT bam_id) FROM phenotype WHERE child = 0 AND gender = 'F'").fetchone()[0] or 0),
        "father": int(conn.execute("SELECT COUNT(DISTINCT bam_id) FROM phenotype WHERE child = 0 AND gender = 'M'").fetchone()[0] or 0),
        "child": int(conn.execute("SELECT COUNT(DISTINCT bam_id) FROM phenotype WHERE child = 1").fetchone()[0] or 0),
        "background": int(conn.execute("SELECT COUNT(DISTINCT sample) FROM background_svs").fetchone()[0] or 0),
    }


def _refresh_phenotype_table(conn: sqlite3.Connection, table: str, denominators: dict[str, int]) -> None:
    _add_columns(conn, table, PHENOTYPE_COLUMNS)
    conn.execute("DROP TABLE IF EXISTS temp_sv_frequency")
    conn.execute(f"""
        CREATE TEMP TABLE temp_sv_frequency AS
        SELECT
            ps.id,
            COUNT(DISTINCT ps.sample) AS count_all,
            COUNT(DISTINCT CASE WHEN p.child = 0 AND p.gender = 'F' THEN ps.sample END) AS count_mother,
            COUNT(DISTINCT CASE WHEN p.child = 0 AND p.gender = 'M' THEN ps.sample END) AS count_father,
            COUNT(DISTINCT CASE WHEN p.child = 1 THEN ps.sample END) AS count_child
        FROM "{table}" AS ps
        JOIN phenotype AS p ON p.bam_id = ps.sample
        GROUP BY ps.id
    """)
    conn.execute("CREATE INDEX temp_idx_sv_frequency_id ON temp_sv_frequency(id)")

    all_denom = denominators["all"] or 1
    mother_denom = denominators["mother"] or 1
    father_denom = denominators["father"] or 1
    child_denom = denominators["child"] or 1

    conn.execute(f"""
        UPDATE "{table}"
        SET
            count_all = COALESCE((SELECT count_all FROM temp_sv_frequency WHERE temp_sv_frequency.id = "{table}".id), 0),
            freq_all = COALESCE((SELECT CAST(count_all AS REAL) / ? FROM temp_sv_frequency WHERE temp_sv_frequency.id = "{table}".id), 0),
            count_mother = COALESCE((SELECT count_mother FROM temp_sv_frequency WHERE temp_sv_frequency.id = "{table}".id), 0),
            freq_mother = COALESCE((SELECT CAST(count_mother AS REAL) / ? FROM temp_sv_frequency WHERE temp_sv_frequency.id = "{table}".id), 0),
            count_father = COALESCE((SELECT count_father FROM temp_sv_frequency WHERE temp_sv_frequency.id = "{table}".id), 0),
            freq_father = COALESCE((SELECT CAST(count_father AS REAL) / ? FROM temp_sv_frequency WHERE temp_sv_frequency.id = "{table}".id), 0),
            count_child = COALESCE((SELECT count_child FROM temp_sv_frequency WHERE temp_sv_frequency.id = "{table}".id), 0),
            freq_child = COALESCE((SELECT CAST(count_child AS REAL) / ? FROM temp_sv_frequency WHERE temp_sv_frequency.id = "{table}".id), 0)
    """, (all_denom, mother_denom, father_denom, child_denom))
    conn.execute("DROP TABLE temp_sv_frequency")


def _refresh_background_table(conn: sqlite3.Connection, denominators: dict[str, int]) -> None:
    table = "background_svs"
    _add_columns(conn, table, BACKGROUND_COLUMNS)
    conn.execute("DROP TABLE IF EXISTS temp_background_frequency")
    conn.execute(f"""
        CREATE TEMP TABLE temp_background_frequency AS
        SELECT id, COUNT(DISTINCT sample) AS count_background
        FROM "{table}"
        GROUP BY id
    """)
    conn.execute("CREATE INDEX temp_idx_background_frequency_id ON temp_background_frequency(id)")

    denom = denominators["background"] or 1
    conn.execute(f"""
        UPDATE "{table}"
        SET
            count_background = COALESCE((SELECT count_background FROM temp_background_frequency WHERE temp_background_frequency.id = "{table}".id), 0),
            freq_background = COALESCE((SELECT CAST(count_background AS REAL) / ? FROM temp_background_frequency WHERE temp_background_frequency.id = "{table}".id), 0)
    """, (denom,))
    conn.execute("DROP TABLE temp_background_frequency")


def precompute(db_path: str = DB_PATH) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        denominators = _denominators(conn)
        for table in ("phenotype_svs", "filtered_svs"):
            _refresh_phenotype_table(conn, table, denominators)
        _refresh_background_table(conn, denominators)
        conn.commit()
        return denominators
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute SV frequency columns in SQLite tables.")
    parser.add_argument("--db-path", default=DB_PATH, help="SQLite database path")
    args = parser.parse_args()
    denominators = precompute(args.db_path)
    print("Updated SV frequency columns with denominators:")
    for key, value in denominators.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
