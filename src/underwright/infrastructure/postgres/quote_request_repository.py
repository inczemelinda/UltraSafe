from __future__ import annotations

from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.quote_decision_audit import (
    QuoteDecisionAuditCreate,
    QuoteDecisionAuditRecord,
)
from underwright.domain.quote_request import QuoteRequest
from underwright.infrastructure.postgres.repository_base import PostgresRepositoryMixin


class PostgresQuoteRequestRepository(PostgresRepositoryMixin):
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def create_request(self, request: QuoteRequest) -> QuoteRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO quote_request (
                        request_id,
                        client_id,
                        request_status,
                        client_data,
                        asset_data,
                        quote_steps,
                        mandatory_data_status,
                        attachments,
                        pricing_preview,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    RETURNING *
                    """,
                    (
                        request.request_id,
                        request.client_id,
                        request.request_status,
                        Jsonb(request.client_data),
                        Jsonb(request.asset_data),
                        Jsonb(request.quote_steps),
                        Jsonb(request.mandatory_data_status),
                        Jsonb(
                            [
                                attachment.model_dump()
                                for attachment in request.attachments
                            ]
                        ),
                        Jsonb(request.pricing_preview),
                        request.created_at,
                        request.updated_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("QuoteRequest was not saved")

        return QuoteRequest.model_validate(row)

    def get_request_by_id(self, request_id: UUID) -> QuoteRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_one(
                    cur,
                    "SELECT * FROM quote_request WHERE request_id = %s",
                    (request_id,),
                    QuoteRequest,
                    "QuoteRequest not found",
                )

    def update_request(self, request: QuoteRequest) -> QuoteRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE quote_request
                    SET client_id = %s,
                        request_status = %s,
                        client_data = %s,
                        asset_data = %s,
                        quote_steps = %s,
                        mandatory_data_status = %s,
                        attachments = %s,
                        pricing_preview = %s,
                        updated_at = %s
                    WHERE request_id = %s
                    RETURNING *
                    """,
                    (
                        request.client_id,
                        request.request_status,
                        Jsonb(request.client_data),
                        Jsonb(request.asset_data),
                        Jsonb(request.quote_steps),
                        Jsonb(request.mandatory_data_status),
                        Jsonb(
                            [
                                attachment.model_dump()
                                for attachment in request.attachments
                            ]
                        ),
                        Jsonb(request.pricing_preview),
                        request.updated_at,
                        request.request_id,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("QuoteRequest not found")

        return QuoteRequest.model_validate(row)

    def list_requests_by_client_id(
        self,
        client_id: int | str | UUID,
    ) -> list[QuoteRequest]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_many(
                    cur,
                    """
                    SELECT * FROM quote_request
                    WHERE client_id = %s
                    ORDER BY created_at DESC, request_id DESC
                    """,
                    (client_id,),
                    QuoteRequest,
                )

    def list_requests_by_status(self, request_status: str) -> list[QuoteRequest]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_many(
                    cur,
                    """
                    SELECT * FROM quote_request
                    WHERE request_status = %s
                    ORDER BY created_at DESC, request_id DESC
                    """,
                    (request_status,),
                    QuoteRequest,
                )

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> QuoteRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE quote_request
                    SET request_status = %s,
                        updated_at = NOW()
                    WHERE request_id = %s
                    RETURNING *
                    """,
                    (request_status, request_id),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("QuoteRequest not found")

        return QuoteRequest.model_validate(row)

    def create_decision_audit(
        self,
        record: QuoteDecisionAuditCreate,
    ) -> QuoteDecisionAuditRecord:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO quote_decision_audit (
                        quote_request_id,
                        previous_status,
                        decision_status,
                        reason,
                        decided_by_auth_user_id,
                        decided_by_name,
                        decided_by_email,
                        decided_at,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        record.quote_request_id,
                        record.previous_status,
                        record.decision_status,
                        record.reason,
                        record.decided_by_auth_user_id,
                        record.decided_by_name,
                        record.decided_by_email,
                        record.decided_at,
                        Jsonb(record.metadata),
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("QuoteDecisionAuditRecord was not saved")

        return QuoteDecisionAuditRecord.model_validate(row)

    def list_decision_audit(
        self,
        request_id: UUID,
    ) -> list[QuoteDecisionAuditRecord]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_many(
                    cur,
                    """
                    SELECT * FROM quote_decision_audit
                    WHERE quote_request_id = %s
                    ORDER BY decided_at DESC, id DESC
                    """,
                    (request_id,),
                    QuoteDecisionAuditRecord,
                )


__all__ = ["PostgresQuoteRequestRepository"]
