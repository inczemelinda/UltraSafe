from __future__ import annotations

from typing import Any, Protocol

from underwright.domain.claim_analysis import (
    CoverageAssessmentResult,
    PolicyWordingSection,
)


class CoverageAssessmentLLMService(Protocol):
    """Interface for LLM-backed coverage-fit assessment."""

    def assess_coverage(
        self,
        *,
        claim_type: str,
        incident_description: str,
        incident_date: str | None,
        wording_sections: list[PolicyWordingSection],
        policy_profile: dict[str, Any],
    ) -> CoverageAssessmentResult | dict[str, Any]: ...


class DeterministicCoverageAssessmentService:
    """Fallback/test-double implementation when no LLM provider is configured."""

    def assess_coverage(
        self,
        *,
        claim_type: str,
        incident_description: str,
        incident_date: str | None,
        wording_sections: list[PolicyWordingSection],
        policy_profile: dict[str, Any],
    ) -> CoverageAssessmentResult:
        _ = incident_date
        _ = policy_profile
        incident_type = self._normalize(claim_type)
        description = incident_description.strip()

        if self._description_is_short(description):
            return CoverageAssessmentResult(
                coverage_status="insufficient_information",
                matched_wording_sections=[],
                possible_exclusions=[],
                rationale=(
                    "The claim description is too short to make a useful "
                    "coverage pre-check against policy wording."
                ),
                confidence="low",
            )

        matched_sections = self._matching_coverage_sections(
            incident_type,
            description,
            wording_sections,
        )
        possible_exclusions = self._possible_exclusions(
            description,
            wording_sections,
        )

        if matched_sections:
            return CoverageAssessmentResult(
                coverage_status="potentially_covered",
                matched_wording_sections=[
                    section.section_id for section in matched_sections
                ],
                possible_exclusions=possible_exclusions,
                rationale=(
                    "Fallback coverage pre-check found policy wording that may "
                    "cover this kind of incident. This is not a final claim decision."
                ),
                confidence="medium" if possible_exclusions else "high",
            )

        if incident_type:
            return CoverageAssessmentResult(
                coverage_status="unclear",
                matched_wording_sections=[],
                possible_exclusions=possible_exclusions,
                rationale=(
                    "Fallback coverage pre-check did not find a clear wording "
                    "match. Coverage should be reviewed by an underwriter."
                ),
                confidence="low",
            )

        return CoverageAssessmentResult(
            coverage_status="insufficient_information",
            matched_wording_sections=[],
            possible_exclusions=possible_exclusions,
            rationale=(
                "The claim type or incident type is missing, so coverage cannot "
                "be pre-checked."
            ),
            confidence="low",
        )

    def _matching_coverage_sections(
        self,
        incident_type: str,
        description: str,
        wording_sections: list[PolicyWordingSection],
    ) -> list[PolicyWordingSection]:
        haystack = self._normalize(f"{incident_type} {description}")
        return [
            section
            for section in wording_sections
            if any(self._normalize(tag) in haystack for tag in section.coverage_tags)
        ]

    def _possible_exclusions(
        self,
        description: str,
        wording_sections: list[PolicyWordingSection],
    ) -> list[str]:
        haystack = self._normalize(description)
        exclusions: list[str] = []
        for section in wording_sections:
            for tag in section.exclusion_tags:
                if self._normalize(tag) in haystack:
                    exclusions.append(f"{section.section_id}: {tag}")
        return exclusions

    def _description_is_short(self, value: str) -> bool:
        meaningful_characters = "".join(
            character for character in value if not character.isspace()
        )
        words = [word for word in value.split() if word.strip()]
        return len(meaningful_characters) < 25 or len(words) < 5

    def _normalize(self, value: Any) -> str:
        normalized = str(value or "").strip().lower().replace("_", " ")
        return " ".join(normalized.split())


__all__ = [
    "CoverageAssessmentLLMService",
    "DeterministicCoverageAssessmentService",
]
