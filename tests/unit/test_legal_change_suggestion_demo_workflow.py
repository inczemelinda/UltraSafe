from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from underwright.application.services.legal_document_template_correlation_service import (
    LegalDocumentTemplateCorrelationService,
)
from underwright.application.services.template_change_suggestion_service import (
    TemplateChangeSuggestionService,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewCandidate,
    NormalizedLegalDocument,
    TemplateChangeSuggestion,
    TemplateChangeSuggestionHunk,
    TemplateDraftRevision,
)
from underwright.domain.models import Template
from underwright.infrastructure.llm.template_change_suggestion_generator import (
    DeterministicDemoTemplateChangeSuggestionGenerator,
)


NOW = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
DATASET = "law_change_pipeline_demo_v1"
TEMPLATE_CONTENT = (
    "Prezenta poliță este emisă în conformitate cu Legea nr. 260/2008. "
    "Asiguratul trebuie să notifice dauna în termen de 10 zile calendaristice "
    "de la producerea evenimentului."
)


def test_demo_legal_change_suggestion_workflow_creates_draft_revision() -> None:
    legal_document = seed_demo_legal_document()
    template = seed_demo_template()
    legal_document_repository = InMemoryLegalDocumentRepository([legal_document])
    template_repository = InMemoryTemplateRepository([template])
    candidate_repository = InMemoryCandidateRepository()

    correlation_service = LegalDocumentTemplateCorrelationService(
        legal_document_repository=legal_document_repository,
        template_repository=template_repository,
        candidate_repository=candidate_repository,
    )
    correlation_result = correlation_service.correlate_batch(limit=10)

    assert correlation_result.status == "success"
    assert correlation_result.candidates_created == 1
    assert len(candidate_repository.candidates) == 1

    candidate = candidate_repository.candidates[0]
    assert candidate.normalized_legal_document_id == legal_document.id
    assert candidate.template_id == template.id
    assert candidate.match_type == "amended_reference"
    assert candidate.matched_reference == "ro:lege:260:2008"

    suggestion_repository = InMemorySuggestionRepository()
    suggestion_service = TemplateChangeSuggestionService(
        candidate_repository=candidate_repository,
        legal_document_repository=legal_document_repository,
        template_repository=template_repository,
        suggestion_repository=suggestion_repository,
        suggestion_generator=DeterministicDemoTemplateChangeSuggestionGenerator(),
    )

    suggestion = suggestion_service.create_suggestion(candidate.candidate_id)

    assert suggestion.id in suggestion_repository.suggestions
    assert suggestion.hunks
    hunk = suggestion.hunks[0]
    assert "10 zile calendaristice" in hunk.old_text
    assert "5 zile calendaristice" in hunk.new_text

    user_modified_text = (
        "Asiguratul trebuie să notifice dauna în termen de 5 zile "
        "calendaristice de la producerea evenimentului asigurat."
    )
    edited_suggestion = suggestion_service.update_hunk(
        suggestion_id=suggestion.id,
        hunk_id=hunk.id,
        new_text=user_modified_text,
        reviewer_notes="Reviewer aligned wording with the policy section.",
    )

    assert edited_suggestion.hunks[0].status == "edited"
    assert edited_suggestion.hunks[0].new_text == user_modified_text

    accepted_suggestion = suggestion_service.accept_hunk(
        suggestion_id=suggestion.id,
        hunk_id=hunk.id,
    )

    assert accepted_suggestion.hunks[0].status == "accepted"

    draft_revision = suggestion_service.create_draft_revision_from_suggestion(
        suggestion.id
    )

    assert draft_revision.id in suggestion_repository.draft_revisions
    assert user_modified_text in draft_revision.revised_content
    assert "10 zile calendaristice" not in draft_revision.revised_content
    assert template.content == TEMPLATE_CONTENT

    stored_suggestion = suggestion_repository.get_by_id(suggestion.id)
    assert stored_suggestion.status == "applied_to_draft"
    assert stored_suggestion.validation_result["valid"] is True
    assert stored_suggestion.candidate_id == candidate.candidate_id
    assert stored_suggestion.normalized_legal_document_id == legal_document.id
    assert draft_revision.template_id == template.id
    assert draft_revision.applied_hunk_ids == [hunk.id]


class InMemoryLegalDocumentRepository:
    def __init__(self, documents: list[NormalizedLegalDocument]) -> None:
        self.documents_by_id = {document.id: document for document in documents}

    def list_for_template_correlation(
        self,
        *,
        limit: int,
        source_id: str | None = None,
    ) -> list[NormalizedLegalDocument]:
        documents = [
            document
            for document in self.documents_by_id.values()
            if source_id is None or document.source_id == source_id
        ]
        return documents[:limit]

    def get_by_id(self, document_id: UUID) -> NormalizedLegalDocument:
        return self.documents_by_id[document_id]


class InMemoryTemplateRepository:
    def __init__(self, templates: list[Template]) -> None:
        self.templates_by_id = {template.id: template for template in templates}

    def list_active(self) -> list[Template]:
        return [
            template
            for template in self.templates_by_id.values()
            if template.is_active
        ]

    def get_by_id(self, template_id: int) -> Template:
        return self.templates_by_id[template_id]


class InMemoryCandidateRepository:
    def __init__(self) -> None:
        self.candidates: list[LegalDocumentTemplateReviewCandidate] = []
        self.candidates_by_id: dict[UUID, LegalDocumentTemplateReviewCandidate] = {}
        self.keys: set[tuple[UUID, int, str, str, str | None]] = set()

    def save_if_new(
        self,
        candidate: LegalDocumentTemplateReviewCandidate,
    ) -> bool:
        key = (
            candidate.normalized_legal_document_id,
            candidate.template_id,
            candidate.template_version_hash,
            candidate.match_type,
            candidate.matched_reference,
        )
        if key in self.keys:
            return False
        self.keys.add(key)
        self.candidates.append(candidate)
        self.candidates_by_id[candidate.candidate_id] = candidate
        return True

    def get_by_id(
        self,
        candidate_id: UUID,
    ) -> LegalDocumentTemplateReviewCandidate:
        return self.candidates_by_id[candidate_id]


class InMemorySuggestionRepository:
    def __init__(self) -> None:
        self.suggestions: dict[UUID, TemplateChangeSuggestion] = {}
        self.draft_revisions: dict[UUID, TemplateDraftRevision] = {}

    def save(self, suggestion: TemplateChangeSuggestion) -> TemplateChangeSuggestion:
        self.suggestions[suggestion.id] = suggestion
        return suggestion

    def get_by_id(self, suggestion_id: UUID) -> TemplateChangeSuggestion:
        return self.suggestions[suggestion_id]

    def update_hunk(
        self,
        *,
        suggestion_id: UUID,
        hunk: TemplateChangeSuggestionHunk,
        validation_result: dict,
        updated_at: datetime,
    ) -> TemplateChangeSuggestion:
        suggestion = self.suggestions[suggestion_id]
        hunks = [
            hunk if existing.id == hunk.id else existing
            for existing in suggestion.hunks
        ]
        updated = suggestion.model_copy(
            update={
                "hunks": hunks,
                "validation_result": validation_result,
                "updated_at": updated_at,
            }
        )
        self.suggestions[suggestion_id] = updated
        return updated

    def update_status(
        self,
        *,
        suggestion_id: UUID,
        status: str,
        validation_result: dict,
        updated_at: datetime,
    ) -> TemplateChangeSuggestion:
        suggestion = self.suggestions[suggestion_id]
        updated = suggestion.model_copy(
            update={
                "status": status,
                "validation_result": validation_result,
                "updated_at": updated_at,
            }
        )
        self.suggestions[suggestion_id] = updated
        return updated

    def save_draft_revision(
        self,
        revision: TemplateDraftRevision,
    ) -> TemplateDraftRevision:
        self.draft_revisions[revision.id] = revision
        return revision


def seed_demo_legal_document() -> NormalizedLegalDocument:
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
        issuer="DEMO - Parlamentul Romaniei",
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
            "DEMO - Legea nr. 99/2026 amending Legea nr. 260/2008. "
            "The claim notification deadline changes from 10 days to 5 days."
        ),
        document_hash="demo-legal-document-hash",
        extraction_confidence=0.95,
        source_metadata={
            "is_synthetic": True,
            "demo_dataset": DATASET,
        },
        created_at=NOW,
        updated_at=NOW,
    )


def seed_demo_template() -> Template:
    return Template(
        id=42,
        template_code="DEMO_PAD_POLICY_WORDING_RO",
        name="DEMO - PAD Policy Wording Romania",
        version="demo-v1",
        document_type="insurance_contract",
        is_active=True,
        content=TEMPLATE_CONTENT,
        jurisdiction="RO",
        product_line="property",
        legal_references_json=["ro:lege:260:2008"],
        metadata_json={
            "is_synthetic": True,
            "demo_dataset": DATASET,
        },
        created_at=NOW,
    )
