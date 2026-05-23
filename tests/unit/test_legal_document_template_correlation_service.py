from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

from underwright.application.services.legal_document_template_correlation_service import (
    LegalDocumentTemplateCorrelationService,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewCandidate,
    NormalizedLegalDocument,
)
from underwright.domain.models import Template


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)


class FakeLegalDocumentRepository:
    def __init__(self, documents: list[NormalizedLegalDocument]) -> None:
        self.documents = documents
        self.limit = None
        self.source_id = None

    def list_for_template_correlation(
        self,
        limit: int,
        source_id: str | None = None,
    ) -> list[NormalizedLegalDocument]:
        self.limit = limit
        self.source_id = source_id
        return self.documents[:limit]


class FakeTemplateRepository:
    def __init__(self, templates: list[Template]) -> None:
        self.templates = templates

    def list_active(self) -> list[Template]:
        return self.templates


class FakeCandidateRepository:
    def __init__(self) -> None:
        self.candidates: list[LegalDocumentTemplateReviewCandidate] = []
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
        return True


def test_correlates_demo_law_change_to_pad_template_by_amended_reference() -> None:
    document = make_legal_document()
    template = make_template()
    candidate_repo = FakeCandidateRepository()
    service = LegalDocumentTemplateCorrelationService(
        legal_document_repository=FakeLegalDocumentRepository([document]),
        template_repository=FakeTemplateRepository([template]),
        candidate_repository=candidate_repo,
    )

    first_run = service.correlate_batch(limit=10)
    second_run = service.correlate_batch(limit=10)

    assert first_run.status == "success"
    assert first_run.legal_documents_seen == 1
    assert first_run.templates_seen == 1
    assert first_run.candidates_created == 1
    assert second_run.candidates_created == 0
    assert len(candidate_repo.candidates) == 1

    candidate = candidate_repo.candidates[0]
    assert candidate.normalized_legal_document_id == document.id
    assert candidate.template_id == template.id
    assert candidate.template_version_hash
    assert candidate.match_type == "amended_reference"
    assert candidate.matched_reference == "ro:lege:260:2008"
    assert candidate.confidence >= 0.9
    assert candidate.status == "needs_review"
    assert "amends ro:lege:260:2008" in candidate.review_reason
    assert "DEMO_PAD_POLICY_WORDING_RO" in candidate.review_reason
    assert candidate.source_metadata["is_synthetic"] is True
    assert (
        candidate.source_metadata["demo_dataset"]
        == "law_change_pipeline_demo_v1"
    )
    assert template.content == TEMPLATE_CONTENT


def test_correlates_repealed_and_direct_references() -> None:
    document = make_legal_document(
        legal_references=["ro:lege:10:2020"],
        amends=[],
        repeals=["ro:lege:20:2021"],
    )
    template = make_template(
        legal_references=["ro:lege:10:2020", "ro:lege:20:2021"]
    )
    candidate_repo = FakeCandidateRepository()
    service = LegalDocumentTemplateCorrelationService(
        legal_document_repository=FakeLegalDocumentRepository([document]),
        template_repository=FakeTemplateRepository([template]),
        candidate_repository=candidate_repo,
    )

    result = service.correlate_batch(limit=10)

    assert result.candidates_created == 2
    candidates_by_type = {
        candidate.match_type: candidate for candidate in candidate_repo.candidates
    }
    assert candidates_by_type["repealed_reference"].matched_reference == (
        "ro:lege:20:2021"
    )
    assert candidates_by_type["direct_reference"].matched_reference == (
        "ro:lege:10:2020"
    )
    assert candidates_by_type["repealed_reference"].confidence > (
        candidates_by_type["direct_reference"].confidence
    )


def test_correlates_by_configured_jurisdiction_and_keyword_topic() -> None:
    document = make_legal_document(
        legal_references=["ro:lege:99:2026"],
        amends=[],
        repeals=[],
        full_text="Noua regula schimba termenul de notificare dauna.",
    )
    template = make_template(
        legal_references=[],
        content="Contract property cu notificare dauna pentru asigurat.",
    )
    candidate_repo = FakeCandidateRepository()
    service = LegalDocumentTemplateCorrelationService(
        legal_document_repository=FakeLegalDocumentRepository([document]),
        template_repository=FakeTemplateRepository([template]),
        candidate_repository=candidate_repo,
        product_topic_keywords={"claim_deadline": ["dauna", "notificare"]},
    )

    result = service.correlate_batch(limit=10)

    assert result.candidates_created == 1
    candidate = candidate_repo.candidates[0]
    assert candidate.match_type == "keyword_topic"
    assert candidate.matched_reference == "claim_deadline"
    assert candidate.confidence < 0.8
    assert "configured jurisdiction/topic keywords" in candidate.review_reason


def test_correlates_legislatie_document_to_template_by_affected_reference() -> None:
    document = make_legislatie_legal_document()
    template = make_template().model_copy(update={"metadata_json": {}})
    candidate_repo = FakeCandidateRepository()
    service = LegalDocumentTemplateCorrelationService(
        legal_document_repository=FakeLegalDocumentRepository([document]),
        template_repository=FakeTemplateRepository([template]),
        candidate_repository=candidate_repo,
    )

    result = service.correlate_batch(limit=10, source_id="ro_portal_legislativ")

    assert result.status == "success"
    assert result.candidates_created == 1
    assert candidate_repo.candidates[0].match_type == "amended_reference"
    assert candidate_repo.candidates[0].matched_reference == "ro:lege:260:2008"
    assert candidate_repo.candidates[0].source_metadata[
        "legal_document_source_key"
    ] == "ro:lege:120:2026"
    assert candidate_repo.candidates[0].source_metadata["is_synthetic"] is False


def test_correlates_legislatie_document_by_default_insurance_topic_keywords() -> None:
    document = make_legislatie_legal_document(
        legal_references=["ro:lege:120:2026"],
        amends=[],
        full_text=(
            "Actul introduce clauze de poliță pentru notificarea de daună "
            "și conformitate în asigurarea obligatorie PAD pentru locuințe."
        ),
    )
    template = make_template(
        legal_references=[],
        content=(
            "Condițiile de asigurare PAD pentru locuințe includ notificarea "
            "de daună și clauze de conformitate."
        ),
    )
    candidate_repo = FakeCandidateRepository()
    service = LegalDocumentTemplateCorrelationService(
        legal_document_repository=FakeLegalDocumentRepository([document]),
        template_repository=FakeTemplateRepository([template]),
        candidate_repository=candidate_repo,
    )

    result = service.correlate_batch(limit=10)

    assert result.candidates_created == 1
    candidate = candidate_repo.candidates[0]
    assert candidate.match_type == "keyword_topic"
    assert candidate.matched_reference in {
        "claims",
        "policy_wording",
        "property_insurance",
        "regulatory_compliance",
    }


def test_keyword_topic_requires_matching_jurisdiction() -> None:
    document = make_legal_document(
        legal_references=[],
        amends=[],
        repeals=[],
        full_text="Noua regula schimba termenul de notificare dauna.",
    )
    template = make_template(
        legal_references=[],
        content="Contract property cu notificare dauna pentru asigurat.",
        jurisdiction="BG",
    )
    candidate_repo = FakeCandidateRepository()
    service = LegalDocumentTemplateCorrelationService(
        legal_document_repository=FakeLegalDocumentRepository([document]),
        template_repository=FakeTemplateRepository([template]),
        candidate_repository=candidate_repo,
        product_topic_keywords={"claim_deadline": ["dauna", "notificare"]},
    )

    result = service.correlate_batch(limit=10)

    assert result.candidates_created == 0
    assert candidate_repo.candidates == []


def test_legal_template_correlation_does_not_import_ai() -> None:
    source = (
        ROOT
        / "src/underwright/application/services/"
        "legal_document_template_correlation_service.py"
    ).read_text()

    for blocked in [
        "underwright.infrastructure.llm",
        "OpenAI",
        "intelligence_classifier",
    ]:
        assert blocked not in source


TEMPLATE_CONTENT = (
    "Prezenta poliță este emisă în conformitate cu Legea nr. 260/2008. "
    "Asiguratul trebuie să notifice dauna în termen de 10 zile calendaristice."
)


def make_legal_document(
    *,
    legal_references: list[str] | None = None,
    amends: list[str] | None = None,
    repeals: list[str] | None = None,
    full_text: str | None = None,
) -> NormalizedLegalDocument:
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
        legal_references=legal_references or ["ro:lege:99:2026"],
        amends=amends if amends is not None else ["ro:lege:260:2008"],
        repeals=repeals or [],
        full_text=full_text
        or "Termenul de notificare a daunei se modifica de la 10 zile la 5 zile.",
        document_hash="demo-hash",
        extraction_confidence=0.95,
        source_metadata={
            "is_synthetic": True,
            "demo_dataset": "law_change_pipeline_demo_v1",
        },
        created_at=NOW,
        updated_at=NOW,
    )


def make_legislatie_legal_document(
    *,
    legal_references: list[str] | None = None,
    amends: list[str] | None = None,
    full_text: str | None = None,
) -> NormalizedLegalDocument:
    return NormalizedLegalDocument(
        id=UUID("92000000-0000-0000-0000-000000000120"),
        raw_source_item_id=UUID("91000000-0000-0000-0000-000000000120"),
        source_id="ro_portal_legislativ",
        source_key="ro:lege:120:2026",
        jurisdiction="RO",
        parser_id="ro_portal_legislativ",
        canonical_url="https://legislatie.just.ro/Public/DetaliiDocument/1202026",
        source_url="https://legislatie.just.ro/Public/DetaliiDocument/1202026",
        external_identifier="ro:lege:120:2026",
        title="LEGE nr. 120/2026 privind asigurarea obligatorie PAD",
        language="ro",
        issuer="Parlamentul României",
        instrument_type="lege",
        instrument_number="120",
        instrument_year=2026,
        publication_reference="Monitorul Oficial nr. 144/2026",
        publication_date=date(2026, 5, 15),
        effective_date=date(2026, 6, 15),
        status="in_force",
        legal_references=legal_references or ["ro:lege:120:2026"],
        amends=amends if amends is not None else ["ro:lege:260:2008"],
        repeals=[],
        full_text=full_text
        or (
            "Actul modifică Legea nr. 260/2008 pentru polițe PAD, brokeri, "
            "clauze de asigurare, notificarea de daună și conformitate."
        ),
        document_hash="legislatie-hash-120",
        extraction_confidence=0.94,
        source_metadata={
            "extractor_id": "legislatie_just",
            "source_item_id": "91000000-0000-0000-0000-000000000120",
        },
        created_at=NOW,
        updated_at=NOW,
    )


def make_template(
    *,
    legal_references: list[str] | None = None,
    content: str = TEMPLATE_CONTENT,
    jurisdiction: str | None = "RO",
) -> Template:
    return Template(
        id=42,
        template_code="DEMO_PAD_POLICY_WORDING_RO",
        name="DEMO - PAD Policy Wording Romania",
        version="demo-v1",
        document_type="insurance_contract",
        is_active=True,
        content=content,
        jurisdiction=jurisdiction,
        product_line="property",
        legal_references_json=(
            legal_references
            if legal_references is not None
            else ["ro:lege:260:2008"]
        ),
        metadata_json={
            "is_synthetic": True,
            "demo_dataset": "law_change_pipeline_demo_v1",
        },
        created_at=NOW,
    )
