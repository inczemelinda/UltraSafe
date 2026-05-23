from __future__ import annotations

from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.quote_document import QuoteDocument


class PostgresQuoteDocumentRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def save(self, document: QuoteDocument) -> QuoteDocument:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO quote_document (
                        quote_request_id,
                        template_id,
                        generation_status,
                        rendered_text,
                        rendered_json,
                        file_url,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        document.quote_request_id,
                        document.template_id,
                        document.generation_status,
                        document.rendered_text,
                        Jsonb(document.rendered_json),
                        document.file_url,
                        document.created_at,
                        document.updated_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("QuoteDocument was not saved")

        return QuoteDocument.model_validate(row)

    def get_by_id(self, document_id: int) -> QuoteDocument:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM quote_document
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (document_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError("QuoteDocument not found")
        return QuoteDocument.model_validate(row)

    def get_latest_successful_by_quote_request_id(
        self,
        quote_request_id: UUID,
    ) -> QuoteDocument | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM quote_document
                    WHERE quote_request_id = %s
                      AND generation_status = 'success'
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (quote_request_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return QuoteDocument.model_validate(row)


__all__ = ["PostgresQuoteDocumentRepository"]
