from __future__ import annotations

from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.customer_profile_document import (
    CustomerProfileDocument,
    CustomerProfileDocumentCreate,
)


class PostgresCustomerProfileDocumentRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def list_by_customer_id(self, customer_id: int) -> list[CustomerProfileDocument]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM customer_profile_document
                    WHERE customer_id = %s
                      AND deleted_at IS NULL
                    ORDER BY created_at DESC, id DESC
                    """,
                    (customer_id,),
                )
                rows = cur.fetchall()
        return [CustomerProfileDocument.model_validate(row) for row in rows]

    def create(
        self,
        document: CustomerProfileDocumentCreate,
    ) -> CustomerProfileDocument:
        file_url = f"/me/customer-profile/documents/{document.id}/download"
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE customer_profile_document
                    SET deleted_at = NOW(),
                        updated_at = NOW()
                    WHERE customer_id = %s
                      AND label = %s
                      AND deleted_at IS NULL
                    """,
                    (document.customer_id, document.label),
                )
                cur.execute(
                    """
                    INSERT INTO customer_profile_document (
                        id,
                        customer_id,
                        label,
                        document_type,
                        file_name,
                        content_type,
                        size_bytes,
                        storage_key,
                        file_url,
                        metadata,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING *
                    """,
                    (
                        document.id,
                        document.customer_id,
                        document.label,
                        document.document_type,
                        document.file_name,
                        document.content_type,
                        document.size_bytes,
                        document.storage_key,
                        file_url,
                        Jsonb(document.metadata),
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("Customer profile document was not saved")
        return CustomerProfileDocument.model_validate(row)

    def get_for_customer(
        self,
        *,
        document_id: UUID,
        customer_id: int,
    ) -> CustomerProfileDocument:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM customer_profile_document
                    WHERE id = %s
                      AND customer_id = %s
                      AND deleted_at IS NULL
                    LIMIT 1
                    """,
                    (document_id, customer_id),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError("Customer profile document not found")
        return CustomerProfileDocument.model_validate(row)

    def delete_for_customer(
        self,
        *,
        document_id: UUID,
        customer_id: int,
    ) -> bool:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE customer_profile_document
                    SET deleted_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                      AND customer_id = %s
                      AND deleted_at IS NULL
                    """,
                    (document_id, customer_id),
                )
                deleted = cur.rowcount > 0
                conn.commit()
        return deleted


__all__ = ["PostgresCustomerProfileDocumentRepository"]
