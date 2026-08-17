"""
Curated case study content loader backed by a committed local folder.

Case-study JSON files and the optional ``SUMMARY.xlsx`` / ``SUMMARY.csv`` table
live in the repository's ``case_studies/`` folder (committed to Git) and are
read directly at runtime. Content is local-only; there is no OneDrive/rclone
refresh step.

Besides per-case JSON files, the folder may contain a ``SUMMARY.xlsx`` or
``SUMMARY.csv`` file (xlsx preferred) describing the curated case-study genes;
``load_case_study_summary()`` reads it into a table the Case Study page renders.

Configuration (os.environ or a gitignored rclone/.env file):

    CASE_STUDY_CACHE_DIR   local case-study folder (default: case_studies)
"""

from __future__ import annotations

import csv
import json
import os
import pathlib
from typing import Any

from .xlsx_reader import read_xlsx

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]

SUMMARY_FILE_NAMES = ("SUMMARY.xlsx", "SUMMARY.csv")
DEFAULT_CACHE_DIR = PROJECT_ROOT / "case_studies"
ENV_FILE = PROJECT_ROOT / "rclone" / ".env"

_REQUIRED_TOP_LEVEL = ("title", "sections")


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
    return pathlib.Path(_getenv("CASE_STUDY_CACHE_DIR", str(DEFAULT_CACHE_DIR)))


def _iter_study_files():
    cache = cache_dir()
    if not cache.is_dir():
        return
    for path in sorted(cache.glob("*.json")):
        yield path


def _validate_case_study(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    for key in _REQUIRED_TOP_LEVEL:
        if not data.get(key):
            return False
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        return False
    for section in sections:
        if not isinstance(section, dict) or not section.get("heading"):
            return False
    return True


def _read_study(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not _validate_case_study(data):
        return None
    return data


def load_case_study(case_id: str) -> dict[str, Any] | None:
    """Load and validate a case study by its key (the JSON filename stem)."""
    for path in _iter_study_files():
        if path.stem == case_id:
            return _read_study(path)
    return None


def invalid_study_files() -> list[tuple[str, str]]:
    """Return [(filename, reason)] for cache JSONs that fail to parse/validate."""
    problems: list[tuple[str, str]] = []
    for path in _iter_study_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append((path.name, f"invalid JSON ({exc.msg} at line {exc.lineno})"))
            continue
        except OSError as exc:
            problems.append((path.name, f"could not read file ({exc})"))
            continue
        if not _validate_case_study(data):
            problems.append((path.name, "missing required fields: 'title' and non-empty 'sections'"))
    return problems


def list_case_studies() -> list[dict[str, Any]]:
    """Return sorted [{id, title, label, path}] from valid cached JSON files.

    The case-study key is the JSON filename stem; ``title`` is the display label.
    """
    studies: list[dict[str, Any]] = []
    for path in _iter_study_files():
        data = _read_study(path)
        if data is None:
            continue
        case_id = path.stem
        title = data.get("title") or case_id
        studies.append({"id": case_id, "title": title, "label": title, "path": str(path)})
    studies.sort(key=lambda study: study["id"].lower())
    return studies


def summary_file() -> pathlib.Path | None:
    """Return the curated summary file in the cache (xlsx preferred), or None."""
    for name in SUMMARY_FILE_NAMES:
        candidate = cache_dir() / name
        if candidate.is_file():
            return candidate
    return None


def load_case_study_summary() -> dict[str, Any] | None:
    """Load the curated case-study summary table into {"file", "columns", "rows"}.

    Reads ``SUMMARY.xlsx`` (via the dependency-free xlsx reader) or falls back
    to ``SUMMARY.csv`` in the cache. Returns None when no summary file is
    present or it cannot be parsed; unreadable files never raise.
    """
    path = summary_file()
    if path is None:
        return None
    try:
        if path.suffix.lower() == ".xlsx":
            rows = read_xlsx(path)
        else:
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = [dict(row) for row in csv.DictReader(handle)]
    except Exception:
        return None
    if not rows:
        return None
    columns = [column for column in rows[0].keys() if str(column).strip()]
    return {"file": path.name, "columns": columns, "rows": rows}
