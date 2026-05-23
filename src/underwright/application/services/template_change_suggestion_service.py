from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import re
from typing import Any, cast
from uuid import UUID, uuid4

from underwright.application.legal_intelligence_ports import (
    TemplateChangeSuggestionGenerator,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewCandidate,
    NormalizedLegalDocument,
    TemplateChangeSuggestion,
    TemplateChangeSuggestionDetail,
    TemplateChangeSuggestionHunk,
    TemplateChangeSuggestionHunkStatus,
    TemplateChangeType,
    TemplateDraftRevision,
)
from underwright.domain.models import Template


ALLOWED_CHANGE_TYPES: set[TemplateChangeType] = {
    "replace",
    "insert_before",
    "insert_after",
    "delete",
    "manual_review",
}
ALLOWED_HUNK_STATUSES: set[TemplateChangeSuggestionHunkStatus] = {
    "draft",
    "accepted",
    "rejected",
    "edited",
}
CONTEXT_FALLBACK_RADIUS = 700
CONTEXT_MAX_CHARS = 2_400
LEGAL_APPROVAL_FROM_EMAIL = "legal-review@ultrasafe.ro"
LEGAL_APPROVAL_TO_EMAIL = "legal-approval@ultrasafe.ro"


class TemplateDraftRevisionValidationError(ValueError):
    def __init__(self, validation_result: dict[str, Any]) -> None:
        super().__init__("Template draft revision validation failed.")
        self.validation_result = validation_result


class TemplateDraftRevisionSubmissionError(ValueError):
    def __init__(self, validation_result: dict[str, Any]) -> None:
        super().__init__("Template draft revision submission failed.")
        self.validation_result = validation_result


class TemplateChangeSuggestionService:
    def __init__(
        self,
        *,
        candidate_repository,
        legal_document_repository,
        template_repository,
        suggestion_repository,
        suggestion_generator: TemplateChangeSuggestionGenerator,
        approval_email_service=None,
        legal_approval_to_email: str = LEGAL_APPROVAL_TO_EMAIL,
    ) -> None:
        self.candidate_repository = candidate_repository
        self.legal_document_repository = legal_document_repository
        self.template_repository = template_repository
        self.suggestion_repository = suggestion_repository
        self.suggestion_generator = suggestion_generator
        self.approval_email_service = approval_email_service
        self.legal_approval_to_email = legal_approval_to_email

    def create_suggestion(self, candidate_id: UUID) -> TemplateChangeSuggestion:
        candidate = self.candidate_repository.get_by_id(candidate_id)
        existing_lookup = getattr(
            self.suggestion_repository,
            "get_active_by_candidate_id",
            None,
        )
        if existing_lookup is not None:
            existing = existing_lookup(candidate_id)
            if existing is not None:
                return existing

        legal_document = self.legal_document_repository.get_by_id(
            candidate.normalized_legal_document_id
        )
        template = self.template_repository.get_by_id(candidate.template_id)
        current_hash = self._template_version_hash(template)

        if current_hash != candidate.template_version_hash:
            suggestion = self._version_mismatch_suggestion(
                candidate=candidate,
                current_hash=current_hash,
            )
            return self.suggestion_repository.save(suggestion)

        generated = self.suggestion_generator.generate(
            legal_document=legal_document,
            template=template,
            candidate=candidate,
            relevant_template_content=self._relevant_template_content(template),
        )
        suggestion = self._build_suggestion(
            candidate=candidate,
            legal_document=legal_document,
            template=template,
            generated=generated,
        )
        return self.suggestion_repository.save(suggestion)

    def get_suggestion_detail(
        self,
        suggestion_id: UUID,
    ) -> TemplateChangeSuggestionDetail:
        suggestion = self.suggestion_repository.get_by_id(suggestion_id)
        candidate = self.candidate_repository.get_by_id(suggestion.candidate_id)
        legal_document = self.legal_document_repository.get_by_id(
            suggestion.normalized_legal_document_id
        )
        template = self.template_repository.get_by_id(suggestion.template_id)
        suggestion = self._suggestion_with_context_fallback(suggestion, template)
        draft_revision = self._latest_draft_revision(suggestion.id)
        return TemplateChangeSuggestionDetail(
            suggestion=suggestion,
            candidate=candidate,
            normalized_legal_document=legal_document,
            template=template,
            draft_revision=draft_revision,
        )

    def update_hunk(
        self,
        *,
        suggestion_id: UUID,
        hunk_id: UUID,
        new_text: str | None = None,
        status: TemplateChangeSuggestionHunkStatus | None = None,
        reviewer_notes: str | None = None,
    ) -> TemplateChangeSuggestion:
        suggestion = self.suggestion_repository.get_by_id(suggestion_id)
        template = self.template_repository.get_by_id(suggestion.template_id)
        hunk_index, hunk = self._find_hunk(suggestion, hunk_id)
        updates: dict[str, Any] = {}
        if new_text is not None:
            updates["new_text"] = new_text
            if status is None:
                updates["status"] = "edited"
        if status is not None:
            updates["status"] = self._hunk_status(status)
        if reviewer_notes is not None:
            updates["reviewer_notes"] = reviewer_notes

        updated_hunk = hunk.model_copy(update=updates)
        updated_hunks = list(suggestion.hunks)
        updated_hunks[hunk_index] = updated_hunk
        validation_result = self._validate_suggestion_hunks(
            suggestion=suggestion,
            hunks=updated_hunks,
            template=template,
        )
        return self.suggestion_repository.update_hunk(
            suggestion_id=suggestion_id,
            hunk=updated_hunk,
            validation_result=validation_result,
            updated_at=datetime.now(UTC),
        )

    def accept_hunk(
        self,
        *,
        suggestion_id: UUID,
        hunk_id: UUID,
    ) -> TemplateChangeSuggestion:
        return self.update_hunk(
            suggestion_id=suggestion_id,
            hunk_id=hunk_id,
            status="accepted",
        )

    def reject_hunk(
        self,
        *,
        suggestion_id: UUID,
        hunk_id: UUID,
    ) -> TemplateChangeSuggestion:
        updated = self.update_hunk(
            suggestion_id=suggestion_id,
            hunk_id=hunk_id,
            status="rejected",
        )
        if updated.hunks and all(hunk.status == "rejected" for hunk in updated.hunks):
            self._update_candidate_status(
                candidate_id=updated.candidate_id,
                status="dismissed",
            )
        return updated

    def create_draft_revision_from_suggestion(
        self,
        suggestion_id: UUID,
    ) -> TemplateDraftRevision:
        suggestion = self.suggestion_repository.get_by_id(suggestion_id)
        existing_revision = self._latest_draft_revision(suggestion_id)
        if existing_revision is not None:
            self._update_candidate_status(
                candidate_id=suggestion.candidate_id,
                status=(
                    "accepted" if existing_revision.applied_hunk_ids else "dismissed"
                ),
            )
            return existing_revision

        template = self.template_repository.get_by_id(suggestion.template_id)
        validation_errors = self._validate_draft_revision_request(
            suggestion=suggestion,
            template=template,
        )
        applied_hunks = [
            hunk for hunk in suggestion.hunks if hunk.status in {"accepted", "edited"}
        ]

        if validation_errors:
            validation_result = self._draft_revision_validation_result(
                valid=False,
                errors=validation_errors,
            )
            self.suggestion_repository.update_status(
                suggestion_id=suggestion.id,
                status=suggestion.status,
                validation_result=validation_result,
                updated_at=datetime.now(UTC),
            )
            raise TemplateDraftRevisionValidationError(validation_result)

        revised_content = self._apply_reviewed_hunks(
            template.content,
            applied_hunks,
        )
        now = datetime.now(UTC)
        revision = TemplateDraftRevision(
            suggestion_id=suggestion.id,
            template_id=template.id or 0,
            template_code=template.template_code,
            template_name=template.name,
            base_template_version=template.version,
            base_template_version_hash=suggestion.template_version_hash,
            status="draft",
            base_content=template.content,
            revised_content=revised_content,
            applied_hunk_ids=[hunk.id for hunk in applied_hunks],
            validation_result=self._draft_revision_validation_result(
                valid=True,
                errors=[],
            ),
            source_metadata={
                "suggestion_id": str(suggestion.id),
                "accepted_hunk_count": len(
                    [hunk for hunk in suggestion.hunks if hunk.status == "accepted"]
                ),
                "edited_hunk_count": len(
                    [hunk for hunk in suggestion.hunks if hunk.status == "edited"]
                ),
                "rejected_hunk_count": len(
                    [hunk for hunk in suggestion.hunks if hunk.status == "rejected"]
                ),
                "applied_hunk_count": len(applied_hunks),
            },
            created_at=now,
            updated_at=now,
        )
        saved_revision = self.suggestion_repository.save_draft_revision(revision)
        self.suggestion_repository.update_status(
            suggestion_id=suggestion.id,
            status="applied_to_draft",
            validation_result=saved_revision.validation_result,
            updated_at=now,
        )
        self._update_candidate_status(
            candidate_id=suggestion.candidate_id,
            status="accepted" if applied_hunks else "dismissed",
            updated_at=now,
        )
        return saved_revision

    def submit_draft_revision_for_approval(
        self,
        draft_revision_id: UUID,
    ) -> TemplateDraftRevision:
        revision = self._draft_revision_by_id(draft_revision_id)
        if revision.status == "submitted_for_approval":
            return revision
        if revision.status != "draft":
            validation_result = self._draft_revision_submission_result(
                valid=False,
                errors=[
                    {
                        "code": "invalid_draft_revision_status",
                        "field": "status",
                        "message": "Only draft revisions can be submitted for approval.",
                        "status": revision.status,
                    }
                ],
                recipient_institution=None,
                submitted_at=None,
            )
            raise TemplateDraftRevisionSubmissionError(validation_result)

        suggestion = self.suggestion_repository.get_by_id(revision.suggestion_id)
        legal_document = self.legal_document_repository.get_by_id(
            suggestion.normalized_legal_document_id
        )
        now = datetime.now(UTC)
        recipient_institution = self._approval_recipient_institution(legal_document)
        validation_result = self._draft_revision_submission_result(
            valid=True,
            errors=[],
            recipient_institution=recipient_institution,
            submitted_at=now,
        )
        approval_email = self._send_legal_approval_email(
            revision=revision,
            legal_document=legal_document,
            recipient_institution=recipient_institution,
            submitted_at=now,
        )
        validation_result["approval_submission"].update(
            {
                "email_message_id": str(approval_email.id),
                "email_provider_message_id": approval_email.provider_message_id,
                "email_to": approval_email.to_email,
                "email_from": approval_email.from_email,
                "email_status": approval_email.status,
            }
        )
        source_metadata = {
            **revision.source_metadata,
            "approval_request": {
                "recipient_institution": recipient_institution,
                "submitted_at": now.isoformat(),
                "submission_status": "sent",
                "submission_channel": "legal_review_workflow",
                "email_message_id": str(approval_email.id),
                "email_provider_message_id": approval_email.provider_message_id,
                "email_to": approval_email.to_email,
                "email_from": approval_email.from_email,
                "submitted_content_hash": hashlib.sha256(
                    revision.revised_content.encode("utf-8")
                ).hexdigest(),
                "source_legal_document_id": str(legal_document.id),
                "source_legal_document_title": legal_document.title,
                "source_legal_update_url": (
                    legal_document.canonical_url or legal_document.source_url
                ),
            },
        }
        updated_revision = revision.model_copy(
            update={
                "status": "submitted_for_approval",
                "validation_result": validation_result,
                "source_metadata": source_metadata,
                "updated_at": now,
            }
        )
        submitted_revision = self.suggestion_repository.update_draft_revision_submission(
            revision_id=updated_revision.id,
            status=updated_revision.status,
            validation_result=updated_revision.validation_result,
            source_metadata=updated_revision.source_metadata,
            updated_at=updated_revision.updated_at,
        )
        self._update_candidate_status(
            candidate_id=suggestion.candidate_id,
            status="accepted",
            updated_at=updated_revision.updated_at,
        )
        return submitted_revision

    def _send_legal_approval_email(
        self,
        *,
        revision: TemplateDraftRevision,
        legal_document: NormalizedLegalDocument,
        recipient_institution: str,
        submitted_at: datetime,
    ):
        if self.approval_email_service is None:
            validation_result = self._draft_revision_submission_result(
                valid=False,
                errors=[
                    {
                        "code": "approval_email_service_required",
                        "field": "approval_email_service",
                        "message": "Legal approval email service is not configured.",
                    }
                ],
                recipient_institution=recipient_institution,
                submitted_at=None,
            )
            raise TemplateDraftRevisionSubmissionError(validation_result)

        subject = f"Legal review draft approval: {revision.template_name}"
        body = self._legal_approval_email_body(
            revision=revision,
            legal_document=legal_document,
            recipient_institution=recipient_institution,
            submitted_at=submitted_at,
        )
        try:
            email = self.approval_email_service.send_case_email(
                case_id=revision.id,
                to_email=self.legal_approval_to_email,
                subject=subject,
                body=body,
            )
        except Exception as exc:
            validation_result = self._draft_revision_submission_result(
                valid=False,
                errors=[
                    {
                        "code": "approval_email_send_failed",
                        "field": "approval_email",
                        "message": str(exc),
                    }
                ],
                recipient_institution=recipient_institution,
                submitted_at=None,
            )
            raise TemplateDraftRevisionSubmissionError(validation_result) from exc

        if email.status != "SENT":
            validation_result = self._draft_revision_submission_result(
                valid=False,
                errors=[
                    {
                        "code": "approval_email_send_failed",
                        "field": "approval_email",
                        "message": email.error_message
                        or "Legal approval email was not sent.",
                        "email_status": email.status,
                    }
                ],
                recipient_institution=recipient_institution,
                submitted_at=None,
            )
            raise TemplateDraftRevisionSubmissionError(validation_result)
        return email

    def _legal_approval_email_body(
        self,
        *,
        revision: TemplateDraftRevision,
        legal_document: NormalizedLegalDocument,
        recipient_institution: str,
        submitted_at: datetime,
    ) -> str:
        source_url = legal_document.canonical_url or legal_document.source_url or "-"
        submitted_content_hash = hashlib.sha256(
            revision.revised_content.encode("utf-8")
        ).hexdigest()
        return "\n".join(
            [
                "A legal review draft has been submitted for approval.",
                "",
                f"Draft revision ID: {revision.id}",
                f"Document: {revision.template_name}",
                f"Document code: {revision.template_code}",
                f"Responsible institution: {recipient_institution}",
                f"Submitted at: {submitted_at.isoformat()}",
                "",
                f"Source legal update: {legal_document.title}",
                f"Source URL: {source_url}",
                f"Submitted content hash: {submitted_content_hash}",
                "",
                "Draft content:",
                revision.revised_content,
            ]
        )

    def _build_suggestion(
        self,
        *,
        candidate: LegalDocumentTemplateReviewCandidate,
        legal_document: NormalizedLegalDocument,
        template: Template,
        generated: dict[str, Any],
    ) -> TemplateChangeSuggestion:
        now = datetime.now(UTC)
        suggestion_id = uuid4()
        validation_errors: list[dict[str, Any]] = []
        hunks = self._build_hunks(
            suggestion_id=suggestion_id,
            template=template,
            raw_hunks=generated.get("hunks"),
            validation_errors=validation_errors,
        )
        if not hunks:
            validation_errors.append(
                {
                    "field": "hunks",
                    "message": "AI output did not include any valid hunks.",
                }
            )

        return TemplateChangeSuggestion(
            id=suggestion_id,
            candidate_id=candidate.candidate_id,
            template_id=candidate.template_id,
            normalized_legal_document_id=legal_document.id,
            template_version_hash=candidate.template_version_hash,
            status="draft",
            overall_summary=str(generated.get("overall_summary") or "").strip()
            or "Draft template change suggestion requires review.",
            validation_result={
                "valid": not validation_errors,
                "errors": validation_errors,
                "generator": {
                    "model_name": self.suggestion_generator.model_name,
                    "model_version": self.suggestion_generator.model_version,
                    "prompt_version": self.suggestion_generator.prompt_version,
                },
            },
            hunks=hunks,
            created_at=now,
            updated_at=now,
        )

    def _update_candidate_status(
        self,
        *,
        candidate_id: UUID,
        status: str,
        updated_at: datetime | None = None,
    ) -> None:
        update_status = getattr(self.candidate_repository, "update_status", None)
        if update_status is None:
            return
        update_status(
            candidate_id=candidate_id,
            status=status,
            updated_at=updated_at or datetime.now(UTC),
        )

    def _build_hunks(
        self,
        *,
        suggestion_id: UUID,
        template: Template,
        raw_hunks: Any,
        validation_errors: list[dict[str, Any]],
    ) -> list[TemplateChangeSuggestionHunk]:
        if not isinstance(raw_hunks, list):
            return []

        hunks: list[TemplateChangeSuggestionHunk] = []
        for index, raw_hunk in enumerate(raw_hunks):
            if not isinstance(raw_hunk, dict):
                validation_errors.append(
                    {
                        "hunk_index": index,
                        "message": "Hunk must be a JSON object.",
                    }
                )
                continue
            hunks.append(
                self._build_hunk(
                    suggestion_id=suggestion_id,
                    template=template,
                    raw_hunk=raw_hunk,
                    index=index,
                    validation_errors=validation_errors,
                )
            )
        return hunks

    def _build_hunk(
        self,
        *,
        suggestion_id: UUID,
        template: Template,
        raw_hunk: dict[str, Any],
        index: int,
        validation_errors: list[dict[str, Any]],
    ) -> TemplateChangeSuggestionHunk:
        change_type = self._change_type(raw_hunk.get("change_type"))
        old_text = str(raw_hunk.get("old_text") or "")
        new_text = str(raw_hunk.get("new_text") or "")
        rationale = str(raw_hunk.get("rationale") or "").strip()
        source_reference = str(raw_hunk.get("source_reference") or "").strip()

        if not rationale:
            validation_errors.append(
                {
                    "hunk_index": index,
                    "field": "rationale",
                    "message": "Every hunk must include rationale.",
                }
            )
        if not source_reference:
            validation_errors.append(
                {
                    "hunk_index": index,
                    "field": "source_reference",
                    "message": "Every hunk must include source_reference.",
                }
            )

        if change_type in {"replace", "delete"} and old_text not in template.content:
            validation_errors.append(
                {
                    "hunk_index": index,
                    "field": "old_text",
                    "message": "old_text could not be located exactly in template.",
                    "old_text": old_text,
                }
            )
            change_type = "manual_review"

        context = self._template_context_fields(
            template=template,
            old_text=old_text,
            section_label=(
                str(raw_hunk["section_label"])
                if raw_hunk.get("section_label") is not None
                else None
            ),
        )

        return TemplateChangeSuggestionHunk(
            id=uuid4(),
            suggestion_id=suggestion_id,
            section_id=(
                str(raw_hunk["section_id"])
                if raw_hunk.get("section_id") is not None
                else None
            ),
            section_label=(
                str(raw_hunk["section_label"])
                if raw_hunk.get("section_label") is not None
                else None
            ),
            **context,
            change_type=change_type,
            old_text=old_text,
            new_text=new_text,
            rationale=rationale or "Manual review required.",
            source_reference=source_reference or "Missing source reference.",
            confidence=self._confidence(raw_hunk.get("confidence")),
            status="draft",
            reviewer_notes=None,
        )

    def _version_mismatch_suggestion(
        self,
        *,
        candidate: LegalDocumentTemplateReviewCandidate,
        current_hash: str,
    ) -> TemplateChangeSuggestion:
        now = datetime.now(UTC)
        return TemplateChangeSuggestion(
            candidate_id=candidate.candidate_id,
            template_id=candidate.template_id,
            normalized_legal_document_id=candidate.normalized_legal_document_id,
            template_version_hash=candidate.template_version_hash,
            status="draft",
            overall_summary=(
                "Template changed after this legal review candidate was created. "
                "Create a fresh candidate before drafting text changes."
            ),
            validation_result={
                "valid": False,
                "errors": [
                    {
                        "field": "template_version_hash",
                        "message": "Candidate template_version_hash does not match current template.",
                        "candidate_template_version_hash": candidate.template_version_hash,
                        "current_template_version_hash": current_hash,
                    }
                ],
            },
            hunks=[],
            created_at=now,
            updated_at=now,
        )

    def _change_type(self, raw_change_type: Any) -> TemplateChangeType:
        change_type = str(raw_change_type or "manual_review").strip()
        if change_type not in ALLOWED_CHANGE_TYPES:
            return "manual_review"
        return cast(TemplateChangeType, change_type)

    def _hunk_status(
        self,
        status: TemplateChangeSuggestionHunkStatus,
    ) -> TemplateChangeSuggestionHunkStatus:
        if status not in ALLOWED_HUNK_STATUSES:
            raise ValueError(f"Unsupported hunk status: {status}")
        return status

    def _find_hunk(
        self,
        suggestion: TemplateChangeSuggestion,
        hunk_id: UUID,
    ) -> tuple[int, TemplateChangeSuggestionHunk]:
        for index, hunk in enumerate(suggestion.hunks):
            if hunk.id == hunk_id:
                return index, hunk
        raise ValueError(f"Template change suggestion hunk not found: {hunk_id}")

    def _validate_suggestion_hunks(
        self,
        *,
        suggestion: TemplateChangeSuggestion,
        hunks: list[TemplateChangeSuggestionHunk],
        template: Template,
    ) -> dict[str, Any]:
        validation_errors: list[dict[str, Any]] = []
        current_hash = self._template_version_hash(template)
        if current_hash != suggestion.template_version_hash:
            validation_errors.append(
                {
                    "field": "template_version_hash",
                    "message": "Suggestion template_version_hash does not match current template.",
                    "suggestion_template_version_hash": suggestion.template_version_hash,
                    "current_template_version_hash": current_hash,
                }
            )

        for index, hunk in enumerate(hunks):
            validation_errors.extend(
                self._validate_hunk(
                    hunk=hunk,
                    template=template,
                    index=index,
                )
            )

        existing = dict(suggestion.validation_result or {})
        return {
            **existing,
            "valid": not validation_errors,
            "errors": validation_errors,
            "last_validated_at": datetime.now(UTC).isoformat(),
        }

    def _validate_hunk(
        self,
        *,
        hunk: TemplateChangeSuggestionHunk,
        template: Template,
        index: int,
    ) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        if not hunk.rationale.strip():
            errors.append(
                {
                    "hunk_index": index,
                    "hunk_id": str(hunk.id),
                    "field": "rationale",
                    "message": "Every hunk must include rationale.",
                }
            )
        if not hunk.source_reference.strip():
            errors.append(
                {
                    "hunk_index": index,
                    "hunk_id": str(hunk.id),
                    "field": "source_reference",
                    "message": "Every hunk must include source_reference.",
                }
            )
        if hunk.change_type in {"replace", "delete"} and (
            hunk.old_text not in template.content
        ):
            errors.append(
                {
                    "hunk_index": index,
                    "hunk_id": str(hunk.id),
                    "field": "old_text",
                    "message": "old_text could not be located exactly in template.",
                    "old_text": hunk.old_text,
                }
            )
        return errors

    def _validate_draft_revision_request(
        self,
        *,
        suggestion: TemplateChangeSuggestion,
        template: Template,
    ) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        current_hash = self._template_version_hash(template)
        if current_hash != suggestion.template_version_hash:
            errors.append(
                {
                    "code": "stale_template_version",
                    "field": "template_version_hash",
                    "message": "Suggestion template_version_hash does not match current template.",
                    "suggestion_template_version_hash": suggestion.template_version_hash,
                    "current_template_version_hash": current_hash,
                }
            )

        unreviewed_hunks = [
            hunk for hunk in suggestion.hunks if hunk.status == "draft"
        ]
        if unreviewed_hunks:
            errors.append(
                {
                    "code": "unreviewed_hunks",
                    "field": "hunks",
                    "message": "All hunks must be accepted, edited, or rejected before draft revision creation.",
                }
            )

        applied_hunks = [
            hunk for hunk in suggestion.hunks if hunk.status in {"accepted", "edited"}
        ]
        for index, hunk in enumerate(applied_hunks):
            errors.extend(
                self._validate_hunk_for_draft_revision(
                    hunk=hunk,
                    template=template,
                    index=index,
                )
            )
        return errors

    def _validate_hunk_for_draft_revision(
        self,
        *,
        hunk: TemplateChangeSuggestionHunk,
        template: Template,
        index: int,
    ) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        if hunk.change_type == "manual_review":
            errors.append(
                {
                    "code": "manual_review_hunk",
                    "hunk_index": index,
                    "hunk_id": str(hunk.id),
                    "field": "change_type",
                    "message": "manual_review hunks cannot be applied automatically.",
                }
            )
            return errors

        if hunk.change_type in {
            "replace",
            "delete",
            "insert_before",
            "insert_after",
        }:
            occurrences = template.content.count(hunk.old_text)
            if occurrences == 0:
                errors.append(
                    {
                        "code": "missing_old_text",
                        "hunk_index": index,
                        "hunk_id": str(hunk.id),
                        "field": "old_text",
                        "message": "old_text could not be located exactly in current template.",
                        "old_text": hunk.old_text,
                    }
                )
            elif occurrences > 1:
                errors.append(
                    {
                        "code": "duplicate_old_text",
                        "hunk_index": index,
                        "hunk_id": str(hunk.id),
                        "field": "old_text",
                        "message": "old_text appears multiple times and requires manual review.",
                        "occurrences": occurrences,
                        "old_text": hunk.old_text,
                    }
                )
        return errors

    def _apply_reviewed_hunks(
        self,
        content: str,
        applied_hunks: list[TemplateChangeSuggestionHunk],
    ) -> str:
        revised_content = content
        for hunk in applied_hunks:
            if hunk.change_type == "replace":
                revised_content = revised_content.replace(
                    hunk.old_text,
                    hunk.new_text,
                    1,
                )
            elif hunk.change_type == "delete":
                revised_content = revised_content.replace(hunk.old_text, "", 1)
            elif hunk.change_type == "insert_before":
                revised_content = revised_content.replace(
                    hunk.old_text,
                    f"{hunk.new_text}{hunk.old_text}",
                    1,
                )
            elif hunk.change_type == "insert_after":
                revised_content = revised_content.replace(
                    hunk.old_text,
                    f"{hunk.old_text}{hunk.new_text}",
                    1,
                )
        return revised_content

    def _draft_revision_validation_result(
        self,
        *,
        valid: bool,
        errors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "valid": valid,
            "errors": errors,
            "draft_revision": {
                "validated_at": datetime.now(UTC).isoformat(),
            },
        }

    def _draft_revision_submission_result(
        self,
        *,
        valid: bool,
        errors: list[dict[str, Any]],
        recipient_institution: str | None,
        submitted_at: datetime | None,
    ) -> dict[str, Any]:
        return {
            "valid": valid,
            "errors": errors,
            "approval_submission": {
                "recipient_institution": recipient_institution,
                "submitted_at": submitted_at.isoformat() if submitted_at else None,
            },
        }

    def _approval_recipient_institution(
        self,
        legal_document: NormalizedLegalDocument,
    ) -> str:
        return (
            (legal_document.issuer or "").strip()
            or legal_document.source_id
            or "responsible legal institution"
        )

    def _confidence(self, raw_confidence: Any) -> float:
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            return 0
        return min(max(confidence, 0), 1)

    def _template_version_hash(self, template: Template) -> str:
        payload = (
            f"{template.template_code}\n{template.version}\n{template.content}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _relevant_template_content(self, template: Template) -> str:
        return template.content[:20_000]

    def _latest_draft_revision(
        self,
        suggestion_id: UUID,
    ) -> TemplateDraftRevision | None:
        latest_lookup = getattr(
            self.suggestion_repository,
            "get_latest_draft_revision_by_suggestion_id",
            None,
        )
        if latest_lookup is None:
            return None
        return latest_lookup(suggestion_id)

    def _draft_revision_by_id(self, draft_revision_id: UUID) -> TemplateDraftRevision:
        lookup = getattr(self.suggestion_repository, "get_draft_revision_by_id", None)
        if lookup is None:
            raise ValueError("Draft revision lookup is not available.")
        revision = lookup(draft_revision_id)
        if revision is None:
            raise ValueError(f"Template draft revision not found: {draft_revision_id}")
        return revision

    def _suggestion_with_context_fallback(
        self,
        suggestion: TemplateChangeSuggestion,
        template: Template,
    ) -> TemplateChangeSuggestion:
        hunks: list[TemplateChangeSuggestionHunk] = []
        changed = False
        for hunk in suggestion.hunks:
            context = self._template_context_fields(
                template=template,
                old_text=hunk.old_text,
                section_label=hunk.section_label,
            )
            if context:
                hunks.append(hunk.model_copy(update=context))
                changed = True
            else:
                hunks.append(hunk)

        if not changed:
            return suggestion
        return suggestion.model_copy(update={"hunks": hunks})

    def _template_context_fields(
        self,
        *,
        template: Template,
        old_text: str,
        section_label: str | None,
    ) -> dict[str, Any]:
        if not old_text:
            return {}

        start = template.content.find(old_text)
        if start < 0:
            return {}

        end = start + len(old_text)
        before_start, after_end = self._context_bounds(template.content, start, end)
        before_context = template.content[before_start:start].strip()
        after_context = template.content[end:after_end].strip()
        full_context_excerpt = template.content[before_start:after_end].strip()

        return {
            "template_section_title": section_label or template.name,
            "template_article_title": self._article_title_for_offset(
                template.content,
                start,
            ),
            "before_context": before_context,
            "after_context": after_context,
            "full_context_excerpt": full_context_excerpt,
            "start_offset": start,
            "end_offset": end,
        }

    def _context_bounds(
        self,
        content: str,
        start: int,
        end: int,
    ) -> tuple[int, int]:
        paragraph_bounds = self._paragraph_context_bounds(content, start, end)
        if paragraph_bounds is not None:
            return paragraph_bounds

        return (
            max(0, start - CONTEXT_FALLBACK_RADIUS),
            min(len(content), end + CONTEXT_FALLBACK_RADIUS),
        )

    def _paragraph_context_bounds(
        self,
        content: str,
        start: int,
        end: int,
    ) -> tuple[int, int] | None:
        spans = [
            (match.start(), match.end())
            for match in re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\Z)", content)
        ]
        if len(spans) < 2:
            return None

        target_index = next(
            (
                index
                for index, (span_start, span_end) in enumerate(spans)
                if span_start <= start and end <= span_end
            ),
            None,
        )
        if target_index is None:
            return None

        before_index = max(0, target_index - 1)
        after_index = min(len(spans) - 1, target_index + 1)
        before_start = spans[before_index][0]
        after_end = spans[after_index][1]

        if after_end - before_start > CONTEXT_MAX_CHARS:
            return (
                max(0, start - CONTEXT_FALLBACK_RADIUS),
                min(len(content), end + CONTEXT_FALLBACK_RADIUS),
            )

        return before_start, after_end

    def _article_title_for_offset(self, content: str, offset: int) -> str | None:
        prefix = content[:offset]
        for line in reversed(prefix.splitlines()):
            label = line.strip()
            if not label:
                continue
            normalized = label.lower()
            if (
                label.endswith(":")
                or normalized.startswith(("art", "section", "capitolul"))
                or re.match(r"^\d+(?:\.\d+)+\.", label)
            ):
                return label
        return None
