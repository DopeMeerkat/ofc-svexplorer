"""Shared constants for the finalized 41-gene curated table."""

CURATED_TABLE_PATH = "assets/table1_41.csv"

CURATED_TABLE_FOOTNOTES = [
    "1. Gene annotations are from https://www.genecards.org.",
    "2. Multi-SV means more than one SV present (i.e., FusorSV_ids) and multi-sample means the SVs are either shared by multiple samples or there are one sample per the multiple SVs.",
    "3. OFCL 1 means that it is already linked to OFC in mouse or human by literature.",
    "4. Palate tissue NCC scRNA long expression.",
]


def curated_table_footnote_lines():
    """Return display-ready footnote lines for the finalized table."""
    return list(CURATED_TABLE_FOOTNOTES)
