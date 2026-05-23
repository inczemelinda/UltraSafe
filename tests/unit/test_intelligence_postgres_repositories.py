from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from underwright.domain.intelligence import (
    Attachment,
    AuditRecord,
    ClassificationOutput,
    EvidenceSnippet,
    ExternalEvent,
    IngestionRun,
    RawSourceItem,
    TemplateReviewCandidate,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentNormalizationResult,
    LegalDocumentTemplateReviewCandidate,
    NormalizedLegalDocument,
    TemplateChangeSuggestion,
    TemplateChangeSuggestionHunk,
    TemplateDraftRevision,
)
from underwright.domain.models import Template
from underwright.infrastructure.postgres.intelligence_repositories import (
    PostgresContractTemplateRepository,
    PostgresAuditRecordRepository,
    PostgresExternalEventRepository,
    PostgresInsightCardRepository,
    PostgresIngestionRunRepository,
    PostgresLegalDocumentTemplateReviewCandidateRepository,
    PostgresNormalizedLegalDocumentRepository,
    PostgresRawSourceItemRepository,
    PostgresSourceRepository,
    PostgresTemplateChangeSuggestionRepository,
    PostgresTemplateReviewCandidateRepository,
)


class FakeCursor:
    def __init__(
        self,
        fetchone_rows: list[dict] | None = None,
        fetchall_rows: list[list[dict]] | None = None,
    ) -> None:
        self.fetchone_rows = list(fetchone_rows or [])
        self.fetchall_rows = list(fetchall_rows or [])
        self.executed: list[tuple[str, object]] = []

    def execute(self, sql: str, params=()) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        if not self.fetchone_rows:
            return None
        return self.fetchone_rows.pop(0)

    def fetchall(self):
        if not self.fetchall_rows:
            return []
        return self.fetchall_rows.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False

    def cursor(self, row_factory=None):
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def make_connection_factory(cursor: FakeCursor, connection: FakeConnection | None = None):
    def factory():
        return connection or FakeConnection(cursor)

    return factory


def make_source_row() -> dict:
    now = datetime(2026, 5, 7, 9, 0, tzinfo=UTC)
    return {
        "source_id": "asf_ro",
        "name": "ASF Romania",
        "country": "RO",
        "source_type": "regulator",
        "trust_tier": "authoritative",
        "connector_type": "web_scrape",
        "language": "ro",
        "enabled": True,
        "config_json": {"list_url": "https://asfromania.ro/list"},
        "last_successful_run_at": None,
        "created_at": now,
        "updated_at": now,
    }


def make_raw_item() -> RawSourceItem:
    now = datetime(2026, 5, 7, 9, 0, tzinfo=UTC)
    return RawSourceItem(
        raw_item_id=UUID("40000000-0000-0000-0000-000000000001"),
        source_id="asf_ro",
        original_url="https://asfromania.ro/item",
        canonical_url="https://asfromania.ro/item",
        published_at=now,
        fetched_at=now,
        title="ASF comunicare",
        raw_html="<html>body</html>",
        extracted_text="Text despre asigurari de locuinte.",
        attachments_json=[
            Attachment(
                url="https://asfromania.ro/file.pdf",
                filename="file.pdf",
                content_type="application/pdf",
            )
        ],
        metadata_json={"issuer": "ASF"},
        content_hash="hash-1",
        created_at=now,
    )


def make_raw_item_row() -> dict:
    item = make_raw_item()
    row = item.model_dump(mode="python")
    row["attachments_json"] = [
        attachment.model_dump(mode="python") for attachment in item.attachments_json
    ]
    return row


def make_classification() -> ClassificationOutput:
    return ClassificationOutput(
        is_insurance_relevant=True,
        is_property_relevant=True,
        event_type="regulatory_update",
        topics=["residential property insurance"],
        affected_products=["residential_property"],
        affected_perils=[],
        severity="low",
        summary_for_underwriter="Review recommended.",
        recommended_action="Review recommended for potentially affected Romanian property work.",
        confidence=0.78,
        evidence=[
            EvidenceSnippet(
                snippet="Text despre asigurari de locuinte.",
                reason="Source text matched Romanian property topic.",
            )
        ],
    )


def make_external_event() -> ExternalEvent:
    now = datetime(2026, 5, 7, 9, 0, tzinfo=UTC)
    classification = make_classification()
    return ExternalEvent(
        event_id=UUID("50000000-0000-0000-0000-000000000001"),
        raw_item_id=make_raw_item().raw_item_id,
        source_id="asf_ro",
        source_type="regulator",
        trust_tier="authoritative",
        original_url="https://asfromania.ro/item",
        published_at=now,
        ingested_at=now,
        title="ASF comunicare",
        body_text_ref="raw_source_item:40000000-0000-0000-0000-000000000001:extracted_text",
        body_text="Text despre asigurari de locuinte.",
        original_language="ro",
        country="RO",
        jurisdiction="RO",
        event_type=classification.event_type,
        line_of_business="property",
        product="residential_property",
        topics_json=classification.topics,
        perils_json=classification.affected_perils,
        severity=classification.severity,
        confidence=classification.confidence,
        underwriter_summary=classification.summary_for_underwriter,
        recommended_action=classification.recommended_action,
        evidence_json=classification.evidence,
        classification_json=classification,
        status="classified",
    )


def make_insight_row(
    attachments_json: list[dict] | None = None,
    summary: str = "ASF published an item potentially relevant to PAD.",
    action: str = "Review recommended for potentially affected Romanian property work.",
) -> dict:
    event = make_external_event()
    row = event.model_dump(mode="python")
    row["topics_json"] = ["PAD / compulsory home insurance", "earthquake"]
    row["severity"] = "medium"
    row["underwriter_summary"] = summary
    row["recommended_action"] = action
    row["source_name"] = "ASF Romania"
    row["raw_attachments_json"] = attachments_json or [
        {
            "url": "https://asfromania.ro/document.pdf",
            "filename": "document.pdf",
            "content_type": "application/pdf",
        },
        {
            "url": "https://asfromania.ro/not-pdf",
            "filename": "page.html",
            "content_type": "text/html",
        },
    ]
    return row


def make_template_row() -> dict:
    return {
        "id": 22,
        "template_code": "PAD_STANDARD_RO",
        "name": "PAD Standard RO",
        "version": "1.0",
        "document_type": "insurance_contract",
        "is_active": True,
        "content": "Contract PAD guvernat de Legea 260/2008.",
        "jurisdiction": "RO",
        "product_line": "property",
        "legal_references_json": ["ro:lege:260:2008"],
        "metadata_json": {"is_synthetic": True},
        "created_at": datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
    }


def make_template_review_candidate() -> TemplateReviewCandidate:
    return TemplateReviewCandidate(
        candidate_id=UUID("60000000-0000-0000-0000-000000000001"),
        event_id=make_external_event().event_id,
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
            "Review recommended. This template may reference a law or topic "
            "potentially affected by the external event."
        ),
        evidence_json=[
            EvidenceSnippet(
                snippet="Legea 260/2008",
                reason="The event and template reference the same legal instrument.",
            )
        ],
        created_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
    )


def make_template_review_candidate_row() -> dict:
    return make_template_review_candidate().model_dump(mode="python")


def make_legal_document() -> NormalizedLegalDocument:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    return NormalizedLegalDocument(
        id=UUID("70000000-0000-0000-0000-000000000001"),
        raw_source_item_id=make_raw_item().raw_item_id,
        source_id="ro_portal_legislativ",
        source_key="ro:lege:260:2008",
        jurisdiction="RO",
        parser_id="ro_portal_legislativ",
        canonical_url="https://legislatie.just.ro/Public/DetaliiDocument/2602008",
        source_url="https://legislatie.just.ro/Public/DetaliiDocument/2602008",
        external_identifier="LEGE-260-2008",
        title="Legea nr. 260/2008",
        language="ro",
        issuer="Parlamentul Romaniei",
        instrument_type="lege",
        instrument_number="260",
        instrument_year=2008,
        instrument_date=date(2008, 11, 10),
        publication_reference="Monitorul Oficial nr. 757/2008",
        publication_date=date(2008, 11, 10),
        effective_date=date(2008, 11, 10),
        status="in_force",
        legal_references=[{"type": "lege", "number": "260", "year": 2008}],
        structured_clauses=[
            {
                "clause_id": "Articolul 1",
                "title": "Articolul 1",
                "text": "Text integral Legea nr. 260/2008.",
                "order": 1,
            }
        ],
        amends=[],
        repeals=[],
        full_text="Text integral Legea nr. 260/2008.",
        summary=None,
        document_hash="legal-doc-hash-1",
        extraction_confidence=0.91,
        parser_warnings=[],
        source_metadata={"source": "portal_legislativ"},
        created_at=now,
        updated_at=now,
    )


def make_legal_document_row() -> dict:
    return make_legal_document().model_dump(mode="python")


def make_legal_review_join_row() -> dict:
    row = make_legal_template_review_candidate().model_dump(mode="python")
    document_row = make_legal_document_row()
    for key, value in document_row.items():
        row[f"document_{key}"] = value
    row["document_id"] = document_row["id"]
    return row


def make_normalization_result(
    status: str = "normalized",
) -> LegalDocumentNormalizationResult:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    document = make_legal_document()
    return LegalDocumentNormalizationResult(
        id=UUID("80000000-0000-0000-0000-000000000001"),
        raw_source_item_id=document.raw_source_item_id,
        source_id=document.source_id,
        parser_id=document.parser_id,
        normalized_legal_document_id=(
            document.id if status == "normalized" else None
        ),
        status=status,
        reason=None if status == "normalized" else "Not a legislative item.",
        parser_warnings=[],
        source_metadata={"parser_id": document.parser_id},
        created_at=now,
        updated_at=now,
    )


def make_normalization_result_row(
    status: str = "normalized",
) -> dict:
    return make_normalization_result(status).model_dump(mode="python")


def make_legal_template_review_candidate() -> LegalDocumentTemplateReviewCandidate:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    return LegalDocumentTemplateReviewCandidate(
        candidate_id=UUID("81000000-0000-0000-0000-000000000001"),
        normalized_legal_document_id=make_legal_document().id,
        template_id=22,
        template_code="PAD_STANDARD_RO",
        template_name="PAD Standard RO",
        template_version="1.0",
        template_version_hash="template-version-hash",
        match_type="amended_reference",
        matched_reference="ro:lege:260:2008",
        review_reason=(
            "DEMO - Legea nr. 99/2026 amends ro:lege:260:2008, "
            "which is referenced by template PAD_STANDARD_RO."
        ),
        confidence=0.95,
        status="needs_review",
        source_metadata={
            "is_synthetic": True,
            "demo_dataset": "law_change_pipeline_demo_v1",
        },
        created_at=now,
        updated_at=now,
    )


def make_template_change_suggestion() -> TemplateChangeSuggestion:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    suggestion_id = UUID("82000000-0000-0000-0000-000000000001")
    return TemplateChangeSuggestion(
        id=suggestion_id,
        candidate_id=make_legal_template_review_candidate().candidate_id,
        template_id=22,
        normalized_legal_document_id=make_legal_document().id,
        template_version_hash="template-version-hash",
        status="draft",
        overall_summary="Draft update for claim notification deadline.",
        validation_result={
            "valid": True,
            "generator": {"model_name": "fake", "model_version": "test"},
        },
        hunks=[
            TemplateChangeSuggestionHunk(
                id=UUID("83000000-0000-0000-0000-000000000001"),
                suggestion_id=suggestion_id,
                section_id="claims.notification",
                section_label="Claim notification",
                change_type="replace",
                old_text="10 zile calendaristice",
                new_text="5 zile calendaristice",
                rationale="The legal document changes the deadline.",
                source_reference="DEMO - Legea nr. 99/2026",
                confidence=0.91,
                status="draft",
            )
        ],
        created_at=now,
        updated_at=now,
    )


def make_template_change_suggestion_row() -> dict:
    suggestion = make_template_change_suggestion()
    row = suggestion.model_dump(mode="python", exclude={"hunks"})
    return row


def make_template_change_suggestion_hunk_row() -> dict:
    return make_template_change_suggestion().hunks[0].model_dump(mode="python")


def make_edited_template_change_suggestion_hunk_row() -> dict:
    row = make_template_change_suggestion_hunk_row()
    row["new_text"] = "5 zile calendaristice de la producerea evenimentului"
    row["status"] = "edited"
    row["reviewer_notes"] = "Reviewer tightened the wording."
    return row


def make_template_draft_revision() -> TemplateDraftRevision:
    now = datetime(2026, 5, 11, 11, 0, tzinfo=UTC)
    return TemplateDraftRevision(
        id=UUID("84000000-0000-0000-0000-000000000001"),
        suggestion_id=make_template_change_suggestion().id,
        template_id=22,
        template_code="PAD_STANDARD_RO",
        template_name="PAD Standard RO",
        base_template_version="1.0",
        base_template_version_hash="template-version-hash",
        status="draft",
        base_content="Asiguratul notifica dauna in 10 zile calendaristice.",
        revised_content="Asiguratul notifica dauna in 5 zile calendaristice.",
        applied_hunk_ids=[make_template_change_suggestion().hunks[0].id],
        validation_result={"valid": True, "errors": []},
        source_metadata={
            "suggestion_id": str(make_template_change_suggestion().id),
        },
        created_at=now,
        updated_at=now,
    )


def make_template_draft_revision_row() -> dict:
    return make_template_draft_revision().model_dump(mode="python")


def test_normalized_legal_document_migration_defines_document_and_result_tables() -> None:
    migration_sql = Path("sql/011_normalized_legal_documents.sql").read_text()
    candidate_migration_sql = Path(
        "sql/013_legal_document_template_review_candidates.sql"
    ).read_text()
    suggestion_migration_sql = Path(
        "sql/014_template_change_suggestions.sql"
    ).read_text()
    draft_revision_migration_sql = Path(
        "sql/015_template_draft_revisions.sql"
    ).read_text()
    draft_revision_submission_migration_sql = Path(
        "sql/036_template_draft_revision_approval_submission.sql"
    ).read_text()
    hunk_context_migration_sql = Path(
        "sql/020_template_change_suggestion_hunk_context.sql"
    ).read_text()
    migrate_script = Path("scripts/db_migrate.sh").read_text()

    assert "CREATE TABLE IF NOT EXISTS normalized_legal_document" in migration_sql
    assert "instrument_date" in migration_sql
    assert "structured_clauses" in migration_sql
    assert "CREATE TABLE IF NOT EXISTS legal_document_normalization_result" in migration_sql
    for status in [
        "normalized",
        "parser_failed",
        "suppressed_non_legislative",
        "duplicate_unchanged",
        "skipped_missing_required_fields",
    ]:
        assert status in migration_sql
    assert "external_event" not in migration_sql
    assert "sql/010_legal_document_sources.sql" in migrate_script
    assert "sql/011_normalized_legal_documents.sql" in migrate_script
    assert "sql/034_normalized_legal_document_structured_clauses.sql" in (
        migrate_script
    )
    assert "CREATE TABLE IF NOT EXISTS legal_document_template_review_candidate" in (
        candidate_migration_sql
    )
    assert "normalized_legal_document_id" in candidate_migration_sql
    assert "template_version_hash" in candidate_migration_sql
    assert "amended_reference" in candidate_migration_sql
    assert "repealed_reference" in candidate_migration_sql
    assert "direct_reference" in candidate_migration_sql
    assert "keyword_topic" in candidate_migration_sql
    assert "needs_review" in candidate_migration_sql
    assert "sql/013_legal_document_template_review_candidates.sql" in migrate_script
    assert "CREATE TABLE IF NOT EXISTS template_change_suggestion" in (
        suggestion_migration_sql
    )
    assert "CREATE TABLE IF NOT EXISTS template_change_suggestion_hunk" in (
        suggestion_migration_sql
    )
    assert "manual_review" in suggestion_migration_sql
    assert "superseded" in suggestion_migration_sql
    assert "sql/014_template_change_suggestions.sql" in migrate_script
    assert "CREATE TABLE IF NOT EXISTS template_draft_revision" in (
        draft_revision_migration_sql
    )
    assert "applied_to_draft" in draft_revision_migration_sql
    assert "template_change_suggestion_status_check" in draft_revision_migration_sql
    assert "sql/015_template_draft_revisions.sql" in migrate_script
    assert "submitted_for_approval" in draft_revision_submission_migration_sql
    assert "template_draft_revision_status_check" in (
        draft_revision_submission_migration_sql
    )
    assert "sql/036_template_draft_revision_approval_submission.sql" in (
        migrate_script
    )
    assert "template_section_title" in hunk_context_migration_sql
    assert "full_context_excerpt" in hunk_context_migration_sql
    assert "start_offset" in hunk_context_migration_sql
    assert "sql/020_template_change_suggestion_hunk_context.sql" in migrate_script


def test_source_repository_get_enabled_returns_source() -> None:
    cursor = FakeCursor(fetchone_rows=[make_source_row()])

    repo = PostgresSourceRepository(make_connection_factory(cursor))
    source = repo.get_enabled("asf_ro")

    assert source.source_id == "asf_ro"
    assert source.connector_type == "web_scrape"
    assert cursor.executed[0][1] == ("asf_ro",)


def test_source_repository_get_by_id_returns_disabled_source() -> None:
    source_row = make_source_row()
    source_row["enabled"] = False
    cursor = FakeCursor(fetchone_rows=[source_row])

    repo = PostgresSourceRepository(make_connection_factory(cursor))
    source = repo.get_by_id("asf_ro")

    assert source.source_id == "asf_ro"
    assert source.enabled is False
    assert "enabled = true" not in cursor.executed[0][0]


def test_source_repository_get_enabled_raises_when_missing() -> None:
    repo = PostgresSourceRepository(make_connection_factory(FakeCursor()))

    try:
        repo.get_enabled("missing")
    except ValueError as exc:
        assert "Source not found" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_raw_source_item_repository_save_if_new_wraps_jsonb_and_commits() -> None:
    cursor = FakeCursor(fetchone_rows=[{"raw_item_id": make_raw_item().raw_item_id}])
    connection = FakeConnection(cursor)
    repo = PostgresRawSourceItemRepository(
        make_connection_factory(cursor, connection)
    )

    inserted = repo.save_if_new(make_raw_item())

    assert inserted is True
    assert connection.committed is True
    _, params = cursor.executed[0]
    assert isinstance(params[9], Jsonb)
    assert isinstance(params[10], Jsonb)


def test_raw_source_item_repository_save_if_new_returns_false_for_duplicate() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    repo = PostgresRawSourceItemRepository(
        make_connection_factory(cursor, connection)
    )

    inserted = repo.save_if_new(make_raw_item())

    assert inserted is False
    assert connection.committed is True


def test_raw_source_item_repository_lists_latest_items() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_raw_item_row()]])
    repo = PostgresRawSourceItemRepository(make_connection_factory(cursor))

    items = repo.list_latest(limit=10)

    assert len(items) == 1
    assert items[0].source_id == "asf_ro"
    assert cursor.executed[0][1] == (10,)


def test_raw_source_item_repository_get_by_id_returns_item() -> None:
    raw_item_id = make_raw_item().raw_item_id
    cursor = FakeCursor(fetchone_rows=[make_raw_item_row()])
    repo = PostgresRawSourceItemRepository(make_connection_factory(cursor))

    item = repo.get_by_id(raw_item_id)

    assert item.raw_item_id == raw_item_id
    assert item.attachments_json[0].filename == "file.pdf"


def test_raw_source_item_repository_get_by_id_raises_when_missing() -> None:
    repo = PostgresRawSourceItemRepository(make_connection_factory(FakeCursor()))

    try:
        repo.get_by_id(uuid4())
    except ValueError as exc:
        assert "RawSourceItem not found" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_raw_source_item_repository_lists_unprocessed_items() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_raw_item_row()]])
    repo = PostgresRawSourceItemRepository(make_connection_factory(cursor))

    items = repo.list_unprocessed(limit=10, source_id="asf_ro")

    assert len(items) == 1
    assert items[0].source_id == "asf_ro"
    assert cursor.executed[0][1] == ("asf_ro", 10)
    assert "LEFT JOIN external_event" in cursor.executed[0][0]
    assert "raw_source_item.source_id = %s" in cursor.executed[0][0]


def test_raw_source_item_repository_lists_all_unprocessed_items() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_raw_item_row()]])
    repo = PostgresRawSourceItemRepository(make_connection_factory(cursor))

    items = repo.list_unprocessed(limit=10)

    assert len(items) == 1
    assert cursor.executed[0][1] == (10,)
    assert "raw_source_item.source_id = %s" not in cursor.executed[0][0]


def test_external_event_repository_save_if_new_wraps_jsonb_and_commits() -> None:
    cursor = FakeCursor(fetchone_rows=[{"event_id": make_external_event().event_id}])
    connection = FakeConnection(cursor)
    repo = PostgresExternalEventRepository(make_connection_factory(cursor, connection))

    inserted = repo.save_if_new(make_external_event())

    assert inserted is True
    assert connection.committed is True
    _, params = cursor.executed[0]
    assert any(isinstance(param, Jsonb) for param in params)
    assert "ON CONFLICT (raw_item_id) DO NOTHING" in cursor.executed[0][0]


def test_external_event_repository_save_if_new_returns_false_for_duplicate() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    repo = PostgresExternalEventRepository(make_connection_factory(cursor, connection))

    inserted = repo.save_if_new(make_external_event())

    assert inserted is False
    assert connection.committed is True


def test_external_event_repository_lists_events_for_template_review() -> None:
    event = make_external_event()
    row = event.model_dump(mode="python")
    row["evidence_json"] = [
        evidence.model_dump(mode="python") for evidence in event.evidence_json
    ]
    row["classification_json"] = event.classification_json.model_dump(mode="python")
    cursor = FakeCursor(fetchall_rows=[[row]])
    repo = PostgresExternalEventRepository(make_connection_factory(cursor))

    events = repo.list_for_template_review(limit=7, source_id="asf_ro")

    assert len(events) == 1
    assert events[0].event_id == event.event_id
    sql, params = cursor.executed[0]
    assert "intelligence_template_review_candidate" in sql
    assert "external_event.source_id = %s" in sql
    assert params == ("asf_ro", 7)


def test_normalized_legal_document_repository_save_wraps_jsonb_and_commits() -> None:
    cursor = FakeCursor(fetchone_rows=[make_legal_document_row()])
    connection = FakeConnection(cursor)
    repo = PostgresNormalizedLegalDocumentRepository(
        make_connection_factory(cursor, connection)
    )

    saved = repo.save(make_legal_document())

    assert saved.id == make_legal_document().id
    assert connection.committed is True
    sql, params = cursor.executed[0]
    assert "INSERT INTO normalized_legal_document" in sql
    assert "external_event" not in sql
    assert isinstance(params[20], Jsonb)
    assert isinstance(params[21], Jsonb)
    assert isinstance(params[22], Jsonb)
    assert isinstance(params[23], Jsonb)
    assert isinstance(params[28], Jsonb)
    assert isinstance(params[29], Jsonb)


def test_normalized_legal_document_repository_save_returns_existing_for_duplicate() -> None:
    cursor = FakeCursor(fetchone_rows=[None, make_legal_document_row()])
    connection = FakeConnection(cursor)
    repo = PostgresNormalizedLegalDocumentRepository(
        make_connection_factory(cursor, connection)
    )

    saved = repo.save(make_legal_document())

    assert saved.id == make_legal_document().id
    assert connection.committed is True
    assert len(cursor.executed) == 2
    assert "INSERT INTO normalized_legal_document" in cursor.executed[0][0]
    assert "raw_source_item_id = %s" in cursor.executed[1][0]


def test_normalized_legal_document_repository_finds_by_document_hash() -> None:
    cursor = FakeCursor(fetchone_rows=[make_legal_document_row()])
    repo = PostgresNormalizedLegalDocumentRepository(make_connection_factory(cursor))

    document = repo.find_by_document_hash(
        source_id="ro_portal_legislativ",
        document_hash="legal-doc-hash-1",
    )

    assert document is not None
    assert document.document_hash == "legal-doc-hash-1"
    assert cursor.executed[0][1] == (
        "ro_portal_legislativ",
        "legal-doc-hash-1",
    )


def test_normalized_legal_document_repository_get_by_id() -> None:
    document = make_legal_document()
    cursor = FakeCursor(fetchone_rows=[make_legal_document_row()])
    repo = PostgresNormalizedLegalDocumentRepository(make_connection_factory(cursor))

    found = repo.get_by_id(document.id)

    assert found.id == document.id
    sql, params = cursor.executed[0]
    assert "FROM normalized_legal_document" in sql
    assert params == (document.id,)


def test_normalized_legal_document_repository_lists_pending_legal_raw_items() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_raw_item_row()]])
    repo = PostgresNormalizedLegalDocumentRepository(make_connection_factory(cursor))

    items = repo.list_pending_legal_raw_items(
        limit=10,
        source_id="ro_portal_legislativ",
    )

    assert len(items) == 1
    assert items[0].raw_item_id == make_raw_item().raw_item_id
    sql, params = cursor.executed[0]
    assert "pipeline_domain' = 'legal_documents'" in sql
    assert "LEFT JOIN normalized_legal_document" in sql
    assert "LEFT JOIN legal_document_normalization_result" in sql
    assert "external_event" not in sql
    assert params == ("ro_portal_legislativ", 10)


def test_normalized_legal_document_repository_lists_for_template_correlation() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_legal_document_row()]])
    repo = PostgresNormalizedLegalDocumentRepository(make_connection_factory(cursor))

    documents = repo.list_for_template_correlation(
        limit=10,
        source_id="ro_portal_legislativ",
    )

    assert len(documents) == 1
    assert documents[0].id == make_legal_document().id
    sql, params = cursor.executed[0]
    assert "FROM normalized_legal_document" in sql
    assert "source_id = %s" in sql
    assert params == ("ro_portal_legislativ", 10)


def test_normalized_legal_document_repository_saves_suppression_result() -> None:
    cursor = FakeCursor(
        fetchone_rows=[
            make_normalization_result_row("suppressed_non_legislative")
        ]
    )
    connection = FakeConnection(cursor)
    repo = PostgresNormalizedLegalDocumentRepository(
        make_connection_factory(cursor, connection)
    )

    result = repo.save_normalization_result(
        make_normalization_result("suppressed_non_legislative")
    )

    assert result.status == "suppressed_non_legislative"
    assert connection.committed is True
    sql, params = cursor.executed[0]
    assert "legal_document_normalization_result" in sql
    assert "ON CONFLICT (raw_source_item_id) DO UPDATE" in sql
    assert isinstance(params[7], Jsonb)
    assert isinstance(params[8], Jsonb)


def test_legal_document_template_review_candidate_repository_save_if_new() -> None:
    candidate = make_legal_template_review_candidate()
    cursor = FakeCursor(fetchone_rows=[{"candidate_id": candidate.candidate_id}])
    connection = FakeConnection(cursor)
    repo = PostgresLegalDocumentTemplateReviewCandidateRepository(
        make_connection_factory(cursor, connection)
    )

    inserted = repo.save_if_new(candidate)

    assert inserted is True
    assert connection.committed is True
    sql, params = cursor.executed[0]
    assert "INSERT INTO legal_document_template_review_candidate" in sql
    assert "ON CONFLICT" in sql
    assert "template_version_hash" in sql
    assert "DO NOTHING" in sql
    assert isinstance(params[12], Jsonb)


def test_legal_document_template_review_candidate_repository_returns_false_duplicate() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    repo = PostgresLegalDocumentTemplateReviewCandidateRepository(
        make_connection_factory(cursor, connection)
    )

    inserted = repo.save_if_new(make_legal_template_review_candidate())

    assert inserted is False
    assert connection.committed is True


def test_legal_document_template_review_candidate_repository_get_by_id() -> None:
    candidate = make_legal_template_review_candidate()
    cursor = FakeCursor(fetchone_rows=[candidate.model_dump(mode="python")])
    repo = PostgresLegalDocumentTemplateReviewCandidateRepository(
        make_connection_factory(cursor)
    )

    found = repo.get_by_id(candidate.candidate_id)

    assert found == candidate
    sql, params = cursor.executed[0]
    assert "FROM legal_document_template_review_candidate" in sql
    assert params == (candidate.candidate_id,)


def test_legal_document_template_review_candidate_repository_update_status() -> None:
    candidate = make_legal_template_review_candidate()
    updated_at = datetime(2026, 5, 11, 11, 0, tzinfo=UTC)
    updated_candidate = candidate.model_copy(
        update={"status": "accepted", "updated_at": updated_at}
    )
    cursor = FakeCursor(fetchone_rows=[updated_candidate.model_dump(mode="python")])
    connection = FakeConnection(cursor)
    repo = PostgresLegalDocumentTemplateReviewCandidateRepository(
        make_connection_factory(cursor, connection)
    )

    saved = repo.update_status(
        candidate_id=candidate.candidate_id,
        status="accepted",
        updated_at=updated_at,
    )

    assert saved.status == "accepted"
    assert saved.updated_at == updated_at
    assert connection.committed is True
    sql, params = cursor.executed[0]
    assert "UPDATE legal_document_template_review_candidate" in sql
    assert "RETURNING *" in sql
    assert params == ("accepted", updated_at, candidate.candidate_id)


def test_legal_document_template_review_candidate_repository_lists_review_items() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_legal_review_join_row()]])
    repo = PostgresLegalDocumentTemplateReviewCandidateRepository(
        make_connection_factory(cursor)
    )

    items = repo.list_review_items(status="needs_review", limit=20)

    assert len(items) == 1
    assert items[0].legal_document.id == make_legal_document().id
    assert items[0].affected_template_count == 1
    assert items[0].highest_confidence == 0.95
    assert items[0].candidates[0].candidate_id == (
        make_legal_template_review_candidate().candidate_id
    )
    sql, params = cursor.executed[0]
    assert "JOIN normalized_legal_document" in sql
    assert "candidate.status = %s" in sql
    assert params == ("needs_review", 20)


def test_template_change_suggestion_repository_saves_suggestion_and_hunks() -> None:
    suggestion = make_template_change_suggestion()
    cursor = FakeCursor(
        fetchone_rows=[
            make_template_change_suggestion_row(),
            make_template_change_suggestion_hunk_row(),
        ]
    )
    connection = FakeConnection(cursor)
    repo = PostgresTemplateChangeSuggestionRepository(
        make_connection_factory(cursor, connection)
    )

    saved = repo.save(suggestion)

    assert saved.id == suggestion.id
    assert saved.status == "draft"
    assert saved.hunks[0].change_type == "replace"
    assert saved.hunks[0].new_text == "5 zile calendaristice"
    assert connection.committed is True
    suggestion_sql, suggestion_params = cursor.executed[0]
    hunk_sql, hunk_params = cursor.executed[1]
    assert "INSERT INTO template_change_suggestion" in suggestion_sql
    assert "INSERT INTO template_change_suggestion_hunk" in hunk_sql
    assert isinstance(suggestion_params[7], Jsonb)
    assert hunk_params[11] == "replace"
    assert hunk_params[16] == 0.91


def test_template_change_suggestion_repository_get_by_id_returns_hunks() -> None:
    suggestion = make_template_change_suggestion()
    cursor = FakeCursor(
        fetchone_rows=[make_template_change_suggestion_row()],
        fetchall_rows=[[make_template_change_suggestion_hunk_row()]],
    )
    repo = PostgresTemplateChangeSuggestionRepository(make_connection_factory(cursor))

    found = repo.get_by_id(suggestion.id)

    assert found.id == suggestion.id
    assert found.hunks[0].old_text == "10 zile calendaristice"
    assert found.hunks[0].new_text == "5 zile calendaristice"
    assert cursor.executed[0][1] == (suggestion.id,)
    assert cursor.executed[1][1] == (suggestion.id,)


def test_template_change_suggestion_repository_get_active_by_candidate_id_returns_latest() -> None:
    suggestion = make_template_change_suggestion()
    cursor = FakeCursor(
        fetchone_rows=[make_template_change_suggestion_row()],
        fetchall_rows=[[make_template_change_suggestion_hunk_row()]],
    )
    repo = PostgresTemplateChangeSuggestionRepository(make_connection_factory(cursor))

    found = repo.get_active_by_candidate_id(suggestion.candidate_id)

    assert found is not None
    assert found.id == suggestion.id
    assert found.hunks[0].old_text == "10 zile calendaristice"
    sql, params = cursor.executed[0]
    assert "status <> 'superseded'" in sql
    assert "ORDER BY created_at DESC" in sql
    assert params == (suggestion.candidate_id,)


def test_template_change_suggestion_repository_update_hunk_review_state() -> None:
    suggestion = make_template_change_suggestion()
    edited_hunk = suggestion.hunks[0].model_copy(
        update={
            "new_text": "5 zile calendaristice de la producerea evenimentului",
            "status": "edited",
            "reviewer_notes": "Reviewer tightened the wording.",
        }
    )
    suggestion_row = make_template_change_suggestion_row()
    suggestion_row["validation_result"] = {"valid": True, "errors": []}
    cursor = FakeCursor(
        fetchone_rows=[
            make_edited_template_change_suggestion_hunk_row(),
            suggestion_row,
        ],
        fetchall_rows=[[make_edited_template_change_suggestion_hunk_row()]],
    )
    connection = FakeConnection(cursor)
    repo = PostgresTemplateChangeSuggestionRepository(
        make_connection_factory(cursor, connection)
    )

    saved = repo.update_hunk(
        suggestion_id=suggestion.id,
        hunk=edited_hunk,
        validation_result={"valid": True, "errors": []},
        updated_at=datetime(2026, 5, 11, 11, 0, tzinfo=UTC),
    )

    assert saved.hunks[0].status == "edited"
    assert saved.hunks[0].new_text.startswith("5 zile calendaristice")
    assert saved.validation_result["valid"] is True
    assert connection.committed is True
    hunk_sql, hunk_params = cursor.executed[0]
    suggestion_sql, suggestion_params = cursor.executed[1]
    assert "UPDATE template_change_suggestion_hunk" in hunk_sql
    assert "old_text" not in hunk_sql
    assert hunk_params[0].startswith("5 zile calendaristice")
    assert hunk_params[1] == "edited"
    assert hunk_params[3] == suggestion.id
    assert "UPDATE template_change_suggestion" in suggestion_sql
    assert isinstance(suggestion_params[0], Jsonb)


def test_template_change_suggestion_repository_update_status() -> None:
    suggestion_row = make_template_change_suggestion_row()
    suggestion_row["status"] = "applied_to_draft"
    suggestion_row["validation_result"] = {"valid": True, "errors": []}
    cursor = FakeCursor(
        fetchone_rows=[suggestion_row],
        fetchall_rows=[[make_template_change_suggestion_hunk_row()]],
    )
    connection = FakeConnection(cursor)
    repo = PostgresTemplateChangeSuggestionRepository(
        make_connection_factory(cursor, connection)
    )

    saved = repo.update_status(
        suggestion_id=make_template_change_suggestion().id,
        status="applied_to_draft",
        validation_result={"valid": True, "errors": []},
        updated_at=datetime(2026, 5, 11, 11, 0, tzinfo=UTC),
    )

    assert saved.status == "applied_to_draft"
    assert saved.validation_result["valid"] is True
    assert connection.committed is True
    sql, params = cursor.executed[0]
    assert "UPDATE template_change_suggestion" in sql
    assert params[0] == "applied_to_draft"
    assert isinstance(params[1], Jsonb)


def test_template_change_suggestion_repository_saves_draft_revision() -> None:
    revision = make_template_draft_revision()
    cursor = FakeCursor(fetchone_rows=[make_template_draft_revision_row()])
    connection = FakeConnection(cursor)
    repo = PostgresTemplateChangeSuggestionRepository(
        make_connection_factory(cursor, connection)
    )

    saved = repo.save_draft_revision(revision)

    assert saved.id == revision.id
    assert saved.status == "draft"
    assert saved.revised_content.endswith("5 zile calendaristice.")
    assert saved.applied_hunk_ids == revision.applied_hunk_ids
    assert connection.committed is True
    sql, params = cursor.executed[0]
    assert "INSERT INTO template_draft_revision" in sql
    assert isinstance(params[10], Jsonb)
    assert isinstance(params[11], Jsonb)
    assert isinstance(params[12], Jsonb)


def test_template_change_suggestion_repository_get_latest_draft_revision() -> None:
    revision = make_template_draft_revision()
    cursor = FakeCursor(fetchone_rows=[make_template_draft_revision_row()])
    repo = PostgresTemplateChangeSuggestionRepository(make_connection_factory(cursor))

    found = repo.get_latest_draft_revision_by_suggestion_id(revision.suggestion_id)

    assert found == revision
    sql, params = cursor.executed[0]
    assert "FROM template_draft_revision" in sql
    assert "ORDER BY created_at DESC" in sql
    assert params == (revision.suggestion_id,)


def test_template_change_suggestion_repository_gets_draft_revision_by_id() -> None:
    revision = make_template_draft_revision()
    cursor = FakeCursor(fetchone_rows=[make_template_draft_revision_row()])
    repo = PostgresTemplateChangeSuggestionRepository(make_connection_factory(cursor))

    found = repo.get_draft_revision_by_id(revision.id)

    assert found == revision
    sql, params = cursor.executed[0]
    assert "FROM template_draft_revision" in sql
    assert "WHERE id = %s" in sql
    assert params == (revision.id,)


def test_template_change_suggestion_repository_updates_draft_revision_submission() -> None:
    revision = make_template_draft_revision()
    submitted_row = make_template_draft_revision_row()
    submitted_row["status"] = "submitted_for_approval"
    submitted_row["validation_result"] = {
        "valid": True,
        "approval_submission": {"recipient_institution": "ASF Romania"},
    }
    submitted_row["source_metadata"] = {
        "approval_request": {"submission_status": "sent"},
    }
    cursor = FakeCursor(fetchone_rows=[submitted_row])
    connection = FakeConnection(cursor)
    repo = PostgresTemplateChangeSuggestionRepository(
        make_connection_factory(cursor, connection)
    )

    saved = repo.update_draft_revision_submission(
        revision_id=revision.id,
        status="submitted_for_approval",
        validation_result=submitted_row["validation_result"],
        source_metadata=submitted_row["source_metadata"],
        updated_at=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
    )

    assert saved.status == "submitted_for_approval"
    assert saved.source_metadata["approval_request"]["submission_status"] == "sent"
    assert connection.committed is True
    sql, params = cursor.executed[0]
    assert "UPDATE template_draft_revision" in sql
    assert params[0] == "submitted_for_approval"
    assert isinstance(params[1], Jsonb)
    assert isinstance(params[2], Jsonb)


def test_audit_record_repository_saves_record_and_wraps_jsonb() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    repo = PostgresAuditRecordRepository(make_connection_factory(cursor, connection))
    record = AuditRecord(
        entity_type="external_event",
        entity_id=make_external_event().event_id,
        action="classified",
        raw_url="https://asfromania.ro/item",
        raw_item_id=make_raw_item().raw_item_id,
        model_name="deterministic-keyword-classifier",
        model_version="mvp-1",
        input_ref_json={"body_text_ref": "raw_source_item:test:extracted_text"},
        output_json={"event_type": "regulatory_update"},
        created_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
    )

    saved = repo.save(record)

    assert saved == record
    assert connection.committed is True
    _, params = cursor.executed[0]
    assert params[2] == str(record.entity_id)
    assert isinstance(params[9], Jsonb)
    assert isinstance(params[10], Jsonb)


def test_contract_template_repository_lists_active_templates() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_template_row()]])
    repo = PostgresContractTemplateRepository(make_connection_factory(cursor))

    templates = repo.list_active()

    assert templates == [Template.model_validate(make_template_row())]
    assert "WHERE is_active = true" in cursor.executed[0][0]


def test_contract_template_repository_get_by_id_returns_template() -> None:
    cursor = FakeCursor(fetchone_rows=[make_template_row()])
    repo = PostgresContractTemplateRepository(make_connection_factory(cursor))

    template = repo.get_by_id(22)

    assert template.id == 22
    assert template.legal_references_json == ["ro:lege:260:2008"]
    assert cursor.executed[0][1] == (22,)


def test_template_review_candidate_repository_save_if_new_wraps_jsonb() -> None:
    candidate = make_template_review_candidate()
    cursor = FakeCursor(fetchone_rows=[{"candidate_id": candidate.candidate_id}])
    connection = FakeConnection(cursor)
    repo = PostgresTemplateReviewCandidateRepository(
        make_connection_factory(cursor, connection)
    )

    inserted = repo.save_if_new(candidate)

    assert inserted is True
    assert connection.committed is True
    sql, params = cursor.executed[0]
    assert "ON CONFLICT (event_id, template_id) DO NOTHING" in sql
    assert isinstance(params[8], Jsonb)
    assert isinstance(params[9], Jsonb)
    assert isinstance(params[12], Jsonb)


def test_template_review_candidate_repository_save_if_new_returns_false_for_duplicate() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    repo = PostgresTemplateReviewCandidateRepository(
        make_connection_factory(cursor, connection)
    )

    inserted = repo.save_if_new(make_template_review_candidate())

    assert inserted is False
    assert connection.committed is True


def test_template_review_candidate_repository_lists_candidates_by_status() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_template_review_candidate_row()]])
    repo = PostgresTemplateReviewCandidateRepository(make_connection_factory(cursor))

    candidates = repo.list_candidates(status="candidate", limit=7)

    assert len(candidates) == 1
    assert candidates[0].template_code == "PAD_STANDARD_RO"
    assert cursor.executed[0][1] == ("candidate", 7)


def test_template_review_candidate_repository_lists_all_candidates() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_template_review_candidate_row()]])
    repo = PostgresTemplateReviewCandidateRepository(make_connection_factory(cursor))

    candidates = repo.list_candidates(status=None, limit=7)

    assert len(candidates) == 1
    assert cursor.executed[0][1] == (7,)


def test_insight_card_repository_lists_classified_cards_with_filters() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_insight_row()]])
    repo = PostgresInsightCardRepository(make_connection_factory(cursor))

    cards = repo.list_cards(
        country="RO",
        source_id="asf_ro",
        line_of_business="property",
        topic="earthquake",
        event_type="regulatory_update",
        severity="medium",
        limit=7,
    )

    assert len(cards) == 1
    assert cards[0].title == "ASF comunicare"
    assert cards[0].paragraphs == [
        "ASF published an item potentially relevant to PAD.",
        "Review recommended for potentially affected Romanian property work.",
    ]
    assert cards[0].source_links[0].url == "https://asfromania.ro/item"
    assert cards[0].source_links[1].url == "https://asfromania.ro/document.pdf"
    assert cards[0].country == "RO"
    assert cards[0].line_of_business == "property"
    sql, params = cursor.executed[0]
    assert "external_event.status = 'classified'" in sql
    assert "external_event.line_of_business = %s" in sql
    assert "external_event.topics_json ? %s" in sql
    assert params == (
        "RO",
        "asf_ro",
        "property",
        "earthquake",
        "regulatory_update",
        "medium",
        27,
    )


def test_insight_card_repository_excludes_duplicate_and_non_pdf_source_links() -> None:
    cursor = FakeCursor(
        fetchall_rows=[
            [
                make_insight_row(
                    attachments_json=[
                        {
                            "url": "https://asfromania.ro/item",
                            "filename": "duplicate.pdf",
                            "content_type": "application/pdf",
                        },
                        {
                            "url": "https://asfromania.ro/page.html",
                            "filename": "page.html",
                            "content_type": "text/html",
                        },
                        {
                            "url": "https://asfromania.ro/extra.pdf",
                            "filename": "extra.pdf",
                        },
                    ]
                )
            ]
        ]
    )
    repo = PostgresInsightCardRepository(make_connection_factory(cursor))

    cards = repo.list_cards(limit=10)

    assert [link.url for link in cards[0].source_links] == [
        "https://asfromania.ro/item",
        "https://asfromania.ro/extra.pdf",
    ]


def test_insight_card_repository_limits_source_links_to_five() -> None:
    cursor = FakeCursor(
        fetchall_rows=[
            [
                make_insight_row(
                    attachments_json=[
                        {
                            "url": f"https://meteoromania.ro/warning-{index}.pdf",
                            "filename": f"warning-{index}.pdf",
                            "content_type": "application/pdf",
                        }
                        for index in range(1, 8)
                    ]
                )
            ]
        ]
    )
    repo = PostgresInsightCardRepository(make_connection_factory(cursor))

    cards = repo.list_cards(limit=10)

    assert [link.url for link in cards[0].source_links] == [
        "https://asfromania.ro/item",
        "https://meteoromania.ro/warning-1.pdf",
        "https://meteoromania.ro/warning-2.pdf",
        "https://meteoromania.ro/warning-3.pdf",
        "https://meteoromania.ro/warning-4.pdf",
    ]


def test_insight_card_repository_rewrites_generic_source_titles() -> None:
    row = make_insight_row()
    row["title"] = "INCDFP - Conducere"
    row["event_type"] = "public_warning"
    row["topics_json"] = ["earthquake"]
    cursor = FakeCursor(fetchall_rows=[[row]])
    repo = PostgresInsightCardRepository(make_connection_factory(cursor))

    cards = repo.list_cards(limit=10)

    assert cards[0].title == (
        "Earthquake warning issued for Romanian property exposure review"
    )


def test_insight_card_repository_uses_weather_headline_for_nowcasting_titles() -> None:
    row = make_insight_row()
    row["source_type"] = "weather"
    row["title"] = "Meteo Romania | Avertizari Nowcasting"
    row["event_type"] = "public_warning"
    row["topics_json"] = ["PAD / compulsory home insurance"]
    cursor = FakeCursor(fetchall_rows=[[row]])
    repo = PostgresInsightCardRepository(make_connection_factory(cursor))

    cards = repo.list_cards(limit=10)

    assert cards[0].title == (
        "Nowcasting weather warnings issued for Romanian property exposure review"
    )


def test_insight_card_repository_excludes_known_source_navigation_pages() -> None:
    row = make_insight_row()
    row["source_id"] = "infp_ro"
    row["original_url"] = "https://www.infp.ro/index.php?i=con"
    cursor = FakeCursor(fetchall_rows=[[row]])
    repo = PostgresInsightCardRepository(make_connection_factory(cursor))

    cards = repo.list_cards(limit=10)

    assert cards == []


def test_insight_card_repository_fills_limit_after_excluding_navigation_pages() -> None:
    excluded = make_insight_row()
    excluded["source_id"] = "infp_ro"
    excluded["original_url"] = "https://www.infp.ro/index.php?i=con"
    kept = make_insight_row()
    kept["title"] = "ANM severe storm and hail warning"
    cursor = FakeCursor(fetchall_rows=[[excluded, kept]])
    repo = PostgresInsightCardRepository(make_connection_factory(cursor))

    cards = repo.list_cards(limit=1)

    assert len(cards) == 1
    assert cards[0].title == "ANM severe storm and hail warning"


def test_insight_card_repository_uses_safe_paragraph_fallbacks() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_insight_row(summary="", action="")]])
    repo = PostgresInsightCardRepository(make_connection_factory(cursor))

    cards = repo.list_cards(limit=10)

    assert len(cards[0].paragraphs) == 2
    assert "potentially relevant" in cards[0].paragraphs[0]
    assert "Review recommended" in cards[0].paragraphs[1]


def test_ingestion_run_repository_start_inserts_run_and_commits() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    repo = PostgresIngestionRunRepository(make_connection_factory(cursor, connection))

    run = repo.start("asf_ro")

    assert run.source_id == "asf_ro"
    assert run.status == "started"
    assert connection.committed is True
    _, params = cursor.executed[0]
    assert params[1] == "asf_ro"
    assert isinstance(params[7], Jsonb)


def test_ingestion_run_repository_finish_updates_run_and_commits() -> None:
    run = IngestionRun(
        run_id=uuid4(),
        source_id="asf_ro",
        status="started",
        started_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
    )
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    repo = PostgresIngestionRunRepository(make_connection_factory(cursor, connection))

    finished = repo.finish(
        run=run,
        status="success",
        raw_items_seen=5,
        raw_items_created=2,
        errors=[],
    )

    assert finished.status == "success"
    assert finished.raw_items_seen == 5
    assert finished.raw_items_created == 2
    assert finished.finished_at is not None
    assert connection.committed is True
    _, params = cursor.executed[0]
    assert params[0] == "success"
    assert params[1] == 5
    assert params[2] == 2


def make_ingestion_run_row(run_id=None) -> dict:
    return {
        "run_id": run_id or uuid4(),
        "source_id": "asf_ro",
        "status": "success",
        "raw_items_seen": 5,
        "raw_items_created": 2,
        "events_created": 0,
        "alerts_created": 0,
        "errors": [],
        "started_at": datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
        "finished_at": datetime(2026, 5, 7, 9, 1, tzinfo=UTC),
    }


def test_ingestion_run_repository_lists_latest_runs() -> None:
    cursor = FakeCursor(fetchall_rows=[[make_ingestion_run_row()]])
    repo = PostgresIngestionRunRepository(make_connection_factory(cursor))

    runs = repo.list_latest(limit=12)

    assert len(runs) == 1
    assert runs[0].source_id == "asf_ro"
    assert runs[0].raw_items_created == 2
    assert cursor.executed[0][1] == (12,)


def test_ingestion_run_repository_get_by_id_returns_run() -> None:
    run_id = uuid4()
    cursor = FakeCursor(fetchone_rows=[make_ingestion_run_row(run_id)])
    repo = PostgresIngestionRunRepository(make_connection_factory(cursor))

    run = repo.get_by_id(run_id)

    assert run.run_id == run_id
    assert run.status == "success"
    assert cursor.executed[0][1] == (run_id,)


def test_ingestion_run_repository_get_by_id_raises_when_missing() -> None:
    repo = PostgresIngestionRunRepository(make_connection_factory(FakeCursor()))

    try:
        repo.get_by_id(uuid4())
    except ValueError as exc:
        assert "IngestionRun not found" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
