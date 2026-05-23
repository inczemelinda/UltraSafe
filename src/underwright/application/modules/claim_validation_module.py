from __future__ import annotations

from typing import Any

from underwright.domain.claim_analysis import ClaimValidationOutput
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.module_result import ModuleResult


class ClaimValidationModule:
    """Validates required claim intake data before deterministic review."""

    module_name = "ClaimValidationModule"

    required_claim_fields = [
        "claim_type",
        "incident_date",
        "incident_time",
        "description",
        "estimated_damage",
        "policy_number",
        "property_address",
        "contact_phone",
        "contact_email",
    ]

    def evaluate(self, case_context: ClaimCaseContext) -> ModuleResult:
        claim_request = case_context.reference_data.claim_request
        claim_data = self._object(claim_request.get("claim_data"))
        attachments = list(claim_request.get("attachments") or [])

        missing_fields = [
            f"claim_data.{field_name}"
            for field_name in self.required_claim_fields
            if not self._has_value(claim_data.get(field_name))
        ]
        evidence_references = [
            {
                "file_name": attachment.get("file_name"),
                "content_type": attachment.get("content_type"),
                "label": self._object(attachment.get("metadata")).get("label"),
            }
            for attachment in attachments
        ]

        attachment_warnings: list[str] = []
        if not attachments:
            missing_fields.append("attachments")
            attachment_warnings.append("No attachment metadata was provided.")
        else:
            if not self._has_photo(attachments):
                attachment_warnings.append("No photo evidence attachment was found.")
            if not self._has_document(attachments):
                attachment_warnings.append("No supporting document attachment was found.")

        output = ClaimValidationOutput(
            is_valid=not missing_fields,
            missing_required_fields=missing_fields,
            attachment_warnings=attachment_warnings,
            evidence_references=evidence_references,
        )
        case_context.generated_outputs.validation = output
        case_context.checks_and_warnings.missing_required_fields = missing_fields
        case_context.checks_and_warnings.attachment_warnings = attachment_warnings

        if missing_fields:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary="Claim intake data is missing required fields.",
                source_fields_used=[
                    "reference_data.claim_request.claim_data",
                    "reference_data.claim_request.attachments",
                ],
            )

        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary="Claim intake data passed deterministic validation.",
            source_fields_used=[
                "reference_data.claim_request.claim_data",
                "reference_data.claim_request.attachments",
            ],
        )

    def _has_value(self, value: Any) -> bool:
        return value is not None and value != "" and value != [] and value != {}

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _has_photo(self, attachments: list[dict[str, Any]]) -> bool:
        return any(self._matches_attachment(attachment, ["photo", "image", "jpg", "jpeg", "png"]) for attachment in attachments)

    def _has_document(self, attachments: list[dict[str, Any]]) -> bool:
        return any(self._matches_attachment(attachment, ["document", "pdf", "invoice", "report", "doc"]) for attachment in attachments)

    def _matches_attachment(
        self,
        attachment: dict[str, Any],
        tokens: list[str],
    ) -> bool:
        metadata = self._object(attachment.get("metadata"))
        haystack = " ".join(
            str(value or "").lower()
            for value in [
                attachment.get("file_name"),
                attachment.get("content_type"),
                metadata.get("label"),
            ]
        )
        return any(token in haystack for token in tokens)


__all__ = ["ClaimValidationModule"]
