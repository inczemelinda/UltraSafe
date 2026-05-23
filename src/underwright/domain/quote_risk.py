from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


QuoteRiskLevel = Literal["Low", "Medium", "High"]


class QuoteRiskAssessment(BaseModel):
    """Authoritative deterministic quote risk derived from policy rules."""

    score: int
    level: QuoteRiskLevel
    reasons: list[str] = Field(default_factory=list)
    triggered_rules: list[str] = Field(default_factory=list)
    requires_manual_review: bool
    recommendation: str
    rule_version: str | None = None
    source: Literal["backend"] = "backend"

    def frontend_payload(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data.update(
            {
                "risk_score": self.score,
                "riskScore": self.score,
                "risk_level": self.level,
                "riskLevel": self.level,
                "triggeredRules": self.reasons,
                "requiresManualReview": self.requires_manual_review,
                "ruleVersion": self.rule_version,
            }
        )
        return data


RULE_SCORE_DEDUCTIONS = {
    "unsupported_property_country": 100,
    "property_claims_gt_5": 30,
    "property_built_before_1975": 20,
    "vacant_property_use": 15,
    "wood_construction": 10,
    "quote_required_fields_missing": 30,
}

SEVERITY_SCORE_DEDUCTIONS = {
    "high": 30,
    "hard": 100,
    "medium": 15,
    "low": 5,
    "info": 0,
}


def build_quote_risk_assessment(
    rule_outcome: dict[str, Any],
) -> QuoteRiskAssessment:
    rule_version = _string(rule_outcome.get("rule_version")) or None
    triggered_rules = _unique_rules(
        [
            *_list_of_dicts(rule_outcome.get("failed_rules")),
            *_list_of_dicts(rule_outcome.get("nonstandard_rules")),
        ]
    )

    score = 100
    reasons: list[str] = []
    rule_ids: list[str] = []
    for rule in triggered_rules:
        rule_id = _string(rule.get("policy_rule_id"))
        if not rule_id:
            continue
        score -= _deduction_for_rule(rule)
        rule_ids.append(rule_id)
        explanation = _string(rule.get("explanation"))
        if explanation:
            reasons.append(explanation)

    score = max(0, min(100, score))
    level = _level_for_score(score)
    recommended_actions = {
        str(action) for action in _list(rule_outcome.get("recommended_actions"))
    }
    requires_manual_review = (
        False
        if "auto_reject" in recommended_actions
        else "underwriter_review" in recommended_actions or score <= 70
    )

    return QuoteRiskAssessment(
        score=score,
        level=level,
        reasons=reasons or ["No backend policy risk rules were triggered."],
        triggered_rules=rule_ids,
        requires_manual_review=requires_manual_review,
        recommendation=(
            "Quote cannot be accepted under hard eligibility rules."
            if "auto_reject" in recommended_actions
            else (
                "Manual underwriting review recommended before approval."
                if requires_manual_review
                else "Quote can be accepted automatically."
            )
        ),
        rule_version=rule_version,
    )


def _deduction_for_rule(rule: dict[str, Any]) -> int:
    rule_id = _string(rule.get("policy_rule_id"))
    if rule_id in RULE_SCORE_DEDUCTIONS:
        return RULE_SCORE_DEDUCTIONS[rule_id]
    severity = _string(rule.get("severity")).lower()
    return SEVERITY_SCORE_DEDUCTIONS.get(severity, 0)


def _level_for_score(score: int) -> QuoteRiskLevel:
    if score > 80:
        return "Low"
    if score > 70:
        return "Medium"
    return "High"


def _unique_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in rules:
        rule_id = _string(rule.get("policy_rule_id"))
        if rule_id and rule_id in seen:
            continue
        if rule_id:
            seen.add(rule_id)
        unique.append(rule)
    return unique


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in _list(value) if isinstance(item, dict)]


def _string(value: Any) -> str:
    return value if isinstance(value, str) else "" if value is None else str(value)


__all__ = [
    "QuoteRiskAssessment",
    "QuoteRiskLevel",
    "build_quote_risk_assessment",
]
