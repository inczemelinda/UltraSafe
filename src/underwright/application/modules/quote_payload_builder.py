from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from underwright.application.ports import DefaultInsurerProvider
from underwright.domain.contract_lifecycle import ContractCreationData
from underwright.domain.module_result import ModuleResult
from underwright.domain.quote_case_context import QuoteCaseContext


class QuotePayloadBuilder:
    """Builds the template payload used to generate an unsigned quote document."""

    module_name = "QuotePayloadBuilder"

    def __init__(
        self,
        default_insurer_provider: DefaultInsurerProvider | None = None,
    ) -> None:
        self.default_insurer_provider = default_insurer_provider

    def build(self, case_context: QuoteCaseContext) -> ModuleResult:
        quote_request = case_context.reference_data.quote_request
        if not quote_request:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary="reference_data.quote_request is required before payload build.",
            )

        request_id = quote_request.get("request_id")
        client_data = quote_request.get("client_data", {})
        asset_data = quote_request.get("asset_data", {})
        pricing_preview = self._pricing_payload(case_context, quote_request)
        coverage_amount = self._coverage_amount(asset_data, quote_request)
        issue_date = self._issue_date(quote_request)
        currency = (
            pricing_preview.get("currency")
            or case_context.generated_outputs.pricing_outputs.currency
        )
        parties = {
            "insured": self._insured_payload(client_data),
        }
        try:
            insurer_payload = self._insurer_payload()
        except ValueError as exc:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary=f"Default insurer data could not be loaded: {exc}",
                source_fields_used=["default_insurer_provider"],
            )
        if insurer_payload is not None:
            parties["insurer"] = insurer_payload

        payload = {
            "document_type": "insurance_quote",
            "document_version": "1.0",
            "language": case_context.source_inputs.language or "ro-RO",
            "generation_mode": "template_plus_ai_additions",
            "quote_meta": {
                "quote_id": request_id,
                "request_id": request_id,
                "status": quote_request.get("request_status"),
            },
            # Existing PAD templates still read contract_meta.contract_id.
            # Keep this compatibility key until quote-native templates exist.
            "contract_meta": {
                "contract_id": f"QUOTE-{str(request_id)[:8]}",
                "issue_date": issue_date.isoformat(),
                "effective_date": issue_date.isoformat(),
                "expiration_date": (issue_date + timedelta(days=364)).isoformat(),
                "currency": currency,
            },
            "parties": parties,
            "insured_asset": self._asset_payload(asset_data),
            "coverage": {
                "building_sum_insured": coverage_amount,
                "contents_sum_insured": coverage_amount,
                "total_sum_insured": coverage_amount,
            },
            "risk_profile": {
                "overall_risk_level": "pending_rules",
                "factors": [],
            },
            "pricing": pricing_preview,
            "approval": case_context.domain_payload.approval_decision,
            "rules": case_context.domain_payload.rule_outcomes,
        }

        case_context.domain_payload.quote_generation_payload = payload
        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary="Built quote generation payload.",
            source_fields_used=[
                "reference_data.quote_request",
                "reference_data.client_profile",
                "reference_data.asset_profile",
                "domain_payload.approval_decision",
            ],
        )

    def _pricing_payload(
        self,
        case_context: QuoteCaseContext,
        quote_request: dict,
    ) -> dict:
        pricing_preview = dict(quote_request.get("pricing_preview", {}))
        pricing_output = case_context.generated_outputs.pricing_outputs
        final_premium = (
            pricing_output.final_premium
            if pricing_output.final_premium is not None
            else pricing_output.final_premium_ron
        )
        base_premium = (
            pricing_output.base_premium
            if pricing_output.base_premium is not None
            else pricing_output.base_premium_ron
        )

        if final_premium is None and not pricing_preview:
            return {}

        pricing_payload = dict(pricing_preview)
        pricing_payload.update(
            {
                "currency": pricing_output.currency,
                "estimated_premium": final_premium,
                "base_premium": base_premium,
                "base_premium_ron": base_premium,
                "final_premium": final_premium,
                "final_premium_ron": final_premium,
                "pricing_adjustments": pricing_output.pricing_adjustments
                or pricing_output.adjustments,
                "deductible_adjustments": pricing_output.deductible_adjustments,
                "calculation_steps": pricing_output.calculation_steps,
                "rule_version": pricing_output.rule_version,
                "pricing_rationale": pricing_output.pricing_rationale,
            }
        )
        pricing_payload.setdefault(
            "payment_plan",
            self._payment_plan_payload(pricing_payload),
        )
        return pricing_payload

    def _coverage_amount(self, asset_data: dict, quote_request: dict) -> float:
        pricing_preview = quote_request.get("pricing_preview", {})
        request_details = pricing_preview.get("request_details", {})
        raw_value = request_details.get("coverage_amount") or asset_data.get(
            "declared_value"
        )
        try:
            return float(raw_value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _insurer_payload(self) -> dict[str, Any] | None:
        if self.default_insurer_provider is None:
            return None
        source = self.default_insurer_provider.get_default_insurer_context_source()
        return {
            "name": source.insurer.name,
            "company_id": source.insurer.company_id,
            "address": source.insurer_address.full_text,
            "representative": {
                "name": source.insurer.representative_name,
                "role": source.insurer.representative_role,
            },
        }

    def _payment_plan_payload(self, pricing_preview: dict[str, Any]) -> dict[str, Any]:
        payment_plan = pricing_preview.get("payment_plan")
        if isinstance(payment_plan, dict):
            return dict(payment_plan)
        return {
            "type": (
                pricing_preview.get("payment_plan_type")
                or pricing_preview.get("paymentPlanType")
                or ContractCreationData.model_fields["payment_plan_type"].default
            ),
            "installments": (
                pricing_preview.get("installments")
                or ContractCreationData.model_fields["installments"].default
            ),
        }

    def _insured_payload(self, client_data: dict[str, Any]) -> dict[str, Any]:
        insured = dict(client_data)
        insured["address"] = self._display_address(client_data.get("address"))
        insured.setdefault("type", "individual")
        insured.setdefault("national_id", "")
        insured.setdefault("company_id", None)
        insured.setdefault("email", "")
        insured.setdefault("phone", "")
        return insured

    def _asset_payload(self, asset_data: dict[str, Any]) -> dict[str, Any]:
        asset = dict(asset_data)
        asset["address"] = self._address_payload(asset_data.get("address"))
        return asset

    def _address_payload(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            address = dict(value)
        elif isinstance(value, str):
            address = {"full_text": value, "street": value}
        else:
            address = {}

        for key in ("country", "county", "city", "street", "number", "postal_code"):
            address.setdefault(key, "")
        address.setdefault("full_text", self._display_address(address))
        return address

    def _display_address(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if not isinstance(value, dict):
            return ""
        full_text = value.get("full_text")
        if full_text:
            return str(full_text)
        return ", ".join(
            str(value[key])
            for key in ("street", "number", "city", "county", "country", "postal_code")
            if value.get(key)
        )

    def _issue_date(self, quote_request: dict[str, Any]) -> date:
        raw_created_at = quote_request.get("created_at")
        if isinstance(raw_created_at, str):
            try:
                return datetime.fromisoformat(
                    raw_created_at.replace("Z", "+00:00")
                ).date()
            except ValueError:
                pass
        return date.today()


__all__ = ["QuotePayloadBuilder"]
