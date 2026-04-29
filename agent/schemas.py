"""
Pydantic schemas for the AI Product Safety Advisor.

Fields:
- query_language       : detected language of the input query
- query_classification : pre-LLM classification (PRODUCT_SAFETY | GENERAL_CHILDCARE | DANGEROUS)
- recommendation       : SAFE | NOT_SUITABLE | UNCERTAIN
- confidence           : float in [0, 1]
- safety_flags         : list of triggered rule identifiers
- reasoning            : concise internal reasoning summary (LLM-facing)
- reasoning_trace      : ordered list of reasoning steps
- alternatives         : safer product alternatives when NOT_SUITABLE
- user_explanation     : 1-2 sentence plain-English summary for parents
- advice               : single actionable instruction for the parent
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Recommendation(str, Enum):
    SUITABLE = "SUITABLE"
    SAFE = "SUITABLE"
    NOT_SUITABLE = "NOT_SUITABLE"
    UNCERTAIN = "UNCERTAIN"


class QueryClassification(str, Enum):
    PRODUCT_SAFETY = "PRODUCT_SAFETY"
    GENERAL_CHILDCARE = "GENERAL_CHILDCARE"
    DANGEROUS = "DANGEROUS"


class AlternativeProduct(BaseModel):
    product_id: str = Field(..., description="Catalog product ID")
    name: str = Field(..., description="Product display name")
    reason: str = Field(..., description="Why this is a safer alternative")


class SafetyResponse(BaseModel):
    """
    Structured safety recommendation returned to the UI and callers.
    All fields are required — no optional holes that could silently hide unsafe state.
    """

    query_language: str = Field(
        default="en",
        description="ISO 639-1 language code of the input query",
    )
    query_classification: QueryClassification = Field(
        ...,
        description="Pre-LLM classification: PRODUCT_SAFETY | GENERAL_CHILDCARE | DANGEROUS",
    )
    recommendation: Recommendation = Field(
        ...,
        description="Final safety recommendation after all overrides applied",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score in [0, 1]. Hard-override paths always set 1.0.",
    )
    safety_flags: List[str] = Field(
        default_factory=list,
        description="Machine-readable identifiers for triggered safety rules",
    )
    reasoning: str = Field(
        ...,
        description="Internal reasoning summary — NOT shown directly to parents",
    )
    reasoning_trace: List[str] = Field(
        default_factory=list,
        description="Ordered reasoning steps including any override notes",
    )
    alternatives: List[AlternativeProduct] = Field(
        default_factory=list,
        description="Safer alternatives, populated when recommendation is NOT_SUITABLE",
    )

    # ── Human-facing fields ────────────────────────────────────────────────────
    user_explanation: str = Field(
        ...,
        description=(
            "1-2 sentences in plain English for a parent. "
            "States clearly whether the product/action is safe and why."
        ),
    )
    advice: str = Field(
        ...,
        description=(
            "One actionable instruction tailored to the recommendation outcome. "
            "Never vague. Never just a copy of reasoning."
        ),
    )

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 4)

    @field_validator("safety_flags", mode="before")
    @classmethod
    def deduplicate_flags(cls, v: list) -> list:
        seen: set = set()
        result = []
        for flag in v:
            if flag not in seen:
                seen.add(flag)
                result.append(flag)
        return result

    class Config:
        use_enum_values = True