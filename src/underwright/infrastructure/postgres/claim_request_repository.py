from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.claim_request import ClaimRequest
from underwright.infrastructure.postgres.repository_base import PostgresRepositoryMixin


class PostgresClaimRequestRepository(PostgresRepositoryMixin):
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def create_request(self, request: ClaimRequest) -> ClaimRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO claim_request (
                        request_id,
                        client_id,
                        request_status,
                        client_data,
                        claim_data,
                        attachments,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        request.request_id,
                        request.client_id,
                        request.request_status,
                        Jsonb(request.client_data),
                        Jsonb(request.claim_data),
                        Jsonb(
                            [
                                attachment.model_dump()
                                for attachment in request.attachments
                            ]
                        ),
                        request.created_at,
                        request.updated_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("ClaimRequest was not saved")

        return ClaimRequest.model_validate(row)

    def get_request_by_id(self, request_id: UUID) -> ClaimRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_one(
                    cur,
                    "SELECT * FROM claim_request WHERE request_id = %s",
                    (request_id,),
                    ClaimRequest,
                    "ClaimRequest not found",
                )

    def list_requests_by_client_id(
        self,
        client_id: int | str | UUID,
    ) -> list[ClaimRequest]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_many(
                    cur,
                    """
                    SELECT * FROM claim_request
                    WHERE client_id = %s
                    ORDER BY created_at DESC, request_id DESC
                    """,
                    (client_id,),
                    ClaimRequest,
                )

    def list_requests_by_status(self, request_status: str) -> list[ClaimRequest]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_many(
                    cur,
                    """
                    SELECT * FROM claim_request
                    WHERE request_status = %s
                    ORDER BY created_at DESC, request_id DESC
                    """,
                    (request_status,),
                    ClaimRequest,
                )

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> ClaimRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE claim_request
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
            raise ValueError("ClaimRequest not found")

        return ClaimRequest.model_validate(row)

    def update_request_attachments(
        self,
        request_id: UUID,
        attachments: list,
    ) -> ClaimRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE claim_request
                    SET attachments = %s,
                        updated_at = NOW()
                    WHERE request_id = %s
                    RETURNING *
                    """,
                    (Jsonb(attachments), request_id),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("ClaimRequest not found")

        return ClaimRequest.model_validate(row)

    def update_request_claim_data(
        self,
        request_id: UUID,
        claim_data: dict[str, Any],
        request_status: str | None = None,
    ) -> ClaimRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE claim_request
                    SET claim_data = %s,
                        request_status = COALESCE(%s, request_status),
                        updated_at = NOW()
                    WHERE request_id = %s
                    RETURNING *
                    """,
                    (Jsonb(claim_data), request_status, request_id),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("ClaimRequest not found")

        return ClaimRequest.model_validate(row)

    def count_client_claims_since(
        self,
        client_id: int | str | UUID,
        since: datetime,
    ) -> int:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS claim_count
                    FROM claim_request
                    WHERE client_id = %s
                      AND created_at >= %s
                    """,
                    (client_id, since),
                )
                row = cur.fetchone() or {}
        return int(row.get("claim_count") or 0)


__all__ = ["PostgresClaimRequestRepository"]
