"""
Echo Analysis — dummy tool for pipeline verification.

Reads a CSV or JSON input file, computes minimal summary stats,
writes metrics.json, results.csv, and prints progress to stdout.
All output goes into the directory specified by --output_dir.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys
import time


def load_csv(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list) and all(isinstance(r, dict) for r in data):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError("JSON must be a list of objects or a single object")


def load_input(path: str) -> list[dict]:
    ext = pathlib.Path(path).suffix.lower()
    if ext == ".csv":
        return load_csv(path)
    if ext == ".json":
        return load_json(path)
    raise ValueError(f"Unsupported file extension: {ext}")


def compute_metrics(rows: list[dict]) -> dict:
    if not rows:
        return {
            "row_count": 0,
            "column_names": [],
            "num_columns": 0,
            "numeric_columns": {},
        }
    col_names = list(rows[0].keys())
    numeric_summary = {}
    for col in col_names:
        vals = []
        for r in rows:
            try:
                vals.append(float(r[col]))
            except (ValueError, TypeError):
                pass
        if vals:
            numeric_summary[col] = {
                "min": min(vals),
                "max": max(vals),
                "mean": sum(vals) / len(vals),
                "count": len(vals),
            }
    return {
        "row_count": len(rows),
        "column_names": col_names,
        "num_columns": len(col_names),
        "numeric_columns": numeric_summary,
    }


def write_results(rows: list[dict], path: str) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys()) + ["echo_label"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, r in enumerate(rows):
            r["echo_label"] = f"row_{i}"
            writer.writerow(r)


def main() -> None:
    parser = argparse.ArgumentParser(description="Echo Analysis dummy tool")
    parser.add_argument("--input_path", required=True, help="Input CSV or JSON file")
    parser.add_argument("--output_dir", required=True, help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    start = time.time()

    print(f"[echo_analysis] Loading input from {args.input_path}")

    rows = load_input(args.input_path)
    print(f"[echo_analysis] Loaded {len(rows)} rows", flush=True)

    metrics = compute_metrics(rows)
    metrics["execution_seconds"] = round(time.time() - start, 3)
    metrics["tool"] = "echo_analysis"
    metrics["status"] = "completed"

    metrics_path = os.path.join(args.output_dir, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[echo_analysis] Wrote {metrics_path}", flush=True)

    results_path = os.path.join(args.output_dir, "results.csv")
    write_results(rows, results_path)
    print(f"[echo_analysis] Wrote {results_path}", flush=True)

    elapsed = round(time.time() - start, 3)
    print(f"[echo_analysis] Done in {elapsed}s", flush=True)


if __name__ == "__main__":
    main()
