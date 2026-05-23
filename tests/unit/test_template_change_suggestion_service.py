from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
from uuid import UUID

from underwright.application.services.template_change_suggestion_service import (
    TemplateDraftRevisionValidationError,
    TemplateChangeSuggestionService,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewCandidate,
    NormalizedLegalDocument,
    TemplateChangeSuggestion,
    TemplateChangeSuggestionHunk,
    TemplateDraftRevision,
)
from underwright.domain.email_message import EmailMessage
from underwright.domain.models import Template
from underwright.infrastructure.llm.template_change_suggestion_generator import (
    DeterministicDemoTemplateChangeSuggestionGenerator,
)


NOW = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
TEMPLATE_CONTENT = (
    "Prezenta poliță este emisă în conformitate cu Legea nr. 260/2008. "
    "Asiguratul trebuie să notifice dauna în termen de 10 zile calendaristice "
    "de la producerea evenimentului."
)


class FakeCandidateRepository:
    def __init__(self, candidate: LegalDocumentTemplateReviewCandidate) -> None:
        self.candidate = candidate
        self.status_updates: list[dict] = []

    def get_by_id(self, candidate_id: UUID) -> LegalDocumentTemplateReviewCandidate:
        assert candidate_id == self.candidate.candidate_id
        return self.candidate

    def update_status(
        self,
        *,
        candidate_id: UUID,
        status: str,
        updated_at: datetime,
    ) -> LegalDocumentTemplateReviewCandidate:
        assert candidate_id == self.candidate.candidate_id
        self.status_updates.append({"status": status, "updated_at": updated_at})
        self.candidate = self.candidate.model_copy(
            update={"status": status, "updated_at": updated_at}
        )
        return self.candidate


class FakeLegalDocumentRepository:
    def __init__(self, document: NormalizedLegalDocument) -> None:
        self.document = document

    def get_by_id(self, document_id: UUID) -> NormalizedLegalDocument:
        assert document_id == self.document.id
        return self.document


class FakeTemplateRepository:
    def __init__(self, template: Template) -> None:
        self.template = template

    def get_by_id(self, template_id: int) -> Template:
        assert template_id == self.template.id
        return self.template


class FakeSuggestionRepository:
    def __init__(self, suggestion: TemplateChangeSuggestion | None = None) -> None:
        self.suggestion = suggestion
        self.saved: TemplateChangeSuggestion | None = None
        self.saved_revision: TemplateDraftRevision | None = None
        self.status_updates: list[dict] = []
        self.submission_updates: list[dict] = []

    def get_active_by_candidate_id(
        self,
        candidate_id: UUID,
    ) -> TemplateChangeSuggestion | None:
        if self.suggestion is None or self.suggestion.candidate_id != candidate_id:
            return None
        if self.suggestion.status == "superseded":
            return None
        return self.suggestion

    def save(self, suggestion: TemplateChangeSuggestion) -> TemplateChangeSuggestion:
        self.saved = suggestion
        self.suggestion = suggestion
        return suggestion

    def get_by_id(self, suggestion_id: UUID) -> TemplateChangeSuggestion:
        assert self.suggestion is not None
        assert suggestion_id == self.suggestion.id
        return self.suggestion

    def update_hunk(
        self,
        *,
        suggestion_id: UUID,
        hunk: TemplateChangeSuggestionHunk,
        validation_result: dict,
        updated_at: datetime,
    ) -> TemplateChangeSuggestion:
        assert self.suggestion is not None
        assert suggestion_id == self.suggestion.id
        hunks = [
            hunk if existing.id == hunk.id else existing
            for existing in self.suggestion.hunks
        ]
        self.suggestion = self.suggestion.model_copy(
            update={
                "hunks": hunks,
                "validation_result": validation_result,
                "updated_at": updated_at,
            }
        )
        return self.suggestion

    def update_status(
        self,
        *,
        suggestion_id: UUID,
        status: str,
        validation_result: dict,
        updated_at: datetime,
    ) -> TemplateChangeSuggestion:
        assert self.suggestion is not None
        assert suggestion_id == self.suggestion.id
        self.status_updates.append(
            {
                "status": status,
                "validation_result": validation_result,
                "updated_at": updated_at,
            }
        )
        self.suggestion = self.suggestion.model_copy(
            update={
                "status": status,
                "validation_result": validation_result,
                "updated_at": updated_at,
            }
        )
        return self.suggestion

    def save_draft_revision(
        self,
        revision: TemplateDraftRevision,
    ) -> TemplateDraftRevision:
        self.saved_revision = revision
        return revision

    def get_latest_draft_revision_by_suggestion_id(
        self,
        suggestion_id: UUID,
    ) -> TemplateDraftRevision | None:
        if self.saved_revision is None:
            return None
        if self.saved_revision.suggestion_id != suggestion_id:
            return None
        return self.saved_revision

    def get_draft_revision_by_id(
        self,
        draft_revision_id: UUID,
    ) -> TemplateDraftRevision | None:
        if self.saved_revision is None or self.saved_revision.id != draft_revision_id:
            return None
        return self.saved_revision

    def update_draft_revision_submission(
        self,
        *,
        revision_id: UUID,
        status: str,
        validation_result: dict,
        source_metadata: dict,
        updated_at: datetime,
    ) -> TemplateDraftRevision:
        assert self.saved_revision is not None
        assert self.saved_revision.id == revision_id
        self.submission_updates.append(
            {
                "status": status,
                "validation_result": validation_result,
                "source_metadata": source_metadata,
                "updated_at": updated_at,
            }
        )
        self.saved_revision = self.saved_revision.model_copy(
            update={
                "status": status,
                "validation_result": validation_result,
                "source_metadata": source_metadata,
                "updated_at": updated_at,
            }
        )
        return self.saved_revision


class FakeSuggestionGenerator:
    model_name = "fake-ai-suggestion-generator"
    model_version = "test"
    prompt_version = "test-prompt"

    def __init__(self, old_text: str = "10 zile calendaristice") -> None:
        self.old_text = old_text
        self.called = False

    def generate(self, **kwargs):
        self.called = True
        return {
            "overall_summary": "Draft update for the claim notification deadline.",
            "hunks": [
                {
                    "section_id": "claims.notification",
                    "section_label": "Claim notification",
                    "change_type": "replace",
                    "old_text": self.old_text,
                    "new_text": "5 zile calendaristice",
                    "rationale": "The law changes the deadline from 10 to 5 days.",
                    "source_reference": "DEMO - Legea nr. 99/2026",
                    "confidence": 0.91,
                }
            ],
        }


class FakeApprovalEmailService:
    def __init__(self, *, status: str = "SENT", error_message: str | None = None) -> None:
        self.sent: list[dict] = []
        self.status = status
        self.error_message = error_message

    def send_case_email(
        self,
        *,
        case_id: UUID,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> EmailMessage:
        self.sent.append(
            {
                "case_id": case_id,
                "to_email": to_email,
                "subject": subject,
                "body": body,
                "html_body": html_body,
            }
        )
        return EmailMessage(
            id=UUID("97000000-0000-0000-0000-000000000001"),
            case_id=case_id,
            direction="OUTBOUND",
            from_email="legal-review@ultrasafe.ro",
            to_email=to_email,
            subject=subject,
            body=body,
            status=self.status,
            provider_message_id="postmark-message-id" if self.status == "SENT" else None,
            error_message=self.error_message,
            sent_at=NOW if self.status == "SENT" else None,
        )


def test_create_suggestion_stores_draft_replace_hunk_for_pad_demo() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    generator = FakeSuggestionGenerator()
    service = make_service(candidate, document, template, generator)

    suggestion = service.create_suggestion(candidate.candidate_id)

    assert generator.called is True
    assert suggestion.status == "draft"
    assert suggestion.candidate_id == candidate.candidate_id
    assert suggestion.template_id == template.id
    assert suggestion.normalized_legal_document_id == document.id
    assert suggestion.template_version_hash == candidate.template_version_hash
    assert suggestion.validation_result["valid"] is True
    assert suggestion.hunks[0].change_type == "replace"
    assert "10 zile calendaristice" in suggestion.hunks[0].old_text
    assert "5 zile calendaristice" in suggestion.hunks[0].new_text
    assert suggestion.hunks[0].status == "draft"
    assert "Legea nr. 99/2026" in suggestion.hunks[0].source_reference
    assert suggestion.hunks[0].template_section_title == "Claim notification"
    assert suggestion.hunks[0].start_offset is not None
    assert suggestion.hunks[0].end_offset is not None
    assert "Asiguratul trebuie" in (suggestion.hunks[0].before_context or "")
    assert "de la producerea evenimentului" in (
        suggestion.hunks[0].after_context or ""
    )
    assert template.content == TEMPLATE_CONTENT


def test_create_suggestion_expands_hunk_context_to_nearby_wording_clauses() -> None:
    document = make_legal_document()
    template = make_template(
        content=(
            "CAPITOLUL X - OBLIGAȚIILE ASIGURATULUI\n\n"
            "10.4. În cazul producerii unui eveniment, Asiguratul trebuie să ia "
            "măsuri pentru limitarea prejudiciului înainte de constatare.\n\n"
            "10.5. Asiguratul trebuie să notifice dauna în termen de "
            "10 zile calendaristice de la producerea evenimentului sau de la "
            "data la care a luat cunoștință de producerea acestuia.\n\n"
            "10.6. Notificarea trebuie să cuprindă data, locul evenimentului "
            "și descrierea împrejurărilor."
        )
    )
    candidate = make_candidate(template, document)
    service = make_service(candidate, document, template, FakeSuggestionGenerator())

    suggestion = service.create_suggestion(candidate.candidate_id)
    hunk = suggestion.hunks[0]

    assert hunk.start_offset == template.content.index("10 zile calendaristice")
    assert hunk.end_offset == hunk.start_offset + len("10 zile calendaristice")
    assert "10.4. În cazul producerii unui eveniment" in (
        hunk.before_context or ""
    )
    assert "10.6. Notificarea trebuie să cuprindă" in (hunk.after_context or "")
    assert "10.4. În cazul producerii unui eveniment" in (
        hunk.full_context_excerpt or ""
    )
    assert "10.6. Notificarea trebuie să cuprindă" in (
        hunk.full_context_excerpt or ""
    )


def test_create_suggestion_works_for_legislatie_correlated_candidate() -> None:
    document = make_legislatie_legal_document()
    template = make_template()
    candidate = make_candidate(template, document).model_copy(
        update={
            "review_reason": (
                "LEGE nr. 120/2026 amends ro:lege:260:2008, which is "
                "referenced by template DEMO_PAD_POLICY_WORDING_RO."
            ),
            "source_metadata": {"extractor_id": "legislatie_just"},
        }
    )
    generator = DeterministicDemoTemplateChangeSuggestionGenerator()
    service = make_service(candidate, document, template, generator)

    suggestion = service.create_suggestion(candidate.candidate_id)

    assert suggestion.validation_result["valid"] is True
    assert suggestion.validation_result["generator"]["model_name"] == (
        "deterministic-demo-template-change-suggestion-generator"
    )
    assert suggestion.hunks[0].change_type == "replace"
    assert "10 zile calendaristice" in suggestion.hunks[0].old_text
    assert "5 zile calendaristice" in suggestion.hunks[0].new_text
    assert suggestion.hunks[0].source_reference == document.title
    assert template.content == TEMPLATE_CONTENT


def test_create_suggestion_returns_existing_active_suggestion_for_reload() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    existing = make_suggestion(candidate, document, template, hunk_status="accepted")
    generator = FakeSuggestionGenerator()
    service = make_service(
        candidate,
        document,
        template,
        generator,
        suggestion=existing,
    )

    suggestion = service.create_suggestion(candidate.candidate_id)

    assert suggestion == existing
    assert suggestion.hunks[0].status == "accepted"
    assert generator.called is False


def test_create_suggestion_marks_unlocatable_replace_as_manual_review() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    generator = FakeSuggestionGenerator(old_text="text not in template")
    service = make_service(candidate, document, template, generator)

    suggestion = service.create_suggestion(candidate.candidate_id)

    assert suggestion.validation_result["valid"] is False
    assert suggestion.hunks[0].change_type == "manual_review"
    assert suggestion.hunks[0].new_text == "5 zile calendaristice"
    assert "old_text could not be located" in (
        suggestion.validation_result["errors"][0]["message"]
    )


def test_create_suggestion_does_not_call_ai_when_template_hash_mismatches() -> None:
    document = make_legal_document()
    template = make_template(content=f"{TEMPLATE_CONTENT}\nUpdated after candidate.")
    candidate = make_candidate(
        make_template(),
        document,
        template_version_hash="stale-template-hash",
    )
    generator = FakeSuggestionGenerator()
    service = make_service(candidate, document, template, generator)

    suggestion = service.create_suggestion(candidate.candidate_id)

    assert generator.called is False
    assert suggestion.status == "draft"
    assert suggestion.hunks == []
    assert suggestion.validation_result["valid"] is False
    assert suggestion.validation_result["errors"][0]["field"] == (
        "template_version_hash"
    )


def test_get_suggestion_detail_returns_linked_records() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion=suggestion,
    )

    detail = service.get_suggestion_detail(suggestion.id)

    assert detail.suggestion.id == suggestion.id
    assert detail.candidate.candidate_id == candidate.candidate_id
    assert detail.normalized_legal_document.id == document.id
    assert detail.template.id == template.id
    assert detail.draft_revision is None


def test_get_suggestion_detail_refreshes_stored_hunk_context() -> None:
    document = make_legal_document()
    template = make_template(
        content=(
            "10.4. Asiguratul păstrează urmele evenimentului până la constatare.\n\n"
            "10.5. Asiguratul trebuie să notifice dauna în termen de "
            "10 zile calendaristice de la producerea evenimentului.\n\n"
            "10.6. Notificarea include data, locul și descrierea evenimentului."
        )
    )
    candidate = make_candidate(template, document)
    stale_hunk = TemplateChangeSuggestionHunk(
        id=UUID("95000000-0000-0000-0000-000000000001"),
        suggestion_id=UUID("94000000-0000-0000-0000-000000000001"),
        section_id="claims.notification",
        section_label="Claim notification",
        template_section_title="Claim notification",
        before_context="old short context",
        after_context="old short context",
        full_context_excerpt="old short context",
        start_offset=1,
        end_offset=2,
        change_type="replace",
        old_text="10 zile calendaristice",
        new_text="5 zile calendaristice",
        rationale="The law changes the deadline from 10 to 5 days.",
        source_reference="DEMO - Legea nr. 99/2026",
        confidence=0.91,
    )
    suggestion = make_suggestion(
        candidate,
        document,
        template,
        old_text="unused old text",
        extra_hunks=[stale_hunk],
    ).model_copy(update={"hunks": [stale_hunk]})
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion=suggestion,
    )

    detail = service.get_suggestion_detail(suggestion.id)
    hunk = detail.suggestion.hunks[0]

    assert hunk.start_offset == template.content.index("10 zile calendaristice")
    assert "10.4. Asiguratul păstrează" in (hunk.before_context or "")
    assert "10.6. Notificarea include" in (hunk.after_context or "")


def test_get_suggestion_detail_returns_existing_draft_revision() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template, hunk_status="accepted")
    suggestion_repository = FakeSuggestionRepository(suggestion)
    revision = make_draft_revision(suggestion, template)
    suggestion_repository.saved_revision = revision
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion_repository=suggestion_repository,
    )

    detail = service.get_suggestion_detail(suggestion.id)

    assert detail.draft_revision == revision


def test_update_hunk_new_text_sets_status_edited_and_revalidates() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion=suggestion,
    )

    updated = service.update_hunk(
        suggestion_id=suggestion.id,
        hunk_id=suggestion.hunks[0].id,
        new_text="5 zile calendaristice de la producerea evenimentului",
        reviewer_notes="Reviewer tightened the wording.",
    )

    assert updated.hunks[0].status == "edited"
    assert updated.hunks[0].new_text.startswith("5 zile calendaristice")
    assert updated.hunks[0].reviewer_notes == "Reviewer tightened the wording."
    assert updated.hunks[0].old_text == "10 zile calendaristice"
    assert updated.validation_result["valid"] is True
    assert template.content == TEMPLATE_CONTENT


def test_update_hunk_marks_validation_error_when_old_text_no_longer_matches() -> None:
    document = make_legal_document()
    template = make_template(content="Template content changed.")
    candidate = make_candidate(make_template(), document)
    suggestion = make_suggestion(candidate, document, make_template())
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion=suggestion,
    )

    updated = service.update_hunk(
        suggestion_id=suggestion.id,
        hunk_id=suggestion.hunks[0].id,
        new_text="5 zile calendaristice",
    )

    assert updated.hunks[0].status == "edited"
    assert updated.validation_result["valid"] is False
    assert updated.validation_result["errors"][0]["field"] == "template_version_hash"
    assert updated.validation_result["errors"][1]["field"] == "old_text"


def test_accept_hunk_sets_status_without_modifying_template() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion=suggestion,
    )

    updated = service.accept_hunk(
        suggestion_id=suggestion.id,
        hunk_id=suggestion.hunks[0].id,
    )

    assert updated.hunks[0].status == "accepted"
    assert updated.hunks[0].new_text == "5 zile calendaristice"
    assert template.content == TEMPLATE_CONTENT


def test_reject_hunk_sets_status_without_modifying_template() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template)
    candidate_repository = FakeCandidateRepository(candidate)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        candidate_repository=candidate_repository,
        suggestion=suggestion,
    )

    updated = service.reject_hunk(
        suggestion_id=suggestion.id,
        hunk_id=suggestion.hunks[0].id,
    )

    assert updated.hunks[0].status == "rejected"
    assert template.content == TEMPLATE_CONTENT
    assert candidate_repository.status_updates[-1]["status"] == "dismissed"


def test_create_draft_revision_from_accepted_hunk_updates_copy_only() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template, hunk_status="accepted")
    candidate_repository = FakeCandidateRepository(candidate)
    suggestion_repository = FakeSuggestionRepository(suggestion)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        candidate_repository=candidate_repository,
        suggestion_repository=suggestion_repository,
    )

    revision = service.create_draft_revision_from_suggestion(suggestion.id)

    assert revision.status == "draft"
    assert "10 zile calendaristice" in revision.base_content
    assert "10 zile calendaristice" not in revision.revised_content
    assert "5 zile calendaristice" in revision.revised_content
    assert revision.applied_hunk_ids == [suggestion.hunks[0].id]
    assert revision.validation_result["valid"] is True
    assert template.content == TEMPLATE_CONTENT
    assert suggestion_repository.saved_revision == revision
    assert suggestion_repository.suggestion is not None
    assert suggestion_repository.suggestion.status == "applied_to_draft"
    assert candidate_repository.status_updates[-1]["status"] == "accepted"


def test_create_draft_revision_returns_existing_draft_for_repeat_request() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template, hunk_status="accepted")
    candidate_repository = FakeCandidateRepository(candidate)
    suggestion_repository = FakeSuggestionRepository(suggestion)
    existing_revision = make_draft_revision(suggestion, template)
    suggestion_repository.saved_revision = existing_revision
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        candidate_repository=candidate_repository,
        suggestion_repository=suggestion_repository,
    )

    revision = service.create_draft_revision_from_suggestion(suggestion.id)

    assert revision == existing_revision
    assert candidate_repository.status_updates[-1]["status"] == "accepted"


def test_create_draft_revision_from_edited_hunk_applies_edited_copy_only() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(
        candidate,
        document,
        template,
        hunk_status="edited",
        new_text="5 zile calendaristice de la producerea evenimentului",
    )
    suggestion_repository = FakeSuggestionRepository(suggestion)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion_repository=suggestion_repository,
    )

    revision = service.create_draft_revision_from_suggestion(suggestion.id)

    assert "5 zile calendaristice de la producerea evenimentului" in (
        revision.revised_content
    )
    assert revision.applied_hunk_ids == [suggestion.hunks[0].id]
    assert revision.source_metadata["edited_hunk_count"] == 1
    assert template.content == TEMPLATE_CONTENT


def test_create_draft_revision_from_rejected_hunk_creates_unchanged_draft() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template, hunk_status="rejected")
    candidate_repository = FakeCandidateRepository(candidate)
    suggestion_repository = FakeSuggestionRepository(suggestion)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        candidate_repository=candidate_repository,
        suggestion_repository=suggestion_repository,
    )

    revision = service.create_draft_revision_from_suggestion(suggestion.id)

    assert revision.base_content == TEMPLATE_CONTENT
    assert revision.revised_content == TEMPLATE_CONTENT
    assert revision.applied_hunk_ids == []
    assert revision.source_metadata["rejected_hunk_count"] == 1
    assert template.content == TEMPLATE_CONTENT
    assert candidate_repository.status_updates[-1]["status"] == "dismissed"


def test_submit_draft_revision_for_approval_marks_responsible_institution() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template, hunk_status="accepted")
    candidate_repository = FakeCandidateRepository(candidate)
    approval_email_service = FakeApprovalEmailService()
    suggestion_repository = FakeSuggestionRepository(suggestion)
    suggestion_repository.saved_revision = make_draft_revision(suggestion, template)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        approval_email_service=approval_email_service,
        candidate_repository=candidate_repository,
        suggestion_repository=suggestion_repository,
    )

    submitted = service.submit_draft_revision_for_approval(
        suggestion_repository.saved_revision.id
    )

    assert submitted.status == "submitted_for_approval"
    approval_request = submitted.source_metadata["approval_request"]
    assert approval_request["recipient_institution"] == document.issuer
    assert approval_request["submission_status"] == "sent"
    assert approval_request["email_to"] == "legal-approval@ultrasafe.ro"
    assert approval_request["email_from"] == "legal-review@ultrasafe.ro"
    assert approval_request["email_provider_message_id"] == "postmark-message-id"
    assert approval_request["source_legal_document_title"] == document.title
    assert len(approval_request["submitted_content_hash"]) == 64
    assert submitted.validation_result["approval_submission"][
        "recipient_institution"
    ] == document.issuer
    assert submitted.validation_result["approval_submission"]["email_status"] == "SENT"
    assert suggestion_repository.submission_updates[0]["status"] == (
        "submitted_for_approval"
    )
    assert candidate_repository.status_updates[-1]["status"] == "accepted"
    assert approval_email_service.sent[0]["case_id"] == (
        suggestion_repository.saved_revision.id
    )
    assert approval_email_service.sent[0]["to_email"] == (
        "legal-approval@ultrasafe.ro"
    )
    assert "Legal review draft approval" in approval_email_service.sent[0]["subject"]
    assert document.title in approval_email_service.sent[0]["body"]
    assert template.name in approval_email_service.sent[0]["body"]


def test_create_draft_revision_blocks_unreviewed_hunks() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template, hunk_status="draft")
    suggestion_repository = FakeSuggestionRepository(suggestion)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion_repository=suggestion_repository,
    )

    try:
        service.create_draft_revision_from_suggestion(suggestion.id)
    except TemplateDraftRevisionValidationError as exc:
        assert exc.validation_result["errors"][0]["code"] == "unreviewed_hunks"
    else:
        raise AssertionError("Expected TemplateDraftRevisionValidationError")
    assert suggestion_repository.saved_revision is None


def test_create_draft_revision_blocks_stale_template_hash() -> None:
    document = make_legal_document()
    original_template = make_template()
    current_template = make_template(content=f"{TEMPLATE_CONTENT}\nNew text.")
    candidate = make_candidate(original_template, document)
    suggestion = make_suggestion(
        candidate,
        document,
        original_template,
        hunk_status="accepted",
    )
    suggestion_repository = FakeSuggestionRepository(suggestion)
    service = make_service(
        candidate,
        document,
        current_template,
        FakeSuggestionGenerator(),
        suggestion_repository=suggestion_repository,
    )

    try:
        service.create_draft_revision_from_suggestion(suggestion.id)
    except TemplateDraftRevisionValidationError as exc:
        assert exc.validation_result["valid"] is False
        assert exc.validation_result["errors"][0]["code"] == (
            "stale_template_version"
        )
    else:
        raise AssertionError("Expected TemplateDraftRevisionValidationError")
    assert suggestion_repository.saved_revision is None


def test_create_draft_revision_blocks_missing_old_text() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(
        candidate,
        document,
        template,
        hunk_status="accepted",
        old_text="text missing from template",
    )
    suggestion_repository = FakeSuggestionRepository(suggestion)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion_repository=suggestion_repository,
    )

    try:
        service.create_draft_revision_from_suggestion(suggestion.id)
    except TemplateDraftRevisionValidationError as exc:
        assert exc.validation_result["errors"][0]["code"] == "missing_old_text"
    else:
        raise AssertionError("Expected TemplateDraftRevisionValidationError")
    assert suggestion_repository.saved_revision is None


def test_create_draft_revision_blocks_duplicate_old_text() -> None:
    document = make_legal_document()
    template = make_template(
        content=f"{TEMPLATE_CONTENT} Repetat: 10 zile calendaristice."
    )
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(candidate, document, template, hunk_status="accepted")
    suggestion_repository = FakeSuggestionRepository(suggestion)
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion_repository=suggestion_repository,
    )

    try:
        service.create_draft_revision_from_suggestion(suggestion.id)
    except TemplateDraftRevisionValidationError as exc:
        assert exc.validation_result["errors"][0]["code"] == "duplicate_old_text"
    else:
        raise AssertionError("Expected TemplateDraftRevisionValidationError")
    assert suggestion_repository.saved_revision is None


def test_create_draft_revision_ignores_rejected_hunks() -> None:
    document = make_legal_document()
    template = make_template()
    candidate = make_candidate(template, document)
    suggestion = make_suggestion(
        candidate,
        document,
        template,
        hunk_status="accepted",
        extra_hunks=[
            TemplateChangeSuggestionHunk(
                id=UUID("95000000-0000-0000-0000-000000000002"),
                suggestion_id=UUID("94000000-0000-0000-0000-000000000001"),
                change_type="replace",
                old_text="text missing from template",
                new_text="SHOULD NOT APPLY",
                rationale="Rejected hunk.",
                source_reference="DEMO",
                confidence=0.2,
                status="rejected",
            )
        ],
    )
    service = make_service(
        candidate,
        document,
        template,
        FakeSuggestionGenerator(),
        suggestion=suggestion,
    )

    revision = service.create_draft_revision_from_suggestion(suggestion.id)

    assert "5 zile calendaristice" in revision.revised_content
    assert "SHOULD NOT APPLY" not in revision.revised_content
    assert revision.applied_hunk_ids == [suggestion.hunks[0].id]


def make_service(
    candidate: LegalDocumentTemplateReviewCandidate,
    document: NormalizedLegalDocument,
    template: Template,
    generator: FakeSuggestionGenerator,
    *,
    approval_email_service: FakeApprovalEmailService | None = None,
    candidate_repository: FakeCandidateRepository | None = None,
    suggestion: TemplateChangeSuggestion | None = None,
    suggestion_repository: FakeSuggestionRepository | None = None,
) -> TemplateChangeSuggestionService:
    candidate_repository = candidate_repository or FakeCandidateRepository(candidate)
    suggestion_repository = suggestion_repository or FakeSuggestionRepository(
        suggestion
    )
    return TemplateChangeSuggestionService(
        candidate_repository=candidate_repository,
        legal_document_repository=FakeLegalDocumentRepository(document),
        template_repository=FakeTemplateRepository(template),
        suggestion_repository=suggestion_repository,
        suggestion_generator=generator,
        approval_email_service=approval_email_service,
    )


def make_candidate(
    template: Template,
    document: NormalizedLegalDocument,
    *,
    template_version_hash: str | None = None,
) -> LegalDocumentTemplateReviewCandidate:
    return LegalDocumentTemplateReviewCandidate(
        candidate_id=UUID("93000000-0000-0000-0000-000000000001"),
        normalized_legal_document_id=document.id,
        template_id=template.id or 0,
        template_code=template.template_code,
        template_name=template.name,
        template_version=template.version,
        template_version_hash=template_version_hash or template_hash(template),
        match_type="amended_reference",
        matched_reference="ro:lege:260:2008",
        review_reason=(
            "DEMO - Legea nr. 99/2026 amends ro:lege:260:2008, "
            "which is referenced by template DEMO_PAD_POLICY_WORDING_RO."
        ),
        confidence=0.95,
        status="needs_review",
        source_metadata={
            "is_synthetic": True,
            "demo_dataset": "law_change_pipeline_demo_v1",
        },
        created_at=NOW,
        updated_at=NOW,
    )


def make_legal_document() -> NormalizedLegalDocument:
    return NormalizedLegalDocument(
        id=UUID("92000000-0000-0000-0000-000000000001"),
        raw_source_item_id=UUID("91000000-0000-0000-0000-000000000001"),
        source_id="demo_ro_portal_legislativ",
        source_key="demo_ro_portal_legislativ",
        jurisdiction="RO",
        parser_id="ro_portal_legislativ",
        canonical_url="demo://law_change_pipeline_demo_v1/ro/lege-99-2026",
        source_url="demo://law_change_pipeline_demo_v1/ro/lege-99-2026",
        external_identifier="demo:ro:lege:99:2026",
        title="DEMO - Legea nr. 99/2026 pentru modificarea Legii nr. 260/2008",
        language="ro",
        issuer="DEMO - Parlamentul României",
        instrument_type="lege",
        instrument_number="99",
        instrument_year=2026,
        publication_reference="DEMO - Monitorul Oficial nr. 500/2026",
        publication_date=date(2026, 5, 15),
        effective_date=date(2026, 6, 15),
        status="in_force",
        legal_references=["ro:lege:99:2026"],
        amends=["ro:lege:260:2008"],
        repeals=[],
        full_text=(
            "Termenul de notificare a daunei se modifica de la "
            "10 zile la 5 zile."
        ),
        document_hash="demo-hash",
        extraction_confidence=0.95,
        source_metadata={
            "is_synthetic": True,
            "demo_dataset": "law_change_pipeline_demo_v1",
        },
        created_at=NOW,
        updated_at=NOW,
    )


def make_legislatie_legal_document() -> NormalizedLegalDocument:
    return make_legal_document().model_copy(
        update={
            "id": UUID("92000000-0000-0000-0000-000000000120"),
            "raw_source_item_id": UUID("91000000-0000-0000-0000-000000000120"),
            "source_id": "ro_portal_legislativ",
            "source_key": "ro:lege:120:2026",
            "canonical_url": (
                "https://legislatie.just.ro/Public/DetaliiDocument/1202026"
            ),
            "source_url": (
                "https://legislatie.just.ro/Public/DetaliiDocument/1202026"
            ),
            "external_identifier": "ro:lege:120:2026",
            "title": "LEGE nr. 120/2026 privind notificarea daunelor PAD",
            "issuer": "Parlamentul României",
            "legal_references": ["ro:lege:120:2026"],
            "amends": ["ro:lege:260:2008"],
            "source_metadata": {"extractor_id": "legislatie_just"},
        }
    )


def make_template(content: str = TEMPLATE_CONTENT) -> Template:
    return Template(
        id=42,
        template_code="DEMO_PAD_POLICY_WORDING_RO",
        name="DEMO - PAD Policy Wording Romania",
        version="demo-v1",
        document_type="insurance_contract",
        is_active=True,
        content=content,
        jurisdiction="RO",
        product_line="property",
        legal_references_json=["ro:lege:260:2008"],
        metadata_json={
            "is_synthetic": True,
            "demo_dataset": "law_change_pipeline_demo_v1",
        },
        created_at=NOW,
    )


def make_suggestion(
    candidate: LegalDocumentTemplateReviewCandidate,
    document: NormalizedLegalDocument,
    template: Template,
    *,
    hunk_status: str = "draft",
    old_text: str = "10 zile calendaristice",
    new_text: str = "5 zile calendaristice",
    extra_hunks: list[TemplateChangeSuggestionHunk] | None = None,
) -> TemplateChangeSuggestion:
    suggestion_id = UUID("94000000-0000-0000-0000-000000000001")
    hunks = [
        TemplateChangeSuggestionHunk(
            id=UUID("95000000-0000-0000-0000-000000000001"),
            suggestion_id=suggestion_id,
            section_id="claims.notification",
            section_label="Claim notification",
            change_type="replace",
            old_text=old_text,
            new_text=new_text,
            rationale="The law changes the deadline from 10 to 5 days.",
            source_reference="DEMO - Legea nr. 99/2026",
            confidence=0.91,
            status=hunk_status,
        )
    ]
    hunks.extend(extra_hunks or [])
    return TemplateChangeSuggestion(
        id=suggestion_id,
        candidate_id=candidate.candidate_id,
        template_id=template.id or 0,
        normalized_legal_document_id=document.id,
        template_version_hash=candidate.template_version_hash,
        status="draft",
        overall_summary="Draft update for the claim notification deadline.",
        validation_result={
            "valid": True,
            "errors": [],
            "generator": {"model_name": "fake", "model_version": "test"},
        },
        hunks=hunks,
        created_at=NOW,
        updated_at=NOW,
    )


def make_draft_revision(
    suggestion: TemplateChangeSuggestion,
    template: Template,
) -> TemplateDraftRevision:
    return TemplateDraftRevision(
        id=UUID("96000000-0000-0000-0000-000000000001"),
        suggestion_id=suggestion.id,
        template_id=template.id or 0,
        template_code=template.template_code,
        template_name=template.name,
        base_template_version=template.version,
        base_template_version_hash=suggestion.template_version_hash,
        status="draft",
        base_content=template.content,
        revised_content=template.content.replace(
            "10 zile calendaristice",
            "5 zile calendaristice",
            1,
        ),
        applied_hunk_ids=[suggestion.hunks[0].id],
        validation_result={"valid": True, "errors": []},
        source_metadata={"suggestion_id": str(suggestion.id)},
        created_at=NOW,
        updated_at=NOW,
    )


def template_hash(template: Template) -> str:
    payload = f"{template.template_code}\n{template.version}\n{template.content}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
