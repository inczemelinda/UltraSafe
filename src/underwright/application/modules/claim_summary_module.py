from __future__ import annotations

from typing import Any

from underwright.domain.claim_analysis import ClaimSummaryOutput
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.module_result import ModuleResult


class ClaimSummaryModule:
    """Builds a concise deterministic claim review summary."""

    module_name = "ClaimSummaryModule"

    def evaluate(self, case_context: ClaimCaseContext) -> ModuleResult:
        classification = case_context.generated_outputs.classification
        if classification is None:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary="Claim classification is required before summary generation.",
                source_fields_used=["generated_outputs.classification"],
            )

        claim_request = case_context.reference_data.claim_request
        client_data = self._object(claim_request.get("client_data"))
        claim_data = self._object(claim_request.get("claim_data"))
        attachments = list(claim_request.get("attachments") or [])

        client_name = client_data.get("full_name") or "Unknown client"
        claim_type = claim_data.get("claim_type") or classification.claim_type
        estimated_damage = claim_data.get("estimated_damage")
        property_address = claim_data.get("property_address") or "unknown property"
        incident_date = claim_data.get("incident_date") or "unknown date"
        summary = (
            f"{client_name} filed a {claim_type} claim for {property_address} "
            f"on {incident_date}. Estimated damage is {estimated_damage}."
        )
        output = ClaimSummaryOutput(
            summary=summary,
            key_facts={
                "client_name": client_name,
                "claim_type": claim_type,
                "property_address": property_address,
                "incident_date": incident_date,
                "incident_time": claim_data.get("incident_time"),
                "estimated_damage": estimated_damage,
                "policy_number": claim_data.get("policy_number"),
                "attachment_count": len(attachments),
                "classification": classification.model_dump(mode="json"),
            },
            recommended_next_steps=[
                "Review submitted evidence.",
                "Confirm policy coverage and exclusions.",
                "Request follow-up information if confidence is low.",
            ],
        )
        case_context.generated_outputs.summary = output
        case_context.generated_outputs.claim_review.review_summary = summary
        case_context.generated_outputs.claim_review.extracted_claim_facts = (
            output.key_facts
        )

        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary="Generated deterministic claim review summary.",
            source_fields_used=[
                "reference_data.claim_request.client_data",
                "reference_data.claim_request.claim_data",
                "generated_outputs.classification",
            ],
        )

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


__all__ = ["ClaimSummaryModule"]
