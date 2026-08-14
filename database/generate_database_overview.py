"""Generate cached aggregate metrics for the Database Overview page.

The Dash page reads the files produced here instead of querying the large
SQLite database on each page load. Outputs are aggregate-only and intentionally
avoid sample identifiers.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from utils.database import DB_PATH


OUTPUT_DIR = Path(__file__).resolve().parent

SV_STATISTIC_COLUMNS = [
    ("Total structural variants", "total"),
    ("Deletion", "deletion"),
    ("Duplication", "duplication"),
    ("Insertion", "insertion"),
    ("Inversion", "inversion"),
]


def _read_sql(conn: sqlite3.Connection, query: str, params=None) -> pd.DataFrame:
    if params is None:
        return pd.read_sql_query(query, conn)
    return pd.read_sql_query(query, conn, params=params)


def _write_csv(dataframe: pd.DataFrame, filename: str) -> None:
    dataframe.to_csv(OUTPUT_DIR / filename, index=False)


def _table_counts(conn: sqlite3.Connection) -> pd.DataFrame:
    tables = [
        "phenotype",
        "phenotype_svs",
        "background_svs",
        "structural_variation",
        "single_nucleotide_variation",
        "genes",
        "exons",
        "sv_gene",
        "sv_freqs",
        "reference",
    ]
    rows = []
    for table in tables:
        count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        rows.append({"table": table, "rows": int(count)})
    return pd.DataFrame(rows)


def _cohort_counts(conn: sqlite3.Connection) -> pd.DataFrame:
    return _read_sql(conn, """
        SELECT 'Phenotype' AS category, pheno AS value, COUNT(*) AS samples
        FROM phenotype
        GROUP BY pheno
        UNION ALL
        SELECT 'Child status', CASE child WHEN 1 THEN 'Child' ELSE 'Parent' END, COUNT(*)
        FROM phenotype
        GROUP BY child
        UNION ALL
        SELECT 'Proband status', CASE proband WHEN 1 THEN 'Proband' ELSE 'Non-proband' END, COUNT(*)
        FROM phenotype
        GROUP BY proband
        UNION ALL
        SELECT 'Affected status', CASE affected WHEN 1 THEN 'Affected' ELSE 'Unaffected' END, COUNT(*)
        FROM phenotype
        GROUP BY affected
        UNION ALL
        SELECT 'Gender', gender, COUNT(*)
        FROM phenotype
        GROUP BY gender
        UNION ALL
        SELECT 'Race', race, COUNT(*)
        FROM phenotype
        GROUP BY race
    """)


def _sv_count_statistics(conn: sqlite3.Connection) -> pd.DataFrame:
    per_sample = _read_sql(conn, """
        SELECT
            p.bam_id AS sample,
            COUNT(ps.id) AS total,
            COUNT(CASE WHEN UPPER(TRIM(ps.type)) = 'DEL' THEN 1 END) AS deletion,
            COUNT(CASE WHEN UPPER(TRIM(ps.type)) = 'DUP' THEN 1 END) AS duplication,
            COUNT(CASE WHEN UPPER(TRIM(ps.type)) = 'INS' THEN 1 END) AS insertion,
            COUNT(CASE WHEN UPPER(TRIM(ps.type)) = 'INV' THEN 1 END) AS inversion
        FROM phenotype AS p
        LEFT JOIN phenotype_svs AS ps ON ps.sample = p.bam_id
        GROUP BY p.bam_id
    """)

    rows = []
    for label, column in SV_STATISTIC_COLUMNS:
        values = pd.to_numeric(per_sample[column], errors="coerce").fillna(0)
        rows.append({
            "metric": label,
            "min": int(values.min()),
            "median": round(float(values.median()), 1),
            "max": int(values.max()),
        })
    return pd.DataFrame(rows)


def _sv_type_counts(conn: sqlite3.Connection) -> pd.DataFrame:
    df = _read_sql(conn, """
        SELECT UPPER(TRIM(type)) AS sv_type, COUNT(*) AS structural_variants
        FROM phenotype_svs
        WHERE type IS NOT NULL AND TRIM(type) != ''
        GROUP BY UPPER(TRIM(type))
        ORDER BY structural_variants DESC
    """)
    total = float(df["structural_variants"].sum() or 1)
    df["ratio"] = df["structural_variants"] / total
    return df


def _chromosome_distribution(conn: sqlite3.Connection) -> pd.DataFrame:
    df = _read_sql(conn, """
        SELECT chrom, COUNT(DISTINCT id) AS structural_variants
        FROM phenotype_svs
        WHERE chrom IS NOT NULL AND TRIM(chrom) != ''
        GROUP BY chrom
    """)
    total = float(df["structural_variants"].sum() or 1)
    df["ratio"] = df["structural_variants"] / total
    return df


def _sv_length_bins(conn: sqlite3.Connection) -> pd.DataFrame:
    return _read_sql(conn, """
        SELECT
            CASE
                WHEN ABS(CAST(length AS REAL)) <= 50 THEN '0-50 bp'
                WHEN ABS(CAST(length AS REAL)) <= 100 THEN '51-100 bp'
                WHEN ABS(CAST(length AS REAL)) <= 1000 THEN '101 bp-1 kb'
                WHEN ABS(CAST(length AS REAL)) <= 10000 THEN '1-10 kb'
                WHEN ABS(CAST(length AS REAL)) <= 100000 THEN '10-100 kb'
                WHEN ABS(CAST(length AS REAL)) <= 1000000 THEN '100 kb-1 Mb'
                ELSE '>1 Mb'
            END AS length_bin,
            COUNT(*) AS structural_variants
        FROM phenotype_svs
        WHERE length IS NOT NULL
        GROUP BY length_bin
    """)


def _gene_exon_by_chromosome(conn: sqlite3.Connection) -> pd.DataFrame:
    return _read_sql(conn, """
        WITH gene_counts AS (
            SELECT chrom, COUNT(*) AS genes
            FROM genes
            WHERE chrom IS NOT NULL AND TRIM(chrom) != ''
            GROUP BY chrom
        ), exon_counts AS (
            SELECT chrom, COUNT(*) AS exons
            FROM exons
            WHERE chrom IS NOT NULL AND TRIM(chrom) != ''
            GROUP BY chrom
        )
        SELECT
            COALESCE(gene_counts.chrom, exon_counts.chrom) AS chrom,
            COALESCE(genes, 0) AS genes,
            COALESCE(exons, 0) AS exons
        FROM gene_counts
        LEFT JOIN exon_counts ON exon_counts.chrom = gene_counts.chrom
        UNION
        SELECT
            exon_counts.chrom,
            COALESCE(genes, 0) AS genes,
            COALESCE(exons, 0) AS exons
        FROM exon_counts
        LEFT JOIN gene_counts ON gene_counts.chrom = exon_counts.chrom
        WHERE gene_counts.chrom IS NULL
    """)


def _sv_gene_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    rows = [
        {
            "metric": "SV-gene overlap records",
            "value": int(conn.execute("SELECT COUNT(*) FROM sv_gene").fetchone()[0]),
        },
        {
            "metric": "Distinct SVs with gene overlap",
            "value": int(conn.execute("SELECT COUNT(DISTINCT sv_id) FROM sv_gene").fetchone()[0]),
        },
        {
            "metric": "Distinct genes overlapped by SVs",
            "value": int(conn.execute("SELECT COUNT(DISTINCT gene_id) FROM sv_gene").fetchone()[0]),
        },
    ]
    return pd.DataFrame(rows)


_SV_GENE_ANNOTATION_COLUMNS = [
    "annotation",
    "overlap_records",
    "distinct_sv_gene_pairs",
    "distinct_svs",
    "distinct_genes",
    "distinct_annotation_records",
]

_ENHANCER_CELLS = ("MESENCHYMAL", "NEURALCREST")


def _exon_distinct_expr(alias: str) -> str:
    return f"{alias}.gene_id || '|' || {alias}.chrom || '|' || {alias}.exon_start || '|' || {alias}.exon_end"


def _interval_distinct_expr(alias: str) -> str:
    return f"{alias}.chrom || '|' || {alias}.start || '|' || {alias}.\"end\""


def _overlap_counts_by_group(left, right, group_col, left_start, left_end, right_start, right_end):
    """Return per-row interval-overlap counts for two grouped dataframes."""
    left_counts = np.zeros(len(left), dtype=np.int64)
    right_counts = np.zeros(len(right), dtype=np.int64)
    if left.empty or right.empty:
        return left_counts, right_counts

    right_groups = right.groupby(group_col, sort=False).groups
    for group, left_index in left.groupby(group_col, sort=False).groups.items():
        right_index = right_groups.get(group)
        if right_index is None:
            continue

        left_positions = np.asarray(left_index, dtype=np.int64)
        right_positions = np.asarray(right_index, dtype=np.int64)
        left_subset = left.iloc[left_positions]
        right_subset = right.iloc[right_positions]

        right_starts = np.sort(right_subset[right_start].to_numpy(dtype=np.int64))
        right_ends = np.sort(right_subset[right_end].to_numpy(dtype=np.int64))
        left_starts = left_subset[left_start].to_numpy(dtype=np.int64)
        left_ends = left_subset[left_end].to_numpy(dtype=np.int64)
        left_counts[left_positions] = (
            np.searchsorted(right_starts, left_ends, side="right")
            - np.searchsorted(right_ends, left_starts, side="left")
        )

        left_starts_sorted = np.sort(left_starts)
        left_ends_sorted = np.sort(left_ends)
        right_starts_values = right_subset[right_start].to_numpy(dtype=np.int64)
        right_ends_values = right_subset[right_end].to_numpy(dtype=np.int64)
        right_counts[right_positions] = (
            np.searchsorted(left_starts_sorted, right_ends_values, side="right")
            - np.searchsorted(left_ends_sorted, right_starts_values, side="left")
        )

    return left_counts, right_counts


def _coerce_interval_columns(frame, columns):
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(-1).astype(np.int64)
    return frame


def _load_overlap_tables(conn: sqlite3.Connection):
    tables = {
        "sv_gene": _read_sql(conn, """
            SELECT sv_id, gene_id, chrom, sv_start, sv_end
            FROM sv_gene
            WHERE sv_id IS NOT NULL AND gene_id IS NOT NULL AND chrom IS NOT NULL
              AND sv_start IS NOT NULL AND sv_end IS NOT NULL
        """),
        "exons": _read_sql(conn, """
            SELECT gene_id, chrom, exon_start, exon_end
            FROM exons
            WHERE gene_id IS NOT NULL AND chrom IS NOT NULL
              AND exon_start IS NOT NULL AND exon_end IS NOT NULL
        """),
        "active_enhancer_candidates": _read_sql(conn, f"""
            SELECT cell, chrom, start, "end" AS end
            FROM active_enhancer_candidates
            WHERE chrom IS NOT NULL AND start IS NOT NULL AND "end" IS NOT NULL
              AND cell IN ({", ".join("?" * len(_ENHANCER_CELLS))})
        """, list(_ENHANCER_CELLS)),
        "promoter_candidates": _read_sql(conn, """
            SELECT chrom, start, "end" AS end
            FROM promoter_candidates
            WHERE chrom IS NOT NULL AND start IS NOT NULL AND "end" IS NOT NULL
        """),
        "insulator_candidates": _read_sql(conn, """
            SELECT chrom, start, "end" AS end
            FROM insulator_candidates
            WHERE chrom IS NOT NULL AND start IS NOT NULL AND "end" IS NOT NULL
        """),
        "noccl_cCREs": _read_sql(conn, """
            SELECT chrom, start, "end" AS end
            FROM noccl_cCREs
            WHERE chrom IS NOT NULL AND start IS NOT NULL AND "end" IS NOT NULL
        """),
        "genes": _read_sql(conn, """
            SELECT id, chrom, x1, x2
            FROM genes
            WHERE id IS NOT NULL AND chrom IS NOT NULL AND x1 IS NOT NULL AND x2 IS NOT NULL
        """),
        "phenotype_svs": _read_sql(conn, """
            SELECT DISTINCT id, chrom, start, "end" AS end
            FROM phenotype_svs
            WHERE id IS NOT NULL AND chrom IS NOT NULL AND start IS NOT NULL AND "end" IS NOT NULL
        """),
    }

    _coerce_interval_columns(tables["sv_gene"], ["sv_start", "sv_end"])
    _coerce_interval_columns(tables["exons"], ["exon_start", "exon_end"])
    _coerce_interval_columns(tables["genes"], ["x1", "x2"])
    _coerce_interval_columns(tables["phenotype_svs"], ["start", "end"])
    for name in ["active_enhancer_candidates", "promoter_candidates", "insulator_candidates", "noccl_cCREs"]:
        _coerce_interval_columns(tables[name], ["start", "end"])

    tables["sv_gene"]["gene_chrom_key"] = tables["sv_gene"]["gene_id"].astype(str) + "|" + tables["sv_gene"]["chrom"].astype(str)
    tables["exons"]["gene_chrom_key"] = tables["exons"]["gene_id"].astype(str) + "|" + tables["exons"]["chrom"].astype(str)
    tables["genes"]["gene_chrom_key"] = tables["genes"]["id"].astype(str) + "|" + tables["genes"]["chrom"].astype(str)
    for name in tables:
        tables[name] = tables[name].reset_index(drop=True)
    return tables


def _sv_gene_annotation_row(label, sv_gene, annotation):
    left_counts, right_counts = _overlap_counts_by_group(
        sv_gene, annotation, "chrom", "sv_start", "sv_end", "start", "end"
    )
    hit_sv_gene = sv_gene[left_counts > 0]
    hit_annotation = annotation[right_counts > 0]
    return {
        "annotation": label,
        "overlap_records": int(left_counts.sum()),
        "distinct_sv_gene_pairs": int(hit_sv_gene[["sv_id", "gene_id"]].drop_duplicates().shape[0]),
        "distinct_svs": int(hit_sv_gene["sv_id"].nunique()),
        "distinct_genes": int(hit_sv_gene["gene_id"].nunique()),
        "distinct_annotation_records": int(hit_annotation[["chrom", "start", "end"]].drop_duplicates().shape[0]),
    }


def _gene_annotation_row(label, genes, annotation):
    left_counts, right_counts = _overlap_counts_by_group(
        genes, annotation, "chrom", "x1", "x2", "start", "end"
    )
    hit_genes = genes[left_counts > 0]
    hit_annotation = annotation[right_counts > 0]
    return {
        "annotation": label,
        "overlap_records": int(left_counts.sum()),
        "distinct_genes": int(hit_genes["id"].nunique()),
        "distinct_annotation_records": int(hit_annotation[["chrom", "start", "end"]].drop_duplicates().shape[0]),
    }


def _sv_gene_annotation_overlap(tables) -> pd.DataFrame:
    """Count SV-gene pairs whose SV interval overlaps each annotation class.

    Exons additionally require the exon to belong to the paired gene. Enhancer
    candidates are limited to the OFC-relevant MESENCHYMAL/NEURALCREST cells
    (the active enhancer table is already trimmed to those cells).
    """
    sv_gene = tables["sv_gene"]
    exons = tables["exons"]
    exon_left_counts, exon_right_counts = _overlap_counts_by_group(
        sv_gene, exons, "gene_chrom_key", "sv_start", "sv_end", "exon_start", "exon_end"
    )
    hit_exon_sv_gene = sv_gene[exon_left_counts > 0]
    hit_exons = exons[exon_right_counts > 0]

    rows = [
        {
            "annotation": "Exons",
            "overlap_records": int(exon_left_counts.sum()),
            "distinct_sv_gene_pairs": int(hit_exon_sv_gene[["sv_id", "gene_id"]].drop_duplicates().shape[0]),
            "distinct_svs": int(hit_exon_sv_gene["sv_id"].nunique()),
            "distinct_genes": int(hit_exon_sv_gene["gene_id"].nunique()),
            "distinct_annotation_records": int(hit_exons[["gene_id", "chrom", "exon_start", "exon_end"]].drop_duplicates().shape[0]),
        },
        _sv_gene_annotation_row("Active enhancers", sv_gene, tables["active_enhancer_candidates"]),
        _sv_gene_annotation_row("Promoters", sv_gene, tables["promoter_candidates"]),
        _sv_gene_annotation_row("Insulators", sv_gene, tables["insulator_candidates"]),
        _sv_gene_annotation_row("No-cleft embryo cCREs", sv_gene, tables["noccl_cCREs"]),
    ]
    result = pd.DataFrame(rows)
    return result[_SV_GENE_ANNOTATION_COLUMNS]


def _gene_annotation_overlap(tables) -> pd.DataFrame:
    """Count gene intervals that overlap each annotation class.

    Exons additionally require the exon to belong to the gene (gene_id match).
    Enhancer candidates are limited to the OFC-relevant enhancer cells.
    """
    genes = tables["genes"]
    exons = tables["exons"]
    exon_left_counts, exon_right_counts = _overlap_counts_by_group(
        genes, exons, "gene_chrom_key", "x1", "x2", "exon_start", "exon_end"
    )
    hit_exon_genes = genes[exon_left_counts > 0]
    hit_exons = exons[exon_right_counts > 0]

    rows = [
        {
            "annotation": "Exons",
            "overlap_records": int(exon_left_counts.sum()),
            "distinct_genes": int(hit_exon_genes["id"].nunique()),
            "distinct_annotation_records": int(hit_exons[["gene_id", "chrom", "exon_start", "exon_end"]].drop_duplicates().shape[0]),
        },
        _gene_annotation_row("Active enhancers", genes, tables["active_enhancer_candidates"]),
        _gene_annotation_row("Promoters", genes, tables["promoter_candidates"]),
        _gene_annotation_row("Insulators", genes, tables["insulator_candidates"]),
        _gene_annotation_row("No-cleft embryo cCREs", genes, tables["noccl_cCREs"]),
    ]
    result = pd.DataFrame(rows)
    return result[
        ["annotation", "overlap_records", "distinct_genes", "distinct_annotation_records"]
    ]


def _individual_group_counts(conn: sqlite3.Connection) -> pd.DataFrame:
    """Individual counts for Background, Parents, and Children."""
    background = int(conn.execute("SELECT COUNT(DISTINCT sample) FROM background_svs").fetchone()[0])
    parents = int(conn.execute("SELECT COUNT(*) FROM phenotype WHERE child = 0").fetchone()[0])
    children = int(conn.execute("SELECT COUNT(*) FROM phenotype WHERE child = 1").fetchone()[0])
    df = pd.DataFrame([
        {"group": "Background", "count": background},
        {"group": "Parents", "count": parents},
        {"group": "Children", "count": children},
    ])
    total = float(df["count"].sum() or 1)
    df["ratio"] = df["count"] / total
    return df


def _individual_sv_counts(conn: sqlite3.Connection) -> pd.DataFrame:
    """Total SV rows for Background, Parents, and Children."""
    background = int(conn.execute("SELECT COUNT(*) FROM background_svs").fetchone()[0])
    parents = int(conn.execute("""
        SELECT COUNT(*)
        FROM phenotype_svs AS ps
        JOIN phenotype AS p ON p.bam_id = ps.sample
        WHERE p.child = 0
    """).fetchone()[0])
    children = int(conn.execute("""
        SELECT COUNT(*)
        FROM phenotype_svs AS ps
        JOIN phenotype AS p ON p.bam_id = ps.sample
        WHERE p.child = 1
    """).fetchone()[0])
    background_samples = int(conn.execute("SELECT COUNT(DISTINCT sample) FROM background_svs").fetchone()[0] or 0)
    parent_samples = int(conn.execute("SELECT COUNT(*) FROM phenotype WHERE child = 0").fetchone()[0] or 0)
    child_samples = int(conn.execute("SELECT COUNT(*) FROM phenotype WHERE child = 1").fetchone()[0] or 0)
    df = pd.DataFrame([
        {"group": "Background", "count": background, "samples": background_samples},
        {"group": "Parents", "count": parents, "samples": parent_samples},
        {"group": "Children", "count": children, "samples": child_samples},
    ])
    df["svs_per_sample"] = df.apply(lambda row: row["count"] / row["samples"] if row["samples"] else 0, axis=1)
    return df


def _phenotype_distribution(conn: sqlite3.Connection) -> pd.DataFrame:
    """Individual counts per phenotype label."""
    df = _read_sql(conn, """
        SELECT pheno AS phenotype, COUNT(*) AS count
        FROM phenotype
        WHERE pheno IS NOT NULL AND TRIM(pheno) != ''
        GROUP BY pheno
        ORDER BY count DESC
    """)
    total = float(df["count"].sum() or 1)
    df["ratio"] = df["count"] / total
    return df


def _distinct_svs_overlapping(svs, annotation, right_start, right_end):
    """Count distinct SV ids in `svs` whose interval overlaps any annotation interval."""
    left_counts, _ = _overlap_counts_by_group(
        svs, annotation, "chrom", "start", "end", right_start, right_end
    )
    return int(svs.loc[left_counts > 0, "id"].nunique())


def _sv_region_counts(tables) -> pd.DataFrame:
    """Where SVs occur: Exonic, Intronic, Promoter, Enhancer, Insulator, Intergenic.

    Exonic counts distinct SVs overlapping any exon. Intronic is the count of
    gene-overlapping SVs that do not fall in exonic regions (sv_gene minus
    exonic). Promoter/Enhancer/Insulator count distinct SVs overlapping those
    candidate tables (enhancers use MESENCHYMAL/NEURALCREST only). Intergenic
    is the count of SVs with no gene overlap at all.
    """
    svs = tables["phenotype_svs"]
    total_svs = int(svs["id"].nunique())

    exonic = _distinct_svs_overlapping(svs, tables["exons"], "exon_start", "exon_end")
    promoter = _distinct_svs_overlapping(svs, tables["promoter_candidates"], "start", "end")
    enhancer = _distinct_svs_overlapping(svs, tables["active_enhancer_candidates"], "start", "end")
    insulator = _distinct_svs_overlapping(svs, tables["insulator_candidates"], "start", "end")

    genic = set(tables["sv_gene"]["sv_id"].unique())
    genic_count = int(svs.loc[svs["id"].isin(genic), "id"].nunique())
    intronic = genic_count - exonic
    intergenic = total_svs - genic_count

    rows = [
        {"region": "Exonic", "sv_count": exonic},
        {"region": "Intronic", "sv_count": intronic},
        {"region": "Promoter", "sv_count": promoter},
        {"region": "Enhancer", "sv_count": enhancer},
        {"region": "Insulator", "sv_count": insulator},
        {"region": "Intergenic", "sv_count": intergenic},
    ]
    df = pd.DataFrame(rows)
    df["ratio"] = df["sv_count"] / float(total_svs or 1)
    return df


def _add_overlap_ratios(sv_gene_overlap, gene_overlap, tables):
    unique_svs = float(tables["phenotype_svs"]["id"].nunique() or 1)
    annotated_genes = float(tables["genes"]["id"].nunique() or 1)
    feature_totals = {
        "Exons": float(tables["exons"][["gene_id", "chrom", "exon_start", "exon_end"]].drop_duplicates().shape[0] or 1),
        "Active enhancers": float(tables["active_enhancer_candidates"][["chrom", "start", "end"]].drop_duplicates().shape[0] or 1),
        "Promoters": float(tables["promoter_candidates"][["chrom", "start", "end"]].drop_duplicates().shape[0] or 1),
        "Insulators": float(tables["insulator_candidates"][["chrom", "start", "end"]].drop_duplicates().shape[0] or 1),
        "No-cleft embryo cCREs": float(tables["noccl_cCREs"][["chrom", "start", "end"]].drop_duplicates().shape[0] or 1),
    }

    sv_gene_overlap = sv_gene_overlap.copy()
    sv_gene_overlap["pct_unique_svs"] = sv_gene_overlap["distinct_svs"] / unique_svs
    sv_gene_overlap["pct_annotated_genes"] = sv_gene_overlap["distinct_genes"] / annotated_genes

    gene_overlap = gene_overlap.copy()
    gene_overlap["pct_annotated_genes"] = gene_overlap["distinct_genes"] / annotated_genes
    gene_overlap["pct_genomic_feature_records"] = gene_overlap.apply(
        lambda row: row["distinct_annotation_records"] / feature_totals.get(row["annotation"], 1),
        axis=1,
    )
    return sv_gene_overlap, gene_overlap


def generate(db_path: str = DB_PATH) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        table_counts = _table_counts(conn)
        cohort_counts = _cohort_counts(conn)
        sv_count_statistics = _sv_count_statistics(conn)
        sv_type_counts = _sv_type_counts(conn)
        chromosome_distribution = _chromosome_distribution(conn)
        sv_length_bins = _sv_length_bins(conn)
        gene_exon_by_chromosome = _gene_exon_by_chromosome(conn)
        sv_gene_summary = _sv_gene_summary(conn)
        overlap_tables = _load_overlap_tables(conn)
        sv_gene_annotation_overlap = _sv_gene_annotation_overlap(overlap_tables)
        gene_annotation_overlap = _gene_annotation_overlap(overlap_tables)
        sv_gene_annotation_overlap, gene_annotation_overlap = _add_overlap_ratios(
            sv_gene_annotation_overlap, gene_annotation_overlap, overlap_tables
        )
        individual_group_counts = _individual_group_counts(conn)
        individual_sv_counts = _individual_sv_counts(conn)
        phenotype_distribution = _phenotype_distribution(conn)
        sv_region_counts = _sv_region_counts(overlap_tables)

        _write_csv(table_counts, "table_counts.csv")
        _write_csv(cohort_counts, "cohort_counts.csv")
        _write_csv(sv_count_statistics, "sv_count_statistics.csv")
        _write_csv(sv_type_counts, "sv_type_counts.csv")
        _write_csv(chromosome_distribution, "chromosome_distribution.csv")
        _write_csv(sv_length_bins, "sv_length_bins.csv")
        _write_csv(gene_exon_by_chromosome, "gene_exon_by_chromosome.csv")
        _write_csv(sv_gene_summary, "sv_gene_summary.csv")
        _write_csv(sv_gene_annotation_overlap, "sv_gene_annotation_overlap.csv")
        _write_csv(gene_annotation_overlap, "gene_annotation_overlap.csv")
        _write_csv(individual_group_counts, "individual_group_counts.csv")
        _write_csv(individual_sv_counts, "individual_sv_counts.csv")
        _write_csv(phenotype_distribution, "phenotype_distribution.csv")
        _write_csv(sv_region_counts, "sv_region_counts.csv")

        individuals = int(conn.execute("SELECT COUNT(*) FROM phenotype").fetchone()[0])
        families = int(conn.execute("SELECT COUNT(DISTINCT family_id) FROM phenotype").fetchone()[0])
        affected_cases = int(conn.execute("SELECT COUNT(*) FROM phenotype WHERE affected = 1").fetchone()[0])
        parents = int(conn.execute("SELECT COUNT(*) FROM phenotype WHERE child = 0").fetchone()[0])
        background_controls = int(conn.execute("SELECT COUNT(DISTINCT sample) FROM background_svs").fetchone()[0])
        unique_svs = int(conn.execute("SELECT COUNT(DISTINCT id) FROM phenotype_svs").fetchone()[0])
        annotated_genes = int(conn.execute("SELECT COUNT(*) FROM genes").fetchone()[0])
        regulatory_elements = sum(
            int(conn.execute(f'SELECT COUNT(DISTINCT chrom || "|" || start || "|" || "end") FROM "{table}"').fetchone()[0])
            for table in ["active_enhancer_candidates", "promoter_candidates", "insulator_candidates", "noccl_cCREs"]
        )
        summary = {
            "family_count": families,
            "individual_count": individuals,
            "affected_case_count": affected_cases,
            "parent_count": parents,
            "background_control_count": background_controls,
            "unique_phenotype_svs": unique_svs,
            "annotated_gene_count": annotated_genes,
            "regulatory_element_count": regulatory_elements,
        }
        (OUTPUT_DIR / "overview_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cached Database Overview metrics.")
    parser.add_argument("--db-path", default=DB_PATH, help="SQLite database path")
    args = parser.parse_args()
    generate(args.db_path)


if __name__ == "__main__":
    main()
