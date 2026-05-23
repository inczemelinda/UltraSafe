from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RuleSeverity = Literal["info", "low", "medium", "high", "hard"]


class PolicyRule(BaseModel):
    """Deterministic quote policy rule definition or matched rule receipt."""

    policy_rule_id: str
    version: str
    category: str
    condition: str
    outcome: str
    severity: RuleSeverity = "info"
    explanation: str


class PolicyRuleOutcome(BaseModel):
    """Structured result of deterministic quote rule matching."""

    matched_rules: list[PolicyRule] = Field(default_factory=list)
    failed_rules: list[PolicyRule] = Field(default_factory=list)
    nonstandard_rules: list[PolicyRule] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    missing_required_evidence: list[str] = Field(default_factory=list)
    coverage_flags: list[str] = Field(default_factory=list)
    exclusion_flags: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    rule_version: str

    @property
    def is_standard(self) -> bool:
        return not (
            self.failed_rules
            or self.nonstandard_rules
            or self.missing_required_fields
            or self.exclusion_flags
        )


__all__ = [
    "PolicyRule",
    "PolicyRuleOutcome",
    "RuleSeverity",
]
