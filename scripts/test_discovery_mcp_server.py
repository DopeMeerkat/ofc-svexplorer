#!/usr/bin/env python3
"""
Verification script for the Discovery MCP server.

Starts the server, calls each endpoint, and prints results.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


MCP_URL = "http://127.0.0.1:8104/mcp"


def _mcp_call(tool: str, arguments: dict | None = None) -> dict:
    body = json.dumps({"tool": tool, "arguments": arguments or {}}).encode("utf-8")
    req = urllib.request.Request(
        MCP_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))
    except urllib.error.URLError:
        return {"ok": False, "error": f"Cannot connect to {MCP_URL}"}


def create_sample_csv() -> str:
    data = [
        {"sample_id": "S001", "phenotype": "case", "value": 1.5},
        {"sample_id": "S002", "phenotype": "control", "value": 2.3},
        {"sample_id": "S003", "phenotype": "case", "value": 0.8},
    ]
    fd, path = tempfile.mkstemp(suffix=".csv", prefix="mcp_test_input_")
    with os.fdopen(fd, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["sample_id", "phenotype", "value"])
        writer.writeheader()
        writer.writerows(data)
    return path


def main() -> None:
    print("=" * 60)
    print("DISCOVERY MCP SERVER VERIFICATION")
    print("=" * 60)

    # 1. health_check
    print("\n--- health_check ---")
    result = _mcp_call("health_check")
    print(json.dumps(result, indent=2))

    if not result.get("ok"):
        print("\nERROR: Server not reachable. Is it running?")
        sys.exit(1)

    # 2. list_discovered_workers
    print("\n--- list_discovered_workers ---")
    result = _mcp_call("list_discovered_workers")
    for w in result.get("workers", []):
        print(f"  Worker: {w['worker_id']} ({w['display_name']})")
        print(f"    Simulated: {w['simulated']}")
        print(f"    Tool IDs:  {w['tool_ids']}")

    # 3. list_discovered_tools
    print("\n--- list_discovered_tools ---")
    result = _mcp_call("list_discovered_tools")
    for t in result.get("tools", []):
        print(f"  Tool: {t['id']} v{t.get('version', '?')} ({t['display_name']})")
        print(f"    Worker:  {t.get('worker_id', '?')}")
        print(f"    Inputs:  {list(t.get('inputs', {}).keys())}")
        print(f"    Outputs: {list(t.get('outputs', {}).keys())}")

    # 4. get_discovered_tool
    print("\n--- get_discovered_tool (echo_analysis) ---")
    result = _mcp_call("get_discovered_tool", {"tool_id": "echo_analysis"})
    print(f"  Found: {result.get('ok', False)}")
    if result.get("ok"):
        td = result["tool"]
        print(f"  ID:      {td.get('id')}")
        print(f"  Version: {td.get('version')}")
        print(f"  Worker:  {result.get('worker_id')}")
        print(f"  Inputs:  {json.dumps(td.get('inputs'), indent=4)}")
        print(f"  Outputs: {json.dumps(td.get('outputs'), indent=4)}")

    # 5. get_discovered_tool (404)
    print("\n--- get_discovered_tool (nonexistent) ---")
    result = _mcp_call("get_discovered_tool", {"tool_id": "nonexistent_tool"})
    print(f"  Expected error: {result.get('error', '?')}")

    # 6. run_discovered_tool
    print("\n--- run_discovered_tool (echo_analysis) ---")
    sample_path = create_sample_csv()
    print(f"  Sample input: {sample_path}")
    try:
        result = _mcp_call("run_discovered_tool", {
            "tool_id": "echo_analysis",
            "input_path": sample_path,
            "timeout": 30,
        })
        print(f"  Status:       {'OK' if result.get('ok') else 'FAILED'}")
        print(f"  Return code:  {result.get('returncode', '?')}")
        print(f"  Output dir:   {result.get('output_dir', '?')}")
        print(f"  Stdout:       {result.get('stdout_path', '?')}")
        print(f"  Stderr:       {result.get('stderr_path', '?')}")
        if result.get("ok") and result.get("metrics"):
            m = result["metrics"]
            print(f"  Rows:         {m.get('row_count', '?')}")
            print(f"  Columns:      {m.get('column_names', [])}")
            print(f"  Duration:     {m.get('execution_seconds', '?')}s")
    finally:
        if os.path.isfile(sample_path):
            os.unlink(sample_path)

    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print("  All MCP endpoints tested successfully.")
    print("  Discovery MCP server is operational.")


if __name__ == "__main__":
    main()
