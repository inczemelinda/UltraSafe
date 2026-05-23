from __future__ import annotations

from typing import Any

from underwright.domain.claim_analysis import PolicyWordingSection


class PolicyWordingRetrievalService:
    """Retrieves policy wording sections for claim coverage pre-checks.

    MVP implementation is static and deterministic. The service boundary keeps
    the workflow module replaceable when real wording retrieval is available.
    """

    def get_relevant_wording_sections(
        self,
        policy_profile: dict[str, Any] | None = None,
        *,
        claim_type: str | None = None,
        description: str | None = None,
    ) -> list[PolicyWordingSection]:
        _ = policy_profile
        _ = claim_type
        _ = description
        return [
            PolicyWordingSection(
                section_id="coverage.fire_damage",
                title="Fire damage coverage",
                text=(
                    "The policy may cover direct physical loss or damage to "
                    "the insured property caused by fire, smoke, or explosion."
                ),
                coverage_tags=["fire"],
            ),
            PolicyWordingSection(
                section_id="coverage.storm_damage",
                title="Storm damage coverage",
                text=(
                    "The policy may cover storm, hail, and wind damage to "
                    "the insured building when the event is sudden and accidental."
                ),
                coverage_tags=["storm", "hail", "wind"],
            ),
            PolicyWordingSection(
                section_id="coverage.water_damage",
                title="Water damage coverage",
                text=(
                    "The policy may cover sudden and accidental water damage "
                    "from burst pipes, plumbing failures, or appliance leakage."
                ),
                coverage_tags=["water damage", "water_damage", "pipe leak"],
            ),
            PolicyWordingSection(
                section_id="coverage.theft",
                title="Theft coverage",
                text=(
                    "The policy may cover theft-related loss or property damage "
                    "when supported by required incident documentation."
                ),
                coverage_tags=["theft", "burglary", "stolen"],
            ),
            PolicyWordingSection(
                section_id="exclusions.common_uncovered_events",
                title="Common exclusions and uncovered events",
                text=(
                    "The policy may exclude gradual deterioration, wear and tear, "
                    "pre-existing damage, intentional acts, and events outside "
                    "the insured period."
                ),
                exclusion_tags=[
                    "wear and tear",
                    "gradual deterioration",
                    "pre-existing",
                    "intentional",
                    "outside insured period",
                ],
            ),
        ]


PolicyWordingService = PolicyWordingRetrievalService


__all__ = ["PolicyWordingRetrievalService", "PolicyWordingService"]
