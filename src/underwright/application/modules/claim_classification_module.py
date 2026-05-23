from __future__ import annotations

from typing import Any

from underwright.domain.claim_analysis import ClaimClassificationOutput
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.module_result import ModuleResult


class ClaimClassificationModule:
    """Classifies claim type and severity with deterministic review rules."""

    module_name = "ClaimClassificationModule"

    severe_types = {"fire", "storm", "water damage"}

    def evaluate(self, case_context: ClaimCaseContext) -> ModuleResult:
        validation = case_context.generated_outputs.validation
        if validation is None or not validation.is_valid:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary="Valid claim intake data is required before classification.",
                source_fields_used=["generated_outputs.validation"],
            )

        claim_data = self._object(case_context.reference_data.claim_request.get("claim_data"))
        claim_type = str(claim_data.get("claim_type") or "Other")
        normalized_type = claim_type.strip().lower()
        review_flags: list[str] = []

        if normalized_type in self.severe_types:
            category = "property_damage"
            complete_severe_evidence = (
                not validation.attachment_warnings
                and self._emergency_services_were_contacted(claim_data)
            )
            severity = "medium" if complete_severe_evidence else "high"
            rationale = (
                "Severe incident type with complete evidence and emergency response."
                if complete_severe_evidence
                else "Severe incident type needs high-priority underwriter review."
            )
            if not complete_severe_evidence:
                review_flags.append("severe_incident_needs_verification")
        elif normalized_type == "theft":
            category = "property_loss"
            severity = "medium"
            rationale = "Theft claims require evidence and policy condition review."
        elif normalized_type == "other":
            category = "manual_classification"
            severity = "medium"
            rationale = "Other claim type needs manual classification by an underwriter."
            review_flags.append("manual_classification_required")
        else:
            category = "property_damage"
            severity = "low"
            rationale = "Standard property claim type with deterministic classification."

        output = ClaimClassificationOutput(
            claim_type=claim_type,
            category=category,
            severity=severity,
            rationale=rationale,
            review_flags=review_flags,
        )
        case_context.generated_outputs.classification = output
        case_context.checks_and_warnings.review_warnings = review_flags

        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary=f"Classified claim as {category} with {severity} severity.",
            source_fields_used=[
                "reference_data.claim_request.claim_data",
                "generated_outputs.validation",
            ],
        )

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _emergency_services_were_contacted(self, claim_data: dict[str, Any]) -> bool:
        value = claim_data.get("emergency_services")
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"yes", "true", "1"}


__all__ = ["ClaimClassificationModule"]
