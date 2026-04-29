"""Pydantic schemas for structured output validation."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class SafetyFlag(str, Enum):
    CHOKING_HAZARD = "choking_hazard"
    AGE_INAPPROPRIATE = "age_inappropriate"
    MATERIAL_CONCERN = "material_concern"
    WEIGHT_LIMIT = "weight_limit"
    SUPERVISION_REQUIRED = "supervision_required"
    INSUFFICIENT_DATA = "insufficient_data"
    RECALL_ALERT = "recall_alert"
    BATTERY_HAZARD = "battery_hazard"


class Recommendation(str, Enum):
    SUITABLE = "SUITABLE"
    NOT_SUITABLE = "NOT_SUITABLE"
    UNCERTAIN = "UNCERTAIN"


class AlternativeProduct(BaseModel):
    product_id: str = Field(description="Product ID of the alternative")
    name: str = Field(description="Product name")
    reason: str = Field(description="Why this is a better fit")


class AdvisorResponse(BaseModel):
    query_language: str = Field(description="Detected language: 'en' or 'ar'")
    product_id: Optional[str] = Field(default=None, description="Product being evaluated")
    product_name: Optional[str] = Field(default=None, description="Product name")
    recommendation: Recommendation = Field(description="SUITABLE / NOT_SUITABLE / UNCERTAIN")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    reasoning: str = Field(description="Summary explanation in user's language")
    reasoning_trace: list[str] = Field(
        default_factory=list,
        description="Step-by-step reasoning trace showing how the decision was made"
    )
    rule_applied: list[str] = Field(default_factory=list, description="Rules triggered (e.g. min_age_violation)")
    safety_flags: list[SafetyFlag] = Field(default_factory=list)
    age_range_months: Optional[str] = Field(default=None, description="e.g. '6-36'")
    alternatives: list[AlternativeProduct] = Field(default_factory=list)
    disclaimer: str = Field(
        default="Always verify product safety with manufacturer guidelines. | تحقق دائماً من سلامة المنتج مع إرشادات الشركة المصنعة."
    )
