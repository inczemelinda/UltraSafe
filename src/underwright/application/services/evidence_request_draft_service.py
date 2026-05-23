from __future__ import annotations

from secrets import token_urlsafe
from typing import Any
from uuid import UUID

from underwright.domain.claim_analysis import (
    ClaimCommunicationSuggestionState,
    EvidenceRequirement,
    EvidenceRequirementResult,
    EvidenceRequestDraft,
)
from underwright.domain.case_context_base import _utc_now
from underwright.domain.claim_case_context import ClaimCaseContext


class EvidenceRequestDraftError(ValueError):
    code = "EVIDENCE_REQUEST_DRAFT_ERROR"


class EvidenceRequestDraftNotFoundError(EvidenceRequestDraftError):
    code = "EVIDENCE_REQUEST_DRAFT_NOT_FOUND"


class EvidenceRequestDraftAlreadySentError(EvidenceRequestDraftError):
    code = "EVIDENCE_REQUEST_DRAFT_ALREADY_SENT"


class EvidenceRequestDraftInvalidError(EvidenceRequestDraftError):
    code = "EVIDENCE_REQUEST_DRAFT_INVALID"


class EvidenceRequestEmailFailedError(EvidenceRequestDraftError):
    code = "EVIDENCE_REQUEST_EMAIL_FAILED"


class EvidenceRequestDraftService:
    """Builds editable evidence-request drafts without sending them.

    Draft generation never sends email and never approves the request. An
    underwriter-facing UI must review/edit the subject and body before any
    future delivery integration uses the draft.

    Persistence is the ClaimCaseContext JSON snapshot. Draft and suggestion
    lifecycle state are stored under generated_outputs so browser state is not
    the authority for communication workflow decisions.
    """

    fire_requirement_types = {
        "official_fire_incident_report",
        "official_fire_incident_confirmation",
    }
    fire_required_documents = [
        "fire service report",
        "emergency intervention report",
        "police report",
        "authority-issued incident confirmation",
        "incident reference number",
    ]

    def generate_draft(
        self,
        case_context: ClaimCaseContext,
    ) -> EvidenceRequestDraft | None:
        evidence_requirements = self._evidence_requirements(case_context)
        if evidence_requirements is None or not evidence_requirements.required_evidence:
            return None

        existing_draft = case_context.generated_outputs.evidence_request_draft
        if existing_draft is not None and not self._is_sent(existing_draft):
            return existing_draft

        required_evidence = evidence_requirements.required_evidence
        claim_request_id = self._claim_request_id(case_context)
        draft = EvidenceRequestDraft(
            claim_request_id=claim_request_id,
            subject=self._subject(case_context, required_evidence),
            body=self._body(case_context, required_evidence),
            recipients=self._recipients(case_context),
            required_documents=self._required_documents(case_context, required_evidence),
            status="draft",
        )
        case_context.generated_outputs.evidence_request_draft = draft
        return draft

    def save_draft(
        self,
        case_context: ClaimCaseContext,
        *,
        subject: str,
        body: str,
        recipients: list[str] | None = None,
        required_documents: list[str] | None = None,
        source_suggestion_id: str | None = None,
        requested_document_type: str | None = None,
        due_date: str | None = None,
    ) -> EvidenceRequestDraft:
        normalized_subject = subject.strip()
        normalized_body = body.strip()
        if not normalized_subject or not normalized_body:
            raise EvidenceRequestDraftInvalidError(
                "Evidence request draft subject and body are required."
            )

        now = _utc_now()
        existing_draft = case_context.generated_outputs.evidence_request_draft
        incoming_documents = self._normalize_list(required_documents)
        if (
            requested_document_type
            and requested_document_type not in incoming_documents
        ):
            incoming_documents.append(requested_document_type)
        if self._is_sent(existing_draft):
            if self._same_request_scope(
                existing_draft,
                source_suggestion_id=source_suggestion_id,
                documents=incoming_documents,
            ):
                raise EvidenceRequestDraftAlreadySentError(
                    "Sent evidence request drafts cannot be edited."
                )
            existing_draft = None

        draft = existing_draft or EvidenceRequestDraft(
            claim_request_id=self._claim_request_id(case_context),
            subject=normalized_subject,
            body=normalized_body,
            recipients=[],
            required_documents=[],
            status="draft",
            created_at=now,
            updated_at=now,
        )

        normalized_recipients = self._normalize_list(
            recipients if recipients is not None else draft.recipients
        )
        if not normalized_recipients:
            normalized_recipients = self._recipients(case_context)

        normalized_documents = (
            incoming_documents
            if required_documents is not None or requested_document_type
            else self._normalize_list(draft.required_documents)
        )

        draft.subject = normalized_subject
        draft.body = normalized_body
        draft.recipients = normalized_recipients
        draft.required_documents = self._dedupe(normalized_documents)
        draft.status = "draft"
        draft.send_status = "not_sent"
        draft.sent_at = None
        draft.sent_to = []
        draft.provider_message_id = None
        draft.email_message_id = None
        draft.send_error_message = None
        draft.source_suggestion_id = source_suggestion_id or draft.source_suggestion_id
        draft.requested_document_type = requested_document_type or draft.requested_document_type
        draft.due_date = due_date or draft.due_date
        draft.updated_at = now
        case_context.generated_outputs.evidence_request_draft = draft

        if draft.source_suggestion_id:
            self.mark_suggestion_state(
                case_context,
                draft.source_suggestion_id,
                "draft_created",
                draft_id=draft.draft_id,
            )
        return draft

    def prepare_draft_send(
        self,
        case_context: ClaimCaseContext,
    ) -> tuple[EvidenceRequestDraft, str]:
        draft = case_context.generated_outputs.evidence_request_draft
        if draft is None:
            raise EvidenceRequestDraftNotFoundError(
                "Evidence request draft was not found."
            )
        if self._is_sent(draft):
            raise EvidenceRequestDraftAlreadySentError(
                "Evidence request draft has already been sent."
            )

        subject = draft.subject.strip()
        body = draft.body.strip()
        if not subject or not body:
            raise EvidenceRequestDraftInvalidError(
                "Evidence request draft subject and body are required before sending."
            )

        recipients = self._normalize_list(draft.recipients)
        if not recipients:
            raise EvidenceRequestDraftInvalidError(
                "Evidence request draft recipient is required before sending."
            )

        if not draft.reply_token:
            draft.reply_token = self._new_reply_token()
        draft.subject = subject
        draft.body = body
        draft.recipients = recipients
        draft.updated_at = _utc_now()
        case_context.generated_outputs.evidence_request_draft = draft
        return draft, recipients[0]

    def mark_draft_sent(
        self,
        case_context: ClaimCaseContext,
        *,
        email_message_id: UUID | str | None,
        provider_message_id: str | None,
        sent_at: Any | None,
        sent_to: str,
    ) -> EvidenceRequestDraft:
        draft = case_context.generated_outputs.evidence_request_draft
        if draft is None:
            raise EvidenceRequestDraftNotFoundError(
                "Evidence request draft was not found."
            )

        now = _utc_now()
        sent_timestamp = sent_at or now
        draft.status = "sent"
        draft.send_status = "sent"
        draft.sent_at = sent_timestamp
        draft.sent_to = [sent_to]
        draft.provider_message_id = provider_message_id
        draft.email_message_id = email_message_id
        draft.send_error_message = None
        draft.updated_at = now
        case_context.generated_outputs.evidence_request_draft = draft

        if draft.source_suggestion_id:
            self.mark_suggestion_state(
                case_context,
                draft.source_suggestion_id,
                "sent",
                draft_id=draft.draft_id,
            )
        return draft

    def mark_draft_send_failed(
        self,
        case_context: ClaimCaseContext,
        *,
        error_message: str,
        sent_to: str | None = None,
        email_message_id: UUID | str | None = None,
        provider_message_id: str | None = None,
    ) -> EvidenceRequestDraft:
        draft = case_context.generated_outputs.evidence_request_draft
        if draft is None:
            raise EvidenceRequestDraftNotFoundError(
                "Evidence request draft was not found."
            )

        now = _utc_now()
        draft.status = "draft"
        draft.send_status = "failed"
        draft.sent_to = [sent_to] if sent_to else []
        draft.email_message_id = email_message_id
        draft.provider_message_id = provider_message_id
        draft.send_error_message = error_message.strip() or "Email delivery failed."
        draft.updated_at = now
        case_context.generated_outputs.evidence_request_draft = draft
        return draft

    def prepare_demo_inbound_email(
        self,
        case_context: ClaimCaseContext,
    ) -> EvidenceRequestDraft:
        draft = case_context.generated_outputs.evidence_request_draft
        if draft is None:
            raise EvidenceRequestDraftNotFoundError(
                "Evidence request draft was not found."
            )
        if not self._is_sent(draft):
            raise EvidenceRequestDraftInvalidError(
                "Send an evidence request before triggering a demo inbound email."
            )
        if not draft.reply_token:
            draft.reply_token = self._new_reply_token()
            draft.updated_at = _utc_now()
        case_context.generated_outputs.evidence_request_draft = draft
        return draft

    def dismiss_suggestion(
        self,
        case_context: ClaimCaseContext,
        suggestion_id: str,
    ) -> ClaimCommunicationSuggestionState:
        normalized_id = suggestion_id.strip()
        if not normalized_id:
            raise EvidenceRequestDraftInvalidError(
                "AI communication suggestion id is required."
            )
        return self.mark_suggestion_state(
            case_context,
            normalized_id,
            "dismissed",
            dismissed=True,
        )

    def mark_suggestion_state(
        self,
        case_context: ClaimCaseContext,
        suggestion_id: str,
        status: str,
        *,
        draft_id: UUID | str | None = None,
        dismissed: bool = False,
    ) -> ClaimCommunicationSuggestionState:
        now = _utc_now()
        existing = case_context.generated_outputs.communication_suggestion_states.get(
            suggestion_id
        )
        state = existing or ClaimCommunicationSuggestionState(
            suggestion_id=suggestion_id,
            status="new",
            created_at=now,
            updated_at=now,
        )
        state.status = status  # type: ignore[assignment]
        state.draft_id = draft_id if draft_id is not None else state.draft_id
        if dismissed:
            state.dismissed_at = now
        state.updated_at = now
        case_context.generated_outputs.communication_suggestion_states[
            suggestion_id
        ] = state
        return state

    def _evidence_requirements(
        self,
        case_context: ClaimCaseContext,
    ) -> EvidenceRequirementResult | None:
        if case_context.generated_outputs.evidence_requirements is not None:
            return case_context.generated_outputs.evidence_requirements

        findings = case_context.generated_outputs.claim_review.findings
        if findings is not None:
            return findings.evidence_requirements
        return None

    def _claim_request_id(self, case_context: ClaimCaseContext) -> UUID | str:
        request_id = case_context.source_inputs.request_id
        if request_id is not None:
            return request_id

        claim_request = self._claim_request(case_context)
        if claim_request.get("request_id") is not None:
            return claim_request["request_id"]

        if case_context.case_metadata.case_id is not None:
            return case_context.case_metadata.case_id

        raise ValueError("Cannot create evidence request draft without a request id.")

    def _subject(
        self,
        case_context: ClaimCaseContext,
        required_evidence: list[EvidenceRequirement],
    ) -> str:
        if self._has_fire_requirement(case_context, required_evidence):
            return "Additional evidence required for your fire claim"
        return "Additional evidence required for your claim"

    def _body(
        self,
        case_context: ClaimCaseContext,
        required_evidence: list[EvidenceRequirement],
    ) -> str:
        client_name = self._client_name(case_context)
        lines = [
            f"Dear {client_name}," if client_name else "Dear client,",
            "",
            "We need a little more information before the underwriter can continue reviewing your claim.",
        ]

        if self._has_fire_requirement(case_context, required_evidence):
            lines.extend(
                [
                    "",
                    "Please provide one of the following for the reported fire incident:",
                    *self._bullet_lines(self.fire_required_documents),
                ]
            )

        if any(
            requirement.requirement_type == "additional_incident_details"
            for requirement in required_evidence
        ):
            lines.extend(
                [
                    "",
                    "Please also provide a fuller incident description, including what happened, when it happened, where it happened, and what damage occurred.",
                ]
            )

        generic_documents = self._generic_required_documents(
            case_context,
            required_evidence,
        )
        if generic_documents:
            lines.extend(
                [
                    "",
                    "Please provide the following supporting documents:",
                    *self._bullet_lines(generic_documents),
                ]
            )

        lines.extend(
            [
                "",
                "Thank you,",
                "Underwright Claims Team",
            ]
        )
        return "\n".join(lines)

    def _required_documents(
        self,
        case_context: ClaimCaseContext,
        required_evidence: list[EvidenceRequirement],
    ) -> list[str]:
        documents: list[str] = []
        if self._has_fire_requirement(case_context, required_evidence):
            documents.extend(self.fire_required_documents)

        if any(
            requirement.requirement_type == "additional_incident_details"
            for requirement in required_evidence
        ):
            documents.append("additional incident details")

        documents.extend(
            self._generic_required_documents(case_context, required_evidence)
        )
        return self._dedupe(documents)

    def _generic_required_documents(
        self,
        case_context: ClaimCaseContext,
        required_evidence: list[EvidenceRequirement],
    ) -> list[str]:
        documents: list[str] = []
        for requirement in required_evidence:
            if self._is_fire_requirement(case_context, requirement):
                continue
            if requirement.requirement_type == "additional_incident_details":
                continue
            documents.extend(
                self._humanize_document_type(document)
                for document in requirement.acceptable_documents
            )
        return self._dedupe(documents)

    def _has_fire_requirement(
        self,
        case_context: ClaimCaseContext,
        required_evidence: list[EvidenceRequirement],
    ) -> bool:
        return any(
            self._is_fire_requirement(case_context, requirement)
            for requirement in required_evidence
        )

    def _is_fire_requirement(
        self,
        case_context: ClaimCaseContext,
        requirement: EvidenceRequirement,
    ) -> bool:
        requirement_type = self._normalize(requirement.requirement_type)
        if requirement_type in self.fire_requirement_types:
            return True
        return (
            requirement_type == "official_incident_confirmation"
            and self._is_fire_claim(case_context)
        )

    def _is_fire_claim(self, case_context: ClaimCaseContext) -> bool:
        claim_data = self._object(self._claim_request(case_context).get("claim_data"))
        incident_type = claim_data.get("incident_type") or claim_data.get("claim_type")
        return self._normalize(incident_type) == "fire"

    def _client_name(self, case_context: ClaimCaseContext) -> str | None:
        claim_request = self._claim_request(case_context)
        client_data = self._object(claim_request.get("client_data"))
        full_name = str(client_data.get("full_name") or "").strip()
        return full_name or None

    def _recipients(self, case_context: ClaimCaseContext) -> list[str]:
        claim_request = self._claim_request(case_context)
        client_data = self._object(claim_request.get("client_data"))
        claim_data = self._object(claim_request.get("claim_data"))
        email = str(
            client_data.get("email") or claim_data.get("contact_email") or ""
        ).strip()
        return [email] if email else []

    def _claim_request(self, case_context: ClaimCaseContext) -> dict[str, Any]:
        return self._object(case_context.reference_data.claim_request)

    def _bullet_lines(self, values: list[str]) -> list[str]:
        return [f"- {value}" for value in self._dedupe(values)]

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            normalized = self._normalize(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_values.append(value)
        return unique_values

    def _normalize_list(self, values: list[str] | None) -> list[str]:
        return [str(value).strip() for value in values or [] if str(value).strip()]

    def _is_sent(self, draft: EvidenceRequestDraft | None) -> bool:
        if draft is None:
            return False
        return draft.status == "sent" or draft.send_status in {"mock_sent", "sent"}

    def _same_request_scope(
        self,
        draft: EvidenceRequestDraft | None,
        *,
        source_suggestion_id: str | None,
        documents: list[str],
    ) -> bool:
        if draft is None:
            return False
        if (
            source_suggestion_id
            and draft.source_suggestion_id
            and source_suggestion_id == draft.source_suggestion_id
        ):
            return True

        existing_documents = self._normalize_list(
            [
                *draft.required_documents,
                *(
                    [draft.requested_document_type]
                    if draft.requested_document_type
                    else []
                ),
            ]
        )
        normalized_existing = {self._normalize(value) for value in existing_documents}
        normalized_incoming = {self._normalize(value) for value in documents}
        return bool(normalized_existing and normalized_incoming) and (
            normalized_existing == normalized_incoming
        )

    def _new_reply_token(self) -> str:
        return token_urlsafe(18).rstrip("=").lower()

    def _humanize_document_type(self, value: str) -> str:
        return self._normalize(value).replace("_", " ")

    def _normalize(self, value: Any) -> str:
        normalized = str(value or "").strip().lower().replace("-", "_")
        return "_".join(normalized.split())

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


__all__ = [
    "EvidenceRequestDraftAlreadySentError",
    "EvidenceRequestEmailFailedError",
    "EvidenceRequestDraftError",
    "EvidenceRequestDraftInvalidError",
    "EvidenceRequestDraftNotFoundError",
    "EvidenceRequestDraftService",
]
