from __future__ import annotations

from typing import Any

from underwright.domain.claim_analysis import ClaimConfidenceOutput
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.module_result import ModuleResult


class ClaimConfidenceModule:
    """Scores review confidence without approving or denying the claim."""

    module_name = "ClaimConfidenceModule"

    def evaluate(self, case_context: ClaimCaseContext) -> ModuleResult:
        validation = case_context.generated_outputs.validation
        classification = case_context.generated_outputs.classification
        summary = case_context.generated_outputs.summary
        if validation is None or classification is None or summary is None:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary="Validation, classification, and summary outputs are required.",
                source_fields_used=[
                    "generated_outputs.validation",
                    "generated_outputs.classification",
                    "generated_outputs.summary",
                ],
            )

        claim_data = self._object(case_context.reference_data.claim_request.get("claim_data"))
        score = 100
        rationale: list[str] = []

        for warning in validation.attachment_warnings:
            if "photo" in warning.lower():
                score -= 25
            elif "document" in warning.lower():
                score -= 25
            rationale.append(warning)

        description = str(claim_data.get("description") or "")
        if len(description.strip()) < 30:
            score -= 15
            rationale.append("Description is too short for high confidence.")

        estimated_damage = self._number(claim_data.get("estimated_damage"))
        coverage_amount = self._number(claim_data.get("coverage_amount"))
        if coverage_amount > 0 and estimated_damage > coverage_amount * 0.5:
            score -= 15
            rationale.append("Estimated damage is over 50% of the coverage amount.")

        if classification.category == "manual_classification":
            score -= 10
            rationale.append("Claim type requires manual classification.")

        if (
            classification.severity == "high"
            and not self._emergency_services_were_contacted(claim_data)
        ):
            score -= 10
            rationale.append("No emergency services were recorded for a severe event.")

        if not rationale:
            rationale.append("Claim evidence looks complete.")

        output = ClaimConfidenceOutput(
            score=max(0, min(100, score)),
            rationale=rationale,
            evidence_references=validation.evidence_references,
        )
        case_context.generated_outputs.confidence = output
        case_context.generated_outputs.claim_review.recommendation = (
            "Review support only; no automated claim decision was made."
        )
        case_context.generated_outputs.claim_review.risk_flags = (
            classification.review_flags
        )
        case_context.generated_outputs.claim_review.generation_metadata = {
            "confidence_score": output.score,
            "confidence_rationale": output.rationale,
        }

        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary=f"Calculated claim review confidence score {output.score}.",
            source_fields_used=[
                "generated_outputs.validation",
                "generated_outputs.classification",
                "generated_outputs.summary",
                "reference_data.claim_request.claim_data",
            ],
        )

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _number(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0

    def _emergency_services_were_contacted(self, claim_data: dict[str, Any]) -> bool:
        value = claim_data.get("emergency_services")
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"yes", "true", "1"}


__all__ = ["ClaimConfidenceModule"]
