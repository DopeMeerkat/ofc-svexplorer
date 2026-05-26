"""
Rule-based shortcuts for common AI Query intents.
"""

from __future__ import annotations


def rule_based_plan(user_text: str):
    text = user_text.lower()

    if "shortest gene" in text:
        return {"intent": "shortest_gene", "limit": 1, "confidence": 1.0}

    if "longest gene" in text:
        return {"intent": "longest_gene", "limit": 1, "confidence": 1.0}

    if "gene distribution" in text and "chromosome" in text:
        return {"intent": "gene_distribution_by_chromosome", "confidence": 1.0}

    return None
