from __future__ import annotations

from underwright.domain.quote_risk import build_quote_risk_assessment


def test_quote_risk_uses_known_policy_rule_deductions() -> None:
    assessment = build_quote_risk_assessment(
        {
            "rule_version": "mvp_quote_rules_v1",
            "recommended_actions": ["underwriter_review"],
            "failed_rules": [],
            "nonstandard_rules": [
                {
                    "policy_rule_id": "property_claims_gt_5",
                    "severity": "high",
                    "explanation": "More than 5 property claims requires underwriting review.",
                },
                {
                    "policy_rule_id": "vacant_property_use",
                    "severity": "medium",
                    "explanation": "Vacant property use increases exposure and requires review.",
                },
            ],
        }
    )

    assert assessment.score == 55
    assert assessment.level == "High"
    assert assessment.requires_manual_review is True
    assert assessment.triggered_rules == [
        "property_claims_gt_5",
        "vacant_property_use",
    ]
    assert assessment.source == "backend"


def test_quote_risk_falls_back_to_severity_for_future_rules() -> None:
    assessment = build_quote_risk_assessment(
        {
            "rule_version": "future_rules_v1",
            "recommended_actions": ["auto_accept"],
            "nonstandard_rules": [
                {
                    "policy_rule_id": "future_rule",
                    "severity": "low",
                    "explanation": "Future low severity rule.",
                }
            ],
        }
    )

    assert assessment.score == 95
    assert assessment.level == "Low"
    assert assessment.requires_manual_review is False
