from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from underwright.application.services.case_context_service import CaseContextService
from underwright.application.services.claim_attachment_roles import (
    claim_analysis_attachments,
)
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.domain.claim_analysis import EvidenceRequestDraft
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_request import ClaimRequest
from underwright.domain.claim_review_models import (
    ClaimAttachmentsPanel,
    ClaimClientPanel,
    ClaimDetailPanel,
    ClaimReviewHeader,
    ClaimReviewView,
)


class ClaimReviewQueryResult(BaseModel):
    claim_request: ClaimRequest
    case_context: ClaimCaseContext | None = None
    review_view: dict[str, Any]
    status: str
    review_state: str
    evidence_request_draft: EvidenceRequestDraft | None = None


class ClaimReviewQueryService:
    """Loads latest persisted claim review state without running analysis."""

    def __init__(
        self,
        claim_request_service: ClaimRequestService,
        case_context_service: CaseContextService,
    ) -> None:
        self.claim_request_service = claim_request_service
        self.case_context_service = case_context_service

    def get_latest_claim_review(self, request_id: UUID) -> ClaimReviewQueryResult:
        claim_request = self.claim_request_service.get_claim_request_detail(
            request_id
        )
        try:
            case_context = (
                self.case_context_service.get_latest_claim_case_context_by_request_id(
                    request_id
                )
            )
        except ValueError:
            review_view = self._empty_review_view(claim_request)
            return ClaimReviewQueryResult(
                claim_request=claim_request,
                review_view=review_view,
                status="not_started",
                review_state="not_started",
            )

        review_state = self._review_state(case_context)
        review_view = self._review_view(case_context, claim_request, review_state)
        return ClaimReviewQueryResult(
            claim_request=claim_request,
            case_context=case_context,
            review_view=review_view,
            status=case_context.case_metadata.status,
            review_state=review_state,
            evidence_request_draft=case_context.generated_outputs.evidence_request_draft,
        )

    def _review_view(
        self,
        case_context: ClaimCaseContext,
        claim_request: ClaimRequest,
        review_state: str,
    ) -> dict[str, Any]:
        persisted_view = self._object(case_context.review_state.claim_review_view)
        if persisted_view:
            review_view = dict(persisted_view)
        else:
            review_view = self._empty_review_view(
                claim_request,
                case_context=case_context,
                workflow_status=case_context.case_metadata.status,
            )

        coverage_assessment = case_context.generated_outputs.coverage_assessment
        if coverage_assessment is not None:
            coverage_data = coverage_assessment.model_dump(mode="json")
            if not review_view.get("coverage_precheck"):
                review_view["coverage_precheck"] = coverage_data
            if not review_view.get("coverage_assessment"):
                review_view["coverage_assessment"] = coverage_data

        if case_context.generated_outputs.document_consistency is None:
            review_view["document_consistency"] = {
                "status": "not_started",
                "message": (
                    "Document consistency review has not started."
                    if review_state == "coverage_precheck_only"
                    else "Claim review analysis has not started."
                ),
                "supporting_fact_count": 0,
                "discrepancy_count": 0,
            }
        if not review_view.get("extracted_documents"):
            review_view["extracted_documents"] = (
                case_context.reference_data.extracted_documents.model_dump(mode="json")
            )

        evidence_requirements = case_context.generated_outputs.evidence_requirements
        if evidence_requirements is not None:
            required_evidence = [
                requirement.model_dump(mode="json")
                for requirement in evidence_requirements.required_evidence
            ]
            review_view["required_evidence"] = required_evidence
            review_view["missing_evidence"] = required_evidence
            review_view.setdefault(
                "suggested_next_action",
                evidence_requirements.suggested_next_action,
            )

        draft = case_context.generated_outputs.evidence_request_draft
        if draft is not None:
            review_view["evidence_request_draft"] = draft.model_dump(mode="json")

        suggestion_states = (
            case_context.generated_outputs.communication_suggestion_states
        )
        if suggestion_states:
            review_view["communication_suggestion_states"] = {
                suggestion_id: state.model_dump(mode="json")
                for suggestion_id, state in suggestion_states.items()
            }

        available_actions = list(
            review_view.get("available_actions")
            or case_context.review_state.available_actions
            or self._available_actions(review_state)
        )
        if review_state == "full_review":
            available_actions = [
                action for action in available_actions if action != "start_analysis"
            ] or self._available_actions(review_state)
        review_view["available_actions"] = available_actions

        self._add_attachment_summary_finding(review_view, claim_request)

        return review_view

    def _empty_review_view(
        self,
        claim_request: ClaimRequest,
        *,
        case_context: ClaimCaseContext | None = None,
        workflow_status: str = "not_started",
    ) -> dict[str, Any]:
        claim_data = claim_request.claim_data
        attachments = [
            attachment.model_dump(mode="json")
            for attachment in claim_request.attachments
        ]
        view = ClaimReviewView(
            header=ClaimReviewHeader(
                case_id=(
                    case_context.case_metadata.case_id
                    if case_context is not None
                    else None
                ),
                request_id=claim_request.request_id,
                domain="claims",
                workflow_status=workflow_status,
            ),
            client_panel=ClaimClientPanel(
                client_id=claim_request.client_id,
                client_data=claim_request.client_data,
            ),
            claim_detail_panel=ClaimDetailPanel(claim_data=claim_data),
            attachments_panel=ClaimAttachmentsPanel(attachments=attachments),
            document_consistency={
                "status": "not_started",
                "message": "Claim review analysis has not started.",
                "supporting_fact_count": 0,
                "discrepancy_count": 0,
            },
            supporting_facts=[],
            discrepancies=[],
            required_evidence=[],
            missing_evidence=[],
            suggested_next_action="start_analysis",
            human_readable_summary="Claim review analysis has not started.",
            available_actions=["start_analysis"],
        )
        review_view = view.model_dump(mode="json")
        self._add_attachment_summary_finding(review_view, claim_request)
        return review_view

    def _add_attachment_summary_finding(
        self,
        review_view: dict[str, Any],
        claim_request: ClaimRequest,
    ) -> None:
        existing_findings = self._findings(review_view)
        if existing_findings:
            return

        summary = self._attachment_extraction_summary_text(claim_request)
        if not summary:
            return

        review_view["ai_review_findings"] = [
            {
                "id": f"attachment-summary-{claim_request.request_id}",
                "claim_id": str(claim_request.request_id),
                "finding_type": "document_summary",
                "description": summary,
                "related_document": "all_attachments",
                "source": (
                    "claim_data.attachment_extraction_summary.summary"
                ),
            }
        ]

    def _attachment_extraction_summary_text(
        self,
        claim_request: ClaimRequest,
    ) -> str:
        claim_data = self._object(claim_request.claim_data)
        summary_data = self._object(claim_data.get("attachment_extraction_summary"))
        if not self._attachment_summary_matches_claim(claim_request, summary_data):
            return ""
        return self._format_attachment_summary_text(
            str(summary_data.get("summary") or "")
        )

    def _attachment_summary_matches_claim(
        self,
        claim_request: ClaimRequest,
        summary_data: dict[str, Any],
    ) -> bool:
        summary_request_id = str(summary_data.get("claim_request_id") or "")
        if summary_request_id != str(claim_request.request_id):
            return False

        summary_attachment_keys = self._string_list(summary_data.get("attachment_keys"))
        if not summary_attachment_keys:
            return False

        current_attachment_keys = [
            self._attachment_key(attachment)
            for attachment in claim_analysis_attachments(list(claim_request.attachments))
        ]
        return summary_attachment_keys == current_attachment_keys

    def _attachment_key(self, attachment: Any) -> str:
        metadata = attachment.metadata if isinstance(attachment.metadata, dict) else {}
        return str(
            metadata.get("attachment_id")
            or metadata.get("storage_key")
            or attachment.file_url
            or attachment.file_name
        )

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item]

    def _format_attachment_summary_text(self, raw_summary: str) -> str:
        text = str(raw_summary or "").strip()
        if not text:
            return ""

        lines = [line.strip() for line in self._attachment_summary_lines(text)]
        cleaned: list[str] = []

        for line in lines:
            if not line:
                if cleaned and cleaned[-1] != "":
                    cleaned.append("")
                continue

            normalized = line
            normalized = self._strip_markdown_emphasis(normalized)

            # Convert markdown headings into plain section labels.
            if normalized.startswith("#"):
                normalized = normalized.lstrip("#").strip()
                if normalized and not normalized.endswith(":"):
                    normalized = f"{normalized}:"

            # Normalize list markers to a consistent bullet style.
            normalized = self._normalize_summary_bullet(normalized)
            normalized = self._clean_legacy_attachment_summary_signal(normalized)
            normalized = self._clean_summary_label(normalized)

            if normalized:
                cleaned.append(normalized)

        # Remove trailing blank separators.
        while cleaned and cleaned[-1] == "":
            cleaned.pop()

        formatted = "\n".join(cleaned).strip()
        return formatted or text

    def _attachment_summary_lines(self, value: str) -> list[str]:
        text = value.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(
            r"(Evidence signals|Out of place\s*/\s*needs review|Out of place needs review|Follow[- ]up|Needs review|Recommendation|Recommended next step)\s*:",
            self._attachment_summary_section_replacement,
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r":\s*[-*]\s+", ":\n- ", text)
        text = re.sub(r"([.!?])\s+[-*]\s+(?=[A-Z0-9\"'])", r"\1\n- ", text)
        text = re.sub(r"\s+[-*]\s+(?=[A-Z0-9\"'])", "\n- ", text)
        return text.splitlines()

    def _attachment_summary_section_replacement(self, match: re.Match[str]) -> str:
        prefix = "" if match.start() == 0 or match.string[match.start() - 1] == "\n" else "\n"
        return f"{prefix}{self._canonical_attachment_summary_label(match.group(1))}:"

    def _canonical_attachment_summary_label(self, value: str) -> str:
        normalized = " ".join(value.lower().replace("-", " ").replace("/", " ").split())
        replacements = {
            "evidence signals": "Evidence signals",
            "follow up": "Follow-up",
            "needs review": "Needs review",
            "out of place needs review": "Out of place / needs review",
            "recommendation": "Recommendation",
            "recommended next step": "Recommended next step",
        }
        return replacements.get(normalized, value.strip())

    def _strip_markdown_emphasis(self, value: str) -> str:
        text = value.strip()
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        text = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", text)
        text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", text)
        return text.strip()

    def _normalize_summary_bullet(self, value: str) -> str:
        text = value.strip()
        text = re.sub(r"^[*\-]\s+", "- ", text)
        text = re.sub(r"^\d+[.)]\s+", "- ", text)
        return text.strip()

    def _clean_legacy_attachment_summary_signal(self, value: str) -> str:
        text = value.strip()
        if text.lower().rstrip(":") == "document summary":
            return "Evidence signals:"

        bullet_prefix = "- " if text.startswith("- ") else ""
        body = text[2:].strip() if bullet_prefix else text
        match = re.match(r"^([^:]{2,80}):\s*(.+?)\s*$", body)
        if match is None:
            return text

        raw_label, raw_detail = match.groups()
        detail = raw_detail.strip()
        if self._is_empty_legacy_summary_value(detail):
            return ""

        label = " ".join(raw_label.lower().split())
        replacements = {
            "incident details": "Incident evidence",
            "visible damages": "Visible damage",
            "missing or unclear information": "Needs review",
        }
        if label in replacements:
            return f"- {replacements[label]}: {detail}"
        return f"{bullet_prefix}{raw_label.strip()}: {detail}"

    def _is_empty_legacy_summary_value(self, value: str) -> bool:
        normalized = " ".join(value.lower().split()).strip(" .")
        return normalized in {
            "not specified",
            "not provided",
            "not visible",
            "unknown",
            "unclear",
            "n/a",
            "none",
        }

    def _clean_summary_label(self, value: str) -> str:
        text = value.strip()
        if not text.endswith(":"):
            return text

        label = text[:-1].strip()
        replacements = {
            "evidence signals": "Evidence signals",
            "extracted fields / ai interpretation": "Document interpretation",
            "extracted fields/ai interpretation": "Document interpretation",
            "follow up": "Follow-up",
            "follow-up": "Follow-up",
            "out of place / needs review": "Out of place / needs review",
            "out of place needs review": "Out of place / needs review",
            "summary / interpretation": "Document summary",
            "summary/interpretation": "Document summary",
        }
        normalized = " ".join(label.lower().split())
        return f"{replacements.get(normalized, label)}:"

    def _findings(self, review_view: dict[str, Any]) -> list[Any]:
        findings = review_view.get("ai_review_findings")
        if isinstance(findings, list) and findings:
            return findings

        camel_case_findings = review_view.get("aiReviewFindings")
        if isinstance(camel_case_findings, list) and camel_case_findings:
            return camel_case_findings

        return []

    def _review_state(self, case_context: ClaimCaseContext) -> str:
        if (
            case_context.generated_outputs.document_consistency is not None
            or case_context.generated_outputs.evidence_requirements is not None
            or case_context.review_state.claim_review_view is not None
        ):
            return "full_review"
        if case_context.generated_outputs.coverage_assessment is not None:
            return "coverage_precheck_only"
        return "not_started"

    def _available_actions(self, review_state: str) -> list[str]:
        if review_state == "coverage_precheck_only":
            return ["view_details", "start_analysis"]
        if review_state == "not_started":
            return ["start_analysis"]
        return ["view_details"]

    def _object(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        return value if isinstance(value, dict) else {}


__all__ = ["ClaimReviewQueryResult", "ClaimReviewQueryService"]
