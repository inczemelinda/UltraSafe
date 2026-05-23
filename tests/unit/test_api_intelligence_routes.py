from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from underwright.api.intelligence_dependencies import (
    get_intelligence_insight_query_service,
    get_intelligence_service,
    get_legal_review_wording_impact_service,
    get_legal_template_review_candidate_repository,
    get_template_change_suggestion_service,
    get_template_review_query_service,
)
from underwright.api.main import create_app
from underwright.application.services.intelligence_service import (
    build_demo_intelligence_service,
)
from underwright.application.services.legal_review_wording_impact_service import (
    LegalReviewWordingImpactService,
)
from underwright.application.services.template_change_suggestion_service import (
    TemplateDraftRevisionSubmissionError,
    TemplateDraftRevisionValidationError,
)
from underwright.domain.intelligence import (
    InsightCard,
    SourceLink,
    TemplateReviewCandidate,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewCandidate,
    LegalDocumentTemplateReviewItem,
    NormalizedLegalDocument,
    TemplateChangeSuggestion,
    TemplateChangeSuggestionDetail,
    TemplateChangeSuggestionHunk,
    TemplateDraftRevision,
    WordingDocumentImpact,
    WordingDocumentProposedChange,
)
from underwright.domain.models import Template
from underwright.domain.wording import WordingDocument, WordingDocumentVersion


UNDERWRITER_HEADERS = {"X-Underwright-Role": "underwriter"}


class FakeInsightQueryService:
    def __init__(self) -> None:
        self.params = None

    def list_insight_cards(
        self,
        country=None,
        source_id=None,
        line_of_business=None,
        topic=None,
        event_type=None,
        severity=None,
        status="classified",
        limit=50,
    ):
        self.params = {
            "country": country,
            "source_id": source_id,
            "line_of_business": line_of_business,
            "topic": topic,
            "event_type": event_type,
            "severity": severity,
            "status": status,
            "limit": limit,
        }
        return [
            InsightCard(
                event_id=UUID("50000000-0000-0000-0000-000000000001"),
                title="ASF comunicare PAD",
                paragraphs=[
                    "Source item is potentially relevant to PAD.",
                    "Review recommended for potentially affected Romanian property work.",
                ],
                source_links=[
                    SourceLink(
                        label="ASF Romania source",
                        url="https://asfromania.ro/item",
                        content_type="text/html",
                    ),
                    SourceLink(
                        label="document.pdf",
                        url="https://asfromania.ro/document.pdf",
                        content_type="application/pdf",
                    ),
                ],
                published_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
                source_id="asf_ro",
                source_name="ASF Romania",
                country="RO",
                line_of_business="property",
                event_type="regulatory_update",
                topics=["PAD / compulsory home insurance"],
                severity="medium",
                confidence=0.78,
                status="classified",
            )
        ]


class FakeTemplateReviewQueryService:
    def __init__(self) -> None:
        self.status = None
        self.limit = None

    def list_candidates(self, status="candidate", limit=50):
        self.status = status
        self.limit = limit
        return [
            TemplateReviewCandidate(
                event_id=UUID("50000000-0000-0000-0000-000000000001"),
                template_id=22,
                template_code="PAD_STANDARD_RO",
                template_name="PAD Standard RO",
                template_version="1.0",
                event_title="ASF actualizare Legea 260/2008",
                source_url="https://asfromania.ro/item",
                legal_references_json=["Legea 260/2008"],
                rule_ids_json=["legal_reference_overlap"],
                match_score=0.95,
                rationale=(
                    "Review recommended. This template may reference a law or "
                    "topic potentially affected by the external event."
                ),
                created_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
            )
        ]


class FakeLegalTemplateReviewCandidateRepository:
    def __init__(self, items: list[LegalDocumentTemplateReviewItem]) -> None:
        self.items = items
        self.status = None
        self.limit = None

    def list_review_items(self, status="needs_review", limit=50):
        self.status = status
        self.limit = limit
        return self.items


class FakeLegalReviewWordingImpactService:
    def __init__(self, impacts: list[WordingDocumentImpact] | None = None) -> None:
        self.impacts = impacts or []

    def enrich_review_items(
        self,
        items: list[LegalDocumentTemplateReviewItem],
    ) -> list[LegalDocumentTemplateReviewItem]:
        return [
            item.model_copy(update={"wording_document_impacts": self.impacts})
            for item in items
        ]


class FakeWordingDocumentService:
    def __init__(
        self,
        documents: list[WordingDocument],
        current_versions: dict[int, WordingDocumentVersion],
    ) -> None:
        self.documents = documents
        self.current_versions = current_versions
        self.publish_calls = []
        self.update_calls = []

    def list_wording_documents(self) -> list[WordingDocument]:
        return self.documents

    def get_current_published_version(
        self,
        wording_document_id: int,
    ) -> WordingDocumentVersion:
        return self.current_versions[wording_document_id]

    def publish_wording_version(self, *args, **kwargs):
        self.publish_calls.append((args, kwargs))
        raise AssertionError("Impact enrichment must not publish wording versions.")

    def update_wording_version_full_text(self, *args, **kwargs):
        self.update_calls.append((args, kwargs))
        raise AssertionError("Impact enrichment must not mutate wording text.")


class EmptyPolicyWordingService:
    def get_relevant_wording_sections(self, *args, **kwargs):
        return []


class FakeTemplateChangeSuggestionService:
    def __init__(
        self,
        suggestion: TemplateChangeSuggestion,
        draft_error: TemplateDraftRevisionValidationError | None = None,
        submission_error: TemplateDraftRevisionSubmissionError | None = None,
    ) -> None:
        self.suggestion = suggestion
        self.draft_error = draft_error
        self.submission_error = submission_error
        self.candidate_id: UUID | None = None
        self.detail_suggestion_id: UUID | None = None
        self.updated = None
        self.accepted = None
        self.rejected = None
        self.draft_suggestion_id: UUID | None = None
        self.submitted_revision_id: UUID | None = None

    def create_suggestion(self, candidate_id: UUID) -> TemplateChangeSuggestion:
        self.candidate_id = candidate_id
        return self.suggestion

    def get_suggestion_detail(
        self,
        suggestion_id: UUID,
    ) -> TemplateChangeSuggestionDetail:
        self.detail_suggestion_id = suggestion_id
        return make_template_change_suggestion_detail(self.suggestion)

    def update_hunk(
        self,
        *,
        suggestion_id: UUID,
        hunk_id: UUID,
        new_text: str | None = None,
        status: str | None = None,
        reviewer_notes: str | None = None,
    ) -> TemplateChangeSuggestion:
        self.updated = {
            "suggestion_id": suggestion_id,
            "hunk_id": hunk_id,
            "new_text": new_text,
            "status": status,
            "reviewer_notes": reviewer_notes,
        }
        hunk = self.suggestion.hunks[0].model_copy(
            update={
                "new_text": new_text or self.suggestion.hunks[0].new_text,
                "status": status or "edited",
                "reviewer_notes": reviewer_notes,
            }
        )
        self.suggestion = self.suggestion.model_copy(update={"hunks": [hunk]})
        return self.suggestion

    def accept_hunk(
        self,
        *,
        suggestion_id: UUID,
        hunk_id: UUID,
    ) -> TemplateChangeSuggestion:
        self.accepted = {"suggestion_id": suggestion_id, "hunk_id": hunk_id}
        hunk = self.suggestion.hunks[0].model_copy(update={"status": "accepted"})
        self.suggestion = self.suggestion.model_copy(update={"hunks": [hunk]})
        return self.suggestion

    def reject_hunk(
        self,
        *,
        suggestion_id: UUID,
        hunk_id: UUID,
    ) -> TemplateChangeSuggestion:
        self.rejected = {"suggestion_id": suggestion_id, "hunk_id": hunk_id}
        hunk = self.suggestion.hunks[0].model_copy(update={"status": "rejected"})
        self.suggestion = self.suggestion.model_copy(update={"hunks": [hunk]})
        return self.suggestion

    def create_draft_revision_from_suggestion(
        self,
        suggestion_id: UUID,
    ) -> TemplateDraftRevision:
        self.draft_suggestion_id = suggestion_id
        if self.draft_error is not None:
            raise self.draft_error
        return make_template_draft_revision(self.suggestion)

    def submit_draft_revision_for_approval(
        self,
        draft_revision_id: UUID,
    ) -> TemplateDraftRevision:
        self.submitted_revision_id = draft_revision_id
        if self.submission_error is not None:
            raise self.submission_error
        revision = make_template_draft_revision(self.suggestion)
        return revision.model_copy(
            update={
                "id": draft_revision_id,
                "status": "submitted_for_approval",
                "source_metadata": {
                    **revision.source_metadata,
                    "approval_request": {
                        "recipient_institution": "DEMO - Parlamentul Romaniei",
                        "submission_status": "sent",
                    },
                },
            }
        )


def test_intelligence_feed_route_returns_cards() -> None:
    app = create_app()
    service = FakeInsightQueryService()
    app.dependency_overrides[get_intelligence_insight_query_service] = lambda: service
    client = TestClient(app)

    response = client.get(
        "/intelligence/events",
        params={
            "country": "RO",
            "source_id": "asf_ro",
            "line_of_business": "property",
            "topic": "PAD / compulsory home insurance",
            "event_type": "regulatory_update",
            "severity": "medium",
            "limit": 7,
        },
    )

    assert response.status_code == 200
    card = response.json()[0]
    assert card["title"] == "ASF comunicare PAD"
    assert len(card["paragraphs"]) == 2
    assert card["source_links"][0]["url"] == "https://asfromania.ro/item"
    assert card["source_links"][1]["content_type"] == "application/pdf"
    assert service.params == {
        "country": "RO",
        "source_id": "asf_ro",
        "line_of_business": "property",
        "topic": "PAD / compulsory home insurance",
        "event_type": "regulatory_update",
        "severity": "medium",
        "status": "classified",
        "limit": 7,
    }


def test_event_detail_route_returns_audit_and_alerts() -> None:
    app = create_app()
    service = build_demo_intelligence_service()
    event_id = service.list_feed_cards()[0].event_id
    app.dependency_overrides[get_intelligence_service] = lambda: service
    client = TestClient(app)

    response = client.get(f"/intelligence/events/{event_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["event"]["event_id"] == str(event_id)
    assert body["source"]["source_id"] == "asf_ro"
    assert body["alerts"]
    assert body["audit_records"]


def test_template_review_candidates_route_returns_persisted_candidates() -> None:
    app = create_app()
    service = FakeTemplateReviewQueryService()
    app.dependency_overrides[get_template_review_query_service] = lambda: service
    client = TestClient(app)

    response = client.get(
        "/intelligence/template-review-candidates",
        params={"status": "candidate", "limit": 7},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["template_code"] == "PAD_STANDARD_RO"
    assert body[0]["source_url"] == "https://asfromania.ro/item"
    assert body[0]["legal_references_json"] == ["Legea 260/2008"]
    assert "Review recommended" in body[0]["rationale"]
    assert service.status == "candidate"
    assert service.limit == 7


def test_legal_template_review_candidates_route_returns_law_change_items() -> None:
    app = create_app()
    item = make_template_change_suggestion_detail(
        make_template_change_suggestion()
    )
    repository = FakeLegalTemplateReviewCandidateRepository(
        [
            LegalDocumentTemplateReviewItem(
                legal_document=item.normalized_legal_document,
                candidates=[item.candidate],
                affected_template_count=1,
                highest_confidence=item.candidate.confidence,
            )
        ]
    )
    app.dependency_overrides[get_legal_template_review_candidate_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_legal_review_wording_impact_service] = (
        lambda: FakeLegalReviewWordingImpactService()
    )
    client = TestClient(app)

    response = client.get(
        "/intelligence/legal-template-review-candidates",
        params={"status": "needs_review", "limit": 7},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["legal_document"]["title"].startswith("DEMO - Legea")
    assert body[0]["affected_template_count"] == 1
    assert body[0]["highest_confidence"] == 0.95
    assert body[0]["candidates"][0]["template_code"] == (
        "DEMO_PAD_POLICY_WORDING_RO"
    )
    assert repository.status == "needs_review"
    assert repository.limit == 7


def test_legal_template_review_candidates_include_wording_document_impacts() -> None:
    app = create_app()
    item = make_template_change_suggestion_detail(
        make_template_change_suggestion()
    )
    repository = FakeLegalTemplateReviewCandidateRepository(
        [
            LegalDocumentTemplateReviewItem(
                legal_document=item.normalized_legal_document,
                candidates=[item.candidate],
                affected_template_count=1,
                highest_confidence=item.candidate.confidence,
            )
        ]
    )
    app.dependency_overrides[get_legal_template_review_candidate_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_legal_review_wording_impact_service] = (
        lambda: FakeLegalReviewWordingImpactService(
            [
                WordingDocumentImpact(
                    wording_document_id=1,
                    wording_document_code="DEMO_PAD_POLICY_WORDING_RO",
                    wording_document_title="PAD Property Insurance Wording RO",
                    current_published_version_id=10,
                    affected_clause_ids=["claims.notification"],
                    affected_legal_references=["ro:lege:260:2008"],
                    matched_text_snippets=["Notify claims in 10 days."],
                    match_reason="legal reference match",
                    confidence="high",
                    confidence_score=0.92,
                    proposed_changes=[
                        WordingDocumentProposedChange(
                            target="structured_clause",
                            clause_id="claims.notification",
                            current_text="Notify claims in 10 days.",
                            proposed_text="Notify claims in 5 days.",
                            rationale="Legal change updates the deadline.",
                            diff=(
                                "--- current\n+++ proposed\n"
                                "- Notify claims in 10 days.\n"
                                "+ Notify claims in 5 days."
                            ),
                        )
                    ],
                )
            ]
        )
    )
    client = TestClient(app)

    response = client.get("/intelligence/legal-template-review-candidates")

    assert response.status_code == 200
    impact = response.json()[0]["wording_document_impacts"][0]
    assert impact["wording_document_code"] == "DEMO_PAD_POLICY_WORDING_RO"
    assert impact["affected_clause_ids"] == ["claims.notification"]
    assert impact["proposed_changes"][0]["proposed_text"] == (
        "Notify claims in 5 days."
    )
    assert impact["safe_to_auto_draft"] is False


def test_legal_template_review_candidates_enrich_legislatie_impacts() -> None:
    app = create_app()
    item = make_legislatie_review_item()
    repository = FakeLegalTemplateReviewCandidateRepository([item])
    wording_service = FakeWordingDocumentService(
        [make_wording_document()],
        {1: make_current_published_wording_version()},
    )
    app.dependency_overrides[get_legal_template_review_candidate_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_legal_review_wording_impact_service] = (
        lambda: LegalReviewWordingImpactService(
            wording_service,
            policy_wording_service=EmptyPolicyWordingService(),
        )
    )
    client = TestClient(app)

    response = client.get("/intelligence/legal-template-review-candidates")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["legal_document"]["parser_id"] == "legislatie_just"
    impact = body[0]["wording_document_impacts"][0]
    assert impact["wording_document_code"] == "DEMO_PAD_POLICY_WORDING_RO"
    assert impact["current_published_version_id"] == 10
    assert impact["affected_legal_references"] == ["ro:lege:260:2008"]
    assert impact["affected_clause_ids"] == ["claims.notification"]
    assert impact["matched_text_snippets"]
    proposed_change = impact["proposed_changes"][0]
    assert proposed_change["current_text"]
    assert "10 zile calendaristice" in proposed_change["current_text"]
    assert "5 zile calendaristice" in proposed_change["proposed_text"]
    assert proposed_change["safe_to_auto_draft"] is False
    assert impact["safe_to_auto_draft"] is False
    assert wording_service.publish_calls == []
    assert wording_service.update_calls == []


def test_create_template_change_suggestion_route_returns_draft_hunks() -> None:
    app = create_app()
    suggestion = make_template_change_suggestion()
    service = FakeTemplateChangeSuggestionService(suggestion)
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/intelligence/legal-template-review-candidates/"
        "81000000-0000-0000-0000-000000000001/suggestions",
        headers=UNDERWRITER_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert body["hunks"][0]["change_type"] == "replace"
    assert body["hunks"][0]["old_text"] == "10 zile calendaristice"
    assert body["hunks"][0]["new_text"] == "5 zile calendaristice"
    assert service.candidate_id == UUID("81000000-0000-0000-0000-000000000001")


def test_template_change_mutation_requires_underwriter_role() -> None:
    app = create_app()
    service = FakeTemplateChangeSuggestionService(make_template_change_suggestion())
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/intelligence/legal-template-review-candidates/"
        "81000000-0000-0000-0000-000000000001/suggestions",
        headers={"X-Underwright-Role": "client"},
    )

    assert response.status_code == 403


def test_template_change_mutation_requires_authentication() -> None:
    app = create_app()
    service = FakeTemplateChangeSuggestionService(make_template_change_suggestion())
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/intelligence/legal-template-review-candidates/"
        "81000000-0000-0000-0000-000000000001/suggestions"
    )

    assert response.status_code == 401


def test_template_change_read_endpoint_does_not_require_mutation_role() -> None:
    app = create_app()
    suggestion = make_template_change_suggestion()
    service = FakeTemplateChangeSuggestionService(suggestion)
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.get(
        "/intelligence/template-change-suggestions/"
        "82000000-0000-0000-0000-000000000001"
    )

    assert response.status_code == 200
    assert service.detail_suggestion_id == suggestion.id


def test_get_template_change_suggestion_route_returns_review_context() -> None:
    app = create_app()
    suggestion = make_template_change_suggestion()
    service = FakeTemplateChangeSuggestionService(suggestion)
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.get(
        "/intelligence/template-change-suggestions/"
        "82000000-0000-0000-0000-000000000001"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggestion"]["id"] == str(suggestion.id)
    assert body["candidate"]["candidate_id"] == str(suggestion.candidate_id)
    assert body["normalized_legal_document"]["title"].startswith("DEMO - Legea")
    assert body["template"]["template_code"] == "DEMO_PAD_POLICY_WORDING_RO"
    assert body["suggestion"]["hunks"][0]["new_text"] == "5 zile calendaristice"
    assert body["suggestion"]["hunks"][0]["template_section_title"] == (
        "Claim notification"
    )
    assert "Asiguratul trebuie să notifice dauna" in (
        body["suggestion"]["hunks"][0]["full_context_excerpt"]
    )
    assert "de la producerea evenimentului" in (
        body["suggestion"]["hunks"][0]["after_context"]
    )
    assert body["suggestion"]["hunks"][0]["start_offset"] == 54
    assert service.detail_suggestion_id == suggestion.id


def test_patch_template_change_suggestion_hunk_edits_new_text_only() -> None:
    app = create_app()
    suggestion = make_template_change_suggestion()
    service = FakeTemplateChangeSuggestionService(suggestion)
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.patch(
        "/intelligence/template-change-suggestions/"
        "82000000-0000-0000-0000-000000000001/hunks/"
        "83000000-0000-0000-0000-000000000001",
        headers=UNDERWRITER_HEADERS,
        json={
            "new_text": "5 zile calendaristice de la producerea evenimentului",
            "reviewer_notes": "Adjusted wording.",
        },
    )

    assert response.status_code == 200
    hunk = response.json()["hunks"][0]
    assert hunk["old_text"] == "10 zile calendaristice"
    assert hunk["new_text"].startswith("5 zile calendaristice")
    assert hunk["status"] == "edited"
    assert hunk["reviewer_notes"] == "Adjusted wording."
    assert service.updated["new_text"].startswith("5 zile calendaristice")


def test_patch_template_change_suggestion_hunk_rejects_old_text_edit() -> None:
    app = create_app()
    service = FakeTemplateChangeSuggestionService(make_template_change_suggestion())
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.patch(
        "/intelligence/template-change-suggestions/"
        "82000000-0000-0000-0000-000000000001/hunks/"
        "83000000-0000-0000-0000-000000000001",
        headers=UNDERWRITER_HEADERS,
        json={"old_text": "edited old text"},
    )

    assert response.status_code == 422


def test_accept_template_change_suggestion_hunk_route_sets_status() -> None:
    app = create_app()
    suggestion = make_template_change_suggestion()
    service = FakeTemplateChangeSuggestionService(suggestion)
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/intelligence/template-change-suggestions/"
        "82000000-0000-0000-0000-000000000001/hunks/"
        "83000000-0000-0000-0000-000000000001/accept",
        headers=UNDERWRITER_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["hunks"][0]["status"] == "accepted"
    assert service.accepted == {
        "suggestion_id": UUID("82000000-0000-0000-0000-000000000001"),
        "hunk_id": UUID("83000000-0000-0000-0000-000000000001"),
    }


def test_reject_template_change_suggestion_hunk_route_sets_status() -> None:
    app = create_app()
    suggestion = make_template_change_suggestion()
    service = FakeTemplateChangeSuggestionService(suggestion)
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/intelligence/template-change-suggestions/"
        "82000000-0000-0000-0000-000000000001/hunks/"
        "83000000-0000-0000-0000-000000000001/reject",
        headers=UNDERWRITER_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["hunks"][0]["status"] == "rejected"
    assert service.rejected == {
        "suggestion_id": UUID("82000000-0000-0000-0000-000000000001"),
        "hunk_id": UUID("83000000-0000-0000-0000-000000000001"),
    }


def test_create_template_draft_revision_route_returns_draft_revision() -> None:
    app = create_app()
    suggestion = make_template_change_suggestion()
    service = FakeTemplateChangeSuggestionService(suggestion)
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/intelligence/template-change-suggestions/"
        "82000000-0000-0000-0000-000000000001/create-draft-revision",
        headers=UNDERWRITER_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert "10 zile calendaristice" in body["base_content"]
    assert "5 zile calendaristice" in body["revised_content"]
    assert body["applied_hunk_ids"] == [
        "83000000-0000-0000-0000-000000000001"
    ]
    assert service.draft_suggestion_id == suggestion.id


def test_create_template_draft_revision_route_returns_validation_error() -> None:
    app = create_app()
    service = FakeTemplateChangeSuggestionService(
        make_template_change_suggestion(),
        draft_error=TemplateDraftRevisionValidationError(
            {
                "valid": False,
                "errors": [
                    {
                        "code": "stale_template_version",
                        "message": "Template changed.",
                    }
                ],
            }
        ),
    )
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/intelligence/template-change-suggestions/"
        "82000000-0000-0000-0000-000000000001/create-draft-revision",
        headers=UNDERWRITER_HEADERS,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["errors"][0]["code"] == "stale_template_version"


def test_submit_template_draft_revision_route_sends_for_approval() -> None:
    app = create_app()
    suggestion = make_template_change_suggestion()
    service = FakeTemplateChangeSuggestionService(suggestion)
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/intelligence/template-draft-revisions/"
        "84000000-0000-0000-0000-000000000001/submit-for-approval",
        headers=UNDERWRITER_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted_for_approval"
    assert body["source_metadata"]["approval_request"]["submission_status"] == "sent"
    assert service.submitted_revision_id == UUID(
        "84000000-0000-0000-0000-000000000001"
    )


def test_submit_template_draft_revision_route_returns_submission_error() -> None:
    app = create_app()
    service = FakeTemplateChangeSuggestionService(
        make_template_change_suggestion(),
        submission_error=TemplateDraftRevisionSubmissionError(
            {
                "valid": False,
                "errors": [
                    {
                        "code": "invalid_draft_revision_status",
                        "message": "Only draft revisions can be submitted.",
                    }
                ],
            }
        ),
    )
    app.dependency_overrides[get_template_change_suggestion_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/intelligence/template-draft-revisions/"
        "84000000-0000-0000-0000-000000000001/submit-for-approval",
        headers=UNDERWRITER_HEADERS,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["errors"][0]["code"] == (
        "invalid_draft_revision_status"
    )


def test_feedback_route_records_feedback() -> None:
    app = create_app()
    service = build_demo_intelligence_service()
    alert = service.list_alerts()[0]
    app.dependency_overrides[get_intelligence_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/intelligence/feedback",
        json={
            "user_id": "ana.ionescu",
            "target_type": "alert",
            "target_id": str(alert.alert_id),
            "feedback_type": "dismiss",
            "comment": "Not useful for this account.",
        },
    )

    assert response.status_code == 200
    assert response.json()["feedback_type"] == "dismiss"


def test_ingestion_run_trigger_route_is_available() -> None:
    app = create_app()
    service = build_demo_intelligence_service()
    app.dependency_overrides[get_intelligence_service] = lambda: service
    client = TestClient(app)

    created = client.post("/intelligence/ingestion-runs", json={"source_id": "asf_ro"})

    assert created.status_code == 200
    assert created.json()["source_id"] == "asf_ro"


def make_template_change_suggestion() -> TemplateChangeSuggestion:
    return TemplateChangeSuggestion(
        id=UUID("82000000-0000-0000-0000-000000000001"),
        candidate_id=UUID("81000000-0000-0000-0000-000000000001"),
        template_id=22,
        normalized_legal_document_id=UUID("70000000-0000-0000-0000-000000000001"),
        template_version_hash="template-version-hash",
        status="draft",
        overall_summary="Draft update for claim notification deadline.",
        validation_result={"valid": True},
        hunks=[
            TemplateChangeSuggestionHunk(
                id=UUID("83000000-0000-0000-0000-000000000001"),
                suggestion_id=UUID("82000000-0000-0000-0000-000000000001"),
                section_id="claims.notification",
                section_label="Claim notification",
                template_section_title="Claim notification",
                template_article_title="Art. 7 - Claim notification",
                before_context="Asiguratul trebuie să notifice dauna în termen de",
                after_context="de la producerea evenimentului.",
                full_context_excerpt=(
                    "Asiguratul trebuie să notifice dauna în termen de "
                    "10 zile calendaristice de la producerea evenimentului."
                ),
                start_offset=54,
                end_offset=78,
                change_type="replace",
                old_text="10 zile calendaristice",
                new_text="5 zile calendaristice",
                rationale="The legal document changes the deadline.",
                source_reference="DEMO - Legea nr. 99/2026",
                confidence=0.91,
            )
        ],
        created_at=datetime(2026, 5, 11, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 11, 10, 0, tzinfo=UTC),
    )


def make_template_change_suggestion_detail(
    suggestion: TemplateChangeSuggestion,
) -> TemplateChangeSuggestionDetail:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    return TemplateChangeSuggestionDetail(
        suggestion=suggestion,
        candidate=LegalDocumentTemplateReviewCandidate(
            candidate_id=suggestion.candidate_id,
            normalized_legal_document_id=suggestion.normalized_legal_document_id,
            template_id=suggestion.template_id,
            template_code="DEMO_PAD_POLICY_WORDING_RO",
            template_name="DEMO - PAD Policy Wording Romania",
            template_version="demo-v1",
            template_version_hash=suggestion.template_version_hash,
            match_type="amended_reference",
            matched_reference="ro:lege:260:2008",
            review_reason="The legal document amends a template reference.",
            confidence=0.95,
            status="needs_review",
            created_at=now,
            updated_at=now,
        ),
        normalized_legal_document=NormalizedLegalDocument(
            id=suggestion.normalized_legal_document_id,
            raw_source_item_id=UUID("71000000-0000-0000-0000-000000000001"),
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
            legal_references=["ro:lege:99:2026"],
            amends=["ro:lege:260:2008"],
            full_text="The deadline changes from 10 days to 5 days.",
            document_hash="demo-hash",
            extraction_confidence=0.95,
            created_at=now,
            updated_at=now,
        ),
        template=Template(
            id=suggestion.template_id,
            template_code="DEMO_PAD_POLICY_WORDING_RO",
            name="DEMO - PAD Policy Wording Romania",
            version="demo-v1",
            document_type="insurance_contract",
            is_active=True,
            content="Asiguratul notifica dauna in 10 zile calendaristice.",
            jurisdiction="RO",
            product_line="property",
            legal_references_json=["ro:lege:260:2008"],
            created_at=now,
        ),
    )


def make_legislatie_review_item() -> LegalDocumentTemplateReviewItem:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    legal_document_id = UUID("70000000-0000-0000-0000-000000000120")
    legal_document = NormalizedLegalDocument(
        id=legal_document_id,
        raw_source_item_id=UUID("71000000-0000-0000-0000-000000000120"),
        source_id="ro_portal_legislativ",
        source_key="legislatie_just:decizie:1074:2018",
        jurisdiction="RO",
        parser_id="legislatie_just",
        canonical_url="https://legislatie.just.ro/Public/DetaliiDocument/204818",
        source_url="https://legislatie.just.ro/Public/DetaliiDocument/204818",
        external_identifier="ro:decizie:1074:2018",
        title="DECIZIE nr. 1074/2018 privind polițele PAD",
        language="ro",
        issuer="Autoritatea de Supraveghere Financiară",
        instrument_type="decizie",
        instrument_number="1074",
        instrument_year=2018,
        instrument_date=date(2018, 9, 4),
        publication_reference="Monitorul Oficial nr. 776",
        publication_date=date(2018, 9, 5),
        effective_date=date(2018, 9, 5),
        status="in_force",
        legal_references=["ro:decizie:1074:2018"],
        structured_clauses=[
            {
                "id": "articolul-1",
                "title": "Articolul 1",
                "text": (
                    "Termenul de notificare a daunelor PAD se modifică de la "
                    "10 zile la 5 zile."
                ),
            }
        ],
        amends=["ro:lege:260:2008"],
        repeals=[],
        full_text=(
            "DECIZIE nr. 1074/2018 privind polițele PAD. Termenul de "
            "notificare a daunelor se modifică de la 10 zile la 5 zile "
            "pentru polițele PAD reglementate de Legea nr. 260/2008."
        ),
        document_hash="legislatie-document-hash",
        extraction_confidence=0.97,
        source_metadata={"extractor_id": "legislatie_just"},
        created_at=now,
        updated_at=now,
    )
    candidate = LegalDocumentTemplateReviewCandidate(
        candidate_id=UUID("81000000-0000-0000-0000-000000000120"),
        normalized_legal_document_id=legal_document_id,
        template_id=22,
        template_code="DEMO_PAD_POLICY_WORDING_RO",
        template_name="DEMO - PAD Policy Wording Romania",
        template_version="demo-v1",
        template_version_hash="template-version-hash",
        match_type="amended_reference",
        matched_reference="ro:lege:260:2008",
        review_reason="Legislatie.just.ro act amends a template reference.",
        confidence=0.95,
        status="needs_review",
        source_metadata={"source_id": "ro_portal_legislativ"},
        created_at=now,
        updated_at=now,
    )
    return LegalDocumentTemplateReviewItem(
        legal_document=legal_document,
        candidates=[candidate],
        affected_template_count=1,
        highest_confidence=0.95,
    )


def make_wording_document() -> WordingDocument:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    return WordingDocument(
        id=1,
        code="DEMO_PAD_POLICY_WORDING_RO",
        title="PAD Property Insurance Wording RO",
        product_line="property",
        jurisdiction="RO",
        language="ro-RO",
        status="published",
        created_at=now,
        updated_at=now,
    )


def make_current_published_wording_version() -> WordingDocumentVersion:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    return WordingDocumentVersion(
        id=10,
        wording_document_id=1,
        version="1.0",
        status="published",
        full_text=(
            "Prezenta poliță este emisă în conformitate cu Legea nr. 260/2008. "
            "Asiguratul trebuie să notifice dauna în termen de 10 zile "
            "calendaristice."
        ),
        content_hash="current-wording-hash",
        legal_references_json=["ro:lege:260:2008"],
        structured_clauses_json=[
            {
                "id": "claims.notification",
                "title": "Notificarea daunelor",
                "text": (
                    "Asiguratul trebuie să notifice dauna în termen de 10 zile "
                    "calendaristice."
                ),
                "legal_references": ["ro:lege:260:2008"],
            }
        ],
        effective_from=date(2026, 1, 1),
        created_at=now,
        updated_at=now,
    )


def make_template_draft_revision(
    suggestion: TemplateChangeSuggestion,
) -> TemplateDraftRevision:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    return TemplateDraftRevision(
        id=UUID("84000000-0000-0000-0000-000000000001"),
        suggestion_id=suggestion.id,
        template_id=suggestion.template_id,
        template_code="DEMO_PAD_POLICY_WORDING_RO",
        template_name="DEMO - PAD Policy Wording Romania",
        base_template_version="demo-v1",
        base_template_version_hash=suggestion.template_version_hash,
        status="draft",
        base_content="Asiguratul notifica dauna in 10 zile calendaristice.",
        revised_content="Asiguratul notifica dauna in 5 zile calendaristice.",
        applied_hunk_ids=[suggestion.hunks[0].id],
        validation_result={"valid": True, "errors": []},
        source_metadata={"suggestion_id": str(suggestion.id)},
        created_at=now,
        updated_at=now,
    )
