"""
Tool Runner — safely executes discovered tools through subprocess.

Only tools registered in the discovery system can be run.
All inputs/outputs are validated; arbitrary shell commands are
not accepted.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import uuid
from typing import Any

from agents.tool_discovery import find_tool, load_tool_registry

RESULTS_BASE_DIR = pathlib.Path(__file__).resolve().parent.parent / "discovered_workers" / "results"
DEFAULT_TIMEOUT = 300


def create_job_dir(base_dir: str | None = None) -> pathlib.Path:
    root = pathlib.Path(base_dir) if base_dir else RESULTS_BASE_DIR
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    job_dir = root / f"job_{timestamp}_{uid}"
    job_dir.mkdir(parents=True, exist_ok=False)
    return job_dir


def run_tool(
    tool_id: str,
    input_path: str,
    parameters: dict[str, Any] | None = None,
    output_base_dir: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    abs_input = os.path.abspath(input_path)
    if not os.path.isfile(abs_input):
        return {"ok": False, "error": f"Input file not found: {abs_input}"}

    registry = load_tool_registry()
    resolved = find_tool(tool_id, registry)
    if resolved is None:
        return {"ok": False, "error": f"Tool '{tool_id}' not found in registry"}

    tool = resolved["tool"]
    tool_dir = resolved["tool_dir"]
    entry_cmd = tool.get("entrypoint", {}).get("command")
    if not entry_cmd:
        return {"ok": False, "error": f"Tool '{tool_id}' has no entrypoint command"}

    timeout = timeout or tool.get("constraints", {}).get("max_runtime_seconds", DEFAULT_TIMEOUT)

    job_dir = create_job_dir(output_base_dir)
    output_dir = str(job_dir)

    script_path = os.path.join(tool_dir, entry_cmd.split()[-1] if " " in entry_cmd else entry_cmd)
    if not os.path.isfile(script_path):
        return {"ok": False, "error": f"Entrypoint script not found: {script_path}"}

    tool_python = os.environ.get("MCP_TOOL_PYTHON", sys.executable)

    args = [
        tool_python,
        script_path,
        "--input_path", abs_input,
        "--output_dir", output_dir,
    ]

    if parameters:
        for key, value in parameters.items():
            if key in ("input_path", "output_dir"):
                continue
            args.extend([f"--{key}", str(value)])

    stdout_path = os.path.join(output_dir, "stdout.log")
    stderr_path = os.path.join(output_dir, "stderr.log")

    try:
        with open(stdout_path, "w") as out_f, open(stderr_path, "w") as err_f:
            proc = subprocess.run(
                args,
                cwd=tool_dir,
                stdout=out_f,
                stderr=err_f,
                timeout=timeout,
                text=True,
            )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"Tool execution timed out after {timeout}s",
            "output_dir": output_dir,
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
        }
    except FileNotFoundError as e:
        return {"ok": False, "error": f"Executable not found: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"Execution failed: {e}"}

    if proc.returncode != 0:
        return {
            "ok": False,
            "error": f"Tool exited with code {proc.returncode}",
            "returncode": proc.returncode,
            "output_dir": output_dir,
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
        }

    result = {
        "ok": True,
        "tool_id": tool_id,
        "returncode": proc.returncode,
        "output_dir": output_dir,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }

    metrics_path = os.path.join(output_dir, "metrics.json")
    if os.path.isfile(metrics_path):
        try:
            with open(metrics_path) as f:
                result["metrics"] = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    return result
