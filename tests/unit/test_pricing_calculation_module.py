from __future__ import annotations

from uuid import UUID

from underwright.application.modules.pricing_calculation_module import (
    PricingCalculationModule,
)
from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.quote_pricing import (
    QuotePricingAdjustment,
    QuotePricingResult,
    QuotePricingStep,
)
from underwright.domain.quote_request import QuoteRequest

REQUEST_ID = UUID("93000000-0000-0000-0000-000000000001")


def quote_request(asset_updates: dict | None = None) -> QuoteRequest:
    request = QuoteRequest(
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
        pricing_preview={
            "request_details": {
                "coverage_amount": 300000,
                "security_features": ["Alarm", "Smoke detector", "Sprinklers"],
            }
        },
    )
    if asset_updates:
        request.asset_data.update(asset_updates)
    return request


def quote_context(request: QuoteRequest) -> QuoteCaseContext:
    context = QuoteCaseContext()
    context.reference_data.quote_request = request.model_dump(mode="json")
    context.domain_payload.rule_outcomes = {
        "rule_version": "mvp_quote_rules_v1",
        "recommended_actions": ["auto_accept"],
        "nonstandard_rules": [],
    }
    context.domain_payload.quote_intake_payload = request.model_dump(mode="json")
    return context


def test_quote_pricing_domain_models_store_calculation() -> None:
    result = QuotePricingResult(
        base_premium=600,
        pricing_adjustments=[
            QuotePricingAdjustment(
                code="property_use_multiplier",
                label="Property use",
                adjustment_type="multiplier",
                value=1.0,
                amount=0,
                explanation="Property use multiplier: 1.00.",
            )
        ],
        final_premium=570,
        calculation_steps=[
            QuotePricingStep(
                step_name="base_premium",
                input_value=300000,
                output_value=600,
                explanation="Base premium equals coverage amount x 0.2%.",
            )
        ],
        rule_version="mvp_quote_rules_v1",
        calculation_year=2026,
    )

    serialized = result.model_dump(mode="json")

    assert serialized["base_premium"] == 600
    assert serialized["final_premium"] == 570
    assert serialized["pricing_adjustments"][0]["code"] == ("property_use_multiplier")


def test_standard_quote_pricing_is_reproducible_and_updates_preview() -> None:
    request = quote_request()
    context = quote_context(request)

    result = PricingCalculationModule().calculate(request, context)

    assert result.status == "success"
    assert context.generated_outputs.pricing_outputs.base_premium == 600
    assert context.generated_outputs.pricing_outputs.final_premium == 513
    assert request.pricing_preview["estimated_premium"] == 513
    assert request.pricing_preview["pricing_status"] == "authoritative"
    assert request.pricing_preview["pricing"]["source"] == "backend"
    assert request.pricing_preview["pricing"]["securityDiscountPercent"] == 0.10
    assert request.pricing_preview["pricing_result"]["rule_version"] == (
        "mvp_quote_rules_v1"
    )
    assert request.pricing_preview["risk_assessment"]["source"] == "backend"
    assert request.risk["score"] == 100


def test_pricing_requires_positive_backend_coverage_value() -> None:
    request = quote_request({"declared_value": 0})
    request.pricing_preview["request_details"]["coverage_amount"] = 0
    context = quote_context(request)

    result = PricingCalculationModule().calculate(request, context)

    assert result.status == "failed"
    assert "positive declared value or coverage amount" in result.summary
    assert request.pricing is None


def test_backend_declared_value_wins_over_submitted_preview_values() -> None:
    request = quote_request()
    request.pricing_preview["request_details"]["coverage_amount"] = 900000
    request.pricing_preview["pricing"] = {
        "basePremium": 9999,
        "finalPremium": 9999,
    }
    context = quote_context(request)

    PricingCalculationModule().calculate(request, context)

    assert context.generated_outputs.pricing_outputs.base_premium == 600
    assert context.generated_outputs.pricing_outputs.final_premium == 513
    assert request.pricing_preview["pricing"]["finalPremium"] == 513


def test_nonstandard_quote_pricing_shows_surcharge() -> None:
    request = quote_request({"previous_claims_count": 6})
    context = quote_context(request)

    PricingCalculationModule().calculate(request, context)

    assert request.pricing_preview["pricing"]["claimsMultiplier"] == 1.25
    assert request.pricing_preview["pricing"]["manualReviewSurcharge"] == 100
    assert context.generated_outputs.pricing_outputs.final_premium == 741


def test_property_type_and_size_adjust_pricing() -> None:
    request = quote_request({"asset_type": "House", "area_sqm": 145})
    context = quote_context(request)

    PricingCalculationModule().calculate(request, context)

    pricing = request.pricing_preview["pricing"]
    assert pricing["propertyTypeMultiplier"] == 1.08
    assert pricing["sizeMultiplier"] == 1.08
    assert pricing["finalPremium"] == 598
    assert any(
        adjustment["code"] == "property_type_multiplier"
        for adjustment in pricing["adjustments"]
    )
    assert any(
        adjustment["code"] == "size_multiplier" for adjustment in pricing["adjustments"]
    )
