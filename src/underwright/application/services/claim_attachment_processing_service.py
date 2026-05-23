from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any
from uuid import UUID

from underwright.application.ports import (
    ClaimAttachmentSummaryGenerator,
    ClaimAttachmentTextExtractor,
)
from underwright.application.services.claim_attachment_roles import (
    claim_analysis_attachments,
    is_optional_legal_claim_attachment,
)
from underwright.application.services.claim_attachment_storage_service import (
    ClaimAttachmentStorageService,
)
from underwright.application.services.claim_precheck_policy_service import (
    ClaimPrecheckPolicyService,
)
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.domain.claim_request import ClaimRequest


class ClaimAttachmentProcessingService:
    """Runs deterministic checks, extraction, and summary persistence for claim evidence."""

    def __init__(
        self,
        *,
        claim_request_service: ClaimRequestService,
        storage_service: ClaimAttachmentStorageService,
        precheck_policy_service: ClaimPrecheckPolicyService,
        text_extractor: ClaimAttachmentTextExtractor,
        summary_generator: ClaimAttachmentSummaryGenerator,
    ) -> None:
        self.claim_request_service = claim_request_service
        self.storage_service = storage_service
        self.precheck_policy_service = precheck_policy_service
        self.text_extractor = text_extractor
        self.summary_generator = summary_generator

    def process_request_attachments(self, request_id: UUID) -> ClaimRequest:
        claim = self.claim_request_service.get_claim_request_detail(request_id)
        analysis_claim = self._analysis_claim(claim)
        precheck = self._evaluate_precheck(analysis_claim)
        claim_data = dict(claim.claim_data or {})
        claim_data["precheck_policy_decision"] = precheck
        self.claim_request_service.update_request_claim_data(request_id, claim_data)

        if precheck.get("status") == "reject":
            return self._block_processing_for_rejected_precheck(
                request_id,
                claim,
                precheck,
            )

        extraction_results = self.text_extractor.extract_texts(
            analysis_claim,
            self.storage_service,
        )
        global_summary = self.summary_generator.summarize(
            extraction_results,
            claim_context=self._claim_context(analysis_claim),
        )
        extracted_at = datetime.now(timezone.utc).isoformat()
        global_summary_text = str(global_summary.get("summary") or "").strip()
        global_summary_error = global_summary.get("error")

        claim_data = dict(claim.claim_data or {})
        claim_data["precheck_policy_decision"] = precheck
        claim_data["attachment_extraction_summary"] = {
            "summary": global_summary_text,
            "error": str(global_summary_error) if global_summary_error else None,
            "extracted_at": extracted_at,
            "source": "global_summary",
            **self._attachment_summary_provenance(
                request_id,
                analysis_claim.attachments,
            ),
        }
        self.claim_request_service.update_request_claim_data(request_id, claim_data)

        updated_attachments = self._attachments_with_extraction_metadata(
            claim,
            analysis_claim.attachments,
            extraction_results,
            global_summary_text=global_summary_text,
            global_summary_error=global_summary_error,
            extracted_at=extracted_at,
        )
        return self.claim_request_service.update_request_attachments(
            request_id,
            updated_attachments,
        )

    def _evaluate_precheck(self, claim: ClaimRequest) -> dict[str, Any]:
        since = datetime.now(timezone.utc) - timedelta(days=365 * 3)
        claims_last_3y = self.claim_request_service.count_client_claims_since(
            claim.client_id,
            since,
        )
        return self.precheck_policy_service.evaluate(
            claim,
            claims_last_3y=claims_last_3y,
        )

    def _analysis_claim(self, claim: ClaimRequest) -> ClaimRequest:
        return claim.model_copy(
            update={"attachments": claim_analysis_attachments(list(claim.attachments))}
        )

    def _block_processing_for_rejected_precheck(
        self,
        request_id: UUID,
        claim: ClaimRequest,
        precheck: dict[str, Any],
    ) -> ClaimRequest:
        blocked_at = datetime.now(timezone.utc).isoformat()
        reasons = [
            item for item in list(precheck.get("reasons") or []) if isinstance(item, dict)
        ]
        reason_codes = [
            str(item.get("code") or "") for item in reasons if item.get("code")
        ]
        reason_text = ", ".join(reason_codes)
        blocked_attachments: list[dict[str, Any]] = []

        for attachment in claim.attachments:
            attachment_data = attachment.model_dump(mode="json")
            metadata = dict(attachment_data.get("metadata") or {})
            metadata["extraction_status"] = "blocked"
            metadata["extraction_error"] = (
                "Deterministic precheck rejected attachment processing"
            )
            metadata["extraction_summary_error"] = (
                f"Precheck reason codes: {reason_text}" if reason_text else None
            )
            metadata["extraction_summary_path"] = None
            metadata["extracted_text"] = ""
            metadata["extracted_text_source"] = None
            metadata["extracted_at"] = blocked_at
            attachment_data["metadata"] = metadata
            blocked_attachments.append(attachment_data)

        claim_data = dict(claim.claim_data or {})
        claim_data["precheck_policy_decision"] = precheck
        claim_data["attachment_extraction_summary"] = {
            "summary": "",
            "error": "Attachment processing was blocked by deterministic precheck.",
            "extracted_at": blocked_at,
            "source": "precheck",
            **self._attachment_summary_provenance(
                request_id,
                self._analysis_claim(claim).attachments,
            ),
        }
        self.claim_request_service.update_request_claim_data(
            request_id,
            claim_data,
            "precheck_rejected",
        )
        return self.claim_request_service.update_request_attachments(
            request_id,
            blocked_attachments,
        )

    def _attachments_with_extraction_metadata(
        self,
        claim: ClaimRequest,
        analysis_attachments: list,
        extraction_results: list[dict[str, Any]],
        *,
        global_summary_text: str,
        global_summary_error: Any,
        extracted_at: str,
    ) -> list[dict[str, Any]]:
        updated_attachments: list[dict[str, Any]] = []
        extraction_results_by_key = {
            self._attachment_key(attachment): extraction_results[index]
            for index, attachment in enumerate(analysis_attachments)
            if index < len(extraction_results)
        }

        for attachment in claim.attachments:
            attachment_data = attachment.model_dump(mode="json")
            metadata = dict(attachment_data.get("metadata") or {})
            if is_optional_legal_claim_attachment(attachment):
                metadata["extraction_status"] = "skipped"
                metadata["extraction_error"] = None
                metadata["extraction_summary_error"] = None
                metadata["extraction_summary_path"] = None
                metadata["extracted_text"] = ""
                metadata["extracted_text_source"] = None
                metadata["extraction_skip_reason"] = "optional_legal_document"
                metadata["extracted_at"] = extracted_at
                attachment_data["metadata"] = metadata
                updated_attachments.append(attachment_data)
                continue

            result = extraction_results_by_key.get(self._attachment_key(attachment))
            if result is None:
                metadata["extraction_status"] = "failed"
                metadata["extraction_error"] = "Missing extraction result for attachment."
                metadata["extraction_summary_error"] = None
                metadata["extraction_summary_path"] = None
                metadata["extracted_text"] = ""
                metadata["extracted_text_source"] = None
            else:
                error = result.get("error")
                text = str(result.get("text") or "")
                has_extracted_text = not error and bool(text.strip())
                highlights_text = self._summarize_attachment_text_highlights(text)

                if error:
                    metadata["extraction_status"] = "failed"
                elif not text.strip():
                    metadata["extraction_status"] = "skipped"
                elif global_summary_error or not global_summary_text:
                    metadata["extraction_status"] = "failed"
                else:
                    metadata["extraction_status"] = "completed"

                metadata["extraction_error"] = str(error) if error else None
                metadata["extraction_summary_error"] = (
                    str(global_summary_error)
                    if has_extracted_text and global_summary_error
                    else None
                )
                metadata["extraction_summary_path"] = (
                    "claim_data.attachment_extraction_summary.summary"
                    if has_extracted_text
                    else None
                )
                metadata["extracted_text"] = highlights_text if has_extracted_text else ""
                metadata["extracted_text_source"] = (
                    "attachment_extraction_highlights" if has_extracted_text else None
                )

            metadata["extracted_at"] = extracted_at
            attachment_data["metadata"] = metadata
            updated_attachments.append(attachment_data)

        return updated_attachments

    def _attachment_key(self, attachment: Any) -> str:
        metadata = attachment.metadata if isinstance(attachment.metadata, dict) else {}
        return str(
            metadata.get("attachment_id")
            or metadata.get("storage_key")
            or attachment.file_url
            or attachment.file_name
        )

    def _attachment_summary_provenance(
        self,
        request_id: UUID,
        attachments: list[Any],
    ) -> dict[str, Any]:
        attachment_keys = [
            key for attachment in attachments if (key := self._attachment_key(attachment))
        ]
        return {
            "claim_request_id": str(request_id),
            "attachment_keys": attachment_keys,
            "attachment_count": len(attachment_keys),
        }

    def _claim_context(self, claim: ClaimRequest) -> dict[str, Any]:
        claim_data = dict(claim.claim_data or {})
        context = {
            "claim_type": claim_data.get("claim_type") or claim_data.get("incident_type"),
            "description": claim_data.get("description")
            or claim_data.get("incident_description"),
            "incident_date": claim_data.get("incident_date"),
            "incident_time": claim_data.get("incident_time"),
            "estimated_damage": claim_data.get("estimated_damage"),
            "policy_number": claim_data.get("policy_number"),
            "property_address": claim_data.get("property_address"),
        }
        return {
            key: value
            for key, value in context.items()
            if value is not None and str(value).strip()
        }

    def _summarize_attachment_text_highlights(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        if not normalized:
            return ""

        lines: list[str] = []
        seen: set[str] = set()

        def capture(label: str, pattern: str) -> None:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match is None:
                return
            raw_value = str(match.group(1) or "").strip()
            if not raw_value:
                return
            value = re.sub(r"[.;,]$", "", raw_value)
            dedupe_key = f"{label}:{value}".lower()
            if dedupe_key in seen:
                return
            seen.add(dedupe_key)
            lines.append(f"- {label}: {value}")

        capture(
            "Policy number",
            r"(?:policy(?:\s*no\.?|\s*number)?)[\s:#-]*([A-Z0-9-]{4,})",
        )
        capture(
            "Claim number",
            r"(?:claim(?:\s*no\.?|\s*number)?)[\s:#-]*([A-Z0-9-]{4,})",
        )
        capture(
            "Incident date",
            r"(?:incident\s*date|date\s*of\s*loss)[\s:#-]*([0-9]{1,2}[\/.-][0-9]{1,2}[\/.-][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4})",
        )
        capture(
            "Amount",
            r"(?:total|amount|damage|estimate|estimated\s*damage)[^\d]{0,15}(\$?\s?[0-9]{1,3}(?:[,\.\s][0-9]{3})*(?:[,.][0-9]{2})?\s?(?:RON|EUR|USD)?)",
        )

        for visual_line in self._claim_photo_analysis_lines(text):
            dedupe_key = visual_line.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            lines.append(visual_line)

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", normalized)
            if sentence.strip() and len(sentence.strip()) > 35
        ]
        priority_sentences = [
            sentence
            for sentence in sentences
            if re.search(
                r"(claim|policy|loss|incident|damage|coverage|invoice|report|repair|denied|approved|missing)",
                sentence,
                flags=re.IGNORECASE,
            )
        ]

        summary_sentence = (
            priority_sentences[0]
            if priority_sentences
            else (sentences[0] if sentences else "")
        ).strip()
        if summary_sentence:
            lines.append(f"- Summary: {summary_sentence[:260]}")

        return "\n".join(lines[:5])

    def _claim_photo_analysis_lines(self, text: str) -> list[str]:
        allowed_labels = {
            "affected area": "Affected area",
            "damage severity": "Damage severity",
            "photo uncertainty": "Photo uncertainty",
            "readable text": "Readable text",
            "relevant conditions": "Relevant conditions",
            "visible damage": "Visible damage",
        }
        lines: list[str] = []
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip().lstrip("-* ").strip()
            match = re.match(r"^([^:]{3,40}):\s*(.+?)\s*$", line)
            if match is None:
                continue
            label, value = match.groups()
            normalized_label = re.sub(r"\s+", " ", label.strip().lower())
            readable_label = allowed_labels.get(normalized_label)
            if readable_label is None:
                continue
            value = value.strip()
            if not value:
                continue
            lines.append(f"- {readable_label}: {value}")
        return lines


__all__ = ["ClaimAttachmentProcessingService"]
