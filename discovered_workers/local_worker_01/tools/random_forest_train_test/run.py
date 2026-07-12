"""
Random Forest Train/Test — repeated train/test splits with aggregated metrics.
Mirrors pages/visualization_uploader.py:render_random_forest_train_test.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

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


def summarize_metrics(metrics_df: pd.DataFrame) -> dict:
    summary = {}
    for metric in ["accuracy", "balanced_accuracy", "f1_weighted", "roc_auc"]:
        if metric not in metrics_df.columns:
            continue
        values = pd.to_numeric(metrics_df[metric], errors="coerce").dropna()
        if values.empty:
            continue
        summary[metric] = {
            "mean": round(float(values.mean()), 4),
            "std": round(float(values.std(ddof=0)), 4),
            "min": round(float(values.min()), 4),
            "max": round(float(values.max()), 4),
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Random Forest Train/Test")
    parser.add_argument("--input_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--target_column", default=None)
    parser.add_argument("--n_runs", type=int, default=100)
    parser.add_argument("--n_estimators", type=int, default=50)
    parser.add_argument("--test_size", type=float, default=0.2)
    parser.add_argument("--random_state", type=int, default=42)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    start = time.time()

    df = pd.read_csv(args.input_path)
    print(f"[rf_train_test] Loaded {len(df)} rows", flush=True)

    feature_df, target, target_col, features, excluded, model_df = prepare_feature_data(df, args.target_column)
    if excluded:
        print(f"[rf_train_test] Excluded columns: {excluded}", flush=True)
    print(f"[rf_train_test] Using {len(features)} features, target = {target_col}", flush=True)

    if len(feature_df) < 5:
        print("[rf_train_test] Too few rows (<5), exiting", flush=True)
        sys.exit(1)

    class_counts = pd.Series(target).value_counts()
    n_test = max(1, int(math.ceil(len(feature_df) * args.test_size)))
    n_train = len(feature_df) - n_test
    n_classes = len(class_counts)
    stratify = target if class_counts.min() >= 2 and n_test >= n_classes and n_train >= n_classes else None

    importances = []
    metric_rows = []

    for run_index in range(args.n_runs):
        seed = args.random_state + run_index
        split = train_test_split(
            feature_df,
            target,
            test_size=args.test_size,
            random_state=seed,
            stratify=stratify,
        )
        x_train, x_test, y_train, y_test = split

        model = RandomForestClassifier(
            n_estimators=args.n_estimators,
            random_state=seed,
            n_jobs=-1,
            class_weight="balanced",
        )
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)

        roc_auc = np.nan
        if len(np.unique(y_test)) == 2 and hasattr(model, "predict_proba"):
            proba = model.predict_proba(x_test)
            if proba.shape[1] == 2:
                roc_auc = roc_auc_score(y_test, proba[:, 1])

        metric_rows.append({
            "run": run_index + 1,
            "accuracy": accuracy_score(y_test, predictions),
            "balanced_accuracy": balanced_accuracy_score(y_test, predictions),
            "f1_weighted": f1_score(y_test, predictions, average="weighted", zero_division=0),
            "roc_auc": roc_auc,
        })
        importances.append(model.feature_importances_)

    per_run_df = pd.DataFrame(metric_rows)
    per_run_df.to_csv(os.path.join(args.output_dir, "train_test_metrics.csv"), index=False)
    print(f"[rf_train_test] Wrote train_test_metrics.csv", flush=True)

    importance_array = np.vstack(importances)
    importance_df = pd.DataFrame({
        "Feature": features,
        "Score": importance_array.mean(axis=0),
        "Std": importance_array.std(axis=0),
    }).sort_values("Score", ascending=False)
    importance_df.to_csv(os.path.join(args.output_dir, "feature_importance.csv"), index=False)
    print(f"[rf_train_test] Wrote feature_importance.csv", flush=True)

    model_df.to_csv(os.path.join(args.output_dir, "results.csv"), index=False)
    print(f"[rf_train_test] Wrote results.csv", flush=True)

    if HAS_PLOTLY and not importance_df.empty:
        import plotly.io as pio
        fig = px.bar(
            importance_df.head(50),
            x="Score",
            y="Feature",
            color="Score",
            color_continuous_scale="viridis",
            title=f"Random Forest Train/Test Feature Importance over {args.n_runs} Runs ({target_col})",
            height=max(400, min(len(importance_df), 50) * 35),
            labels={"Score": "Mean Importance", "Feature": ""},
            custom_data=["Std"],
        )
        fig.update_traces(
            error_x={"array": importance_df.head(50)["Std"], "visible": True},
            hovertemplate="<b>%{y}</b><br>Mean importance: %{x:.5f}<br>Std: %{customdata[0]:.5f}<extra></extra>",
        )
        fig.update_layout(
            bargap=0.3,
            margin=dict(l=10, r=30, t=60, b=30),
            yaxis=dict(autorange="reversed"),
        )
        pio.write_json(fig, os.path.join(args.output_dir, "plot.json"))
        print(f"[rf_train_test] Wrote plot.json", flush=True)

    elapsed = round(time.time() - start, 3)
    metric_summary = summarize_metrics(per_run_df)
    top = importance_df.head(10).to_dict("records") if not importance_df.empty else []
    metrics = {
        "tool": "random_forest_train_test",
        "status": "completed",
        "row_count": len(df),
        "feature_count": len(features),
        "target_column": target_col,
        "n_runs": args.n_runs,
        "n_estimators": args.n_estimators,
        "test_size": args.test_size,
        "metric_summary": metric_summary,
        "execution_seconds": elapsed,
        "top_features": top,
    }
    with open(os.path.join(args.output_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[rf_train_test] Done in {elapsed}s", flush=True)


if __name__ == "__main__":
    main()
