"""
Query plan model and validation helpers for AI Query.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Optional, Set

try:
    from pydantic import BaseModel, Field
    _HAS_PYDANTIC = True
except ImportError:  # pragma: no cover - fallback when pydantic is unavailable
    BaseModel = object
    Field = None
    _HAS_PYDANTIC = False


ALLOWED_SV_TYPES: Set[str] = {"DEL", "DUP", "INS", "INV", "BND"}
ALLOWED_ROLES: Set[str] = {"child", "parent", "mother", "father", "any"}


if _HAS_PYDANTIC:

    class QueryPlan(BaseModel):
        intent: str = Field(..., description="The selected query intent/template name")

        gene: Optional[str] = None
        gene_a: Optional[str] = None
        gene_b: Optional[str] = None

        chromosome: Optional[str] = None
        sv_type: Optional[str] = None
        phenotype: Optional[str] = None
        race: Optional[str] = None
        gender: Optional[str] = None
        family_id: Optional[str] = None
        sample: Optional[str] = None

        role: Optional[Literal["child", "parent", "mother", "father", "any"]] = "any"

        flank_bp: int = 0
        limit: int = 50

        result_kind: Optional[Literal["scalar", "table", "distribution"]] = "table"
        visualization_kind: Optional[str] = "none"

        confidence: float = 0.0

else:

    @dataclass
    class QueryPlan:
        intent: str

        gene: Optional[str] = None
        gene_a: Optional[str] = None
        gene_b: Optional[str] = None

        chromosome: Optional[str] = None
        sv_type: Optional[str] = None
        phenotype: Optional[str] = None
        race: Optional[str] = None
        gender: Optional[str] = None
        family_id: Optional[str] = None
        sample: Optional[str] = None

        role: Optional[Literal["child", "parent", "mother", "father", "any"]] = "any"

        flank_bp: int = 0
        limit: int = 50

        result_kind: Optional[Literal["scalar", "table", "distribution"]] = "table"
        visualization_kind: Optional[str] = "none"

        confidence: float = 0.0

        def model_dump(self) -> dict[str, Any]:
            return asdict(self)


def normalize_gene(value: str | None) -> str | None:
    return value.strip().upper() if value else None


def normalize_chromosome(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.startswith("chr"):
        return value
    return f"chr{value}"


def validate_plan(plan: QueryPlan, supported_intents: set[str]) -> QueryPlan:
    if plan.intent not in supported_intents:
        raise ValueError(f"Unsupported intent: {plan.intent}")

    plan.gene = normalize_gene(plan.gene)
    plan.gene_a = normalize_gene(plan.gene_a)
    plan.gene_b = normalize_gene(plan.gene_b)
    plan.chromosome = normalize_chromosome(plan.chromosome)

    if plan.sv_type:
        plan.sv_type = plan.sv_type.upper()
        if plan.sv_type not in ALLOWED_SV_TYPES:
            raise ValueError(f"Unsupported SV type: {plan.sv_type}")

    if plan.role and plan.role not in ALLOWED_ROLES:
        plan.role = "any"

    if plan.limit <= 0:
        plan.limit = 50
    if plan.limit > 500:
        plan.limit = 500

    if plan.flank_bp < 0:
        plan.flank_bp = 0
    if plan.flank_bp > 100000:
        plan.flank_bp = 100000

    return plan


def plan_to_dict(plan: QueryPlan) -> dict[str, Any]:
    if hasattr(plan, "model_dump"):
        return plan.model_dump()
    return plan.__dict__
