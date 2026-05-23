from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from underwright.domain.claim_request import ClaimRequest


_DEFAULT_REQUIRED_DOCUMENT_ROLES = (
    "property_photo_after",
)
_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png"}
_ANIMAL_TOKENS = {"cat", "cats", "kitten", "dog", "dogs", "puppy", "pet", "pets"}
_PROPERTY_TOKENS = {
    "property",
    "house",
    "home",
    "building",
    "room",
    "kitchen",
    "roof",
    "wall",
    "damage",
    "incident",
    "fire",
    "flood",
    "water",
    "smoke",
    "storm",
}


@dataclass(frozen=True)
class ClaimPrecheckPolicyConfig:
    max_auto_damage: float = 100000.0
    max_claims_in_3y: int = 50
    required_document_roles: tuple[str, ...] = _DEFAULT_REQUIRED_DOCUMENT_ROLES


class ClaimPrecheckPolicyService:
    """Deterministic evidence prechecks before attachment processing."""

    def __init__(self, config: ClaimPrecheckPolicyConfig | None = None) -> None:
        self.config = config or ClaimPrecheckPolicyConfig()

    def evaluate(
        self,
        claim: ClaimRequest,
        *,
        claims_last_3y: int | None,
    ) -> dict[str, Any]:
        claim_data = claim.claim_data or {}
        reasons: list[dict[str, str]] = []

        def add_reason(code: str, message: str, severity: str = "review") -> None:
            reasons.append(
                {
                    "code": code,
                    "message": message,
                    "severity": severity,
                }
            )

        estimated_damage = self._number(
            claim_data.get("estimated_damage")
            or claim_data.get("requested_damage")
            or claim_data.get("damage_amount")
        )
        coverage_amount = self._number(claim_data.get("coverage_amount"))

        if estimated_damage is not None and estimated_damage > self.config.max_auto_damage:
            add_reason(
                "DAMAGE_AMOUNT_EXCEEDS_AUTOPROCESS_LIMIT",
                "Estimated damage exceeds deterministic auto-processing limit.",
            )

        if (
            estimated_damage is not None
            and coverage_amount is not None
            and coverage_amount > 0
            and estimated_damage > coverage_amount
        ):
            add_reason(
                "CONTRACT_LIMIT_EXCEEDED",
                "Estimated damage exceeds contract coverage amount.",
            )

        if (
            claims_last_3y is not None
            and claims_last_3y > self.config.max_claims_in_3y
        ):
            add_reason(
                "CLAIM_COUNT_3Y_EXCEEDED",
                "Client has more than allowed claims in the last 3 years.",
            )

        incident_type = self._normalize(
            claim_data.get("incident_type") or claim_data.get("claim_type")
        )
        covered_incident_types = self._normalize_set(claim_data.get("covered_incident_types"))
        if incident_type and covered_incident_types and incident_type not in covered_incident_types:
            add_reason(
                "CONTRACT_PERIL_NOT_COVERED",
                "Incident type is not covered by contract configuration.",
            )

        attachments = list(claim.attachments or [])
        present_roles = {
            str(attachment.metadata.get("document_role") or "").strip()
            for attachment in attachments
            if str(attachment.metadata.get("document_role") or "").strip()
        }
        if attachments:
            missing_roles = [
                role for role in self.config.required_document_roles if role not in present_roles
            ]
            if missing_roles:
                add_reason(
                    "REQUIRED_DOCUMENTS_MISSING",
                    f"Missing required document roles: {', '.join(missing_roles)}",
                )

        for attachment in attachments:
            content_type = str(attachment.content_type or "").strip().lower()
            if content_type not in _IMAGE_CONTENT_TYPES:
                continue

            haystack = self._attachment_haystack(attachment)
            has_animal_token = self._has_token(haystack, _ANIMAL_TOKENS)
            has_property_token = self._has_token(haystack, _PROPERTY_TOKENS)
            if has_animal_token and not has_property_token:
                add_reason(
                    "IMAGE_UNRELATED_SUBJECT",
                    (
                        f"Attachment '{attachment.file_name}' looks unrelated to property damage evidence."
                    ),
                    severity="hard",
                )
                break

        has_hard_rejection = any(
            str(reason.get("severity") or "") == "hard" for reason in reasons
        )
        status = "reject" if has_hard_rejection else "review" if reasons else "pass"
        return {
            "status": status,
            "reasons": reasons,
            "claims_last_3y": claims_last_3y,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "policy_snapshot": {
                "max_auto_damage": self.config.max_auto_damage,
                "max_claims_in_3y": self.config.max_claims_in_3y,
                "required_document_roles": list(self.config.required_document_roles),
            },
        }

    def _attachment_haystack(self, attachment: Any) -> str:
        metadata = attachment.metadata if isinstance(attachment.metadata, dict) else {}
        return " ".join(
            self._normalize(value)
            for value in (
                attachment.file_name,
                metadata.get("label"),
                metadata.get("description"),
                metadata.get("document_role"),
            )
            if value is not None
        )

    def _has_token(self, text: str, tokens: set[str]) -> bool:
        words = set(re.findall(r"[a-z0-9]+", text.lower()))
        return any(token in words for token in tokens)

    def _normalize_set(self, value: Any) -> set[str]:
        if isinstance(value, str):
            return {self._normalize(value)} if self._normalize(value) else set()
        if isinstance(value, (list, tuple, set)):
            return {self._normalize(item) for item in value if self._normalize(item)}
        return set()

    def _normalize(self, value: Any) -> str:
        return str(value or "").strip().lower().replace("-", " ").replace("_", " ")

    def _number(self, value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None


__all__ = [
    "ClaimPrecheckPolicyConfig",
    "ClaimPrecheckPolicyService",
]
