from __future__ import annotations

from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.quote_acceptance import QuoteAcceptance, QuoteAcceptanceCreate


class PostgresQuoteAcceptanceRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def create(self, acceptance: QuoteAcceptanceCreate) -> QuoteAcceptance:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO quote_acceptance (
                        quote_request_id,
                        quote_document_id,
                        accepted_by_auth_user_id,
                        accepted_by_customer_id,
                        signer_name,
                        signer_email,
                        signer_role,
                        acceptance_method,
                        ip_address,
                        user_agent,
                        acceptance_statement,
                        quote_content_hash,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (quote_request_id) DO NOTHING
                    RETURNING *
                    """,
                    (
                        acceptance.quote_request_id,
                        acceptance.quote_document_id,
                        acceptance.accepted_by_auth_user_id,
                        acceptance.accepted_by_customer_id,
                        acceptance.signer_name,
                        acceptance.signer_email,
                        acceptance.signer_role,
                        acceptance.acceptance_method,
                        acceptance.ip_address,
                        acceptance.user_agent,
                        acceptance.acceptance_statement,
                        acceptance.quote_content_hash,
                        Jsonb(acceptance.metadata),
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            existing = self.get_by_quote_request_id(acceptance.quote_request_id)
            if existing is not None:
                return existing
            raise ValueError("QuoteAcceptance was not saved")
        return QuoteAcceptance.model_validate(row)

    def get_by_quote_request_id(self, quote_request_id: UUID) -> QuoteAcceptance | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM quote_acceptance
                    WHERE quote_request_id = %s
                    ORDER BY accepted_at DESC, id DESC
                    LIMIT 1
                    """,
                    (quote_request_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return QuoteAcceptance.model_validate(row)

    def get_by_id(self, acceptance_id: int) -> QuoteAcceptance:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM quote_acceptance
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (acceptance_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError("QuoteAcceptance not found")
        return QuoteAcceptance.model_validate(row)


__all__ = ["PostgresQuoteAcceptanceRepository"]
