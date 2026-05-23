from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from underwright.domain.module_result import ModuleResult
from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.quote_pricing import (
    QuotePricingAdjustment,
    QuotePricingResult,
    QuotePricingStep,
)
from underwright.domain.quote_request import QuoteRequest
from underwright.domain.quote_risk import build_quote_risk_assessment


class PricingCalculationModule:
    """Calculates deterministic MVP quote premiums from request values."""

    module_name = "PricingCalculationModule"

    RULE_VERSION = "mvp_quote_rules_v1"
    BASE_RATE = 0.002
    MAX_SECURITY_DISCOUNT = 0.10

    property_type_multipliers = {
        "apartment": 1.0,
        "house": 1.08,
        "commercial": 1.25,
    }
    usage_multipliers = {
        "owner occupied": 1.0,
        "rented": 1.10,
        "holiday home": 1.10,
        "vacant": 1.30,
        "commercial use": 1.25,
    }
    construction_multipliers = {
        "concrete": 0.95,
        "brick": 0.95,
        "steel": 1.0,
        "wood": 1.20,
    }
    security_discounts = {
        "alarm": 0.05,
        "smoke detector": 0.03,
        "sprinklers": 0.05,
        "security cameras": 0.05,
        "security door": 0.03,
        "security guard": 0.05,
    }

    def calculate(
        self,
        quote_request: QuoteRequest,
        case_context: QuoteCaseContext,
    ) -> ModuleResult:
        quote_request_data = case_context.reference_data.quote_request
        if not quote_request_data:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary="reference_data.quote_request is required before pricing.",
            )

        asset_data = self._object(quote_request_data.get("asset_data"))
        pricing_preview = self._object(quote_request_data.get("pricing_preview"))
        request_details = self._object(pricing_preview.get("request_details"))

        coverage_amount = self._number(
            asset_data.get("declared_value") or request_details.get("coverage_amount")
        )
        if coverage_amount <= 0:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary="A positive declared value or coverage amount is required before backend pricing.",
                source_fields_used=[
                    "reference_data.quote_request.asset_data.declared_value",
                    "reference_data.quote_request.pricing_preview.request_details.coverage_amount",
                ],
            )

        year_built = self._number(asset_data.get("year_built"))
        previous_claims = self._number(asset_data.get("previous_claims_count"))
        property_type = self._property_type(asset_data.get("asset_type"))
        usage_type = self._usage_type(
            asset_data.get("usage_type") or asset_data.get("occupancy")
        )
        construction_type = self._construction_type(asset_data.get("construction_type"))
        area_sqm = self._number(asset_data.get("area_sqm"))
        security_features = self._security_features(request_details)

        base_premium = round(coverage_amount * self.BASE_RATE)
        property_type_multiplier = self.property_type_multipliers[property_type]
        usage_multiplier = self.usage_multipliers[usage_type]
        size_multiplier = self._size_multiplier(area_sqm)
        construction_multiplier = self.construction_multipliers[construction_type]
        age_multiplier = self._age_multiplier(year_built)
        claims_multiplier = 1.0 if previous_claims == 0 else 1.25
        raw_security_discount = sum(
            self.security_discounts.get(feature, 0.0) for feature in security_features
        )
        security_discount = min(
            raw_security_discount,
            self.MAX_SECURITY_DISCOUNT,
        )
        manual_review_surcharge = 100.0 if previous_claims > 5 else 0.0
        running_premium = float(base_premium)
        pricing_adjustments: list[QuotePricingAdjustment] = []
        for code, label, multiplier, explanation in (
            (
                "property_type_multiplier",
                "Property type",
                property_type_multiplier,
                f"Property type multiplier: {property_type_multiplier:.2f}.",
            ),
            (
                "age_multiplier",
                "Property age",
                age_multiplier,
                f"Age multiplier: {age_multiplier:.2f}.",
            ),
            (
                "size_multiplier",
                "Property size",
                size_multiplier,
                f"Property size multiplier: {size_multiplier:.2f}.",
            ),
            (
                "construction_multiplier",
                "Construction",
                construction_multiplier,
                f"Construction multiplier: {construction_multiplier:.2f}.",
            ),
            (
                "property_use_multiplier",
                "Property use",
                usage_multiplier,
                f"Property use multiplier: {usage_multiplier:.2f}.",
            ),
            (
                "claims_multiplier",
                "Claims history",
                claims_multiplier,
                f"Claims multiplier: {claims_multiplier:.2f}.",
            ),
        ):
            before = running_premium
            running_premium *= multiplier
            pricing_adjustments.append(
                self._multiplier(
                    code,
                    label,
                    multiplier,
                    running_premium - before,
                    explanation,
                )
            )

        before_discount = running_premium
        final_premium = round(
            before_discount * (1 - security_discount) + manual_review_surcharge
        )

        pricing_result = QuotePricingResult(
            base_premium=float(base_premium),
            pricing_adjustments=[
                *pricing_adjustments,
                QuotePricingAdjustment(
                    code="security_discount",
                    label="Security measures",
                    adjustment_type="discount",
                    value=security_discount,
                    amount=round(before_discount * security_discount, 2),
                    explanation=(
                        f"Security discount: {round(security_discount * 100)}%."
                    ),
                ),
                QuotePricingAdjustment(
                    code="manual_review_surcharge",
                    label="Manual review surcharge",
                    adjustment_type="surcharge",
                    value=manual_review_surcharge,
                    amount=manual_review_surcharge,
                    explanation=(
                        "Manual review surcharge applies when claims history "
                        "exceeds 5 claims."
                        if manual_review_surcharge
                        else "No manual review surcharge applies."
                    ),
                ),
            ],
            final_premium=float(final_premium),
            calculation_steps=[
                QuotePricingStep(
                    step_name="base_premium",
                    input_value=coverage_amount,
                    output_value=float(base_premium),
                    explanation="Base premium equals coverage amount x 0.2%.",
                ),
                QuotePricingStep(
                    step_name="multipliers",
                    input_value=None,
                    output_value=round(before_discount, 2),
                    explanation=(
                        "Applied property type, property age, property size, "
                        "construction, property use, and claims multipliers."
                    ),
                ),
                QuotePricingStep(
                    step_name="discounts_and_surcharges",
                    input_value=None,
                    output_value=float(final_premium),
                    explanation=(
                        "Applied capped security discount and manual review surcharge."
                    ),
                ),
            ],
            rule_version=self._rule_version(case_context),
            pricing_rationale=[
                "Base premium equals coverage amount x 0.2%.",
                f"Property type multiplier: {property_type_multiplier:.2f}.",
                f"Property size multiplier: {size_multiplier:.2f}.",
                f"Property use multiplier: {usage_multiplier:.2f}.",
                f"Construction multiplier: {construction_multiplier:.2f}.",
                f"Age multiplier: {age_multiplier:.2f}.",
                f"Claims multiplier: {claims_multiplier:.2f}.",
                f"Security discount: {round(security_discount * 100)}%.",
            ],
            calculation_year=datetime.now(timezone.utc).year,
        )

        self._write_pricing_output(
            quote_request,
            case_context,
            pricing_result,
            property_type_multiplier=property_type_multiplier,
            usage_multiplier=usage_multiplier,
            size_multiplier=size_multiplier,
            construction_multiplier=construction_multiplier,
            age_multiplier=age_multiplier,
            claims_multiplier=claims_multiplier,
            security_discount=security_discount,
            manual_review_surcharge=manual_review_surcharge,
        )

        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary="Calculated deterministic quote premium.",
            source_fields_used=[
                "reference_data.quote_request",
                "domain_payload.rule_outcomes",
                "generated_outputs.pricing_outputs",
            ],
        )

    def _write_pricing_output(
        self,
        quote_request: QuoteRequest,
        case_context: QuoteCaseContext,
        pricing_result: QuotePricingResult,
        *,
        property_type_multiplier: float,
        usage_multiplier: float,
        size_multiplier: float,
        construction_multiplier: float,
        age_multiplier: float,
        claims_multiplier: float,
        security_discount: float,
        manual_review_surcharge: float,
    ) -> None:
        pricing_data = pricing_result.model_dump(mode="json")
        frontend_pricing = {
            "source": "backend",
            "authoritative": True,
            "rule_version": pricing_result.rule_version,
            "ruleVersion": pricing_result.rule_version,
            "currency": pricing_result.currency,
            "coverage_amount": pricing_result.calculation_steps[0].input_value,
            "coverageAmount": pricing_result.calculation_steps[0].input_value,
            "base_premium": pricing_result.base_premium,
            "basePremium": pricing_result.base_premium,
            "propertyTypeMultiplier": property_type_multiplier,
            "propertyUseMultiplier": usage_multiplier,
            "sizeMultiplier": size_multiplier,
            "constructionMultiplier": construction_multiplier,
            "ageMultiplier": age_multiplier,
            "claimsMultiplier": claims_multiplier,
            "securityDiscountPercent": security_discount,
            "manualReviewSurcharge": manual_review_surcharge,
            "estimatedPremium": pricing_result.final_premium,
            "final_premium": pricing_result.final_premium,
            "finalPremium": pricing_result.final_premium,
            "adjustments": [
                self._frontend_adjustment(adjustment)
                for adjustment in pricing_result.pricing_adjustments
                if adjustment.amount
            ],
            "explanation": pricing_result.pricing_rationale,
        }

        output = case_context.generated_outputs.pricing_outputs
        output.base_premium_ron = pricing_result.base_premium
        output.adjustments = pricing_data["pricing_adjustments"]
        output.final_premium_ron = pricing_result.final_premium
        output.base_premium = pricing_result.base_premium
        output.pricing_adjustments = pricing_data["pricing_adjustments"]
        output.deductible_adjustments = pricing_data["deductible_adjustments"]
        output.final_premium = pricing_result.final_premium
        output.calculation_steps = pricing_data["calculation_steps"]
        output.rule_version = pricing_result.rule_version
        output.pricing_rationale = pricing_result.pricing_rationale
        output.currency = pricing_result.currency
        output.calculation_year = pricing_result.calculation_year
        output.pricing_metadata = pricing_data
        risk_assessment = build_quote_risk_assessment(
            case_context.domain_payload.rule_outcomes
        ).frontend_payload()

        quote_request.pricing_preview.update(
            {
                "currency": pricing_result.currency,
                "estimated_premium": pricing_result.final_premium,
                "pricing_source": "backend",
                "pricing_status": "authoritative",
                "risk_status": "authoritative",
                "pricing": frontend_pricing,
                "pricing_result": pricing_data,
                "rule_summary": {
                    "rule_version": pricing_result.rule_version,
                    "recommended_actions": case_context.domain_payload.rule_outcomes.get(
                        "recommended_actions",
                        [],
                    ),
                    "nonstandard_rules": case_context.domain_payload.rule_outcomes.get(
                        "nonstandard_rules",
                        [],
                    ),
                },
                "risk_assessment": risk_assessment,
            }
        )

        case_context.reference_data.quote_request["pricing_preview"] = (
            quote_request.pricing_preview
        )
        case_context.reference_data.quote_request["risk"] = risk_assessment
        case_context.domain_payload.quote_evaluation["risk_assessment"] = (
            risk_assessment
        )
        case_context.domain_payload.quote_intake_payload["pricing_preview"] = (
            quote_request.pricing_preview
        )

    def _multiplier(
        self,
        code: str,
        label: str,
        value: float,
        amount: float,
        explanation: str,
    ) -> QuotePricingAdjustment:
        return QuotePricingAdjustment(
            code=code,
            label=label,
            adjustment_type="multiplier",
            value=value,
            amount=round(amount, 2),
            explanation=explanation,
        )

    def _age_multiplier(self, year_built: float) -> float:
        if not year_built:
            return 1.0
        age = datetime.now(timezone.utc).year - int(year_built)
        if age < 20:
            return 0.95
        if age <= 50:
            return 1.0
        return 1.15

    def _size_multiplier(self, area_sqm: float) -> float:
        if not area_sqm or area_sqm <= 80:
            return 1.0
        if area_sqm <= 150:
            return 1.08
        if area_sqm <= 250:
            return 1.16
        return 1.25

    def _frontend_adjustment(
        self,
        adjustment: QuotePricingAdjustment,
    ) -> dict[str, float | str]:
        amount = adjustment.amount
        if adjustment.adjustment_type == "discount" and amount > 0:
            amount = -amount
        value = adjustment.value
        if adjustment.adjustment_type == "multiplier":
            formatted_value = f"x {value:.2f}"
        elif adjustment.adjustment_type == "discount":
            formatted_value = f"-{round(value * 100)}%"
        elif adjustment.adjustment_type == "surcharge":
            formatted_value = f"+{round(value)} RON"
        else:
            formatted_value = str(value)
        return {
            "code": adjustment.code,
            "label": adjustment.label,
            "value": formatted_value,
            "amountDelta": round(amount),
        }

    def _rule_version(self, case_context: QuoteCaseContext) -> str:
        rule_version = case_context.domain_payload.rule_outcomes.get("rule_version")
        return str(rule_version or self.RULE_VERSION)

    def _property_type(self, value: Any) -> str:
        normalized = self._text(value)
        if normalized in {"house", "home"}:
            return "house"
        if normalized in {"commercial", "business"}:
            return "commercial"
        return "apartment"

    def _usage_type(self, value: Any) -> str:
        normalized = self._text(value)
        if normalized in {"vacant"}:
            return "vacant"
        if normalized in {"commercial use", "commercial", "business"}:
            return "commercial use"
        if normalized in {"rented", "rental"}:
            return "rented"
        if normalized in {"holiday home", "holiday"}:
            return "holiday home"
        return "owner occupied"

    def _construction_type(self, value: Any) -> str:
        normalized = self._text(value)
        if normalized in {"brick"}:
            return "brick"
        if normalized in {"steel"}:
            return "steel"
        if normalized in {"wood", "timber"}:
            return "wood"
        return "concrete"

    def _security_features(self, request_details: dict[str, Any]) -> list[str]:
        raw_features = request_details.get("security_features", [])
        if isinstance(raw_features, str):
            raw_features = [part.strip() for part in raw_features.split(",")]
        if not isinstance(raw_features, list):
            return []
        return [self._text(feature) for feature in raw_features if feature]

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _number(self, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return number if number > 0 else 0.0

    def _text(self, value: Any) -> str:
        return str(value or "").strip().replace("_", " ").lower()


__all__ = ["PricingCalculationModule"]
