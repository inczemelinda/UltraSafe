from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from underwright.application.ports import WordingDocumentRepository
from underwright.application.services.legal_review_wording_impact_service import (
    LegalReviewWordingImpactService,
)
from underwright.domain.claim_analysis import PolicyWordingSection
from underwright.domain.legal_intelligence import NormalizedLegalDocument
from underwright.domain.wording import WordingDocument, WordingDocumentVersion


NOW = datetime(2026, 5, 16, 10, 0, tzinfo=UTC)


def test_wording_impact_matches_current_published_version_by_legal_reference() -> None:
    legal_document = make_legal_document(
        amends=["ro:lege:260:2008"],
        full_text="Termenul de notificare se modifica de la 10 zile la 5 zile.",
    )
    version = make_version(
        legal_references_json=["ro:lege:260:2008"],
        full_text=(
            "Prezenta polita este emisa in conformitate cu Legea nr. 260/2008. "
            "Asiguratul trebuie sa notifice dauna in termen de 10 zile calendaristice."
        ),
    )
    service = LegalReviewWordingImpactService(
        FakeWordingDocumentService([make_document()], {1: version}),
        policy_wording_service=EmptyPolicyWordingService(),
    )

    impacts = service.impacts_for_legal_document(legal_document)

    assert len(impacts) == 1
    impact = impacts[0]
    assert impact.wording_document_code == "DEMO_PAD_POLICY_WORDING_RO"
    assert impact.current_published_version_id == 10
    assert impact.affected_legal_references == ["ro:lege:260:2008"]
    assert impact.match_reason == "legal reference match"
    assert impact.confidence == "high"
    assert "Legea nr. 260/2008" in impact.matched_text_snippets[0]
    assert impact.proposed_changes[0].current_text
    assert "5 zile calendaristice" in impact.proposed_changes[0].proposed_text
    assert impact.safe_to_auto_draft is False


def test_wording_impact_matches_structured_clause_by_clause_text() -> None:
    legal_document = make_legal_document(
        legal_references=[],
        amends=[],
        full_text="Noua regula schimba notificare dauna pentru asigurat.",
    )
    version = make_version(
        legal_references_json=[],
        structured_clauses_json=[
            {
                "id": "claims.notification",
                "title": "Claim notification",
                "text": "Asiguratul trebuie sa transmita notificare dauna.",
            }
        ],
    )
    service = LegalReviewWordingImpactService(
        FakeWordingDocumentService([make_document()], {1: version}),
        policy_wording_service=EmptyPolicyWordingService(),
    )

    impact = service.impacts_for_legal_document(legal_document)[0]

    assert impact.match_reason == "clause semantic/text match"
    assert impact.affected_clause_ids == ["claims.notification"]
    assert impact.proposed_changes[0].target == "structured_clause"
    assert impact.proposed_changes[0].clause_id == "claims.notification"


def test_wording_impact_matches_full_text_keyword_overlap() -> None:
    legal_document = make_legal_document(
        legal_references=[],
        amends=[],
        full_text="Regula noua modifica acoperire furt pentru locuinta.",
    )
    version = make_version(
        legal_references_json=[],
        structured_clauses_json=None,
        full_text="Polita include acoperire furt pentru locuinta asigurata.",
    )
    service = LegalReviewWordingImpactService(
        FakeWordingDocumentService([make_document()], {1: version}),
        policy_wording_service=EmptyPolicyWordingService(),
    )

    impact = service.impacts_for_legal_document(legal_document)[0]

    assert impact.match_reason == "full text keyword match"
    assert impact.confidence == "medium"
    assert "acoperire furt" in impact.matched_text_snippets[0]


def test_wording_impact_returns_empty_when_nothing_matches() -> None:
    legal_document = make_legal_document(
        legal_references=[],
        amends=[],
        full_text="Schimbare despre raportari financiare pentru brokeri.",
    )
    service = LegalReviewWordingImpactService(
        FakeWordingDocumentService([make_document()], {1: make_version()}),
        policy_wording_service=EmptyPolicyWordingService(),
    )

    assert service.impacts_for_legal_document(legal_document) == []


def test_static_policy_wording_fallback_is_used_when_no_document_matches() -> None:
    legal_document = make_legal_document(
        legal_references=[],
        amends=[],
        full_text="Regula noua clarifica fire damage coverage pentru claims.",
    )
    service = LegalReviewWordingImpactService(
        FakeWordingDocumentService([], {}),
        policy_wording_service=FakePolicyWordingService(),
    )

    impact = service.impacts_for_legal_document(legal_document)[0]

    assert impact.wording_document_id is None
    assert impact.wording_document_code == "STATIC_POLICY_WORDING_FALLBACK"
    assert impact.match_reason == "static policy wording fallback"
    assert impact.affected_clause_ids == ["coverage.fire_damage"]


def test_legislatie_document_generates_review_only_wording_impact() -> None:
    legal_document = make_legislatie_legal_document(
        amends=["ro:lege:260:2008"],
        full_text=(
            "LEGE nr. 120/2026 modifică termenul de notificare a daunelor "
            "de la 10 zile la 5 zile pentru polițele PAD."
        ),
    )
    version = make_version(
        legal_references_json=["ro:lege:260:2008"],
        structured_clauses_json=[
            {
                "id": "claims.notification",
                "title": "Notificarea daunelor",
                "text": (
                    "Prezenta poliță este emisă în conformitate cu Legea nr. "
                    "260/2008. Asiguratul trebuie să notifice dauna în termen "
                    "de 10 zile calendaristice."
                ),
                "legal_references": ["ro:lege:260:2008"],
            }
        ],
        full_text=(
            "Prezenta poliță este emisă în conformitate cu Legea nr. 260/2008. "
            "Asiguratul trebuie să notifice dauna în termen de 10 zile "
            "calendaristice."
        ),
    )
    wording_service = FakeWordingDocumentService([make_document()], {1: version})
    service = LegalReviewWordingImpactService(
        wording_service,
        policy_wording_service=EmptyPolicyWordingService(),
    )

    impact = service.impacts_for_legal_document(legal_document)[0]

    assert impact.wording_document_code == "DEMO_PAD_POLICY_WORDING_RO"
    assert impact.current_published_version_id == 10
    assert impact.affected_legal_references == ["ro:lege:260:2008"]
    assert impact.affected_clause_ids == ["claims.notification"]
    assert impact.matched_text_snippets
    assert impact.proposed_changes[0].current_text
    assert "5 zile calendaristice" in impact.proposed_changes[0].proposed_text
    assert impact.proposed_changes[0].safe_to_auto_draft is False
    assert impact.safe_to_auto_draft is False
    assert wording_service.publish_calls == []
    assert wording_service.update_calls == []


def test_legislatie_document_uses_static_policy_wording_fallback_when_needed() -> None:
    legal_document = make_legislatie_legal_document(
        legal_references=["ro:lege:120:2026"],
        amends=[],
        full_text="Regula nouă clarifică fire damage coverage pentru claims PAD.",
    )
    service = LegalReviewWordingImpactService(
        FakeWordingDocumentService([], {}),
        policy_wording_service=FakePolicyWordingService(),
    )

    impact = service.impacts_for_legal_document(legal_document)[0]

    assert impact.wording_document_id is None
    assert impact.wording_document_code == "STATIC_POLICY_WORDING_FALLBACK"
    assert impact.match_reason == "static policy wording fallback"
    assert impact.affected_clause_ids == ["coverage.fire_damage"]
    assert impact.proposed_changes[0].safe_to_auto_draft is False


def test_compare_draft_wording_version_to_current_published_version() -> None:
    current = make_version(
        id=10,
        content_hash="current-hash",
        legal_references_json=["ro:lege:260:2008"],
        structured_clauses_json=[
            {"id": "claims.notification", "text": "Notify in 10 days."}
        ],
        effective_from=date(2026, 1, 1),
        full_text="Notify in 10 days.",
    )
    draft = make_version(
        id=11,
        status="draft",
        content_hash="draft-hash",
        legal_references_json=["ro:lege:260:2008", "ro:lege:99:2026"],
        structured_clauses_json=[
            {"id": "claims.notification", "text": "Notify in 5 days."},
            {"id": "appeals.channel", "text": "Use the dispute channel."},
        ],
        effective_from=date(2026, 6, 1),
        full_text="Notify in 5 days.",
    )
    service = LegalReviewWordingImpactService(
        FakeWordingDocumentService([make_document()], {1: current}, {11: draft}),
        policy_wording_service=EmptyPolicyWordingService(),
    )

    comparison = service.compare_draft_to_current(
        wording_document_id=1,
        draft_version_id=11,
    )

    assert comparison.current_published_version_id == 10
    assert comparison.draft_version_id == 11
    assert comparison.added_clauses == ["appeals.channel"]
    assert comparison.modified_clauses == ["claims.notification"]
    assert comparison.changed_legal_references == ["ro:lege:99:2026"]
    assert comparison.changed_effective_dates == ["effective_from"]
    assert comparison.content_hash_changed is True
    assert comparison.proposed_changes[0].current_text == "Notify in 10 days."
    assert comparison.proposed_changes[0].proposed_text == "Notify in 5 days."


def test_wording_document_repository_protocol_matches_service_usage() -> None:
    assert "publish_wording_version" in WordingDocumentRepository.__dict__
    assert "update_wording_version_full_text" in WordingDocumentRepository.__dict__


class FakeWordingDocumentService:
    def __init__(
        self,
        documents: list[WordingDocument],
        current_versions: dict[int, WordingDocumentVersion],
        versions_by_id: dict[int, WordingDocumentVersion] | None = None,
    ) -> None:
        self.documents = documents
        self.current_versions = current_versions
        self.versions_by_id = versions_by_id or {}
        self.publish_calls = []
        self.update_calls = []

    def list_wording_documents(self) -> list[WordingDocument]:
        return self.documents

    def get_current_published_version(
        self,
        wording_document_id: int,
    ) -> WordingDocumentVersion:
        return self.current_versions[wording_document_id]

    def get_wording_version(self, wording_version_id: int) -> WordingDocumentVersion:
        return self.versions_by_id[wording_version_id]

    def publish_wording_version(self, *args, **kwargs):
        self.publish_calls.append((args, kwargs))
        raise AssertionError("Impact service must not publish wording versions.")

    def update_wording_version_full_text(self, *args, **kwargs):
        self.update_calls.append((args, kwargs))
        raise AssertionError("Impact service must not mutate wording text.")


class EmptyPolicyWordingService:
    def get_relevant_wording_sections(self, *args, **kwargs):
        return []


class FakePolicyWordingService:
    def get_relevant_wording_sections(self, *args, **kwargs):
        return [
            PolicyWordingSection(
                section_id="coverage.fire_damage",
                title="Fire damage coverage",
                text="The policy may cover fire damage claims.",
                coverage_tags=["fire", "claims"],
            )
        ]


def make_document() -> WordingDocument:
    return WordingDocument(
        id=1,
        code="DEMO_PAD_POLICY_WORDING_RO",
        title="PAD Property Insurance Wording RO",
        product_line="property",
        jurisdiction="RO",
        language="ro-RO",
        status="published",
        created_at=NOW,
        updated_at=NOW,
    )


def make_version(
    *,
    id: int = 10,
    status: str = "published",
    content_hash: str = "content-hash",
    legal_references_json=None,
    structured_clauses_json=None,
    effective_from: date | None = date(2026, 5, 14),
    full_text: str = "Polita standard pentru locuinta.",
) -> WordingDocumentVersion:
    return WordingDocumentVersion(
        id=id,
        wording_document_id=1,
        version="1.0",
        status=status,
        full_text=full_text,
        content_hash=content_hash,
        legal_references_json=legal_references_json,
        structured_clauses_json=structured_clauses_json,
        effective_from=effective_from,
        created_at=NOW,
        updated_at=NOW,
    )


def make_legal_document(
    *,
    legal_references: list[str] | None = None,
    amends: list[str] | None = None,
    full_text: str = "Termenul de notificare se modifica.",
) -> NormalizedLegalDocument:
    return NormalizedLegalDocument(
        id=UUID("92000000-0000-0000-0000-000000000001"),
        raw_source_item_id=UUID("91000000-0000-0000-0000-000000000001"),
        source_id="demo_ro_portal_legislativ",
        source_key="demo_ro_portal_legislativ",
        jurisdiction="RO",
        parser_id="ro_portal_legislativ",
        canonical_url="demo://legal-document",
        source_url="demo://legal-document",
        external_identifier="demo:ro:lege:99:2026",
        title="DEMO - Legea nr. 99/2026",
        language="ro",
        issuer="DEMO - Parlamentul Romaniei",
        instrument_type="lege",
        instrument_number="99",
        instrument_year=2026,
        publication_date=date(2026, 5, 15),
        effective_date=date(2026, 6, 15),
        status="in_force",
        legal_references=legal_references or ["ro:lege:99:2026"],
        amends=amends if amends is not None else ["ro:lege:260:2008"],
        repeals=[],
        full_text=full_text,
        document_hash="demo-hash",
        extraction_confidence=0.95,
        created_at=NOW,
        updated_at=NOW,
    )


def make_legislatie_legal_document(
    *,
    legal_references: list[str] | None = None,
    amends: list[str] | None = None,
    full_text: str = "Termenul de notificare se modifică.",
) -> NormalizedLegalDocument:
    return make_legal_document(
        legal_references=legal_references or ["ro:lege:120:2026"],
        amends=amends if amends is not None else ["ro:lege:260:2008"],
        full_text=full_text,
    ).model_copy(
        update={
            "source_id": "ro_portal_legislativ",
            "source_key": "legislatie_just:decizie:1074:2018",
            "parser_id": "legislatie_just",
            "canonical_url": (
                "https://legislatie.just.ro/Public/DetaliiDocument/204818"
            ),
            "source_url": "https://legislatie.just.ro/Public/DetaliiDocument/204818",
            "external_identifier": "ro:decizie:1074:2018",
            "title": "DECIZIE nr. 1074/2018 privind polițele PAD",
            "issuer": "Autoritatea de Supraveghere Financiară",
            "instrument_type": "decizie",
            "instrument_number": "1074",
            "instrument_year": 2018,
            "publication_reference": "Monitorul Oficial nr. 776",
            "source_metadata": {"extractor_id": "legislatie_just"},
        }
    )
