from datetime import UTC, datetime
import unicodedata
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.intelligence import (
    AuditRecord,
    ExternalEvent,
    InsightCard,
    IngestionRun,
    RawSourceItem,
    Source,
    SourceLink,
    TemplateReviewCandidate,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentNormalizationResult,
    LegalDocumentTemplateReviewItem,
    LegalDocumentTemplateReviewCandidate,
    NormalizedLegalDocument,
    TemplateChangeSuggestion,
    TemplateChangeSuggestionHunk,
    TemplateDraftRevision,
)
from underwright.domain.models import Template


MAX_SOURCE_LINKS_PER_INSIGHT_CARD = 5
GENERIC_INSIGHT_TITLE_FRAGMENTS = {
    "avertizari nowcasting",
    "conducere",
    "incdfp -",
    "informatii de interes public",
    "integritate",
    "meteo romania |",
    "organizare",
    "organigrama",
}
INSIGHT_TOPIC_LABELS = {
    "PAD / compulsory home insurance": "PAD home insurance",
    "commercial property insurance": "commercial property insurance",
    "coverage wording": "coverage wording",
    "deductibles / limits": "deductibles and limits",
    "earthquake": "earthquake",
    "fire": "fire",
    "flood": "flood",
    "insurer sanctions": "insurer sanctions",
    "pricing / premium affordability": "property insurance pricing",
    "residential property insurance": "residential property insurance",
    "solvency": "insurer solvency",
    "storm / hail": "storm and hail",
}
INSIGHT_TOPIC_PRIORITY = [
    "storm / hail",
    "earthquake",
    "flood",
    "fire",
    "PAD / compulsory home insurance",
    "coverage wording",
    "deductibles / limits",
    "pricing / premium affordability",
    "residential property insurance",
    "commercial property insurance",
]
EXCLUDED_FEED_URL_FRAGMENTS_BY_SOURCE = {
    "infp_ro": ["?i=con", "?i=des", "?i=doc", "?i=int", "?i=org"],
}


class PostgresSourceRepository:
    """loads enabled source config"""

    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def get_enabled(self, source_id: str) -> Source:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                        SELECT * 
                        FROM intelligence_source 
                        WHERE source_id = %s AND enabled = true
                        """,
                    (source_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError(f"Source not found: {source_id}")

        return Source.model_validate(row)

    def get_by_id(self, source_id: str) -> Source:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                        SELECT *
                        FROM intelligence_source
                        WHERE source_id = %s
                        """,
                    (source_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError(f"Source not found: {source_id}")

        return Source.model_validate(row)


class PostgresRawSourceItemRepository:
    """inserts new raw items and skips duplicates"""

    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def save_if_new(self, item: RawSourceItem) -> bool:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                INSERT INTO raw_source_item (
                    raw_item_id,
                    source_id,
                    original_url,
                    canonical_url,
                    published_at,
                    fetched_at,
                    title,
                    raw_html,
                    extracted_text,
                    attachments_json,
                    metadata_json,
                    content_hash,
                    fetch_status,
                    parse_status,
                    error_message,
                    created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s
                )
                ON CONFLICT DO NOTHING
                RETURNING raw_item_id
                """,
                    (
                        item.raw_item_id,
                        item.source_id,
                        item.original_url,
                        item.canonical_url,
                        item.published_at,
                        item.fetched_at,
                        item.title,
                        item.raw_html,
                        item.extracted_text,
                        Jsonb(
                            [a.model_dump(mode="json") for a in item.attachments_json]
                        ),
                        Jsonb(item.metadata_json),
                        item.content_hash,
                        item.fetch_status,
                        item.parse_status,
                        item.error_message,
                        item.created_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

            return row is not None

    def list_latest(self, limit: int = 50) -> list[RawSourceItem]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      SELECT *
                      FROM raw_source_item
                      ORDER BY fetched_at DESC
                      LIMIT %s
                      """,
                    (limit,),
                )
                rows = cur.fetchall()

        return [RawSourceItem.model_validate(row) for row in rows]

    def list_unprocessed(
        self,
        limit: int = 50,
        source_id: str | None = None,
    ) -> list[RawSourceItem]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if source_id is None:
                    cur.execute(
                        """
                          SELECT raw_source_item.*
                          FROM raw_source_item
                          LEFT JOIN external_event
                            ON external_event.raw_item_id = raw_source_item.raw_item_id
                          WHERE external_event.raw_item_id IS NULL
                          ORDER BY raw_source_item.fetched_at ASC
                          LIMIT %s
                          """,
                        (limit,),
                    )
                else:
                    cur.execute(
                        """
                          SELECT raw_source_item.*
                          FROM raw_source_item
                          LEFT JOIN external_event
                            ON external_event.raw_item_id = raw_source_item.raw_item_id
                          WHERE external_event.raw_item_id IS NULL
                            AND raw_source_item.source_id = %s
                          ORDER BY raw_source_item.fetched_at ASC
                          LIMIT %s
                          """,
                        (source_id, limit),
                    )
                rows = cur.fetchall()

        return [RawSourceItem.model_validate(row) for row in rows]

    def get_by_id(self, raw_item_id: UUID) -> RawSourceItem:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM raw_source_item WHERE raw_item_id = %s",
                    (raw_item_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError(f"RawSourceItem not found: {raw_item_id}")

        return RawSourceItem.model_validate(row)


class PostgresNormalizedLegalDocumentRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def save(self, document: NormalizedLegalDocument) -> NormalizedLegalDocument:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      INSERT INTO normalized_legal_document (
                          id,
                          raw_source_item_id,
                          source_id,
                          source_key,
                          jurisdiction,
                          parser_id,
                          canonical_url,
                          source_url,
                          external_identifier,
                          title,
                          language,
                          issuer,
                          instrument_type,
                          instrument_number,
                          instrument_year,
                          instrument_date,
                          publication_reference,
                          publication_date,
                          effective_date,
                          status,
                          legal_references,
                          structured_clauses,
                          amends,
                          repeals,
                          full_text,
                          summary,
                          document_hash,
                          extraction_confidence,
                          parser_warnings,
                          source_metadata,
                          created_at,
                          updated_at
                      )
                      VALUES (
                          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          %s, %s
                      )
                      ON CONFLICT DO NOTHING
                      RETURNING *
                      """,
                    (
                        document.id,
                        document.raw_source_item_id,
                        document.source_id,
                        document.source_key,
                        document.jurisdiction,
                        document.parser_id,
                        document.canonical_url,
                        document.source_url,
                        document.external_identifier,
                        document.title,
                        document.language,
                        document.issuer,
                        document.instrument_type,
                        document.instrument_number,
                        document.instrument_year,
                        document.instrument_date,
                        document.publication_reference,
                        document.publication_date,
                        document.effective_date,
                        document.status,
                        Jsonb(document.legal_references),
                        Jsonb(document.structured_clauses),
                        Jsonb(document.amends),
                        Jsonb(document.repeals),
                        document.full_text,
                        document.summary,
                        document.document_hash,
                        document.extraction_confidence,
                        Jsonb(document.parser_warnings),
                        Jsonb(document.source_metadata),
                        document.created_at,
                        document.updated_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is not None:
            return NormalizedLegalDocument.model_validate(row)

        existing = self._find_existing_document(document)
        if existing is None:
            raise ValueError(
                "Normalized legal document insert skipped but no existing document was found."
            )
        return existing

    def find_by_raw_source_item_id(
        self,
        raw_source_item_id: UUID,
    ) -> NormalizedLegalDocument | None:
        return self._find_one(
            "normalized_legal_document.raw_source_item_id = %s",
            (raw_source_item_id,),
        )

    def find_by_document_hash(
        self,
        source_id: str,
        document_hash: str,
    ) -> NormalizedLegalDocument | None:
        return self._find_one(
            "normalized_legal_document.source_id = %s AND normalized_legal_document.document_hash = %s",
            (source_id, document_hash),
        )

    def list_pending_legal_raw_items(
        self,
        limit: int = 50,
        source_id: str | None = None,
    ) -> list[RawSourceItem]:
        where = [
            "intelligence_source.config_json->>'pipeline_domain' = 'legal_documents'",
            "normalized_legal_document.raw_source_item_id IS NULL",
            "legal_document_normalization_result.raw_source_item_id IS NULL",
        ]
        params: list[object] = []
        if source_id is not None:
            where.append("raw_source_item.source_id = %s")
            params.append(source_id)
        params.append(limit)

        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                      SELECT raw_source_item.*
                      FROM raw_source_item
                      JOIN intelligence_source
                        ON intelligence_source.source_id = raw_source_item.source_id
                      LEFT JOIN normalized_legal_document
                        ON normalized_legal_document.raw_source_item_id = raw_source_item.raw_item_id
                      LEFT JOIN legal_document_normalization_result
                        ON legal_document_normalization_result.raw_source_item_id = raw_source_item.raw_item_id
                      WHERE {' AND '.join(where)}
                      ORDER BY raw_source_item.fetched_at ASC
                      LIMIT %s
                      """,
                    tuple(params),
                )
                rows = cur.fetchall()

        return [RawSourceItem.model_validate(row) for row in rows]

    def list_for_template_correlation(
        self,
        limit: int = 50,
        source_id: str | None = None,
    ) -> list[NormalizedLegalDocument]:
        params: list[object] = []
        where = ["TRUE"]
        if source_id is not None:
            where.append("source_id = %s")
            params.append(source_id)
        params.append(limit)

        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                      SELECT *
                      FROM normalized_legal_document
                      WHERE {' AND '.join(where)}
                      ORDER BY created_at DESC
                      LIMIT %s
                      """,
                    tuple(params),
                )
                rows = cur.fetchall()

        return [NormalizedLegalDocument.model_validate(row) for row in rows]

    def save_normalization_result(
        self,
        result: LegalDocumentNormalizationResult,
    ) -> LegalDocumentNormalizationResult:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      INSERT INTO legal_document_normalization_result (
                          id,
                          raw_source_item_id,
                          source_id,
                          parser_id,
                          normalized_legal_document_id,
                          status,
                          reason,
                          parser_warnings,
                          source_metadata,
                          created_at,
                          updated_at
                      )
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                      ON CONFLICT (raw_source_item_id) DO UPDATE SET
                          source_id = EXCLUDED.source_id,
                          parser_id = EXCLUDED.parser_id,
                          normalized_legal_document_id = EXCLUDED.normalized_legal_document_id,
                          status = EXCLUDED.status,
                          reason = EXCLUDED.reason,
                          parser_warnings = EXCLUDED.parser_warnings,
                          source_metadata = EXCLUDED.source_metadata,
                          updated_at = EXCLUDED.updated_at
                      RETURNING *
                      """,
                    (
                        result.id,
                        result.raw_source_item_id,
                        result.source_id,
                        result.parser_id,
                        result.normalized_legal_document_id,
                        result.status,
                        result.reason,
                        Jsonb(result.parser_warnings),
                        Jsonb(result.source_metadata),
                        result.created_at,
                        result.updated_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("Legal document normalization result was not saved.")
        return LegalDocumentNormalizationResult.model_validate(row)

    def _find_existing_document(
        self,
        document: NormalizedLegalDocument,
    ) -> NormalizedLegalDocument | None:
        existing = self.find_by_raw_source_item_id(document.raw_source_item_id)
        if existing is not None:
            return existing

        if document.external_identifier:
            existing = self._find_one(
                "normalized_legal_document.source_id = %s AND normalized_legal_document.external_identifier = %s",
                (document.source_id, document.external_identifier),
            )
            if existing is not None:
                return existing

        existing = self._find_one(
            "normalized_legal_document.source_id = %s AND normalized_legal_document.canonical_url = %s",
            (document.source_id, document.canonical_url),
        )
        if existing is not None:
            return existing

        return self.find_by_document_hash(document.source_id, document.document_hash)

    def _find_one(
        self,
        where_clause: str,
        params: tuple[object, ...],
    ) -> NormalizedLegalDocument | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                      SELECT *
                      FROM normalized_legal_document
                      WHERE {where_clause}
                      """,
                    params,
                )
                row = cur.fetchone()

        if row is None:
            return None
        return NormalizedLegalDocument.model_validate(row)

    def get_by_id(self, document_id: UUID) -> NormalizedLegalDocument:
        document = self._find_one("normalized_legal_document.id = %s", (document_id,))
        if document is None:
            raise ValueError(f"NormalizedLegalDocument not found: {document_id}")
        return document


class PostgresLegalDocumentTemplateReviewCandidateRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def save_if_new(
        self,
        candidate: LegalDocumentTemplateReviewCandidate,
    ) -> bool:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      INSERT INTO legal_document_template_review_candidate (
                          candidate_id,
                          normalized_legal_document_id,
                          template_id,
                          template_code,
                          template_name,
                          template_version,
                          template_version_hash,
                          match_type,
                          matched_reference,
                          review_reason,
                          confidence,
                          status,
                          source_metadata,
                          created_at,
                          updated_at
                      )
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                      ON CONFLICT (
                          normalized_legal_document_id,
                          template_id,
                          template_version_hash,
                          match_type,
                          matched_reference
                      ) DO NOTHING
                      RETURNING candidate_id
                      """,
                    (
                        candidate.candidate_id,
                        candidate.normalized_legal_document_id,
                        candidate.template_id,
                        candidate.template_code,
                        candidate.template_name,
                        candidate.template_version,
                        candidate.template_version_hash,
                        candidate.match_type,
                        candidate.matched_reference,
                        candidate.review_reason,
                        candidate.confidence,
                        candidate.status,
                        Jsonb(candidate.source_metadata),
                        candidate.created_at,
                        candidate.updated_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        return row is not None

    def get_by_id(
        self,
        candidate_id: UUID,
    ) -> LegalDocumentTemplateReviewCandidate:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      SELECT *
                      FROM legal_document_template_review_candidate
                      WHERE candidate_id = %s
                      """,
                    (candidate_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError(
                f"LegalDocumentTemplateReviewCandidate not found: {candidate_id}"
            )
        return LegalDocumentTemplateReviewCandidate.model_validate(row)

    def update_status(
        self,
        *,
        candidate_id: UUID,
        status: str,
        updated_at: datetime | None = None,
    ) -> LegalDocumentTemplateReviewCandidate:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      UPDATE legal_document_template_review_candidate
                      SET
                          status = %s,
                          updated_at = %s
                      WHERE candidate_id = %s
                      RETURNING *
                      """,
                    (
                        status,
                        updated_at or datetime.now(UTC),
                        candidate_id,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError(
                f"LegalDocumentTemplateReviewCandidate not found: {candidate_id}"
            )
        return LegalDocumentTemplateReviewCandidate.model_validate(row)

    def list_review_items(
        self,
        *,
        status: str | None = "needs_review",
        limit: int = 50,
    ) -> list[LegalDocumentTemplateReviewItem]:
        params: list[object] = []
        where = ["TRUE"]
        if status is not None:
            where.append("candidate.status = %s")
            params.append(status)
        params.append(limit)

        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                      SELECT
                          candidate.*,
                          document.id AS document_id,
                          document.raw_source_item_id AS document_raw_source_item_id,
                          document.source_id AS document_source_id,
                          document.source_key AS document_source_key,
                          document.jurisdiction AS document_jurisdiction,
                          document.parser_id AS document_parser_id,
                          document.canonical_url AS document_canonical_url,
                          document.source_url AS document_source_url,
                          document.external_identifier AS document_external_identifier,
                          document.title AS document_title,
                          document.language AS document_language,
                          document.issuer AS document_issuer,
                          document.instrument_type AS document_instrument_type,
                          document.instrument_number AS document_instrument_number,
                          document.instrument_year AS document_instrument_year,
                          document.publication_reference AS document_publication_reference,
                          document.publication_date AS document_publication_date,
                          document.effective_date AS document_effective_date,
                          document.status AS document_status,
                          document.legal_references AS document_legal_references,
                          document.amends AS document_amends,
                          document.repeals AS document_repeals,
                          document.full_text AS document_full_text,
                          document.summary AS document_summary,
                          document.document_hash AS document_document_hash,
                          document.extraction_confidence AS document_extraction_confidence,
                          document.parser_warnings AS document_parser_warnings,
                          document.source_metadata AS document_source_metadata,
                          document.created_at AS document_created_at,
                          document.updated_at AS document_updated_at
                      FROM legal_document_template_review_candidate AS candidate
                      JOIN normalized_legal_document AS document
                        ON document.id = candidate.normalized_legal_document_id
                      WHERE {' AND '.join(where)}
                      ORDER BY document.effective_date DESC NULLS LAST,
                               candidate.confidence DESC
                      LIMIT %s
                      """,
                    tuple(params),
                )
                rows = cur.fetchall()

        items_by_document: dict[UUID, LegalDocumentTemplateReviewItem] = {}
        for row in rows:
            document = self._legal_document_from_joined_row(row)
            candidate = LegalDocumentTemplateReviewCandidate.model_validate(
                {
                    key: value
                    for key, value in row.items()
                    if not key.startswith("document_")
                }
            )
            item = items_by_document.get(document.id)
            if item is None:
                item = LegalDocumentTemplateReviewItem(
                    legal_document=document,
                    candidates=[],
                    affected_template_count=0,
                    highest_confidence=0,
                )
                items_by_document[document.id] = item
            item.candidates.append(candidate)
            item.affected_template_count = len(
                {candidate.template_id for candidate in item.candidates}
            )
            item.highest_confidence = max(
                item.highest_confidence,
                candidate.confidence,
            )

        return list(items_by_document.values())

    def _legal_document_from_joined_row(self, row: dict) -> NormalizedLegalDocument:
        return NormalizedLegalDocument.model_validate(
            {
                "id": row["document_id"],
                "raw_source_item_id": row["document_raw_source_item_id"],
                "source_id": row["document_source_id"],
                "source_key": row["document_source_key"],
                "jurisdiction": row["document_jurisdiction"],
                "parser_id": row["document_parser_id"],
                "canonical_url": row["document_canonical_url"],
                "source_url": row["document_source_url"],
                "external_identifier": row["document_external_identifier"],
                "title": row["document_title"],
                "language": row["document_language"],
                "issuer": row["document_issuer"],
                "instrument_type": row["document_instrument_type"],
                "instrument_number": row["document_instrument_number"],
                "instrument_year": row["document_instrument_year"],
                "publication_reference": row["document_publication_reference"],
                "publication_date": row["document_publication_date"],
                "effective_date": row["document_effective_date"],
                "status": row["document_status"],
                "legal_references": row["document_legal_references"],
                "amends": row["document_amends"],
                "repeals": row["document_repeals"],
                "full_text": row["document_full_text"],
                "summary": row["document_summary"],
                "document_hash": row["document_document_hash"],
                "extraction_confidence": row["document_extraction_confidence"],
                "parser_warnings": row["document_parser_warnings"],
                "source_metadata": row["document_source_metadata"],
                "created_at": row["document_created_at"],
                "updated_at": row["document_updated_at"],
            }
        )


class PostgresTemplateChangeSuggestionRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def get_by_id(self, suggestion_id: UUID) -> TemplateChangeSuggestion:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      SELECT *
                      FROM template_change_suggestion
                      WHERE id = %s
                      """,
                    (suggestion_id,),
                )
                suggestion_row = cur.fetchone()
                cur.execute(
                    """
                      SELECT *
                      FROM template_change_suggestion_hunk
                      WHERE suggestion_id = %s
                      ORDER BY id ASC
                      """,
                    (suggestion_id,),
                )
                hunk_rows = cur.fetchall()

        if suggestion_row is None:
            raise ValueError(f"TemplateChangeSuggestion not found: {suggestion_id}")
        saved = TemplateChangeSuggestion.model_validate(suggestion_row)
        return saved.model_copy(
            update={
                "hunks": [
                    TemplateChangeSuggestionHunk.model_validate(row)
                    for row in hunk_rows
                ]
            }
        )

    def get_active_by_candidate_id(
        self,
        candidate_id: UUID,
    ) -> TemplateChangeSuggestion | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      SELECT *
                      FROM template_change_suggestion
                      WHERE candidate_id = %s
                        AND status <> 'superseded'
                      ORDER BY created_at DESC
                      LIMIT 1
                      """,
                    (candidate_id,),
                )
                suggestion_row = cur.fetchone()
                if suggestion_row is None:
                    return None
                cur.execute(
                    """
                      SELECT *
                      FROM template_change_suggestion_hunk
                      WHERE suggestion_id = %s
                      ORDER BY id ASC
                      """,
                    (suggestion_row["id"],),
                )
                hunk_rows = cur.fetchall()

        saved = TemplateChangeSuggestion.model_validate(suggestion_row)
        return saved.model_copy(
            update={
                "hunks": [
                    TemplateChangeSuggestionHunk.model_validate(row)
                    for row in hunk_rows
                ]
            }
        )

    def save(self, suggestion: TemplateChangeSuggestion) -> TemplateChangeSuggestion:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      INSERT INTO template_change_suggestion (
                          id,
                          candidate_id,
                          template_id,
                          normalized_legal_document_id,
                          template_version_hash,
                          status,
                          overall_summary,
                          validation_result,
                          created_at,
                          updated_at
                      )
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                      RETURNING *
                      """,
                    (
                        suggestion.id,
                        suggestion.candidate_id,
                        suggestion.template_id,
                        suggestion.normalized_legal_document_id,
                        suggestion.template_version_hash,
                        suggestion.status,
                        suggestion.overall_summary,
                        Jsonb(suggestion.validation_result),
                        suggestion.created_at,
                        suggestion.updated_at,
                    ),
                )
                suggestion_row = cur.fetchone()
                hunk_rows = []
                for hunk in suggestion.hunks:
                    cur.execute(
                        """
                          INSERT INTO template_change_suggestion_hunk (
                              id,
                              suggestion_id,
                              section_id,
                              section_label,
                              template_section_title,
                              template_article_title,
                              before_context,
                              after_context,
                              full_context_excerpt,
                              start_offset,
                              end_offset,
                              change_type,
                              old_text,
                              new_text,
                              rationale,
                              source_reference,
                              confidence,
                              status,
                              reviewer_notes
                          )
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                          RETURNING *
                          """,
                        (
                            hunk.id,
                            suggestion.id,
                            hunk.section_id,
                            hunk.section_label,
                            hunk.template_section_title,
                            hunk.template_article_title,
                            hunk.before_context,
                            hunk.after_context,
                            hunk.full_context_excerpt,
                            hunk.start_offset,
                            hunk.end_offset,
                            hunk.change_type,
                            hunk.old_text,
                            hunk.new_text,
                            hunk.rationale,
                            hunk.source_reference,
                            hunk.confidence,
                            hunk.status,
                            hunk.reviewer_notes,
                        ),
                    )
                    hunk_rows.append(cur.fetchone())
                conn.commit()

        if suggestion_row is None:
            raise ValueError("Template change suggestion was not saved.")
        saved = TemplateChangeSuggestion.model_validate(suggestion_row)
        return saved.model_copy(
            update={
                "hunks": [
                    TemplateChangeSuggestionHunk.model_validate(row)
                    for row in hunk_rows
                    if row is not None
                ]
            }
        )

    def update_hunk(
        self,
        *,
        suggestion_id: UUID,
        hunk: TemplateChangeSuggestionHunk,
        validation_result: dict,
        updated_at: datetime,
    ) -> TemplateChangeSuggestion:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      UPDATE template_change_suggestion_hunk
                      SET
                          new_text = %s,
                          status = %s,
                          reviewer_notes = %s
                      WHERE suggestion_id = %s
                        AND id = %s
                      RETURNING *
                      """,
                    (
                        hunk.new_text,
                        hunk.status,
                        hunk.reviewer_notes,
                        suggestion_id,
                        hunk.id,
                    ),
                )
                hunk_row = cur.fetchone()
                if hunk_row is None:
                    raise ValueError(
                        f"TemplateChangeSuggestionHunk not found: {hunk.id}"
                    )
                cur.execute(
                    """
                      UPDATE template_change_suggestion
                      SET
                          validation_result = %s,
                          updated_at = %s
                      WHERE id = %s
                      RETURNING *
                      """,
                    (
                        Jsonb(validation_result),
                        updated_at,
                        suggestion_id,
                    ),
                )
                suggestion_row = cur.fetchone()
                cur.execute(
                    """
                      SELECT *
                      FROM template_change_suggestion_hunk
                      WHERE suggestion_id = %s
                      ORDER BY id ASC
                      """,
                    (suggestion_id,),
                )
                hunk_rows = cur.fetchall()
                conn.commit()

        if suggestion_row is None:
            raise ValueError(f"TemplateChangeSuggestion not found: {suggestion_id}")
        saved = TemplateChangeSuggestion.model_validate(suggestion_row)
        return saved.model_copy(
            update={
                "hunks": [
                    TemplateChangeSuggestionHunk.model_validate(row)
                    for row in hunk_rows
                ]
            }
        )

    def update_status(
        self,
        *,
        suggestion_id: UUID,
        status: str,
        validation_result: dict,
        updated_at: datetime,
    ) -> TemplateChangeSuggestion:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      UPDATE template_change_suggestion
                      SET
                          status = %s,
                          validation_result = %s,
                          updated_at = %s
                      WHERE id = %s
                      RETURNING *
                      """,
                    (
                        status,
                        Jsonb(validation_result),
                        updated_at,
                        suggestion_id,
                    ),
                )
                suggestion_row = cur.fetchone()
                cur.execute(
                    """
                      SELECT *
                      FROM template_change_suggestion_hunk
                      WHERE suggestion_id = %s
                      ORDER BY id ASC
                      """,
                    (suggestion_id,),
                )
                hunk_rows = cur.fetchall()
                conn.commit()

        if suggestion_row is None:
            raise ValueError(f"TemplateChangeSuggestion not found: {suggestion_id}")
        saved = TemplateChangeSuggestion.model_validate(suggestion_row)
        return saved.model_copy(
            update={
                "hunks": [
                    TemplateChangeSuggestionHunk.model_validate(row)
                    for row in hunk_rows
                ]
            }
        )

    def save_draft_revision(
        self,
        revision: TemplateDraftRevision,
    ) -> TemplateDraftRevision:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      INSERT INTO template_draft_revision (
                          id,
                          suggestion_id,
                          template_id,
                          template_code,
                          template_name,
                          base_template_version,
                          base_template_version_hash,
                          status,
                          base_content,
                          revised_content,
                          applied_hunk_ids,
                          validation_result,
                          source_metadata,
                          created_at,
                          updated_at
                      )
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                      RETURNING *
                      """,
                    (
                        revision.id,
                        revision.suggestion_id,
                        revision.template_id,
                        revision.template_code,
                        revision.template_name,
                        revision.base_template_version,
                        revision.base_template_version_hash,
                        revision.status,
                        revision.base_content,
                        revision.revised_content,
                        Jsonb([str(hunk_id) for hunk_id in revision.applied_hunk_ids]),
                        Jsonb(revision.validation_result),
                        Jsonb(revision.source_metadata),
                        revision.created_at,
                        revision.updated_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("Template draft revision was not saved.")
        return TemplateDraftRevision.model_validate(row)

    def get_latest_draft_revision_by_suggestion_id(
        self,
        suggestion_id: UUID,
    ) -> TemplateDraftRevision | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      SELECT *
                      FROM template_draft_revision
                      WHERE suggestion_id = %s
                      ORDER BY created_at DESC
                      LIMIT 1
                      """,
                    (suggestion_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return TemplateDraftRevision.model_validate(row)

    def get_draft_revision_by_id(
        self,
        draft_revision_id: UUID,
    ) -> TemplateDraftRevision | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      SELECT *
                      FROM template_draft_revision
                      WHERE id = %s
                      """,
                    (draft_revision_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return TemplateDraftRevision.model_validate(row)

    def update_draft_revision_submission(
        self,
        *,
        revision_id: UUID,
        status: str,
        validation_result: dict,
        source_metadata: dict,
        updated_at: datetime,
    ) -> TemplateDraftRevision:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      UPDATE template_draft_revision
                      SET
                          status = %s,
                          validation_result = %s,
                          source_metadata = %s,
                          updated_at = %s
                      WHERE id = %s
                      RETURNING *
                      """,
                    (
                        status,
                        Jsonb(validation_result),
                        Jsonb(source_metadata),
                        updated_at,
                        revision_id,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError(f"Template draft revision not found: {revision_id}")
        return TemplateDraftRevision.model_validate(row)


class PostgresExternalEventRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def save_if_new(self, event: ExternalEvent) -> bool:
        classification_json = (
            event.classification_json.model_dump(mode="json")
            if event.classification_json is not None
            else None
        )
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      INSERT INTO external_event (
                          event_id,
                          raw_item_id,
                          source_id,
                          source_type,
                          trust_tier,
                          original_url,
                          published_at,
                          ingested_at,
                          title,
                          body_text_ref,
                          body_text,
                          original_language,
                          country,
                          jurisdiction,
                          event_type,
                          line_of_business,
                          product,
                          topics_json,
                          perils_json,
                          severity,
                          confidence,
                          underwriter_summary,
                          recommended_action,
                          evidence_json,
                          classification_json,
                          status
                      )
                      VALUES (
                          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                      )
                      ON CONFLICT (raw_item_id) DO NOTHING
                      RETURNING event_id
                      """,
                    (
                        event.event_id,
                        event.raw_item_id,
                        event.source_id,
                        event.source_type,
                        event.trust_tier,
                        event.original_url,
                        event.published_at,
                        event.ingested_at,
                        event.title,
                        event.body_text_ref,
                        event.body_text,
                        event.original_language,
                        event.country,
                        event.jurisdiction,
                        event.event_type,
                        event.line_of_business,
                        event.product,
                        Jsonb(event.topics_json),
                        Jsonb(event.perils_json),
                        event.severity,
                        event.confidence,
                        event.underwriter_summary,
                        event.recommended_action,
                        Jsonb(
                            [
                                evidence.model_dump(mode="json")
                                for evidence in event.evidence_json
                            ]
                        ),
                        Jsonb(classification_json) if classification_json is not None else None,
                        event.status,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        return row is not None

    def list_for_template_review(
        self,
        limit: int = 50,
        source_id: str | None = None,
    ) -> list[ExternalEvent]:
        where = [
            "external_event.status = 'classified'",
            """
            NOT EXISTS (
                SELECT 1
                FROM intelligence_template_review_candidate
                WHERE intelligence_template_review_candidate.event_id = external_event.event_id
            )
            """,
        ]
        params: list[object] = []
        if source_id is not None:
            where.append("external_event.source_id = %s")
            params.append(source_id)
        params.append(limit)

        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                      SELECT *
                      FROM external_event
                      WHERE {' AND '.join(where)}
                      ORDER BY COALESCE(published_at, ingested_at) DESC
                      LIMIT %s
                      """,
                    tuple(params),
                )
                rows = cur.fetchall()

        return [ExternalEvent.model_validate(row) for row in rows]


class PostgresAuditRecordRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def save(self, record: AuditRecord) -> AuditRecord:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      INSERT INTO intelligence_audit_record (
                          audit_id,
                          entity_type,
                          entity_id,
                          action,
                          raw_url,
                          raw_item_id,
                          model_name,
                          model_version,
                          prompt_version,
                          input_ref_json,
                          output_json,
                          rules_triggered_json,
                          user_id,
                          created_at
                      )
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                      """,
                    (
                        record.audit_id,
                        record.entity_type,
                        str(record.entity_id),
                        record.action,
                        record.raw_url,
                        record.raw_item_id,
                        record.model_name,
                        record.model_version,
                        record.prompt_version,
                        Jsonb(record.input_ref_json),
                        Jsonb(record.output_json),
                        Jsonb(record.rules_triggered_json),
                        record.user_id,
                        record.created_at,
                    ),
                )
                conn.commit()

        return record


class PostgresInsightCardRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def list_cards(
        self,
        country: str | None = None,
        source_id: str | None = None,
        line_of_business: str | None = None,
        topic: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        status: str | None = "classified",
        limit: int = 50,
    ) -> list[InsightCard]:
        where: list[str] = []
        params: list[object] = []
        if status == "classified":
            where.append("external_event.status = 'classified'")
        elif status is not None and status != "all":
            where.append("external_event.status = %s")
            params.append(status)
        if country is not None:
            where.append("external_event.country = %s")
            params.append(country)
        if source_id is not None:
            where.append("external_event.source_id = %s")
            params.append(source_id)
        if line_of_business is not None:
            where.append("external_event.line_of_business = %s")
            params.append(line_of_business)
        if topic is not None:
            where.append("external_event.topics_json ? %s")
            params.append(topic)
        if event_type is not None:
            where.append("external_event.event_type = %s")
            params.append(event_type)
        if severity is not None:
            where.append("external_event.severity = %s")
            params.append(severity)
        query_limit = max(limit * 3, limit + 20)
        params.append(query_limit)

        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                      SELECT
                          external_event.*,
                          intelligence_source.name AS source_name,
                          raw_source_item.attachments_json AS raw_attachments_json
                      FROM external_event
                      JOIN raw_source_item
                        ON raw_source_item.raw_item_id = external_event.raw_item_id
                      JOIN intelligence_source
                        ON intelligence_source.source_id = external_event.source_id
                      {"WHERE " + " AND ".join(where) if where else ""}
                      ORDER BY COALESCE(
                          external_event.published_at,
                          external_event.ingested_at
                      ) DESC
                      LIMIT %s
                      """,
                    tuple(params),
                )
                rows = cur.fetchall()

        cards = [
            self._card_from_row(row)
            for row in rows
            if not self._is_excluded_feed_row(row)
        ]
        return cards[:limit]

    def _is_excluded_feed_row(self, row: dict) -> bool:
        url_fragments = EXCLUDED_FEED_URL_FRAGMENTS_BY_SOURCE.get(row["source_id"], [])
        original_url = row["original_url"].lower()
        return any(fragment in original_url for fragment in url_fragments)

    def _card_from_row(self, row: dict) -> InsightCard:
        return InsightCard(
            event_id=row["event_id"],
            title=self._card_title(row),
            paragraphs=self._paragraphs(row),
            source_links=self._source_links(row),
            published_at=row["published_at"],
            source_id=row["source_id"],
            source_name=row["source_name"],
            country=row["country"],
            line_of_business=row["line_of_business"],
            event_type=row["event_type"],
            topics=row["topics_json"],
            severity=row["severity"],
            confidence=float(row["confidence"]),
            status=row["status"],
        )

    def _card_title(self, row: dict) -> str:
        title = row["title"]
        if not self._looks_like_source_label(title):
            return title
        return self._fallback_title(row)

    def _looks_like_source_label(self, title: str) -> bool:
        normalized = self._ascii_lower(title)
        return any(
            fragment in normalized for fragment in GENERIC_INSIGHT_TITLE_FRAGMENTS
        )

    def _fallback_title(self, row: dict) -> str:
        topics = row["topics_json"] or []
        if row["source_type"] == "weather" and not self._has_weather_topic(topics):
            return "Nowcasting weather warnings issued for Romanian property exposure review"
        topic = self._headline_topic(topics)
        subject = self._headline_subject(topic)
        event_type = row["event_type"]
        if event_type == "public_warning":
            return f"{subject} warning issued for Romanian property exposure review"
        if event_type == "consultation_or_draft_rule":
            return f"{subject} consultation may affect Romanian property wording"
        if event_type == "regulatory_update":
            return f"{subject} update may affect Romanian property underwriting"
        if event_type == "market_report":
            return f"{subject} market report signals Romanian property underwriting context"
        if event_type == "claims_update":
            return f"{subject} claims update may affect Romanian property review"
        if event_type == "sanction_or_enforcement":
            return f"{subject} enforcement action may affect Romanian property review"
        return f"{subject} event may affect Romanian property underwriting"

    def _headline_subject(self, topic: str) -> str:
        return f"{topic[:1].upper()}{topic[1:]}"

    def _headline_topic(self, topics: list[str]) -> str:
        for topic in INSIGHT_TOPIC_PRIORITY:
            if topic in topics:
                return INSIGHT_TOPIC_LABELS[topic]
        if topics:
            return INSIGHT_TOPIC_LABELS.get(topics[0], topics[0])
        return "insurance"

    def _has_weather_topic(self, topics: list[str]) -> bool:
        return bool({"storm / hail", "flood", "fire"} & set(topics))

    def _ascii_lower(self, value: str) -> str:
        return (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
        )

    def _paragraphs(self, row: dict) -> list[str]:
        summary = (
            row["underwriter_summary"].strip()
            or "Source item was classified as potentially relevant to Romanian property insurance."
        )
        action = (
            row["recommended_action"].strip()
            or "Review recommended for potentially affected underwriting or document work."
        )
        return [summary, action]

    def _source_links(self, row: dict) -> list[SourceLink]:
        links = [
            SourceLink(
                label=f"{row['source_name']} source",
                url=row["original_url"],
                content_type="text/html",
            )
        ]
        seen_urls = {row["original_url"]}
        for attachment in row["raw_attachments_json"] or []:
            url = attachment.get("url")
            if not url or url in seen_urls:
                continue
            filename = attachment.get("filename") or "Source attachment"
            content_type = attachment.get("content_type")
            is_pdf = content_type == "application/pdf" or filename.lower().endswith(
                ".pdf"
            )
            if not is_pdf:
                continue
            links.append(
                SourceLink(
                    label=filename,
                    url=url,
                    content_type=content_type or "application/pdf",
                )
            )
            seen_urls.add(url)
            if len(links) >= MAX_SOURCE_LINKS_PER_INSIGHT_CARD:
                break
        return links


class PostgresContractTemplateRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def list_active(self) -> list[Template]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      SELECT *
                      FROM template
                      WHERE is_active = true
                      ORDER BY template_code ASC
                      """
                )
                rows = cur.fetchall()

        return [Template.model_validate(row) for row in rows]

    def get_by_id(self, template_id: int) -> Template:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      SELECT *
                      FROM template
                      WHERE id = %s
                      """,
                    (template_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError(f"Template not found: {template_id}")
        return Template.model_validate(row)


class PostgresTemplateReviewCandidateRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def save_if_new(self, candidate: TemplateReviewCandidate) -> bool:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      INSERT INTO intelligence_template_review_candidate (
                          candidate_id,
                          event_id,
                          template_id,
                          template_code,
                          template_name,
                          template_version,
                          event_title,
                          source_url,
                          legal_references_json,
                          rule_ids_json,
                          match_score,
                          rationale,
                          evidence_json,
                          status,
                          created_at
                      )
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                      ON CONFLICT (event_id, template_id) DO NOTHING
                      RETURNING candidate_id
                      """,
                    (
                        candidate.candidate_id,
                        candidate.event_id,
                        candidate.template_id,
                        candidate.template_code,
                        candidate.template_name,
                        candidate.template_version,
                        candidate.event_title,
                        candidate.source_url,
                        Jsonb(candidate.legal_references_json),
                        Jsonb(candidate.rule_ids_json),
                        candidate.match_score,
                        candidate.rationale,
                        Jsonb(
                            [
                                evidence.model_dump(mode="json")
                                for evidence in candidate.evidence_json
                            ]
                        ),
                        candidate.status,
                        candidate.created_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        return row is not None

    def list_candidates(
        self,
        status: str | None = "candidate",
        limit: int = 50,
    ) -> list[TemplateReviewCandidate]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if status is None:
                    cur.execute(
                        """
                          SELECT *
                          FROM intelligence_template_review_candidate
                          ORDER BY created_at DESC
                          LIMIT %s
                          """,
                        (limit,),
                    )
                else:
                    cur.execute(
                        """
                          SELECT *
                          FROM intelligence_template_review_candidate
                          WHERE status = %s
                          ORDER BY created_at DESC
                          LIMIT %s
                          """,
                        (status, limit),
                    )
                rows = cur.fetchall()

        return [TemplateReviewCandidate.model_validate(row) for row in rows]


class PostgresIngestionRunRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def start(self, source_id: str) -> IngestionRun:
        run = IngestionRun(
            run_id=uuid4(),
            source_id=source_id,
            status="started",
            started_at=datetime.now(UTC),
        )

        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      INSERT INTO intelligence_ingestion_run (
                          run_id,
                          source_id,
                          status,
                          raw_items_seen,
                          raw_items_created,
                          events_created,
                          alerts_created,
                          errors,
                          started_at,
                          finished_at
                      )
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                      """,
                    (
                        run.run_id,
                        run.source_id,
                        run.status,
                        run.raw_items_seen,
                        run.raw_items_created,
                        run.events_created,
                        run.alerts_created,
                        Jsonb(run.errors),
                        run.started_at,
                        run.finished_at,
                    ),
                )
                conn.commit()

        return run

    def finish(
        self,
        run: IngestionRun,
        status: str,
        raw_items_seen: int,
        raw_items_created: int,
        errors: list[str],
    ) -> IngestionRun:
        run.status = status
        run.raw_items_seen = raw_items_seen
        run.raw_items_created = raw_items_created
        run.errors = errors
        run.finished_at = datetime.now(UTC)

        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                      UPDATE intelligence_ingestion_run
                      SET status = %s,
                          raw_items_seen = %s,
                          raw_items_created = %s,
                          errors = %s,
                          finished_at = %s
                      WHERE run_id = %s
                      """,
                    (
                        run.status,
                        run.raw_items_seen,
                        run.raw_items_created,
                        Jsonb(run.errors),
                        run.finished_at,
                        run.run_id,
                    ),
                )
                conn.commit()

        return run

    def list_latest(self, limit: int = 50) -> list[IngestionRun]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                        SELECT * 
                        FROM intelligence_ingestion_run 
                        ORDER BY started_at DESC 
                        LIMIT %s 
                        """,
                    (limit,),
                )
                rows = cur.fetchall()

        return [IngestionRun.model_validate(row) for row in rows]

    def get_by_id(self, run_id: UUID) -> IngestionRun:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                        SELECT * 
                        FROM intelligence_ingestion_run 
                        WHERE run_id=%s
                        """,
                    (run_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError(f"IngestionRun not found: {run_id}")

        return IngestionRun.model_validate(row)
