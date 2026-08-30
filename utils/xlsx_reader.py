"""
Minimal .xlsx reader using only the Python standard library.

Reads the first worksheet of an .xlsx file into a list of dict rows. By default
the header row is auto-detected: leading rows with fewer than two non-empty
cells (e.g. a merged title row) are skipped, and the first data-bearing row
becomes the column headers. An explicit ``header_row`` (0-based) can override
this. Handles shared strings, inline strings, numbers, and booleans. Kept
dependency-free so the app does not require openpyxl/xlrd.
"""

from __future__ import annotations

import zipfile
from typing import Any
import xml.etree.ElementTree as ET

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_M = f"{{{_NS}}}"


def _col_index(letters: str) -> int:
    index = 0
    for char in letters.upper():
        index = index * 26 + (ord(char) - 64)
    return index - 1


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except (KeyError, ET.ParseError):
        return []
    strings: list[str] = []
    for si in root.findall(f"{_M}si"):
        text = "".join(node.text or "" for node in si.iter(f"{_M}t"))
        strings.append(text)
    return strings


def _sheet_targets(zf: zipfile.ZipFile) -> list[str]:
    try:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    except (KeyError, ET.ParseError):
        return []
    id_to_target = {}
    for rel in rels:
        rid = rel.get("Id")
        target = rel.get("Target")
        if rid and target:
            if not target.startswith("/"):
                target = "xl/" + target
            id_to_target[rid] = target
    targets = []
    sheets = wb.find(f"{_M}sheets")
    if sheets is not None:
        for sheet in sheets:
            rid = sheet.get(f"{{{_REL}}}id")
            if rid in id_to_target:
                targets.append(id_to_target[rid])
    return targets


def _cell_value(cell: ET.Element, shared: list[str]) -> Any:
    cell_type = cell.get("t")
    value_node = cell.find(f"{_M}v")
    if cell_type == "inlineStr":
        inline = cell.find(f"{_M}is")
        if inline is None:
            return ""
        return "".join(node.text or "" for node in inline.iter(f"{_M}t"))
    if value_node is None:
        return ""
    text = (value_node.text or "").strip()
    if cell_type == "s":
        try:
            return shared[int(text)]
        except (ValueError, IndexError):
            return ""
    if cell_type == "b":
        return text == "1"
    return text


def _has_content(cells: dict[int, Any]) -> bool:
    return any(str(value).strip() for value in cells.values())


def read_xlsx(path, header_row: int | None = None) -> list[dict[str, Any]]:
    """Read the first worksheet of ``path`` into a list of header-keyed dicts.

    ``header_row`` is 0-based and overrides auto-detection. When ``None``, rows
    with fewer than two non-empty cells before the first data-bearing row (for
    example a merged title row) are treated as non-header rows and skipped.
    """
    with zipfile.ZipFile(path) as zf:
        shared = _shared_strings(zf)
        targets = _sheet_targets(zf)
        if not targets:
            return []
        root = ET.fromstring(zf.read(targets[0]))
        sheet_data = root.find(f"{_M}sheetData")

        parsed_rows: list[tuple[dict[int, Any], int]] = []
        for row in sheet_data or []:
            row_cells: dict[int, Any] = {}
            max_col = -1
            for cell in row.findall(f"{_M}c"):
                ref = cell.get("r") or ""
                letters = "".join(char for char in ref if char.isalpha())
                if not letters:
                    continue
                index = _col_index(letters)
                row_cells[index] = _cell_value(cell, shared)
                max_col = max(max_col, index)
            parsed_rows.append((row_cells, max_col))

        if not parsed_rows:
            return []

        if header_row is None:
            header_index = next(
                (index for index, (cells, _) in enumerate(parsed_rows)
                 if sum(1 for value in cells.values() if str(value).strip()) >= 2),
                0,
            )
        else:
            header_index = header_row
        if header_index >= len(parsed_rows):
            return []

        header_cells, _ = parsed_rows[header_index]
        width = max(row_max + 1 for _, row_max in parsed_rows)
        headers = [str(header_cells.get(index, "")).strip() for index in range(width)]

        records: list[dict[str, Any]] = []
        for row_cells, _ in parsed_rows[header_index + 1:]:
            if not _has_content(row_cells):
                continue
            records.append({header: row_cells.get(index, "") for index, header in enumerate(headers)})
        return records
