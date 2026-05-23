from __future__ import annotations

from uuid import UUID

from underwright.application.modules.policy_rules_module import PolicyRulesModule
from underwright.domain.policy_rules import PolicyRule, PolicyRuleOutcome
from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.quote_request import QuoteRequest

REQUEST_ID = UUID("92000000-0000-0000-0000-000000000001")


def quote_context(asset_updates: dict | None = None) -> QuoteCaseContext:
    quote_request = QuoteRequest(
        request_id=REQUEST_ID,
        client_id=1001,
        client_data={
            "full_name": "Ion Popescu",
            "email": "ion@example.test",
            "phone": "+40700000000",
        },
        asset_data={
            "asset_type": "Apartment",
            "usage_type": "Owner occupied",
            "construction_type": "Concrete",
            "year_built": 1998,
            "area_sqm": 70,
            "declared_value": 300000,
            "occupancy": "Owner occupied",
            "previous_claims_count": 0,
        },
    )
    if asset_updates:
        quote_request.asset_data.update(asset_updates)
    context = QuoteCaseContext()
    context.reference_data.quote_request = quote_request.model_dump(mode="json")
    return context


def test_policy_rule_domain_models_store_structured_outcome() -> None:
    rule = PolicyRule(
        policy_rule_id="property_claims_standard",
        version="mvp_quote_rules_v1",
        category="claims_history",
        condition="asset_data.previous_claims_count <= 5",
        outcome="standard",
        explanation="Claims history is within standard quote bounds.",
    )

    outcome = PolicyRuleOutcome(
        matched_rules=[rule],
        rule_version="mvp_quote_rules_v1",
        recommended_actions=["auto_accept"],
    )

    assert outcome.is_standard
    assert outcome.model_dump(mode="json")["matched_rules"][0][
        "policy_rule_id"
    ] == "property_claims_standard"


def test_standard_quote_produces_auto_accept_action() -> None:
    context = quote_context()

    result = PolicyRulesModule().evaluate(context)

    assert result.status == "success"
    assert context.domain_payload.rule_outcomes["nonstandard_rules"] == []
    assert context.domain_payload.rule_outcomes["recommended_actions"] == [
        "auto_accept"
    ]
    assert context.checks_and_warnings.rule_warnings == []


def test_nonstandard_quote_reports_review_rules() -> None:
    context = quote_context(
        {
            "usage_type": "Vacant",
            "construction_type": "Wood",
            "year_built": 1965,
            "previous_claims_count": 6,
        }
    )

    result = PolicyRulesModule().evaluate(context)

    assert result.status == "success"
    rule_ids = {
        rule["policy_rule_id"]
        for rule in context.domain_payload.rule_outcomes["nonstandard_rules"]
    }
    assert {
        "property_built_before_1975",
        "property_claims_gt_5",
        "vacant_property_use",
        "wood_construction",
    }.issubset(rule_ids)
    assert context.domain_payload.rule_outcomes["recommended_actions"] == [
        "underwriter_review"
    ]


def test_missing_required_quote_data_is_reported() -> None:
    context = quote_context({"declared_value": 0})

    PolicyRulesModule().evaluate(context)

    assert "asset_data.declared_value" in context.domain_payload.rule_outcomes[
        "missing_required_fields"
    ]
    assert context.domain_payload.rule_outcomes["failed_rules"][0][
        "policy_rule_id"
    ] == "quote_required_fields_missing"


def test_unsupported_property_country_auto_rejects() -> None:
    context = quote_context(
        {
            "address": {
                "country": "Bulgaria",
                "county": "Sofia",
                "city": "Sofia",
                "street": "Test",
                "number": "1",
                "postal_code": "1000",
                "full_text": "Test 1, Sofia",
            }
        }
    )

    PolicyRulesModule().evaluate(context)

    assert context.domain_payload.rule_outcomes["exclusion_flags"] == [
        "unsupported_property_country"
    ]
    assert context.domain_payload.rule_outcomes["recommended_actions"] == [
        "auto_reject"
    ]
