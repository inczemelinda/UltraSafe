from __future__ import annotations

from pathlib import PurePath
import re
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from underwright.application.services.claim_attachment_roles import (
    claim_analysis_attachments,
)
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.domain.claim_analysis import (
    ExtractedClaimDocument,
    ExtractedDocumentBundle,
)
from underwright.domain.claim_request import ClaimAttachmentMetadata, ClaimRequest


class ClaimDocumentExtractor(Protocol):
    """Extracts structured claim evidence data from already-stored attachments."""

    source_name: str

    def extract_documents(
        self,
        claim_request: ClaimRequest,
        attachments: list[ClaimAttachmentMetadata],
    ) -> ExtractedDocumentBundle:
        ...


class AttachmentMetadataDocumentExtractor:
    """Uses actual attachment extraction metadata when it is available.

    This adapter does not OCR, parse PDFs, call AI, or infer claim facts from
    filenames. It only translates metadata produced by the attachment
    processing path into the claim-review extraction bundle.
    """

    source_name = "attachment_extraction_metadata"

    def extract_documents(
        self,
        claim_request: ClaimRequest,
        attachments: list[ClaimAttachmentMetadata],
    ) -> ExtractedDocumentBundle:
        documents = [
            self._document_from_attachment(claim_request, attachment)
            for attachment in attachments
            if attachment.file_name
        ]
        has_completed_document = any(
            document.extraction_status == "completed" for document in documents
        )
        return ExtractedDocumentBundle(
            source=self.source_name,
            extraction_status="completed" if has_completed_document else "unavailable",
            extraction_provenance="actual",
            documents=documents,
        )

    def _document_from_attachment(
        self,
        claim_request: ClaimRequest,
        attachment: ClaimAttachmentMetadata,
    ) -> ExtractedClaimDocument:
        metadata = dict(attachment.metadata or {})
        status = self._metadata_text(metadata, "extraction_status") or "unavailable"
        extracted_text = self._metadata_text(metadata, "extracted_text")
        source = self._metadata_text(metadata, "extracted_text_source")
        extracted_fields = self._fields_from_extracted_text(extracted_text)
        message = self._message_for_status(status, metadata)
        completed = status == "completed" and bool(extracted_text.strip())

        return ExtractedClaimDocument(
            document_id=metadata.get("document_id")
            or self._document_id(claim_request.request_id, attachment.file_name),
            filename=attachment.file_name,
            document_type=self._document_type_from_metadata(metadata)
            if completed
            else "unknown",
            extracted_fields=extracted_fields if completed else {},
            extraction_confidence=self._confidence(completed, extracted_fields),
            source=self.source_name if completed else "extraction_unavailable",
            extraction_status=status if completed else self._unavailable_status(status),
            extraction_provenance="actual" if completed else "unavailable",
            extraction_message=message,
            extraction_metadata={
                **self._attachment_identity_metadata(attachment),
                "extracted_text_source": source,
                "extracted_at": self._metadata_text(metadata, "extracted_at"),
            },
        )

    def _attachment_identity_metadata(
        self,
        attachment: ClaimAttachmentMetadata,
    ) -> dict[str, Any]:
        metadata = dict(attachment.metadata or {})
        return {
            "attachment_id": self._metadata_text(metadata, "attachment_id"),
            "storage_key": self._metadata_text(metadata, "storage_key"),
            "file_url": attachment.file_url or "",
            "content_type": attachment.content_type,
        }

    def _document_type_from_metadata(self, metadata: dict[str, Any]) -> str:
        for key in ("document_role", "document_type"):
            value = self._metadata_text(metadata, key)
            if value:
                return self._normalize_identifier(value)
        return "unknown"

    def _fields_from_extracted_text(self, text: str) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        normalized_text = str(text or "").strip()
        if not normalized_text:
            return fields

        for line in normalized_text.splitlines():
            match = re.match(r"^\s*-\s*([^:]+):\s*(.+?)\s*$", line)
            if match is None:
                continue
            raw_label, raw_value = match.groups()
            key = self._normalize_identifier(raw_label)
            value = raw_value.strip()
            if key and value:
                fields[key] = value

        fields.setdefault("extracted_text", normalized_text)
        return fields

    def _message_for_status(
        self,
        status: str,
        metadata: dict[str, Any],
    ) -> str | None:
        if status == "completed":
            return "Actual attachment extraction metadata is available."
        error = (
            self._metadata_text(metadata, "extraction_error")
            or self._metadata_text(metadata, "extraction_summary_error")
        )
        if error:
            return error
        if status in {"failed", "blocked"}:
            return "Attachment extraction did not complete; manual review is required."
        if status == "skipped":
            return "No extractable text was available; manual review is required."
        return "Document extraction is unavailable; manual review is required."

    def _confidence(self, completed: bool, fields: dict[str, Any]) -> float:
        if not completed:
            return 0.0
        structured_field_count = len(
            [key for key in fields if key != "extracted_text"]
        )
        return 0.75 if structured_field_count else 0.45

    def _unavailable_status(self, status: str) -> str:
        if status in {"pending", "failed", "blocked", "skipped", "unavailable"}:
            return status
        return "unavailable"

    def _metadata_text(self, metadata: dict[str, Any], key: str) -> str:
        value = metadata.get(key)
        return value if isinstance(value, str) else "" if value is None else str(value)

    def _normalize_identifier(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

    def _document_id(self, claim_request_id: UUID, filename: str) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"underwright:claim:{claim_request_id}:attachment:{filename}",
        )


class UnavailableClaimDocumentExtractor:
    """Returns explicit unavailable extraction state without synthetic facts."""

    source_name = "extraction_unavailable"

    def extract_documents(
        self,
        claim_request: ClaimRequest,
        attachments: list[ClaimAttachmentMetadata],
    ) -> ExtractedDocumentBundle:
        return ExtractedDocumentBundle(
            source=self.source_name,
            extraction_status="unavailable",
            extraction_provenance="unavailable",
            documents=[
                ExtractedClaimDocument(
                    document_id=attachment.metadata.get("document_id")
                    or self._document_id(claim_request.request_id, attachment.file_name),
                    filename=attachment.file_name,
                    document_type="unknown",
                    extracted_fields={},
                    extraction_confidence=0.0,
                    source=self.source_name,
                    extraction_status="unavailable",
                    extraction_provenance="unavailable",
                    extraction_message=(
                        "Document extraction is unavailable; manual review is required."
                    ),
                    extraction_metadata={
                        **self._attachment_identity_metadata(attachment),
                    },
                )
                for attachment in attachments
                if attachment.file_name
            ],
        )

    def _attachment_identity_metadata(
        self,
        attachment: ClaimAttachmentMetadata,
    ) -> dict[str, Any]:
        metadata = dict(attachment.metadata or {})
        return {
            "attachment_id": str(metadata.get("attachment_id") or ""),
            "storage_key": str(metadata.get("storage_key") or ""),
            "file_url": attachment.file_url or "",
            "content_type": attachment.content_type,
        }

    def _document_id(self, claim_request_id: UUID, filename: str) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"underwright:claim:{claim_request_id}:attachment:{filename}",
        )


class DemoFilenameClaimDocumentExtractor:
    """Demo-only filename adapter for seeded/local demonstrations.

    This is intentionally isolated from the default backend path. It should only
    be enabled by explicit test or demo configuration.
    """

    source_name = "demo_mock_filename_adapter"

    document_type_by_filename = {
        "id-document.pdf": "id_document",
        "property-ownership-document.pdf": "property_ownership",
        "land-registry-extract.pdf": "land_registry_extract",
        "existing-policy-document.pdf": "policy_document",
        "bank-document.pdf": "bank_document",
        "property-photos.pdf": "property_photos",
        "photos-from-incident.pdf": "incident_photos",
        "fire-service-report.pdf": "fire_service_report",
        "emergency-report.pdf": "emergency_report",
        "police-report.pdf": "police_report",
        "official-incident-confirmation.pdf": "official_incident_confirmation",
    }

    def extract_documents(
        self,
        claim_request: ClaimRequest,
        attachments: list[ClaimAttachmentMetadata],
    ) -> ExtractedDocumentBundle:
        return ExtractedDocumentBundle(
            source=self.source_name,
            extraction_status="demo_mock",
            extraction_provenance="demo_mock",
            documents=[
                self._document_from_attachment(claim_request, attachment)
                for attachment in attachments
                if attachment.file_name
            ],
        )

    def infer_document_type(self, filename: str) -> str:
        normalized_filename = self._normalized_filename(filename)
        return self.document_type_by_filename.get(normalized_filename, "unknown")

    def _document_from_attachment(
        self,
        claim_request: ClaimRequest,
        attachment: ClaimAttachmentMetadata,
    ) -> ExtractedClaimDocument:
        document_type = self.infer_document_type(attachment.file_name)
        return ExtractedClaimDocument(
            document_id=attachment.metadata.get("document_id")
            or self._document_id(claim_request.request_id, attachment.file_name),
            filename=attachment.file_name,
            document_type=document_type,
            extracted_fields=self._mock_extracted_fields(
                document_type,
                claim_request,
                attachment,
            ),
            extraction_confidence=self._mock_confidence(document_type),
            source=self.source_name,
            extraction_status="demo_mock",
            extraction_provenance="demo_mock",
            extraction_message=(
                "Demo/mock extraction derived from filename; not authoritative evidence."
            ),
            extraction_metadata={
                **self._attachment_identity_metadata(attachment),
                "demo_mock": True,
            },
        )

    def _attachment_identity_metadata(
        self,
        attachment: ClaimAttachmentMetadata,
    ) -> dict[str, Any]:
        metadata = dict(attachment.metadata or {})
        return {
            "attachment_id": str(metadata.get("attachment_id") or ""),
            "storage_key": str(metadata.get("storage_key") or ""),
            "file_url": attachment.file_url or "",
            "content_type": attachment.content_type,
        }

    def _mock_extracted_fields(
        self,
        document_type: str,
        claim_request: ClaimRequest,
        attachment: ClaimAttachmentMetadata,
    ) -> dict[str, Any]:
        claim_data = claim_request.claim_data
        client_data = claim_request.client_data
        property_address = claim_data.get("property_address")
        policy_number = claim_data.get("policy_number")
        full_name = client_data.get("full_name")

        fields_by_type: dict[str, dict[str, Any]] = {
            "id_document": {
                "document_holder_name": full_name,
                "identity_verified": full_name is not None,
                "issuing_country": "RO",
            },
            "property_ownership": {
                "owner_name": full_name,
                "property_address": property_address,
                "ownership_status": "owner_declared",
            },
            "land_registry_extract": {
                "registered_owner": full_name,
                "property_address": property_address,
                "cadastral_reference_present": True,
            },
            "policy_document": {
                "policy_number": policy_number,
                "insured_name": full_name,
                "insured_property_address": property_address,
                "coverage_amount": claim_data.get("coverage_amount"),
            },
            "bank_document": {
                "account_holder": full_name,
                "iban_present": True,
                "bank_name": "Mock Bank",
            },
            "property_photos": {
                "property_address": property_address,
                "photo_set_type": "property_condition",
                "photo_count": 3,
            },
            "incident_photos": {
                "incident_date": claim_data.get("incident_date"),
                "photo_set_type": "incident_damage",
                "visible_damage": True,
                "photo_count": 4,
            },
            "fire_service_report": {
                "authority_verified": True,
                "incident_type": "fire",
                "incident_date": claim_data.get("incident_date"),
                "reference_number": "MOCK-FIRE-REPORT",
            },
            "emergency_report": {
                "authority_verified": True,
                "incident_type": claim_data.get("claim_type"),
                "incident_date": claim_data.get("incident_date"),
                "reference_number": "MOCK-EMERGENCY-REPORT",
            },
            "police_report": {
                "authority_verified": True,
                "incident_type": claim_data.get("claim_type"),
                "incident_date": claim_data.get("incident_date"),
                "reference_number": "MOCK-POLICE-REPORT",
            },
            "official_incident_confirmation": {
                "authority_verified": True,
                "incident_type": claim_data.get("claim_type"),
                "incident_date": claim_data.get("incident_date"),
                "reference_number": "MOCK-OFFICIAL-CONFIRMATION",
            },
        }
        return fields_by_type.get(
            document_type,
            {
                "filename": attachment.file_name,
                "content_type": attachment.content_type,
                "mock_note": (
                    "No structured demo/mock fields are configured for this filename."
                ),
            },
        )

    def _mock_confidence(self, document_type: str) -> float:
        if document_type == "unknown":
            return 0.2
        if document_type in {"property_photos", "incident_photos"}:
            return 0.65
        return 0.8

    def _document_id(self, claim_request_id: UUID, filename: str) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"underwright:claim:{claim_request_id}:attachment:{filename}",
        )

    def _normalized_filename(self, filename: str) -> str:
        return PurePath(filename).name.strip().lower().replace("_", "-")


class ExtractedDocumentDataService:
    """Loads extracted document facts through an explicit extractor adapter."""

    def __init__(
        self,
        claim_request_service: ClaimRequestService,
        extractor: ClaimDocumentExtractor | None = None,
        *,
        allow_demo_filename_extraction: bool = False,
    ) -> None:
        self.claim_request_service = claim_request_service
        if extractor is not None:
            self.extractor = extractor
        elif allow_demo_filename_extraction:
            self.extractor = DemoFilenameClaimDocumentExtractor()
        else:
            self.extractor = AttachmentMetadataDocumentExtractor()

    def get_extracted_documents(
        self,
        claim_request_id: str,
        additional_attachments: list[ClaimAttachmentMetadata] | None = None,
    ) -> ExtractedDocumentBundle:
        claim_request = self.claim_request_service.get_claim_request_detail(
            UUID(claim_request_id)
        )
        attachments = [
            *claim_request.attachments,
            *(additional_attachments or []),
        ]
        analysis_attachments = claim_analysis_attachments(attachments)
        return self.extractor.extract_documents(claim_request, analysis_attachments)


__all__ = [
    "AttachmentMetadataDocumentExtractor",
    "ClaimDocumentExtractor",
    "DemoFilenameClaimDocumentExtractor",
    "ExtractedDocumentDataService",
    "UnavailableClaimDocumentExtractor",
]
