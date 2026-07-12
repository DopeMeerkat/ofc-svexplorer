"""
Decision Tree Feature Importance — replicates visualization_uploader logic.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


def zero_containing_features(df: pd.DataFrame, target_col: str) -> tuple[list[str], list[str]]:
    features = []
    excluded = []
    for column in df.columns:
        if column == target_col:
            continue
        numeric_values = pd.to_numeric(df[column], errors="coerce")
        if numeric_values.eq(0).any():
            features.append(column)
        else:
            excluded.append(column)
    return features, excluded


def prepare_feature_data(df: pd.DataFrame, target_col: str | None = None):
    if target_col is None:
        target_col = df.columns[-1]
    features, excluded = zero_containing_features(df, target_col)
    if not features:
        raise ValueError("No zero-containing indicator features found.")

    model_df = df[features + [target_col]].copy()
    for col in model_df.columns:
        if model_df[col].dtype == "object":
            model_df[col], _ = pd.factorize(model_df[col], sort=True)

    feature_df = model_df[features].apply(pd.to_numeric, errors="coerce").fillna(0)
    target = pd.to_numeric(model_df[target_col], errors="coerce")
    if target.isna().any():
        target, _ = pd.factorize(model_df[target_col], sort=True)
        target = pd.Series(target, index=model_df.index)
    else:
        target = target.fillna(0)

    if pd.Series(target).nunique(dropna=True) < 2:
        raise ValueError("Target column must contain at least two classes.")

    return feature_df, target.astype(int), target_col, features, excluded, model_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Decision Tree Classifier")
    parser.add_argument("--input_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--target_column", default=None)
    parser.add_argument("--random_state", type=int, default=42)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    start = time.time()

    df = pd.read_csv(args.input_path)
    print(f"[decision_tree] Loaded {len(df)} rows", flush=True)

    feature_df, target, target_col, features, excluded, model_df = prepare_feature_data(df, args.target_column)
    if excluded:
        print(f"[decision_tree] Excluded columns: {excluded}", flush=True)
    print(f"[decision_tree] Using {len(features)} features, target = {target_col}", flush=True)

    model = DecisionTreeClassifier(
        random_state=args.random_state,
        class_weight="balanced",
    )
    model.fit(feature_df, target)
    print(f"[decision_tree] Model trained", flush=True)

    importance_df = pd.DataFrame({
        "Feature": features,
        "Importance": model.feature_importances_,
    }).sort_values("Importance", ascending=False)
    importance_df.to_csv(os.path.join(args.output_dir, "feature_importance.csv"), index=False)
    print(f"[decision_tree] Wrote feature_importance.csv", flush=True)

    model_df.to_csv(os.path.join(args.output_dir, "results.csv"), index=False)
    print(f"[decision_tree] Wrote results.csv", flush=True)

    if HAS_PLOTLY and not importance_df.empty:
        import plotly.io as pio
        fig = px.bar(
            importance_df.head(50),
            x="Importance",
            y="Feature",
            color="Importance",
            color_continuous_scale="viridis",
            title=f"Decision Tree Feature Importance (target: {target_col})",
            height=max(400, min(len(importance_df), 50) * 35),
            labels={"Importance": "Importance Score", "Feature": ""},
        )
        fig.update_layout(
            bargap=0.3,
            margin=dict(l=10, r=30, t=60, b=30),
            yaxis=dict(autorange="reversed"),
        )
        pio.write_json(fig, os.path.join(args.output_dir, "plot.json"))
        print(f"[decision_tree] Wrote plot.json", flush=True)

    elapsed = round(time.time() - start, 3)
    top = importance_df.head(10).to_dict("records") if not importance_df.empty else []
    metrics = {
        "tool": "decision_tree",
        "status": "completed",
        "row_count": len(df),
        "feature_count": len(features),
        "target_column": target_col,
        "execution_seconds": elapsed,
        "top_features": top,
    }
    with open(os.path.join(args.output_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[decision_tree] Done in {elapsed}s", flush=True)


if __name__ == "__main__":
    main()
