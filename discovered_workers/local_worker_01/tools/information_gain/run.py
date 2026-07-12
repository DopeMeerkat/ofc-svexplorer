"""
Information Gain — computes IG for each feature vs a target column.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


def entropy(series: pd.Series) -> float:
    probs = series.value_counts(normalize=True)
    return -sum(p * np.log2(p) for p in probs if p > 0)


def information_gain(df: pd.DataFrame, feature: str, target: str) -> float:
    original = entropy(df[target])
    weighted = 0.0
    for _val, subset in df.groupby(feature, observed=True):
        weighted += len(subset) / len(df) * entropy(subset[target])
    return original - weighted


def conditional_entropy(df: pd.DataFrame, feature: str, target: str) -> float:
    weighted = 0.0
    for _val, subset in df.groupby(feature, observed=True):
        weighted += len(subset) / len(df) * entropy(subset[target])
    return weighted


def _zero_containing_features(df: pd.DataFrame, target_col: str) -> list[str]:
    """Return feature columns that contain at least one zero (indicator columns)."""
    features = []
    for column in df.columns:
        if column == target_col:
            continue
        numeric_values = pd.to_numeric(df[column], errors="coerce")
        if numeric_values.eq(0).any():
            features.append(column)
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description="Information Gain")
    parser.add_argument("--input_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--target_column", default=None)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    start = time.time()

    df = pd.read_csv(args.input_path)
    target = args.target_column if args.target_column else df.columns[-1]
    print(f"[information_gain] Loaded {len(df)} rows, target = {target}", flush=True)

    df_encoded = df.copy()
    for col in df_encoded.columns:
        if df_encoded[col].dtype == "object":
            df_encoded[col], _ = pd.factorize(df_encoded[col])

    features = _zero_containing_features(df, target)
    excluded = [c for c in df.columns if c != target and c not in features]
    if excluded:
        print(f"[information_gain] Excluded non-indicator columns: {excluded}", flush=True)
    results = []
    for feat in features:
        ig = information_gain(df_encoded, feat, target)
        ce = conditional_entropy(df_encoded, feat, target)
        results.append({
            "Feature": feat,
            "Information_Gain": round(ig, 6),
            "Conditional_Entropy": round(ce, 6),
        })

    ranking = pd.DataFrame(results).sort_values("Information_Gain", ascending=False)
    ranking.to_csv(os.path.join(args.output_dir, "feature_ranking.csv"), index=False)
    print(f"[information_gain] Wrote feature_ranking.csv ({len(ranking)} features)", flush=True)

    df.to_csv(os.path.join(args.output_dir, "results.csv"), index=False)
    print(f"[information_gain] Wrote results.csv", flush=True)

    if HAS_PLOTLY and not ranking.empty:
        import plotly.io as pio
        fig = px.bar(
            ranking.head(50),
            x="Information_Gain",
            y="Feature",
            color="Information_Gain",
            color_continuous_scale="viridis",
            title=f"Information Gain by Feature (target: {target})",
            height=max(400, min(len(ranking), 50) * 35),
            labels={"Information_Gain": "Information Gain", "Feature": ""},
        )
        fig.update_layout(
            bargap=0.3,
            margin=dict(l=10, r=30, t=60, b=30),
            yaxis=dict(autorange="reversed"),
        )
        pio.write_json(fig, os.path.join(args.output_dir, "plot.json"))
        print(f"[information_gain] Wrote plot.json", flush=True)

    elapsed = round(time.time() - start, 3)
    metrics = {
        "tool": "information_gain",
        "status": "completed",
        "row_count": len(df),
        "feature_count": len(features),
        "target_column": target,
        "execution_seconds": elapsed,
        "top_features": ranking.head(10).to_dict("records"),
    }
    with open(os.path.join(args.output_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[information_gain] Done in {elapsed}s", flush=True)


if __name__ == "__main__":
    main()
