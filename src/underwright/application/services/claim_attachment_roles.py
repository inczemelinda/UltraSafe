from __future__ import annotations

import re
from typing import Any

from underwright.domain.claim_request import ClaimAttachmentMetadata


OPTIONAL_LEGAL_DOCUMENT_ROLES = frozenset(
    {
        "bank_document",
        "company_registration",
        "existing_policy",
        "id_document",
        "identity_document",
        "land_registry",
        "land_registry_extract",
        "policy_document",
        "property_ownership",
        "property_ownership_document",
        "terms_consent",
    }
)

OPTIONAL_LEGAL_DOCUMENT_PHRASES = (
    "bank document",
    "company registration",
    "consent document",
    "existing policy",
    "id document",
    "identity card",
    "identity document",
    "insurance policy",
    "land registry",
    "national id",
    "passport",
    "policy document",
    "proof of ownership",
    "property deed",
    "property ownership",
    "signed policy",
    "terms consent",
    "title deed",
)


def claim_analysis_attachments(
    attachments: list[ClaimAttachmentMetadata],
) -> list[ClaimAttachmentMetadata]:
    return [
        attachment
        for attachment in attachments
        if not is_optional_legal_claim_attachment(attachment)
    ]


def is_optional_legal_claim_attachment(
    attachment: ClaimAttachmentMetadata,
) -> bool:
    metadata = _metadata(attachment)
    role = _normalize_identifier(
        metadata.get("document_role")
        or metadata.get("document_type")
        or metadata.get("category")
    )
    if role in OPTIONAL_LEGAL_DOCUMENT_ROLES:
        return True

    haystack = _normalize_text(
        " ".join(
            str(value or "")
            for value in (
                attachment.file_name,
                attachment.content_type,
                metadata.get("label"),
                metadata.get("document_role"),
                metadata.get("document_type"),
                metadata.get("source"),
            )
        )
    )
    return any(phrase in haystack for phrase in OPTIONAL_LEGAL_DOCUMENT_PHRASES)


def _metadata(attachment: ClaimAttachmentMetadata) -> dict[str, Any]:
    return attachment.metadata if isinstance(attachment.metadata, dict) else {}


def _normalize_identifier(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_./-]+", " ", value.lower())).strip()


__all__ = [
    "OPTIONAL_LEGAL_DOCUMENT_PHRASES",
    "OPTIONAL_LEGAL_DOCUMENT_ROLES",
    "claim_analysis_attachments",
    "is_optional_legal_claim_attachment",
]
