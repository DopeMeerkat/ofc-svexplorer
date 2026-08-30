"""
Pathway network (edges/nodes) loader backed by a local rclone cache.

Each network version is a subdirectory of the configured OneDrive pathway
folder (e.g. ``Baseline``, ``Extended1``, ``CaseStudy6``). Within a directory the first CSV
whose filename starts with ``edges`` is used as the edge table and the first
starting with ``nodes`` as the node table. The cache mirrors the remote via
``rclone sync``.

Configuration (os.environ or the gitignored ``rclone/.env`` file):

    PATHWAY_RCLONE_BIN                rclone executable
    PATHWAY_RCLONE_REMOTE             OneDrive pathway folder, e.g. "uconn:.../Data/Pathway"
    PATHWAY_CACHE_DIR                 local cache (default: rclone/cache/pathway_networks)
    PATHWAY_REFRESH_TIMEOUT_SECONDS   rclone timeout (default: 120)

If the cache is not configured or populated yet, a built-in fallback list is
returned based on the bundled ``pathway/*.csv`` files so the page still
renders Baseline/Extended/Case Study 6 without OneDrive access.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
from typing import Any

from pathway.network_app_rel import build_cytoscape_elements, build_node_table, load_edges

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = PROJECT_ROOT / "rclone" / "cache" / "pathway_networks"
ENV_FILE = PROJECT_ROOT / "rclone" / ".env"
DEFAULT_RCLONE_BIN = "rclone"
DEFAULT_TIMEOUT = 120
PATHWAY_DIR = PROJECT_ROOT / "pathway"

_BUILTIN_NETWORKS = (
    ("Baseline", "Baseline", "edges_e.csv", "nodes_e.csv"),
    ("Extended1", "Extended", "edges_v1.csv", "nodes_v1.csv"),
    ("CaseStudy6", "Case Study 6", "edges_v3.csv", "nodes_v3.csv"),
)


def _load_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return values


def _getenv(key: str, default: str = "") -> str:
    return os.environ.get(key) or _load_env_file().get(key) or default


def cache_dir() -> pathlib.Path:
    return pathlib.Path(_getenv("PATHWAY_CACHE_DIR", str(DEFAULT_CACHE_DIR)))


def rclone_bin() -> str:
    return _getenv("PATHWAY_RCLONE_BIN") or _getenv("CASE_STUDY_RCLONE_BIN") or DEFAULT_RCLONE_BIN


def rclone_remote() -> str:
    return _getenv("PATHWAY_RCLONE_REMOTE", "")


def is_configured() -> bool:
    """True when a OneDrive remote has been configured for refresh."""
    return bool(rclone_remote())


def _redact(text: str) -> str:
    """Replace configured paths with placeholders so errors do not leak them."""
    for secret in (rclone_remote(), str(cache_dir())):
        if secret:
            text = text.replace(secret, "<configured-path>")
    return text


def refresh_networks(timeout: int | None = None) -> dict[str, Any]:
    """Sync the configured OneDrive pathway folder into the local cache.

    Mirrors the remote for ``*.csv``: local CSVs no longer present on OneDrive
    are deleted. Non-CSV files in the cache are left untouched.
    """
    remote = rclone_remote()
    cache = cache_dir()
    if not remote:
        return {
            "ok": False,
            "configured": False,
            "error": "PATHWAY_RCLONE_REMOTE is not configured.",
        }

    cache.mkdir(parents=True, exist_ok=True)
    if timeout is None:
        timeout = int(_getenv("PATHWAY_REFRESH_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT)))

    cmd = [rclone_bin(), "sync", remote, str(cache), "--include", "*.csv"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return {"ok": False, "configured": True, "error": f"rclone not found: {rclone_bin()}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "configured": True, "error": f"rclone sync timed out after {timeout}s"}
    except Exception as exc:
        return {"ok": False, "configured": True, "error": _redact(f"rclone sync failed: {exc}")}

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or f"rclone exited with code {proc.returncode}").strip()
        return {"ok": False, "configured": True, "error": _redact(detail)}

    return {"ok": True, "configured": True, "count": len(_discovered_versions())}


def _first_csv(directory: pathlib.Path, prefix: str) -> pathlib.Path | None:
    matches = sorted(directory.glob(f"{prefix}*.csv"))
    return matches[0] if matches else None


def _discovered_versions() -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = []
    cache = cache_dir()
    if not cache.is_dir():
        return versions
    for subdir in sorted(path for path in cache.iterdir() if path.is_dir()):
        edges = _first_csv(subdir, "edges")
        nodes = _first_csv(subdir, "nodes")
        if edges and nodes:
            versions.append({"id": subdir.name, "label": subdir.name, "edges": edges, "nodes": nodes})
    return versions


def _builtin_versions() -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = []
    for version_id, label, edges_name, nodes_name in _BUILTIN_NETWORKS:
        edges = PATHWAY_DIR / edges_name
        nodes = PATHWAY_DIR / nodes_name
        if edges.is_file() and nodes.is_file():
            versions.append({"id": version_id, "label": label, "edges": edges, "nodes": nodes})
    return versions


def list_versions() -> list[dict[str, Any]]:
    """Return sorted [{id, label, edges, nodes}] network versions.

    Uses bundled local CSVs as the baseline registry and lets discovered cache
    entries replace bundled versions with the same ID.
    """
    versions = {version["id"]: version for version in _builtin_versions()}
    for version in _discovered_versions():
        versions[version["id"]] = version
    return list(versions.values())


def invalid_versions() -> list[tuple[str, str]]:
    """Return [(dirname, reason)] for cache subdirectories missing edges/nodes CSVs."""
    problems: list[tuple[str, str]] = []
    cache = cache_dir()
    if not cache.is_dir():
        return problems
    for subdir in sorted(path for path in cache.iterdir() if path.is_dir()):
        missing = []
        if _first_csv(subdir, "edges") is None:
            missing.append("edges")
        if _first_csv(subdir, "nodes") is None:
            missing.append("nodes")
        if missing:
            problems.append((subdir.name, f"missing {' and '.join(missing)} CSV"))
    return problems


def load_version(version_id: str) -> dict[str, Any]:
    """Load edges/nodes/elements for a network version by its directory name."""
    for version in list_versions():
        if version["id"] == version_id:
            edges_df = load_edges(version["edges"])
            nodes_df = build_node_table(edges_df, version["nodes"], require_nodes_csv=True)
            return {
                "version": version,
                "edges": edges_df,
                "nodes": nodes_df,
                "elements": build_cytoscape_elements(edges_df, nodes_df),
            }
    raise KeyError(f"Pathway network version '{version_id}' not found.")
