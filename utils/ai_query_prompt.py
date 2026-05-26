"""
Prompt builder for AI Query intent planning.
"""

from __future__ import annotations

from utils.ai_query_templates import get_template_catalog_for_prompt


PLAN_PROMPT_SCHEMA = """
Return JSON only. No markdown. No explanation.

JSON shape:
{
  "intent": "one of the available intent names",
  "gene": null,
  "gene_a": null,
  "gene_b": null,
  "chromosome": null,
  "sv_type": null,
  "phenotype": null,
  "race": null,
  "gender": null,
  "family_id": null,
  "sample": null,
  "role": "any",
  "flank_bp": 0,
  "limit": 50,
  "visualization_kind": "none",
  "confidence": 0.0
}
"""

SCHEMA_NOTES = """
Database notes:
- genes columns: id, chrom, x1, x2, length, strand
- phenotype columns: family_id, part_id, bio_id, bam_id, pheno, child, proband, affected, gender, race
- phenotype_svs columns: sample, id, type, chrom, start, end, length, likelihood, methods, freq, pheno, gender
- background_svs columns: sample, id, type, chrom, start, end, length, likelihood, methods, freq, pheno, gender, pop_code, superpop_code
- phenotype_svs.sample matches phenotype.bam_id
- genes.x1/x2 are gene coordinates
- phenotype_svs.start/end are SV coordinates
- child=1 means child, child=0 means parent
- Use role='mother' for child=0 and gender='F'
- Use role='father' for child=0 and gender='M'
- For 'inside gene', use svs_contained_in_gene_window
- For 'overlap', 'affecting', or 'near gene', use svs_overlapping_gene_window
- Optional visualization_kind values: none, bar_chart, pie_chart, histogram, scatter_plot, igv_gene_window, family_igv_compare, population_igv_gene_window
"""


def build_plan_prompt(user_question: str) -> str:
    return f"""
You are an intent planner for OFC-SV Explorer.
Do not write SQL.
Choose the best query intent and extract arguments.

{SCHEMA_NOTES}

{get_template_catalog_for_prompt()}

{PLAN_PROMPT_SCHEMA}

User question:
{user_question.strip()}
""".strip()
