#!/usr/bin/env python3
"""
Manual verification script for the tool discovery and execution pipeline.

Loads the registry, prints discovered workers and tools,
runs the dummy echo_analysis tool on a small sample input,
and prints the result.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.tool_discovery import load_tool_registry, find_tool
from agents.tool_runner import run_tool


def create_sample_csv() -> str:
    data = [
        {"sample_id": "S001", "phenotype": "case", "value": 1.5},
        {"sample_id": "S002", "phenotype": "control", "value": 2.3},
        {"sample_id": "S003", "phenotype": "case", "value": 0.8},
        {"sample_id": "S004", "phenotype": "case", "value": 3.1},
        {"sample_id": "S005", "phenotype": "control", "value": 1.9},
    ]
    fd, path = tempfile.mkstemp(suffix=".csv", prefix="test_input_")
    with os.fdopen(fd, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["sample_id", "phenotype", "value"])
        writer.writeheader()
        writer.writerows(data)
    return path


def main() -> None:
    print("=" * 60)
    print("TOOL DISCOVERY VERIFICATION")
    print("=" * 60)

    # 1. Load registry
    registry = load_tool_registry()
    print(f"\nWorkers discovered: {registry['worker_count']}")
    if not registry.get("ok"):
        print(f"ERROR: {registry.get('error', 'Unknown error')}")
        sys.exit(1)

    # 2. Print worker and tool details
    for w in registry["workers"]:
        wd = w["worker"]
        print(f"\n--- Worker: {wd.get('display_name', wd.get('worker_id', '?'))} ---")
        print(f"  ID:            {wd.get('worker_id', '?')}")
        print(f"  Description:   {wd.get('description', '?')}")
        print(f"  Simulated:     {wd.get('simulated', '?')}")
        print(f"  CPU cores:     {wd.get('resources', {}).get('cpu_cores', '?')}")
        print(f"  GPU available: {wd.get('resources', {}).get('gpu', {}).get('available', '?')}")
        print(f"  Tools found:   {len(w['tools'])}")

        for t in w["tools"]:
            td = t["tool"]
            print(f"\n    --- Tool: {td.get('display_name', td.get('id', '?'))} ---")
            print(f"      ID:          {td.get('id', '?')}")
            print(f"      Version:     {td.get('version', '?')}")
            print(f"      Entrypoint:  {td.get('entrypoint', {}).get('command', '?')}")
            print(f"      Max runtime: {td.get('constraints', {}).get('max_runtime_seconds', '?')}s")

    # 3. Verify find_tool
    print("\n" + "=" * 60)
    print("TOOL LOOKUP: find_tool('echo_analysis')")
    print("=" * 60)
    resolved = find_tool("echo_analysis", registry)
    if resolved:
        print(f"  Found:          yes")
        print(f"  Worker:         {resolved['worker'].get('worker_id', '?')}")
        print(f"  Tool ID:        {resolved['tool'].get('id', '?')}")
        print(f"  Tool dir:       {resolved['tool_dir']}")
    else:
        print("  Found:          NO")
        print("  ERROR: echo_analysis not registered.")

    # 4. Run the dummy tool
    print("\n" + "=" * 60)
    print("TOOL EXECUTION: run_tool('echo_analysis')")
    print("=" * 60)
    sample_path = create_sample_csv()
    print(f"  Sample input:   {sample_path}")
    try:
        result = run_tool("echo_analysis", sample_path, timeout=30)
        print(f"  Status:         {'OK' if result.get('ok') else 'FAILED'}")
        print(f"  Return code:    {result.get('returncode', '?')}")
        print(f"  Output dir:     {result.get('output_dir', '?')}")
        print(f"  Stdout log:     {result.get('stdout_path', '?')}")
        print(f"  Stderr log:     {result.get('stderr_path', '?')}")

        if result.get("ok"):
            metrics = result.get("metrics", {})
            print(f"\n  --- metrics.json ---")
            print(f"    Rows:          {metrics.get('row_count', '?')}")
            print(f"    Columns:       {metrics.get('column_names', [])}")
            print(f"    Numeric cols:  {list(metrics.get('numeric_columns', {}).keys())}")
            print(f"    Tool:          {metrics.get('tool', '?')}")
            print(f"    Status:        {metrics.get('status', '?')}")
            print(f"    Duration:      {metrics.get('execution_seconds', '?')}s")
        else:
            print(f"  Error:          {result.get('error', '?')}")
    finally:
        if os.path.isfile(sample_path):
            os.unlink(sample_path)

    # 5. Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    if resolved and result.get("ok"):
        print("  All checks passed.")
        print("  Discovery and execution pipeline is working.")
    else:
        print("  Some checks failed. Review output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
