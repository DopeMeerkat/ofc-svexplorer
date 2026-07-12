"""
Tool Discovery — scans discovered_workers/ directories and loads
worker+tool metadata into a validated Python data structure.
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

import yaml

DEFAULT_WORKERS_DIR = pathlib.Path(__file__).resolve().parent.parent / "discovered_workers"
REQUIRED_WORKER_FIELDS = ["worker_id", "display_name", "description", "tools_directory"]
REQUIRED_TOOL_FIELDS = ["id", "version", "display_name", "description", "entrypoint", "inputs", "outputs"]


def _load_yaml(path: str) -> dict[str, Any] | None:
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None
    except yaml.YAMLError as e:
        print(f"[tool_discovery] YAML parse error in {path}: {e}")
        return None


def validate_worker(data: dict[str, Any] | None, path: str) -> dict[str, Any]:
    if data is None:
        return {"ok": False, "error": f"Could not load worker metadata from {path}"}
    missing = [f for f in REQUIRED_WORKER_FIELDS if f not in data]
    if missing:
        return {"ok": False, "error": f"Missing required fields in {path}: {missing}"}
    return {"ok": True, "data": data}


def validate_tool(data: dict[str, Any] | None, path: str) -> dict[str, Any]:
    if data is None:
        return {"ok": False, "error": f"Could not load tool metadata from {path}"}
    missing = [f for f in REQUIRED_TOOL_FIELDS if f not in data]
    if missing:
        return {"ok": False, "error": f"Missing required fields in {path}: {missing}"}
    return {"ok": True, "data": data}


def discover_workers(workers_dir: str | None = None) -> list[dict[str, Any]]:
    root = pathlib.Path(workers_dir) if workers_dir else DEFAULT_WORKERS_DIR
    if not root.is_dir():
        print(f"[tool_discovery] Workers directory not found: {root}")
        return []

    workers = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        worker_yaml = entry / "worker.yaml"
        if not worker_yaml.is_file():
            continue

        raw = _load_yaml(str(worker_yaml))
        result = validate_worker(raw, str(worker_yaml))
        if not result["ok"]:
            print(f"[tool_discovery] Skipping {entry.name}: {result['error']}")
            continue

        wd = result["data"]
        tools = discover_tools(entry, wd.get("tools_directory", "tools"))
        workers.append({
            "worker": wd,
            "worker_dir": str(entry),
            "tools": tools,
        })

    return workers


def discover_tools(worker_dir: pathlib.Path, tools_subdir: str) -> list[dict[str, Any]]:
    tools_path = worker_dir / tools_subdir
    if not tools_path.is_dir():
        return []

    found = []
    for tool_dir in sorted(tools_path.iterdir()):
        if not tool_dir.is_dir():
            continue
        tool_yaml = tool_dir / "tool.yaml"
        if not tool_yaml.is_file():
            continue

        raw = _load_yaml(str(tool_yaml))
        result = validate_tool(raw, str(tool_yaml))
        if not result["ok"]:
            print(f"[tool_discovery] Skipping tool in {tool_dir.name}: {result['error']}")
            continue

        td = result["data"]
        found.append({
            "tool": td,
            "tool_dir": str(tool_dir),
        })

    return found


def load_tool_registry(workers_dir: str | None = None) -> dict[str, Any]:
    workers = discover_workers(workers_dir)
    return {
        "ok": True,
        "worker_count": len(workers),
        "workers": workers,
    }


def find_tool(tool_id: str, registry: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if registry is None:
        registry = load_tool_registry()
    if not registry.get("ok"):
        return None
    for w in registry.get("workers", []):
        for t in w.get("tools", []):
            if t.get("tool", {}).get("id") == tool_id:
                return {
                    "worker": w["worker"],
                    "worker_dir": w["worker_dir"],
                    "tool": t["tool"],
                    "tool_dir": t["tool_dir"],
                }
    return None
