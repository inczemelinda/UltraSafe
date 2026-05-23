from __future__ import annotations

from typing import Any

from underwright.application.services.coverage_assessment_llm_service import (
    CoverageAssessmentLLMService,
    DeterministicCoverageAssessmentService,
)
from underwright.application.services.policy_wording_service import (
    PolicyWordingRetrievalService,
)
from underwright.domain.claim_analysis import (
    ClaimReviewFindings,
    CoverageAssessmentResult,
    PolicyWordingSection,
)
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.module_result import ModuleResult


class CoverageAssessmentModule:
    """Orchestrates LLM-backed wording-fit assessment.

    The module retrieves policy wording/rulebook sections and delegates the
    incident-description-vs-wording comparison to a CoverageAssessmentLLMService.
    The result is a conservative pre-check for human review, not a final
    coverage decision and not a claim accept/reject decision.
    """

    module_name = "CoverageAssessmentModule"

    def __init__(
        self,
        policy_wording_retrieval_service: PolicyWordingRetrievalService | None = None,
        coverage_assessment_service: CoverageAssessmentLLMService | None = None,
    ) -> None:
        self.policy_wording_retrieval_service = (
            policy_wording_retrieval_service or PolicyWordingRetrievalService()
        )
        self.coverage_assessment_service = (
            coverage_assessment_service or DeterministicCoverageAssessmentService()
        )

    def evaluate(self, case_context: ClaimCaseContext) -> ModuleResult:
        claim_request = self._object(case_context.reference_data.claim_request)
        claim_data = self._object(claim_request.get("claim_data"))
        policy_profile = self._object(case_context.reference_data.policy_profile)

        claim_type = self._claim_type(claim_data)
        description = str(claim_data.get("description") or "").strip()
        incident_date = self._optional_string(claim_data.get("incident_date"))
        wording_sections = self._wording_sections(
            case_context=case_context,
            policy_profile=policy_profile,
            claim_type=claim_type,
            description=description,
        )

        result = self._assess_safely(
            claim_type=claim_type,
            description=description,
            incident_date=incident_date,
            wording_sections=wording_sections,
            policy_profile=policy_profile,
        )
        self._attach_result(case_context, result, wording_sections)
        return self._module_result(result)

    def _wording_sections(
        self,
        *,
        case_context: ClaimCaseContext,
        policy_profile: dict[str, Any],
        claim_type: str,
        description: str,
    ) -> list[PolicyWordingSection]:
        configured_sections = case_context.reference_data.external_reference_data.get(
            "policy_wording_sections"
        )
        if isinstance(configured_sections, list) and configured_sections:
            return [
                PolicyWordingSection.model_validate(section)
                for section in configured_sections
            ]
        return self.policy_wording_retrieval_service.get_relevant_wording_sections(
            policy_profile,
            claim_type=claim_type,
            description=description,
        )

    def _assess_safely(
        self,
        *,
        claim_type: str,
        description: str,
        incident_date: str | None,
        wording_sections: list[PolicyWordingSection],
        policy_profile: dict[str, Any],
    ) -> CoverageAssessmentResult:
        try:
            raw_result = self.coverage_assessment_service.assess_coverage(
                claim_type=claim_type,
                incident_description=description,
                incident_date=incident_date,
                wording_sections=wording_sections,
                policy_profile=policy_profile,
            )
            result = CoverageAssessmentResult.model_validate(raw_result)
            return self._normalize_result(result, wording_sections)
        except Exception:
            return self._normalize_result(
                self._safe_fallback_result(description),
                wording_sections,
            )

    def _normalize_result(
        self,
        result: CoverageAssessmentResult,
        wording_sections: list[PolicyWordingSection],
    ) -> CoverageAssessmentResult:
        section_lookup = {
            self._normalize(section.section_id): section.section_id
            for section in wording_sections
        }
        section_lookup.update(
            {
                self._normalize(section.title): section.section_id
                for section in wording_sections
            }
        )
        matched_wording_sections = [
            section_lookup.get(self._normalize(section), section)
            for section in result.matched_wording_sections
        ]
        wording_section_ids = result.wording_section_ids or [
            section.section_id for section in wording_sections
        ]
        return result.model_copy(
            update={
                "matched_wording_sections": matched_wording_sections,
                "wording_section_ids": wording_section_ids,
            }
        )

    def _safe_fallback_result(self, description: str) -> CoverageAssessmentResult:
        if self._description_is_short(description):
            return CoverageAssessmentResult(
                coverage_status="insufficient_information",
                matched_wording_sections=[],
                possible_exclusions=[],
                rationale=(
                    "Coverage assessment could not be completed, and the "
                    "incident description is too limited for a reliable pre-check."
                ),
                confidence="low",
            )
        return CoverageAssessmentResult(
            coverage_status="unclear",
            matched_wording_sections=[],
            possible_exclusions=[],
            rationale=(
                "Coverage assessment could not be completed from the available "
                "LLM output. Underwriter coverage review is needed."
            ),
            confidence="low",
        )

    def _description_is_short(self, value: str) -> bool:
        meaningful_characters = "".join(
            character for character in value if not character.isspace()
        )
        words = [word for word in value.split() if word.strip()]
        return len(meaningful_characters) < 25 or len(words) < 5

    def _attach_result(
        self,
        case_context: ClaimCaseContext,
        result: CoverageAssessmentResult,
        wording_sections: list[PolicyWordingSection],
    ) -> None:
        case_context.reference_data.external_reference_data[
            "policy_wording_sections"
        ] = [section.model_dump(mode="json") for section in wording_sections]
        case_context.generated_outputs.coverage_assessment = result
        case_context.generated_outputs.claim_review.coverage_findings = (
            result.model_dump(mode="json")
        )
        findings = (
            case_context.generated_outputs.claim_review.findings
            or ClaimReviewFindings()
        )
        findings.coverage_assessment = result
        case_context.generated_outputs.claim_review.findings = findings

    def _module_result(self, result: CoverageAssessmentResult) -> ModuleResult:
        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary=(
                "Coverage pre-check set status "
                f"{result.coverage_status} with {result.confidence} confidence."
            ),
            source_fields_used=[
                "reference_data.claim_request",
                "reference_data.policy_profile",
                "reference_data.external_reference_data.policy_wording_sections",
                "coverage_assessment_service",
            ],
        )

    def _claim_type(self, claim_data: dict[str, Any]) -> str:
        return self._optional_string(
            claim_data.get("incident_type") or claim_data.get("claim_type")
        ) or ""

    def _optional_string(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _normalize(self, value: Any) -> str:
        normalized = str(value or "").strip().lower().replace("_", " ")
        return " ".join(normalized.split())

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


__all__ = ["CoverageAssessmentModule"]
