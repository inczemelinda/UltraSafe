from __future__ import annotations

from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.contract_decline import (
    ContractDecline,
    ContractDeclineCreate,
)


class PostgresContractDeclineRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def create(self, decline: ContractDeclineCreate) -> ContractDecline:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO contract_decline (
                        contract_id,
                        source_quote_request_id,
                        declined_by_auth_user_id,
                        declined_by_customer_id,
                        reason,
                        ip_address,
                        user_agent,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (contract_id) DO NOTHING
                    RETURNING *
                    """,
                    (
                        decline.contract_id,
                        decline.source_quote_request_id,
                        decline.declined_by_auth_user_id,
                        decline.declined_by_customer_id,
                        decline.reason,
                        decline.ip_address,
                        decline.user_agent,
                        Jsonb(decline.metadata),
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            existing = self.get_by_contract_id(decline.contract_id)
            if existing is not None:
                return existing
            raise ValueError("ContractDecline was not saved")
        return ContractDecline.model_validate(row)

    def get_by_contract_id(self, contract_id: UUID) -> ContractDecline | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM contract_decline
                    WHERE contract_id = %s
                    ORDER BY declined_at DESC, id DESC
                    LIMIT 1
                    """,
                    (contract_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return ContractDecline.model_validate(row)

    def get_by_id(self, decline_id: int) -> ContractDecline:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM contract_decline
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (decline_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError("ContractDecline not found")
        return ContractDecline.model_validate(row)


__all__ = ["PostgresContractDeclineRepository"]
