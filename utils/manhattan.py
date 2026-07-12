#!/usr/bin/env python3

"""
Generate Manhattan-like plot from two-hit pair p-value table.

Expected p-value input columns from previous script:
    event_group,item_1,item_2,p_value,fdr_bh,bonferroni,...

For gene pairs:
    item_1 and item_2 are gene names from genes.id

For SV pairs:
    item_1 and item_2 are SV IDs from phenotype_svs/background_svs

Example usage for gene pairs:
    python plot_two_hit_manhattan.py \
        --input two_hit_gene_pair_pvalues.csv \
        --output two_hit_gene_pair_manhattan.png \
        --db-path /data/cellvar.db/cellvar.db \
        --kind gene \
        --p-col p_value \
        --title "Two-hit gene-pair Manhattan plot"

Example usage for SV pairs:
    python plot_two_hit_manhattan.py \
        --input two_hit_sv_pair_pvalues.csv \
        --output two_hit_sv_pair_manhattan.png \
        --db-path /data/cellvar.db/cellvar.db \
        --kind sv \
        --p-col p_value \
        --cohort combined \
        --title "Two-hit SV-pair Manhattan plot"

Hover support:
    Install mplcursors:
        pip install mplcursors

    Then run with:
        python plot_two_hit_manhattan.py ... --show
"""

from __future__ import annotations

import argparse
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_DB_PATH = "/data/cellvar.db/cellvar.db"


CHROM_ORDER = {
    **{f"chr{i}": i for i in range(1, 23)},
    "chrX": 23,
    "chrY": 24,
    "chrM": 25,
    "chrMT": 25,
}


def chrom_sort_key(chrom: str) -> tuple[int, str]:
    return (CHROM_ORDER.get(chrom, 999), chrom)


def connect_readonly(db_path: str) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def clean_item_id(value) -> str:
    return str(value).strip()


def split_event_group(value: str) -> tuple[str, str] | tuple[None, None]:
    """
    Fallback if item_1/item_2 columns are missing.
    Assumes event_group looks like:
        KCNK12, DGKB
        C_1000, C_2501
    """
    if pd.isna(value):
        return None, None

    parts = [x.strip() for x in str(value).split(",") if x.strip()]
    if len(parts) < 2:
        return None, None

    return parts[0], parts[1]


def load_gene_locations(conn: sqlite3.Connection, gene_ids: set[str]) -> pd.DataFrame:
    """
    Look up gene coordinates from genes table.

    genes schema:
        id, chrom, x1, x2, length, strand
    """
    if not gene_ids:
        return pd.DataFrame(columns=["item", "chrom", "start", "end"])

    placeholders = ",".join("?" for _ in gene_ids)

    query = f"""
        SELECT
            id AS item,
            chrom,
            CAST(x1 AS INTEGER) AS start,
            CAST(x2 AS INTEGER) AS end
        FROM genes
        WHERE id IN ({placeholders})
          AND chrom IS NOT NULL
          AND x1 IS NOT NULL
          AND x2 IS NOT NULL
    """

    df = pd.read_sql_query(query, conn, params=list(gene_ids))

    # If duplicate gene rows exist, collapse to one span per gene.
    if not df.empty:
        df = (
            df.groupby(["item", "chrom"], as_index=False)
              .agg(start=("start", "min"), end=("end", "max"))
        )

        # If same gene appears on multiple chromosomes, keep the first by chrom order.
        df["chrom_rank"] = df["chrom"].map(lambda c: chrom_sort_key(c)[0])
        df = (
            df.sort_values(["item", "chrom_rank", "start"])
              .drop_duplicates("item", keep="first")
              .drop(columns=["chrom_rank"])
        )

    return df


def load_sv_locations(
    conn: sqlite3.Connection,
    sv_ids: set[str],
    cohort: str,
) -> pd.DataFrame:
    """
    Look up SV coordinates from phenotype_svs and/or background_svs.

    Returns one row per SV ID.
    """
    if not sv_ids:
        return pd.DataFrame(columns=["item", "chrom", "start", "end", "type", "freq"])

    tables = []

    if cohort in {"kidsfirst", "combined"}:
        tables.append("phenotype_svs")

    if cohort in {"background", "combined"}:
        tables.append("background_svs")

    dfs = []

    for table in tables:
        placeholders = ",".join("?" for _ in sv_ids)

        query = f"""
            SELECT
                id AS item,
                type,
                chrom,
                CAST(start AS INTEGER) AS start,
                CAST("end" AS INTEGER) AS end,
                CAST(freq AS REAL) AS freq
            FROM {table}
            WHERE id IN ({placeholders})
              AND chrom IS NOT NULL
              AND start IS NOT NULL
              AND "end" IS NOT NULL
        """

        dfs.append(pd.read_sql_query(query, conn, params=list(sv_ids)))

    if not dfs:
        return pd.DataFrame(columns=["item", "chrom", "start", "end", "type", "freq"])

    df = pd.concat(dfs, ignore_index=True)

    if df.empty:
        return df

    # Same SV ID can appear in many samples, so collapse to one SV coordinate.
    df = (
        df.groupby(["item", "type", "chrom"], as_index=False)
          .agg(
              start=("start", "min"),
              end=("end", "max"),
              freq=("freq", "min"),
          )
    )

    # If same SV ID appears in multiple coordinate forms, keep first by chrom/start.
    df["chrom_rank"] = df["chrom"].map(lambda c: chrom_sort_key(c)[0])
    df = (
        df.sort_values(["item", "chrom_rank", "start", "end"])
          .drop_duplicates("item", keep="first")
          .drop(columns=["chrom_rank"])
    )

    return df


def build_chrom_offsets(location_df: pd.DataFrame) -> tuple[dict[str, int], dict[str, float]]:
    """
    Build cumulative chromosome offsets from the max coordinate observed per chromosome.

    This avoids needing a separate chromosome-size file.
    """
    chrom_max = (
        location_df.groupby("chrom")["end"]
        .max()
        .reset_index()
        .sort_values("chrom", key=lambda s: s.map(chrom_sort_key))
    )

    offsets = {}
    centers = {}
    current = 0

    for _, row in chrom_max.iterrows():
        chrom = row["chrom"]
        max_end = int(row["end"])

        offsets[chrom] = current
        centers[chrom] = current + max_end / 2

        # Add a small spacer between chromosomes.
        current += max_end + 5_000_000

    return offsets, centers


def prepare_plot_points(
    pval_df: pd.DataFrame,
    loc_df: pd.DataFrame,
    p_col: str,
) -> pd.DataFrame:
    """
    Turn pair-level p-value table into item-level plotting points.

    Each pair creates two rows:
        one for item_1
        one for item_2
    """
    loc_map = loc_df.set_index("item").to_dict(orient="index")

    points = []

    for _, row in pval_df.iterrows():
        event_group = row.get("event_group", "")

        item_1 = row.get("item_1", None)
        item_2 = row.get("item_2", None)

        if pd.isna(item_1) or pd.isna(item_2):
            item_1, item_2 = split_event_group(event_group)

        if item_1 is None or item_2 is None:
            continue

        item_1 = clean_item_id(item_1)
        item_2 = clean_item_id(item_2)

        p = row.get(p_col, np.nan)

        if pd.isna(p):
            continue

        p = float(p)

        # Avoid infinite -log10 if p is exactly 0.
        if p <= 0:
            p = np.nextafter(0, 1)

        neg_log10_p = -math.log10(p)

        for plotted_item, partner_item in [(item_1, item_2), (item_2, item_1)]:
            if plotted_item not in loc_map:
                continue

            loc = loc_map[plotted_item]

            start = int(loc["start"])
            end = int(loc["end"])
            midpoint = (start + end) / 2

            points.append(
                {
                    "event_group": event_group,
                    "plotted_item": plotted_item,
                    "partner_item": partner_item,
                    "chrom": loc["chrom"],
                    "start": start,
                    "end": end,
                    "midpoint": midpoint,
                    "p_value": p,
                    "neg_log10_p": neg_log10_p,
                    "odds_ratio": row.get("odds_ratio", np.nan),
                    "case_hit": row.get("case_hit", np.nan),
                    "control_hit": row.get("control_hit", np.nan),
                    "n_known_hit_samples": row.get("n_known_hit_samples", np.nan),
                    "samples": row.get("samples", ""),
                }
            )

    point_df = pd.DataFrame(points)

    if point_df.empty:
        return point_df

    offsets, centers = build_chrom_offsets(point_df)

    point_df["x"] = point_df.apply(
        lambda r: offsets[r["chrom"]] + r["midpoint"],
        axis=1,
    )

    point_df["chrom_order"] = point_df["chrom"].map(lambda c: chrom_sort_key(c)[0])
    point_df = point_df.sort_values(["chrom_order", "x", "plotted_item"])

    point_df.attrs["chrom_centers"] = centers

    return point_df


def add_hover(fig, ax, scatter, point_df: pd.DataFrame) -> None:
    """
    Add hover labels if mplcursors is installed.

    Works in interactive windows or notebook backends.
    """
    try:
        import mplcursors
    except ImportError:
        print("Hover disabled: install mplcursors with `pip install mplcursors`.")
        return

    cursor = mplcursors.cursor(scatter, hover=True)

    @cursor.connect("add")
    def on_add(sel):
        idx = sel.index
        row = point_df.iloc[idx]

        text = (
            f"Pair: {row['event_group']}\n"
            f"Point: {row['plotted_item']}\n"
            f"Partner: {row['partner_item']}\n"
            f"Location: {row['chrom']}:{int(row['start'])}-{int(row['end'])}\n"
            f"-log10(p): {row['neg_log10_p']:.3f}\n"
            f"p: {row['p_value']:.3e}\n"
            f"odds ratio: {row['odds_ratio']}\n"
            f"case_hit: {row['case_hit']}\n"
            f"control_hit: {row['control_hit']}"
        )

        sel.annotation.set_text(text)
        sel.annotation.get_bbox_patch().set(alpha=0.9)


def plot_manhattan(
    point_df: pd.DataFrame,
    output_path: str,
    title: str,
    p_threshold: float | None,
    show: bool,
) -> None:
    import matplotlib.pyplot as plt

    if point_df.empty:
        raise RuntimeError("No plot points were created. Check item IDs and database locations.")

    chroms = sorted(point_df["chrom"].unique(), key=chrom_sort_key)
    chrom_centers = point_df.attrs["chrom_centers"]

    fig, ax = plt.subplots(figsize=(16, 6))

    color_cycle = [
        "tab:blue",
        "tab:orange",
        "tab:green",
        "tab:red",
        "tab:purple",
        "tab:brown",
        "tab:pink",
        "tab:gray",
    ]

    # Plot chromosome by chromosome so colors alternate.
    all_scatters = []

    for i, chrom in enumerate(chroms):
        sub = point_df[point_df["chrom"] == chrom]

        sc = ax.scatter(
            sub["x"],
            sub["neg_log10_p"],
            s=14,
            alpha=0.8,
            color=color_cycle[i % len(color_cycle)],
            edgecolors="none",
        )

        all_scatters.append((sc, sub))

    ax.set_title(title)
    ax.set_xlabel("Chromosome")
    ax.set_ylabel("-log10(p-value)")

    ax.set_xticks([chrom_centers[c] for c in chroms])
    ax.set_xticklabels([c.replace("chr", "") for c in chroms], rotation=0)

    ax.grid(axis="y", linestyle="--", alpha=0.25)

    if p_threshold is not None and p_threshold > 0:
        y = -math.log10(p_threshold)
        ax.axhline(y, linestyle="--", linewidth=1)
        ax.text(
            point_df["x"].min(),
            y,
            f"  p = {p_threshold:g}",
            va="bottom",
        )

    fig.tight_layout()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300)
    print(f"Wrote plot: {output}")

    # Hover only works interactively.
    if show:
        # Use one combined invisible-ish scatter for hover indexing consistency.
        # Simpler: redraw one scatter over all points with alpha 0 for cursor target.
        hover_scatter = ax.scatter(
            point_df["x"],
            point_df["neg_log10_p"],
            s=24,
            alpha=0.01,
        )
        add_hover(fig, ax, hover_scatter, point_df)
        plt.show()

    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help="P-value CSV from compute_two_hit_event_pvalues.py.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output PNG path.",
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to SQLite database.",
    )
    parser.add_argument(
        "--kind",
        choices=["gene", "sv"],
        required=True,
        help="Whether item_1/item_2 are genes or SV IDs.",
    )
    parser.add_argument(
        "--cohort",
        choices=["kidsfirst", "background", "combined"],
        default="combined",
        help="For --kind sv, which SV table(s) to search.",
    )
    parser.add_argument(
        "--p-col",
        default="p_value",
        help="Column to plot. Examples: p_value, fdr_bh, bonferroni.",
    )
    parser.add_argument(
        "--title",
        default="Two-hit Manhattan-like plot",
    )
    parser.add_argument(
        "--p-threshold",
        type=float,
        default=0.05,
        help="Draw horizontal p-value threshold line. Use 0 to disable.",
    )
    parser.add_argument(
        "--points-output",
        default=None,
        help="Optional CSV of expanded plotting points.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show interactive matplotlib window with hover labels if mplcursors is installed.",
    )

    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    pval_df = pd.read_csv(args.input)

    if args.p_col not in pval_df.columns:
        raise ValueError(f"Column not found in input: {args.p_col}")

    if "item_1" not in pval_df.columns or "item_2" not in pval_df.columns:
        if "event_group" not in pval_df.columns:
            raise ValueError("Input must contain item_1/item_2 or event_group.")
        pval_df[["item_1", "item_2"]] = pval_df["event_group"].apply(
            lambda x: pd.Series(split_event_group(x))
        )

    item_ids = set()
    item_ids.update(pval_df["item_1"].dropna().map(clean_item_id))
    item_ids.update(pval_df["item_2"].dropna().map(clean_item_id))

    conn = connect_readonly(str(db_path))

    try:
        if args.kind == "gene":
            loc_df = load_gene_locations(conn, item_ids)
        else:
            loc_df = load_sv_locations(conn, item_ids, cohort=args.cohort)
    finally:
        conn.close()

    print(f"Input pairs: {len(pval_df):,}")
    print(f"Unique items in pairs: {len(item_ids):,}")
    print(f"Items with database locations: {len(loc_df):,}")

    missing = sorted(item_ids - set(loc_df["item"]))
    if missing:
        print(f"Warning: {len(missing):,} items had no database location.")
        print("First missing items:", ", ".join(missing[:20]))

    point_df = prepare_plot_points(
        pval_df=pval_df,
        loc_df=loc_df,
        p_col=args.p_col,
    )

    print(f"Plot points created: {len(point_df):,}")

    if args.points_output:
        point_df.to_csv(args.points_output, index=False)
        print(f"Wrote plot points: {args.points_output}")

    threshold = args.p_threshold
    if threshold is not None and threshold <= 0:
        threshold = None

    plot_manhattan(
        point_df=point_df,
        output_path=args.output,
        title=args.title,
        p_threshold=threshold,
        show=args.show,
    )


if __name__ == "__main__":
    main()