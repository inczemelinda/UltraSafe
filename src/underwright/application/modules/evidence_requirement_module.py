from __future__ import annotations

from typing import Any

from underwright.domain.claim_analysis import (
    ClaimReviewFindings,
    DocumentConsistencyResult,
    EvidenceRequirement,
    EvidenceRequirementNextAction,
    EvidenceRequirementResult,
    ExtractedClaimDocument,
)
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.module_result import ModuleResult


class EvidenceRequirementModule:
    """Determines what evidence is needed before underwriter review."""

    module_name = "EvidenceRequirementModule"

    severe_incident_types = {"fire", "storm", "water damage", "water_damage"}
    official_document_types = {
        "fire_service_report",
        "police_report",
        "emergency_report",
        "official_incident_confirmation",
    }

    def evaluate(self, case_context: ClaimCaseContext) -> ModuleResult:
        claim_request = self._object(case_context.reference_data.claim_request)
        claim_data = self._object(claim_request.get("claim_data"))
        documents = list(case_context.reference_data.extracted_documents.documents)
        consistency = case_context.generated_outputs.document_consistency

        required_evidence: list[EvidenceRequirement] = []
        incident_type = self._incident_type(claim_data)
        has_official_report = self._has_official_report(documents)

        if (
            incident_type == "fire"
            and self._is_false_or_no(claim_data.get("emergency_services"))
            and not has_official_report
        ):
            required_evidence.append(self._official_fire_requirement())
        elif (
            incident_type in self.severe_incident_types
            and not has_official_report
        ):
            required_evidence.append(
                EvidenceRequirement(
                    requirement_type="official_incident_confirmation",
                    reason=(
                        "Severe incidents need authoritative confirmation before "
                        "underwriter decision support is complete."
                    ),
                    acceptable_documents=[
                        "fire_service_report",
                        "police_report",
                        "emergency_report",
                        "official_incident_confirmation",
                    ],
                    severity="high",
                    status="missing",
                    suggested_next_action="request_evidence",
                )
            )

        if self._description_is_short(claim_data.get("description")):
            required_evidence.append(
                EvidenceRequirement(
                    requirement_type="additional_incident_details",
                    reason=(
                        "The incident description is too short to support a "
                        "complete underwriter review."
                    ),
                    acceptable_documents=[
                        "claimant_statement",
                        "written_incident_description",
                    ],
                    severity="medium",
                    status="missing",
                    suggested_next_action="request_evidence",
                )
            )

        suggested_next_action = self._next_action(
            required_evidence,
            consistency,
        )
        result = EvidenceRequirementResult(
            required_evidence=required_evidence,
            suggested_next_action=suggested_next_action,
            rationale=self._rationale(
                required_evidence,
                consistency,
                suggested_next_action,
            ),
            summary=self._summary(required_evidence, suggested_next_action),
        )
        self._attach_result(case_context, result)
        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary=f"Evidence requirements set action {suggested_next_action}.",
            source_fields_used=[
                "reference_data.claim_request",
                "reference_data.extracted_documents",
                "generated_outputs.document_consistency",
            ],
        )

    def _official_fire_requirement(self) -> EvidenceRequirement:
        return EvidenceRequirement(
            requirement_type="official_fire_incident_confirmation",
            reason=(
                "Fire claims without recorded emergency-services contact need "
                "official fire incident confirmation."
            ),
            acceptable_documents=[
                "fire_service_report",
                "emergency_report",
                "official_incident_confirmation",
            ],
            severity="high",
            status="missing",
            suggested_next_action="request_evidence",
        )

    def _next_action(
        self,
        required_evidence: list[EvidenceRequirement],
        consistency: DocumentConsistencyResult | None,
    ) -> EvidenceRequirementNextAction:
        if self._has_high_discrepancy(consistency):
            return "manual_review"
        if required_evidence:
            return "request_evidence"
        return "underwriter_review"

    def _has_high_discrepancy(
        self,
        consistency: DocumentConsistencyResult | None,
    ) -> bool:
        if consistency is None:
            return False
        return any(
            discrepancy.severity == "high"
            for discrepancy in consistency.discrepancies
        )

    def _has_official_report(self, documents: list[ExtractedClaimDocument]) -> bool:
        return any(
            document.document_type in self.official_document_types
            or self._is_true(document.extracted_fields.get("authority_verified"))
            for document in documents
        )

    def _incident_type(self, claim_data: dict[str, Any]) -> str:
        return self._normalize_text(
            claim_data.get("incident_type") or claim_data.get("claim_type")
        )

    def _description_is_short(self, value: Any) -> bool:
        description = str(value or "").strip()
        meaningful_characters = "".join(
            character for character in description if not character.isspace()
        )
        words = [word for word in description.split() if word.strip()]
        return len(meaningful_characters) < 25 or len(words) < 5

    def _rationale(
        self,
        required_evidence: list[EvidenceRequirement],
        consistency: DocumentConsistencyResult | None,
        suggested_next_action: EvidenceRequirementNextAction,
    ) -> str:
        if suggested_next_action == "manual_review":
            return (
                "High-severity document discrepancies require manual review "
                "before evidence follow-up can be treated as routine."
            )
        if required_evidence:
            requirement_types = ", ".join(
                requirement.requirement_type for requirement in required_evidence
            )
            return f"Missing evidence requirements: {requirement_types}."
        if (
            consistency is not None
            and consistency.status == "insufficient_document_data"
        ):
            return (
                "No blocking evidence requirement was found, but document data "
                "is limited."
            )
        return "No additional evidence requirement was identified."

    def _summary(
        self,
        required_evidence: list[EvidenceRequirement],
        suggested_next_action: EvidenceRequirementNextAction,
    ) -> str:
        if suggested_next_action == "manual_review":
            return "Manual review is needed because of critical discrepancies."
        if required_evidence:
            return "Additional evidence is required before underwriter review."
        return "Evidence is ready for underwriter review."

    def _attach_result(
        self,
        case_context: ClaimCaseContext,
        result: EvidenceRequirementResult,
    ) -> None:
        case_context.generated_outputs.evidence_requirements = result
        findings = (
            case_context.generated_outputs.claim_review.findings
            or ClaimReviewFindings()
        )
        findings.evidence_requirements = result
        findings.suggested_next_action = result.suggested_next_action
        case_context.generated_outputs.claim_review.findings = findings

    def _normalize_text(self, value: Any) -> str:
        normalized = str(value or "").strip().lower().replace("_", " ")
        return " ".join(normalized.split())

    def _is_true(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "y"}

    def _is_false_or_no(self, value: Any) -> bool:
        if isinstance(value, bool):
            return not value
        return str(value or "").strip().lower() in {"0", "false", "no", "n"}

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


__all__ = ["EvidenceRequirementModule"]
