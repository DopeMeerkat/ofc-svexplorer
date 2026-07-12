"""
MCP Query Agent — recommends discovered tools via LLM and
coordinates execution through the discovery MCP server.
"""

from __future__ import annotations

import json
from typing import Any

from utils.mcp_client_manager import MCPClientManager
from utils.ollama_client import generate_ollama_response


def _ollama_model_name(model: str) -> str:
    if model.startswith("ollama:"):
        return model.split("ollama:", 1)[1]
    return model


def _build_tool_description(tools: list[dict]) -> str:
    lines = []
    for t in tools:
        tid = t.get("id", "?")
        desc = t.get("description", "?")
        inputs = list(t.get("inputs", {}).keys())
        lines.append(f"- {tid}: {desc}  [inputs: {', '.join(inputs)}]")
    return "\n".join(lines)


def recommend_tools(
    instructions: str,
    columns: list[str],
    row_count: int,
    client: MCPClientManager | None = None,
    model: str = "ollama:qwen3:8b",
) -> tuple[bool, list[str] | str]:
    if client is None:
        client = MCPClientManager()

    tools_result = client.call_discovery_tool("list_discovered_tools", {})
    if not tools_result.get("ok"):
        return False, f"Failed to list tools: {tools_result.get('error', 'unknown')}"

    tools = tools_result.get("tools", [])
    if not tools:
        return False, "No discovered tools available."

    tool_desc = _build_tool_description(tools)
    col_str = ", ".join(columns)

    prompt = (
        "You are a tool recommendation assistant for an OFC/SV analysis platform.\n\n"
        "Available tools:\n"
        f"{tool_desc}\n\n"
        "User dataset columns: "
        f"{col_str}\n"
        f"Row count: {row_count}\n\n"
        "User instruction:\n"
        f"{instructions}\n\n"
        "Recommend which tools are relevant. "
        "Return JSON only, no extra text:\n"
        "{\n"
        '  "recommendations": ["tool_id_1", "tool_id_2"]\n'
        "}\n\n"
        "Only include tool IDs that are clearly relevant to the user's instruction and dataset."
    )

    try:
        raw = generate_ollama_response(prompt, model=_ollama_model_name(model))
    except (ConnectionError, ValueError) as exc:
        return False, f"LLM call failed: {exc}"
    except Exception as exc:
        return False, f"LLM call failed unexpectedly: {exc}"

    raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            return False, f"LLM returned unparseable response: {raw[:200]}"
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return False, f"LLM returned unparseable response: {raw[:200]}"

    recs = data.get("recommendations", [])
    if not isinstance(recs, list):
        recs = []

    valid_ids = {t.get("id") for t in tools}
    recs = [r for r in recs if r in valid_ids]

    if not recs:
        return False, "LLM did not recommend any compatible tools."

    return True, recs


def run_discovered_tool(
    tool_id: str,
    input_path: str,
    parameters: dict[str, Any] | None = None,
    client: MCPClientManager | None = None,
) -> dict[str, Any]:
    if client is None:
        client = MCPClientManager()
    return client.call_discovery_tool("run_discovered_tool", {
        "tool_id": tool_id,
        "input_path": input_path,
        "parameters": parameters or {},
    })
