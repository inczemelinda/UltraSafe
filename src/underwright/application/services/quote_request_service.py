from __future__ import annotations

from typing import Any
from uuid import UUID

from underwright.application.modules.policy_rules_module import PolicyRulesModule
from underwright.application.modules.pricing_calculation_module import (
    PricingCalculationModule,
)
from underwright.application.ports import QuoteRequestRepository
from underwright.domain.auth_user import AuthUser
from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.module_result import ModuleResult
from underwright.domain.quote_decision_audit import (
    QuoteDecisionAuditCreate,
    QuoteDecisionAuditRecord,
)
from underwright.domain.quote_request import QuoteRequest
from underwright.domain.quote_risk import build_quote_risk_assessment


class QuoteRequestService:
    """Wraps quote request repository access for UI-facing quote flows."""

    def __init__(
        self,
        quote_request_repository: QuoteRequestRepository,
        policy_rules_module: PolicyRulesModule | None = None,
        pricing_calculation_module: PricingCalculationModule | None = None,
    ) -> None:
        self.quote_request_repository = quote_request_repository
        self.policy_rules_module = policy_rules_module or PolicyRulesModule()
        self.pricing_calculation_module = (
            pricing_calculation_module or PricingCalculationModule()
        )

    def create_quote_request(self, request: QuoteRequest) -> QuoteRequest:
        self._apply_backend_quote_outputs(request)
        return self.quote_request_repository.create_request(request)

    def save_step_updates(self, request: QuoteRequest) -> QuoteRequest:
        self._apply_backend_quote_outputs(request)
        return self.quote_request_repository.update_request(request)

    def list_client_quote_requests(
        self,
        client_id: int | str | UUID,
    ) -> list[QuoteRequest]:
        return [
            self._apply_backend_quote_outputs(request)
            for request in self.quote_request_repository.list_requests_by_client_id(
                client_id
            )
        ]

    def list_underwriter_review_quote_requests(self) -> list[QuoteRequest]:
        return self.list_quote_requests_by_status("underwriter_review")

    def list_quote_requests_by_status(self, request_status: str) -> list[QuoteRequest]:
        return [
            self._apply_backend_quote_outputs(request)
            for request in self.quote_request_repository.list_requests_by_status(
                request_status
            )
        ]

    def get_quote_request_detail(self, request_id: UUID) -> QuoteRequest:
        return self._apply_backend_quote_outputs(
            self.quote_request_repository.get_request_by_id(request_id)
        )

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> QuoteRequest:
        return self._apply_backend_quote_outputs(
            self.quote_request_repository.update_request_status(
                request_id,
                request_status,
            )
        )

    def update_underwriter_decision(
        self,
        request_id: UUID,
        request_status: str,
        *,
        reason: str | None,
        user: AuthUser,
    ) -> QuoteRequest:
        current = self.quote_request_repository.get_request_by_id(request_id)
        updated = self.quote_request_repository.update_request_status(
            request_id,
            request_status,
        )
        self.quote_request_repository.create_decision_audit(
            QuoteDecisionAuditCreate(
                quote_request_id=request_id,
                previous_status=current.request_status,
                decision_status=request_status,
                reason=reason.strip() if reason and reason.strip() else None,
                decided_by_auth_user_id=user.id,
                decided_by_name=user.full_name,
                decided_by_email=user.email,
            )
        )
        return self._apply_backend_quote_outputs(updated)

    def record_system_decision(
        self,
        request_id: UUID,
        *,
        previous_status: str,
        decision_status: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> QuoteDecisionAuditRecord:
        return self.quote_request_repository.create_decision_audit(
            QuoteDecisionAuditCreate(
                quote_request_id=request_id,
                previous_status=previous_status,
                decision_status=decision_status,
                reason=reason.strip() if reason and reason.strip() else None,
                decided_by_name="Underwright Rules Engine",
                decided_by_email="system@underwright.local",
                metadata=metadata or {},
            )
        )

    def list_decision_audit(
        self,
        request_id: UUID,
    ) -> list[QuoteDecisionAuditRecord]:
        return self.quote_request_repository.list_decision_audit(request_id)

    def mark_underwriter_review(self, request_id: UUID) -> QuoteRequest:
        return self.update_request_status(request_id, "underwriter_review")

    def mark_approved(self, request_id: UUID) -> QuoteRequest:
        return self.update_request_status(request_id, "approved")

    def mark_disapproved(self, request_id: UUID) -> QuoteRequest:
        return self.update_request_status(request_id, "disapproved")

    def mark_failed(self, request_id: UUID) -> QuoteRequest:
        return self.update_request_status(request_id, "failed")

    def _apply_backend_quote_outputs(self, request: QuoteRequest) -> QuoteRequest:
        request.pricing_preview = self._non_binding_pricing_context(
            request.pricing_preview
        )
        context = QuoteCaseContext()
        context.reference_data.quote_request = request.model_dump(mode="json")
        result = self.policy_rules_module.evaluate(context)
        if result.status != "success":
            self._mark_backend_outputs_unavailable(request, result)
            return request

        rule_outcomes = context.domain_payload.rule_outcomes
        risk_assessment = build_quote_risk_assessment(rule_outcomes).frontend_payload()
        request.pricing_preview.update(
            {
                "risk_assessment": risk_assessment,
                "risk_status": "authoritative",
                "rule_summary": {
                    "rule_version": rule_outcomes.get("rule_version"),
                    "recommended_actions": rule_outcomes.get(
                        "recommended_actions",
                        [],
                    ),
                    "nonstandard_rules": rule_outcomes.get(
                        "nonstandard_rules",
                        [],
                    ),
                },
            }
        )
        context.reference_data.quote_request["pricing_preview"] = (
            request.pricing_preview
        )
        pricing_result = self.pricing_calculation_module.calculate(
            request,
            context,
        )
        if pricing_result.status != "success":
            self._mark_backend_pricing_unavailable(request, pricing_result)
        return request

    def _non_binding_pricing_context(
        self,
        pricing_preview: dict[str, Any],
    ) -> dict[str, Any]:
        preview = dict(pricing_preview or {})
        ui_context = self._object(preview.get("ui_context")).copy()
        submitted_outputs: dict[str, Any] = {}

        for key in (
            "pricing",
            "pricing_result",
            "risk_assessment",
            "rule_summary",
            "estimated_premium",
            "estimatedPremium",
            "final_premium",
            "finalPremium",
            "premium",
            "base_premium",
            "basePremium",
            "risk_score",
            "riskScore",
            "pricing_source",
            "pricing_status",
            "risk_status",
            "pricing_error",
            "risk_error",
            "currency",
        ):
            if key in preview:
                submitted_outputs[key] = preview.pop(key)

        if submitted_outputs:
            ui_context["submitted_quote_estimate"] = {
                "source": "frontend_preview",
                "binding": False,
                "values": submitted_outputs,
            }

        if ui_context:
            preview["ui_context"] = ui_context

        preview["source"] = "frontend_preview_context"
        preview["binding"] = False
        return preview

    def _mark_backend_outputs_unavailable(
        self,
        request: QuoteRequest,
        result: ModuleResult,
    ) -> None:
        request.pricing_preview.update(
            {
                "pricing_status": "unavailable",
                "pricing_error": result.summary,
                "risk_status": "unavailable",
                "risk_error": result.summary,
            }
        )

    def _mark_backend_pricing_unavailable(
        self,
        request: QuoteRequest,
        result: ModuleResult,
    ) -> None:
        request.pricing_preview.update(
            {
                "pricing_status": "unavailable",
                "pricing_error": result.summary,
            }
        )

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


__all__ = ["QuoteRequestService"]
