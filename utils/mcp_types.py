"""
Shared MCP types for AI Query.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class MCPToolCall:
    tool_name: str
    arguments: dict[str, Any]
    ok: bool
    result: dict[str, Any]


@dataclass
class MCPError:
    message: str
    details: Optional[str] = None


@dataclass
class DBMCPResult:
    ok: bool
    sql: str
    row_count: int
    columns: list[str]
    rows: list[dict[str, Any]]
    error: Optional[str] = None


@dataclass
class VisualizationSpec:
    kind: str
    title: Optional[str] = None
    x: Optional[str] = None
    y: Optional[str] = None
    rows: Optional[list[dict[str, Any]]] = None
    gene: Optional[str] = None
    locus: Optional[str] = None
    chrom: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
