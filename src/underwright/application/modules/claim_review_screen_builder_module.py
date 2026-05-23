from __future__ import annotations

from typing import Any

from underwright.domain.claim_analysis import (
    ClaimReviewFindings,
    CoverageAssessmentResult,
    DocumentConsistencyResult,
    EvidenceRequirementResult,
)
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_review_models import (
    ClaimAttachmentsPanel,
    ClaimClientPanel,
    ClaimDetailPanel,
    ClaimReviewHeader,
    ClaimReviewView,
)
from underwright.domain.module_result import ModuleResult


class ClaimReviewScreenBuilderModule:
    """Builds and stores the underwriter claim review packet."""

    module_name = "ClaimReviewScreenBuilderModule"

    def build(self, case_context: ClaimCaseContext) -> ModuleResult:
        claim_request = case_context.reference_data.claim_request
        validation = case_context.generated_outputs.validation
        classification = case_context.generated_outputs.classification
        summary = case_context.generated_outputs.summary
        coverage_assessment = case_context.generated_outputs.coverage_assessment
        document_consistency = case_context.generated_outputs.document_consistency
        evidence_requirements = case_context.generated_outputs.evidence_requirements
        if (
            not claim_request
            or validation is None
            or classification is None
            or summary is None
            or document_consistency is None
            or evidence_requirements is None
        ):
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary="Claim request and finding-based review outputs are required.",
                source_fields_used=[
                    "reference_data.claim_request",
                    "generated_outputs.validation",
                    "generated_outputs.classification",
                    "generated_outputs.summary",
                    "generated_outputs.document_consistency",
                    "generated_outputs.evidence_requirements",
                ],
            )

        findings = self._findings(case_context)
        findings.coverage_assessment = (
            coverage_assessment or findings.coverage_assessment
        )
        suggested_next_action = self._suggested_next_action(
            evidence_requirements,
            findings.coverage_assessment,
        )
        human_readable_summary = self._human_readable_summary(
            coverage_assessment=findings.coverage_assessment,
            document_consistency=document_consistency,
            evidence_requirements=evidence_requirements,
            suggested_next_action=suggested_next_action,
        )
        findings.document_consistency = document_consistency
        findings.evidence_requirements = evidence_requirements
        findings.suggested_next_action = suggested_next_action
        findings.human_readable_summary = human_readable_summary
        case_context.generated_outputs.claim_review.findings = findings
        case_context.generated_outputs.claim_review.recommendation = (
            suggested_next_action
        )
        case_context.generated_outputs.claim_review.review_summary = (
            human_readable_summary
        )

        available_actions = ["view_details", suggested_next_action]
        view = ClaimReviewView(
            header=ClaimReviewHeader(
                case_id=case_context.case_metadata.case_id,
                request_id=case_context.source_inputs.request_id,
                domain=case_context.case_metadata.domain,
                workflow_status=case_context.case_metadata.status,
            ),
            client_panel=ClaimClientPanel(
                client_id=case_context.source_inputs.client_id,
                client_data=claim_request.get("client_data", {}),
            ),
            claim_detail_panel=ClaimDetailPanel(
                claim_data=claim_request.get("claim_data", {}),
            ),
            attachments_panel=ClaimAttachmentsPanel(
                attachments=claim_request.get("attachments", []),
                warnings=validation.attachment_warnings,
            ),
            ai_validation_panel=validation.model_dump(mode="json"),
            classification_panel=classification.model_dump(mode="json"),
            summary_panel=summary.model_dump(mode="json"),
            coverage_precheck=(
                findings.coverage_assessment.model_dump(mode="json")
                if findings.coverage_assessment is not None
                else case_context.generated_outputs.claim_review.coverage_findings
                or None
            ),
            coverage_assessment=(
                findings.coverage_assessment.model_dump(mode="json")
                if findings.coverage_assessment is not None
                else None
            ),
            document_consistency={
                "status": document_consistency.status,
                "supporting_fact_count": len(document_consistency.supporting_facts),
                "discrepancy_count": len(document_consistency.discrepancies),
            },
            supporting_facts=[
                fact.model_dump(mode="json")
                for fact in document_consistency.supporting_facts
            ],
            discrepancies=[
                discrepancy.model_dump(mode="json")
                for discrepancy in document_consistency.discrepancies
            ],
            extracted_documents=(
                case_context.reference_data.extracted_documents.model_dump(mode="json")
            ),
            required_evidence=[
                requirement.model_dump(mode="json")
                for requirement in evidence_requirements.required_evidence
            ],
            missing_evidence=[
                requirement.model_dump(mode="json")
                for requirement in evidence_requirements.required_evidence
            ],
            suggested_next_action=suggested_next_action,
            human_readable_summary=human_readable_summary,
            evidence_request_draft=(
                case_context.generated_outputs.evidence_request_draft.model_dump(
                    mode="json"
                )
                if case_context.generated_outputs.evidence_request_draft is not None
                else None
            ),
            confidence_panel=self._legacy_confidence_panel(case_context),
            warnings_panel={
                "missing_required_fields": (
                    case_context.checks_and_warnings.missing_required_fields
                ),
                "attachment_warnings": (
                    case_context.checks_and_warnings.attachment_warnings
                ),
                "review_warnings": case_context.checks_and_warnings.review_warnings,
            },
            available_actions=available_actions,
        )
        case_context.review_state.claim_review_view = view
        case_context.review_state.available_actions = available_actions
        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary="Built claim review screen view.",
            source_fields_used=[
                "case_metadata",
                "source_inputs",
                "reference_data.claim_request",
                "generated_outputs.validation",
                "generated_outputs.classification",
                "generated_outputs.summary",
                "reference_data.extracted_documents",
                "generated_outputs.coverage_assessment",
                "generated_outputs.document_consistency",
                "generated_outputs.evidence_requirements",
            ],
        )

    def _findings(self, case_context: ClaimCaseContext) -> ClaimReviewFindings:
        return (
            case_context.generated_outputs.claim_review.findings
            or ClaimReviewFindings()
        )

    def _legacy_confidence_panel(
        self,
        case_context: ClaimCaseContext,
    ) -> dict[str, Any]:
        confidence = case_context.generated_outputs.confidence
        if confidence is None:
            return {
                "legacy_internal_signal": True,
                "not_decisioning": True,
                "score": None,
                "rationale": ["Confidence score is not used for claim decisioning."],
            }
        return {
            **confidence.model_dump(mode="json"),
            "legacy_internal_signal": True,
            "not_decisioning": True,
        }

    def _suggested_next_action(
        self,
        evidence_requirements: EvidenceRequirementResult,
        coverage_assessment: CoverageAssessmentResult | None,
    ) -> str:
        if evidence_requirements.suggested_next_action in {
            "request_evidence",
            "manual_review",
        }:
            return evidence_requirements.suggested_next_action
        if (
            coverage_assessment is not None
            and coverage_assessment.coverage_status
            in {"not_covered", "excluded", "unclear"}
        ):
            return "coverage_review"
        return evidence_requirements.suggested_next_action or "underwriter_review"

    def _human_readable_summary(
        self,
        *,
        coverage_assessment: CoverageAssessmentResult | None,
        document_consistency: DocumentConsistencyResult,
        evidence_requirements: EvidenceRequirementResult,
        suggested_next_action: str,
    ) -> str:
        discrepancy_count = len(document_consistency.discrepancies)
        requirement_count = len(evidence_requirements.required_evidence)
        if suggested_next_action == "manual_review":
            return (
                "Manual review is needed because the claim has critical "
                "document discrepancies."
            )
        if suggested_next_action == "request_evidence":
            return (
                f"{requirement_count} evidence requirement(s) must be resolved "
                "before underwriter review."
            )
        if suggested_next_action == "coverage_review":
            rationale = (
                coverage_assessment.rationale
                if coverage_assessment is not None
                else "Coverage wording needs underwriter review."
            )
            return f"Coverage review is needed. {rationale}"
        if discrepancy_count:
            return (
                f"{discrepancy_count} document discrepancy/discrepancies need "
                "underwriter attention."
            )
        return (
            "No blocking evidence requirement was identified; ready for "
            "underwriter review."
        )


__all__ = ["ClaimReviewScreenBuilderModule"]
