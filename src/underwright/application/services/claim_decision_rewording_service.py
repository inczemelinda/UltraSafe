from __future__ import annotations

from typing import Protocol


SUPPORTED_REWORD_DECISIONS = {"approved", "denied", "inspection_requested"}

META_COMMENT_PHRASES = (
    "the justification provided is inappropriate",
    "the provided justification is inappropriate",
    "justification provided is inappropriate",
    "lacks professionalism",
    "lack professionalism",
    "unprofessional",
    "inappropriate",
    "please provide",
    "cannot reword",
    "can't reword",
    "unable to reword",
    "i cannot",
    "i can't",
    "as an ai",
)

FALLBACK_REWORDING_BY_DECISION = {
    "approved": (
        "Based on the claim review, the submitted information supports approval "
        "under the applicable policy terms. The claim has therefore been "
        "approved, and the claims team will continue with the next steps."
    ),
    "denied": (
        "Based on the claim review, the submitted information does not provide "
        "sufficient support for approval under the applicable policy terms. "
        "The claim has therefore been denied. Please contact the claims team if "
        "you would like additional clarification or wish to provide further "
        "documentation."
    ),
    "inspection_requested": (
        "Based on the claim review, additional on-site assessment is required "
        "before a final decision can be completed. An inspection has therefore "
        "been requested so the claims team can verify the damage and supporting "
        "details."
    ),
}

DEFAULT_FALLBACK_REWORDING = (
    "Based on the claim review, the submitted information has been assessed "
    "under the applicable policy terms. The decision explanation should reflect "
    "the evidence available, any remaining documentation gaps, and the policy "
    "reasoning used by the claims team."
)


class ClaimDecisionRewordingNotConfiguredError(RuntimeError):
    pass


class ClaimDecisionRewordingProviderError(RuntimeError):
    pass


class ClaimDecisionRewordingProvider(Protocol):
    def reword_decision_justification(
        self,
        *,
        justification: str,
        decision: str | None = None,
    ) -> str:
        ...


class ClaimDecisionRewordingService:
    def __init__(
        self,
        provider: ClaimDecisionRewordingProvider | None = None,
    ) -> None:
        self.provider = provider

    def reword_decision_justification(
        self,
        *,
        justification: str,
        decision: str | None = None,
    ) -> str:
        trimmed = justification.strip()
        if not trimmed:
            raise ValueError("Decision justification is required.")

        normalized_decision = decision.strip().lower() if decision else None
        if normalized_decision and normalized_decision not in SUPPORTED_REWORD_DECISIONS:
            raise ValueError(
                "Decision must be approved, denied, or inspection_requested."
            )

        if self.provider is None:
            raise ClaimDecisionRewordingNotConfiguredError(
                "AI rewording is not configured."
            )

        suggestion = self.provider.reword_decision_justification(
            justification=trimmed,
            decision=normalized_decision,
        ).strip()
        if not suggestion:
            raise ClaimDecisionRewordingProviderError(
                "AI provider returned an empty suggestion."
            )
        if is_meta_comment_suggestion(suggestion):
            return fallback_decision_justification(normalized_decision)
        return suggestion


def fallback_decision_justification(decision: str | None = None) -> str:
    normalized_decision = decision.strip().lower() if decision else None
    if normalized_decision in FALLBACK_REWORDING_BY_DECISION:
        return FALLBACK_REWORDING_BY_DECISION[normalized_decision]
    return DEFAULT_FALLBACK_REWORDING


def is_meta_comment_suggestion(suggestion: str) -> bool:
    normalized = " ".join(suggestion.lower().split())
    return any(phrase in normalized for phrase in META_COMMENT_PHRASES)


__all__ = [
    "ClaimDecisionRewordingNotConfiguredError",
    "ClaimDecisionRewordingProviderError",
    "ClaimDecisionRewordingService",
    "SUPPORTED_REWORD_DECISIONS",
    "fallback_decision_justification",
    "is_meta_comment_suggestion",
]
