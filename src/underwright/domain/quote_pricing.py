from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PricingAdjustmentType = Literal["multiplier", "discount", "surcharge"]


class QuotePricingAdjustment(BaseModel):
    """One deterministic premium adjustment applied during quote pricing."""

    code: str
    label: str
    adjustment_type: PricingAdjustmentType
    value: float
    amount: float
    explanation: str


class QuotePricingStep(BaseModel):
    """Auditable step in the deterministic quote premium calculation."""

    step_name: str
    input_value: float | str | int | None = None
    output_value: float
    explanation: str


class QuotePricingResult(BaseModel):
    """Versioned deterministic premium output for a quote request."""

    base_premium: float
    pricing_adjustments: list[QuotePricingAdjustment] = Field(default_factory=list)
    deductible_adjustments: list[dict[str, float | str]] = Field(default_factory=list)
    final_premium: float
    calculation_steps: list[QuotePricingStep] = Field(default_factory=list)
    rule_version: str
    pricing_rationale: list[str] = Field(default_factory=list)
    currency: str = "RON"
    calculation_year: int


__all__ = [
    "PricingAdjustmentType",
    "QuotePricingAdjustment",
    "QuotePricingResult",
    "QuotePricingStep",
]
