"""Convert Case_Study_*.docx files into case-study JSON for the Case Study page.

Each .docx is parsed into the page's JSON schema:

    {
      "title": "...",
      "genes": [...],
      "sections": [
        {"heading": "Function", "paragraphs": [...]},
        ...
      ]
    }

Section paragraphs are classified by their leading label (Function, IGV,
Literature, Pathway, Supporting Data). The IGV and Pathway paragraphs are
converted to ``{text, links, suffix}`` objects that link to the Population IGV
page (``/population?gene=<GENE>``) and the Pathway page
(``/pathway?genes=...``). Citation-like paragraphs become a "References"
section, and other unlabeled paragraphs are placed under "EMT" or "Notes".

The "Supporting Data" section is augmented with an evidence table computed with
read-only queries against the local database (exon / enhancer / promoter
overlap at freq <= 0.01) plus a gene-expression finding read from the curated
gene table. This mirrors the TET3 fallback content in ``pages/case_study.py``.

Usage:

    PYTHONPATH=. python scripts/convert_case_study_docx.py \
        --input-dir /path/to/docx \
        [--output-dir case_studies] \
        [--db-path /data/cellvar.db/cellvar.db] \
        [--gene-table pLI/tab_43_genes.csv] \
        [--remote "uconn:.../Data/Case_Study"]

The generated JSON files are written into the committed ``case_studies/``
folder (the default output dir), which the Case Study page reads directly.
When ``--remote`` is given, the generated JSON files (and any SUMMARY.xlsx /
SUMMARY.csv in the output dir) are additionally uploaded with rclone as a
manual OneDrive backup; they are not pulled back automatically. The rclone
binary comes from ``CASE_STUDY_RCLONE_BIN`` or defaults to ``rclone``. The
remote path is read from ``--remote`` or from the gitignored ``rclone/.env``
``CASE_STUDY_RCLONE_REMOTE`` and is never printed.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sqlite3
import subprocess
import zipfile
from typing import Any

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "case_studies"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "case_studies"
DEFAULT_DB_PATH = pathlib.Path("/data/cellvar.db/cellvar.db")
DEFAULT_GENE_TABLE = PROJECT_ROOT / "pLI" / "tab_43_genes.csv"
ENV_FILE = PROJECT_ROOT / "rclone" / ".env"

DOCX_PATTERN = "Case_Study_*.docx"

SECTION_LABELS = ("Function", "IGV", "Literature", "Pathway", "Supporting Data")
SECTION_RE = re.compile(r"^(Function|IGV|Literature|Pathway|Supporting Data):\s*(.*)$", re.S)

IGV_LINK_RE = re.compile(r"^(.*?)Open ([A-Za-z0-9_.\-]+) in IGV(.*)$", re.S)
PATHWAY_LINK_RE = re.compile(r"^(.*?)Click here \(([^)]+)\)(.*)$", re.S)

SUPPORTING_SQL = """
WITH target AS (
    SELECT chrom, CAST(x1 AS INT) AS start, CAST(x2 AS INT) AS end
    FROM genes
    WHERE UPPER(id) = ?
),
target_svs AS (
    SELECT ps.*
    FROM phenotype_svs ps
    JOIN target g ON ps.chrom = g.chrom
        AND ps.start <= g.end
        AND ps."end" >= g.start
    WHERE CAST(COALESCE(ps.freq, 0) AS REAL) <= 0.01
)
SELECT 'Overlapping with exons' AS evidence, COUNT(*) AS overlap_count, COUNT(DISTINCT ps.id) AS distinct_svs
FROM target_svs ps
JOIN exons e ON e.chrom = ps.chrom
    AND ps.start <= e.exon_end
    AND ps."end" >= e.exon_start
UNION ALL
SELECT 'Overlapping with enhancer candidates', COUNT(*), COUNT(DISTINCT ps.id)
FROM target_svs ps
JOIN poised_enhancer_candidates c ON c.chrom = ps.chrom
    AND ps.start <= c.end
    AND ps."end" >= c.start
UNION ALL
SELECT 'Overlapping with active candidates', COUNT(*), COUNT(DISTINCT ps.id)
FROM target_svs ps
JOIN active_enhancer_candidates c ON c.chrom = ps.chrom
    AND ps.start <= c.end
    AND ps."end" >= c.start
UNION ALL
SELECT 'Overlapping with promoter candidates', COUNT(*), COUNT(DISTINCT ps.id)
FROM target_svs ps
JOIN promoter_candidates c ON c.chrom = ps.chrom
    AND ps.start <= c.end
    AND ps."end" >= c.start
"""


def _load_env() -> dict[str, str]:
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


def extract_paragraphs(docx_path: pathlib.Path) -> list[str]:
    """Extract non-empty paragraph text from a .docx using only stdlib."""
    with zipfile.ZipFile(docx_path) as zf:
        try:
            xml = zf.read("word/document.xml").decode("utf-8")
        except KeyError:
            return []

    paragraphs = []
    for block in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", block, re.S))
        text = (
            text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .strip()
        )
        if text:
            paragraphs.append(text)
    return paragraphs


def _gene_from_title(title: str) -> str:
    if " - " in title:
        return title.split(" - ", 1)[0].strip()
    return title.strip()


def _linkify_igv(body: str) -> Any:
    match = IGV_LINK_RE.match(body)
    if not match:
        return body
    gene = match.group(2)
    return {
        "text": match.group(1),
        "links": [{"label": f"Open {gene} in IGV", "href": f"/population?gene={gene}"}],
        "suffix": match.group(3),
    }


def _linkify_pathway(body: str) -> Any:
    match = PATHWAY_LINK_RE.match(body)
    if not match:
        return body
    genes = match.group(2).strip()
    href_genes = ",".join(gene.strip() for gene in genes.split(",") if gene.strip())
    return {
        "text": match.group(1),
        "links": [{"label": f"Click here ({genes})", "href": f"/pathway?genes={href_genes}"}],
        "suffix": match.group(3),
    }


def _pathway_genes(sections: list[dict[str, Any]]) -> list[str]:
    for section in sections:
        for item in section.get("paragraphs", []) or []:
            if not isinstance(item, dict):
                continue
            for link in item.get("links", []) or []:
                href = link.get("href", "")
                if href.startswith("/pathway?genes="):
                    return [gene.strip() for gene in href.split("=", 1)[1].split(",") if gene.strip()]
    return []


def _expression_finding(gene: str, gene_table: pathlib.Path) -> str:
    if not gene_table.is_file():
        return "Not available"
    try:
        with gene_table.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if (row.get("Gene") or "").strip().upper() == gene.upper():
                    try:
                        value = float(row.get("NCC_13.5"))
                    except (TypeError, ValueError):
                        return "Not available"
                    if value >= 7:
                        return f"Highly expressed (NCC E13.5 = {value:.2f})"
                    return f"Detected (NCC E13.5 = {value:.2f})"
    except (OSError, csv.Error):
        pass
    return "Not available"


def _supporting_table(gene: str, db_path: pathlib.Path, gene_table: pathlib.Path) -> dict[str, Any]:
    evidence_rows = []
    if db_path.is_file():
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = conn.execute(SUPPORTING_SQL, (gene,)).fetchall()
            evidence_rows = [
                {"Evidence": row[0], "Finding": "Yes" if int(row[1] or 0) > 0 else "No"}
                for row in rows
            ]
        finally:
            conn.close()
    evidence_rows.append({"Evidence": "Gene expression data (NCC E13.5)", "Finding": _expression_finding(gene, gene_table)})
    return {
        "columns": [{"name": "Evidence", "id": "Evidence"}, {"name": "Finding", "id": "Finding"}],
        "rows": evidence_rows,
    }


def build_study(docx_path: pathlib.Path, db_path: pathlib.Path, gene_table: pathlib.Path) -> dict[str, Any] | None:
    paragraphs = extract_paragraphs(docx_path)
    if not paragraphs:
        return None

    title = paragraphs[0]
    gene = _gene_from_title(title)

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for paragraph in paragraphs[1:]:
        label_match = SECTION_RE.match(paragraph)
        if label_match:
            heading, body = label_match.group(1), label_match.group(2).strip()
            item: Any = body
            if heading == "IGV":
                item = _linkify_igv(body)
            elif heading == "Pathway":
                item = _linkify_pathway(body)
            current = {"heading": heading, "paragraphs": [item]}
            sections.append(current)
            continue

        stripped = paragraph.strip()
        if not stripped or stripped == "--":
            continue
        if "doi" in stripped.lower() or "PMID" in stripped:
            extra_heading = "References"
        elif "EMT" in stripped.upper():
            extra_heading = "EMT"
        else:
            extra_heading = "Notes"
        if current is None or current["heading"] != extra_heading:
            current = {"heading": extra_heading, "paragraphs": []}
            sections.append(current)
        current["paragraphs"].append(stripped)

    for section in sections:
        if section["heading"] == "Supporting Data":
            section["table"] = _supporting_table(gene, db_path, gene_table)

    pathway_genes = _pathway_genes(sections)
    return {
        "title": title,
        "genes": pathway_genes or [gene],
        "sections": sections,
    }


def _rclone_bin() -> str:
    return _load_env().get("CASE_STUDY_RCLONE_BIN", "rclone")


def upload_outputs(output_dir: pathlib.Path, files: list[pathlib.Path], remote: str, rclone_bin: str) -> bool:
    """Copy the given files to OneDrive via ``rclone copy`` (filtered)."""
    if not files:
        return True
    include_flags: list[str] = []
    for path in files:
        include_flags.extend(["--include", path.name])
    proc = subprocess.run(
        [rclone_bin, "copy", str(output_dir), remote, *include_flags],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "unknown rclone error").strip()
        raise RuntimeError(detail)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert case-study .docx files to page JSON.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--gene-table", default=str(DEFAULT_GENE_TABLE))
    parser.add_argument("--remote", default=_load_env().get("CASE_STUDY_RCLONE_REMOTE", ""),
                        help="Optional OneDrive remote to upload outputs to (rclone copy).")
    args = parser.parse_args()

    input_dir = pathlib.Path(args.input_dir)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for docx_path in sorted(input_dir.glob(DOCX_PATTERN)):
        study = build_study(docx_path, pathlib.Path(args.db_path), pathlib.Path(args.gene_table))
        if study is None:
            print(f"Skipped {docx_path.name}: no paragraphs found")
            continue
        gene = _gene_from_title(study["title"])
        out_path = output_dir / f"{gene}.json"
        out_path.write_text(json.dumps(study, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(out_path)
        print(f"Wrote {out_path.name} ({study['title']!r})")

    if args.remote and written:
        upload_files = list(written)
        for name in ("SUMMARY.xlsx", "SUMMARY.csv"):
            candidate = output_dir / name
            if candidate.is_file():
                upload_files.append(candidate)
        try:
            upload_outputs(output_dir, upload_files, args.remote, _rclone_bin())
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"Upload to OneDrive failed: {exc}")
            return
        print(f"Uploaded {len(upload_files)} file(s) to OneDrive: "
              + ", ".join(path.name for path in upload_files))
    elif args.remote:
        print("Nothing to upload (no case studies generated).")


if __name__ == "__main__":
    main()
