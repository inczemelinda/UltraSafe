from __future__ import annotations

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.contract_request import ContractRequest


class PostgresContractRequestRepository:
    """Legacy adapter for the old direct contract-request flow."""

    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def create_request(self, request: ContractRequest) -> ContractRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO contract_request (
                        request_id,
                        client_id,
                        request_status,
                        client_data,
                        insured_data,
                        request_details,
                        attachments,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        request.request_id,
                        request.client_id,
                        request.request_status,
                        Jsonb(request.client_data),
                        Jsonb(request.insured_data),
                        Jsonb(request.request_details),
                        Jsonb(request.attachments),
                        request.created_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("ContractRequest was not saved")

        return ContractRequest.model_validate(row)

    def get_request_by_id(self, request_id: int) -> ContractRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_one(
                    cur,
                    "SELECT * FROM contract_request WHERE request_id = %s",
                    (request_id,),
                )

    def list_requests_by_client_id(self, client_id: int) -> list[ContractRequest]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_many(
                    cur,
                    """
                    SELECT * FROM contract_request
                    WHERE client_id = %s
                    ORDER BY created_at DESC, request_id DESC
                    """,
                    (client_id,),
                )

    def list_requests_by_status(self, request_status: str) -> list[ContractRequest]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_many(
                    cur,
                    """
                    SELECT * FROM contract_request
                    WHERE request_status = %s
                    ORDER BY created_at DESC, request_id DESC
                    """,
                    (request_status,),
                )

    def update_request_status(
        self,
        request_id: int,
        request_status: str,
    ) -> ContractRequest:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE contract_request
                    SET request_status = %s
                    WHERE request_id = %s
                    RETURNING *
                    """,
                    (request_status, request_id),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("ContractRequest not found")

        return ContractRequest.model_validate(row)

    def _fetch_one(self, cur, sql, params) -> ContractRequest:
        cur.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            raise ValueError("ContractRequest not found")
        return ContractRequest.model_validate(row)

    def _fetch_many(self, cur, sql, params) -> list[ContractRequest]:
        cur.execute(sql, params)
        return [ContractRequest.model_validate(row) for row in cur.fetchall()]


__all__ = ["PostgresContractRequestRepository"]
