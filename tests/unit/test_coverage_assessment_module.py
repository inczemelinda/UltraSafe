from __future__ import annotations

from typing import Any
from uuid import UUID

from underwright.application.modules.coverage_assessment_module import (
    CoverageAssessmentModule,
)
from underwright.domain.claim_analysis import PolicyWordingSection
from underwright.domain.claim_case_context import ClaimCaseContext


REQUEST_ID = UUID("83000000-0000-0000-0000-000000000001")


class FakeCoverageAssessmentService:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response or {}
        self.calls: list[dict[str, Any]] = []

    def assess_coverage(
        self,
        *,
        claim_type: str,
        incident_description: str,
        incident_date: str | None,
        wording_sections: list[PolicyWordingSection],
        policy_profile: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "claim_type": claim_type,
                "incident_description": incident_description,
                "incident_date": incident_date,
                "wording_sections": wording_sections,
                "policy_profile": policy_profile,
            }
        )
        return self.response


class FailingCoverageAssessmentService:
    def assess_coverage(self, **kwargs):
        raise RuntimeError("LLM provider unavailable")


def test_fire_claim_uses_llm_response_and_normalizes_wording_section_ids() -> None:
    llm_service = FakeCoverageAssessmentService(
        {
            "coverage_status": "potentially_covered",
            "matched_wording_sections": ["Fire damage coverage"],
            "possible_exclusions": [],
            "rationale": "Fire wording appears to fit the described smoke damage.",
            "confidence": "high",
        }
    )
    context = make_context(
        claim_type="Fire",
        description="Kitchen fire caused smoke and wall damage to the insured property.",
    )

    result = CoverageAssessmentModule(
        coverage_assessment_service=llm_service
    ).evaluate(context)

    assessment = context.generated_outputs.coverage_assessment
    assert result.status == "success"
    assert assessment is not None
    assert assessment.coverage_status == "potentially_covered"
    assert assessment.confidence == "high"
    assert assessment.matched_wording_sections == ["coverage.fire_damage"]
    assert "coverage.fire_damage" in assessment.wording_section_ids
    assert assessment.assessed_at is not None
    assert llm_service.calls[0]["claim_type"] == "Fire"
    assert context.review_state.claim_review_view is None


def test_storm_claim_uses_mocked_llm_response() -> None:
    llm_service = FakeCoverageAssessmentService(
        {
            "coverage_status": "potentially_covered",
            "matched_wording_sections": ["coverage.storm_damage"],
            "possible_exclusions": [],
            "rationale": "Storm wording explicitly refers to sudden wind damage.",
            "confidence": "high",
        }
    )
    context = make_context(
        claim_type="Storm",
        description="A sudden storm damaged roof tiles and exterior gutters.",
    )

    CoverageAssessmentModule(coverage_assessment_service=llm_service).evaluate(
        context
    )

    assessment = context.generated_outputs.coverage_assessment
    assert assessment is not None
    assert assessment.coverage_status == "potentially_covered"
    assert assessment.matched_wording_sections == ["coverage.storm_damage"]


def test_vague_description_can_return_insufficient_information() -> None:
    llm_service = FakeCoverageAssessmentService(
        {
            "coverage_status": "insufficient_information",
            "matched_wording_sections": [],
            "possible_exclusions": [],
            "rationale": "The incident description does not provide enough facts.",
            "confidence": "low",
        }
    )
    context = make_context(claim_type="Fire", description="Damage happened.")

    CoverageAssessmentModule(coverage_assessment_service=llm_service).evaluate(
        context
    )

    assessment = context.generated_outputs.coverage_assessment
    assert assessment is not None
    assert assessment.coverage_status == "insufficient_information"
    assert assessment.confidence == "low"


def test_wording_exclusion_can_return_excluded() -> None:
    llm_service = FakeCoverageAssessmentService(
        {
            "coverage_status": "excluded",
            "matched_wording_sections": [],
            "possible_exclusions": [
                "exclusions.common_uncovered_events: wear and tear"
            ],
            "rationale": "The wording identifies wear and tear as an exclusion.",
            "confidence": "medium",
        }
    )
    context = make_context(
        claim_type="Water damage",
        description=(
            "The wall shows gradual deterioration and wear and tear from a "
            "long-running leak."
        ),
    )

    CoverageAssessmentModule(coverage_assessment_service=llm_service).evaluate(
        context
    )

    assessment = context.generated_outputs.coverage_assessment
    assert assessment is not None
    assert assessment.coverage_status == "excluded"
    assert assessment.possible_exclusions == [
        "exclusions.common_uncovered_events: wear and tear"
    ]


def test_malformed_llm_response_produces_safe_unclear_result() -> None:
    llm_service = FakeCoverageAssessmentService(
        {
            "coverage_status": "accepted",
            "matched_wording_sections": ["coverage.fire_damage"],
            "possible_exclusions": [],
            "rationale": "Bad final decision language.",
            "confidence": "certain",
        }
    )
    context = make_context(
        claim_type="Fire",
        description="Kitchen fire caused smoke and wall damage to the insured property.",
    )

    CoverageAssessmentModule(coverage_assessment_service=llm_service).evaluate(
        context
    )

    assessment = context.generated_outputs.coverage_assessment
    assert assessment is not None
    assert assessment.coverage_status == "unclear"
    assert assessment.confidence == "low"
    assert "coverage.storm_damage" in assessment.wording_section_ids
    assert assessment.matched_wording_sections == []


def test_llm_service_failure_produces_safe_unclear_result() -> None:
    context = make_context(
        claim_type="Storm",
        description="A sudden storm damaged roof tiles and exterior gutters.",
    )

    CoverageAssessmentModule(
        coverage_assessment_service=FailingCoverageAssessmentService()
    ).evaluate(context)

    assessment = context.generated_outputs.coverage_assessment
    assert assessment is not None
    assert assessment.coverage_status == "unclear"
    assert assessment.confidence == "low"


def test_default_deterministic_service_is_only_a_fallback() -> None:
    context = make_context(
        claim_type="Fire",
        description="Kitchen fire caused smoke and wall damage to the insured property.",
    )

    CoverageAssessmentModule().evaluate(context)

    assessment = context.generated_outputs.coverage_assessment
    assert assessment is not None
    assert assessment.coverage_status == "potentially_covered"
    assert assessment.matched_wording_sections == ["coverage.fire_damage"]


def make_context(
    *,
    claim_type: str,
    description: str,
) -> ClaimCaseContext:
    context = ClaimCaseContext(source_inputs={"request_id": REQUEST_ID})
    context.reference_data.claim_request = {
        "request_id": str(REQUEST_ID),
        "client_id": 1001,
        "client_data": {"full_name": "Ion Popescu"},
        "claim_data": {
            "claim_type": claim_type,
            "incident_date": "2026-05-01",
            "description": description,
            "policy_number": "PAD-001",
            "property_address": "Bucharest",
            "estimated_damage": 12000,
        },
        "attachments": [],
    }
    context.reference_data.policy_profile = {
        "policy_number": "PAD-001",
        "property_address": "Bucharest",
    }
    return context
