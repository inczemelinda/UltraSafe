from __future__ import annotations

from datetime import datetime

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.wording import (
    WordingDocument,
    WordingDocumentCreate,
    WordingDocumentVersion,
    WordingDocumentVersionCreate,
)
from underwright.infrastructure.postgres.repository_base import PostgresRepositoryMixin


class PostgresWordingDocumentRepository(PostgresRepositoryMixin):
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def list_wording_documents(self) -> list[WordingDocument]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_many(
                    cur,
                    """
                    SELECT *
                    FROM wording_document
                    ORDER BY product_line, jurisdiction, language, code
                    """,
                    (),
                    WordingDocument,
                )

    def get_wording_document(self, wording_document_id: int) -> WordingDocument:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_one(
                    cur,
                    """
                    SELECT *
                    FROM wording_document
                    WHERE id = %s
                    """,
                    (wording_document_id,),
                    WordingDocument,
                    "Wording document not found",
                )

    def get_wording_document_by_code(self, code: str) -> WordingDocument:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_one(
                    cur,
                    """
                    SELECT *
                    FROM wording_document
                    WHERE code = %s
                    """,
                    (code,),
                    WordingDocument,
                    "Wording document not found",
                )

    def create_wording_document(
        self,
        document: WordingDocumentCreate,
    ) -> WordingDocument:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO wording_document (
                        code,
                        title,
                        product_line,
                        jurisdiction,
                        language,
                        insurer_id,
                        status,
                        metadata_json,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING *
                    """,
                    (
                        document.code,
                        document.title,
                        document.product_line,
                        document.jurisdiction,
                        document.language,
                        document.insurer_id,
                        document.status,
                        Jsonb(document.metadata_json),
                    ),
                )
                row = cur.fetchone()
                conn.commit()
        if row is None:
            raise ValueError("Wording document was not saved")
        return WordingDocument.model_validate(row)

    def list_wording_versions(
        self,
        wording_document_id: int,
    ) -> list[WordingDocumentVersion]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_many(
                    cur,
                    """
                    SELECT *
                    FROM wording_document_version
                    WHERE wording_document_id = %s
                    ORDER BY created_at DESC, id DESC
                    """,
                    (wording_document_id,),
                    WordingDocumentVersion,
                )

    def get_wording_version(self, wording_version_id: int) -> WordingDocumentVersion:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_one(
                    cur,
                    """
                    SELECT *
                    FROM wording_document_version
                    WHERE id = %s
                    """,
                    (wording_version_id,),
                    WordingDocumentVersion,
                    "Wording version not found",
                )

    def get_current_published_version(
        self,
        wording_document_id: int,
    ) -> WordingDocumentVersion | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM wording_document_version
                    WHERE wording_document_id = %s
                      AND status = 'published'
                      AND (effective_from IS NULL OR effective_from <= CURRENT_DATE)
                      AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
                    ORDER BY
                      effective_from DESC NULLS LAST,
                      published_at DESC NULLS LAST,
                      created_at DESC,
                      id DESC
                    LIMIT 1
                    """,
                    (wording_document_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return WordingDocumentVersion.model_validate(row)

    def create_wording_version(
        self,
        version: WordingDocumentVersionCreate,
        *,
        content_hash: str,
    ) -> WordingDocumentVersion:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO wording_document_version (
                        wording_document_id,
                        version,
                        status,
                        full_text,
                        content_hash,
                        legal_references_json,
                        structured_clauses_json,
                        file_url,
                        effective_from,
                        effective_to,
                        published_at,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, NOW(), NOW()
                    )
                    RETURNING *
                    """,
                    (
                        version.wording_document_id,
                        version.version,
                        version.status,
                        version.full_text,
                        content_hash,
                        _jsonb_or_none(version.legal_references_json),
                        _jsonb_or_none(version.structured_clauses_json),
                        version.file_url,
                        version.effective_from,
                        version.effective_to,
                        version.published_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
        if row is None:
            raise ValueError("Wording version was not saved")
        return WordingDocumentVersion.model_validate(row)

    def publish_wording_version(
        self,
        wording_version_id: int,
        *,
        published_at: datetime,
    ) -> WordingDocumentVersion:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE wording_document_version
                    SET status = 'published',
                        published_at = COALESCE(published_at, %s),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (published_at, wording_version_id),
                )
                row = cur.fetchone()
                conn.commit()
        if row is None:
            raise ValueError("Wording version not found")
        return WordingDocumentVersion.model_validate(row)

    def update_wording_version_full_text(
        self,
        wording_version_id: int,
        *,
        full_text: str,
        content_hash: str,
    ) -> WordingDocumentVersion:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT status
                    FROM wording_document_version
                    WHERE id = %s
                    """,
                    (wording_version_id,),
                )
                status_row = cur.fetchone()
                if status_row is None:
                    raise ValueError("Wording version not found")
                if status_row["status"] == "published":
                    raise ValueError("Published wording versions are immutable")

                cur.execute(
                    """
                    UPDATE wording_document_version
                    SET full_text = %s,
                        content_hash = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (full_text, content_hash, wording_version_id),
                )
                row = cur.fetchone()
                conn.commit()
        if row is None:
            raise ValueError("Wording version not found")
        return WordingDocumentVersion.model_validate(row)


def _jsonb_or_none(value):
    return Jsonb(value) if value is not None else None


__all__ = ["PostgresWordingDocumentRepository"]
