from __future__ import annotations

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.generated_document_lifecycle import GeneratedDocumentReadModel
from underwright.domain.models import GeneratedDocument


class PostgresGeneratedDocumentRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def save(self, document: GeneratedDocument) -> GeneratedDocument:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO generated_document (
                        contract_id,
                        template_id,
                        generation_status,
                        rendered_text,
                        rendered_json,
                        template_code,
                        template_version,
                        template_version_hash,
                        payload_snapshot,
                        generation_metadata,
                        content_hash,
                        file_url,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING *
                    """,
                    (
                        document.contract_id,
                        document.template_id,
                        document.generation_status,
                        document.rendered_text,
                        Jsonb(document.rendered_json),
                        document.template_code,
                        document.template_version,
                        document.template_version_hash,
                        Jsonb(document.payload_snapshot),
                        Jsonb(document.generation_metadata),
                        document.content_hash,
                        document.file_url,
                        document.created_at,
                        document.updated_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("GeneratedDocument was not saved")

        return GeneratedDocument.model_validate(row)

    def get_latest_by_contract_id(
        self,
        contract_id,
    ) -> GeneratedDocumentReadModel | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM generated_document
                    WHERE contract_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (contract_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._read_model(row)

    def get_by_id(self, document_id: int) -> GeneratedDocumentReadModel:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM generated_document
                    WHERE id = %s
                    """,
                    (document_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError("GeneratedDocument not found")
        return self._read_model(row)

    def update_pdf_metadata(
        self,
        *,
        document_id: int,
        pdf_storage_key: str,
        pdf_filename: str,
        pdf_content_hash: str,
        pdf_source_content_hash: str,
        pdf_generated_at,
        pdf_generation_metadata: dict,
    ) -> GeneratedDocumentReadModel:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE generated_document
                    SET pdf_storage_key = %s,
                        pdf_filename = %s,
                        pdf_content_hash = %s,
                        pdf_source_content_hash = %s,
                        pdf_generated_at = %s,
                        pdf_generation_metadata = %s,
                        updated_at = updated_at
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        pdf_storage_key,
                        pdf_filename,
                        pdf_content_hash,
                        pdf_source_content_hash,
                        pdf_generated_at,
                        Jsonb(pdf_generation_metadata),
                        document_id,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("GeneratedDocument not found")
        return self._read_model(row)

    def _read_model(self, row: dict) -> GeneratedDocumentReadModel:
        rendered_json = row.get("rendered_json") or {}
        payload_snapshot = (
            row.get("payload_snapshot")
            or rendered_json.get("contract_generation_payload")
            or {}
        )
        template_used = rendered_json.get("template_used") or {}
        generation_metadata = (
            row.get("generation_metadata")
            or rendered_json.get("generation_metadata")
            or {}
        )
        return GeneratedDocumentReadModel(
            id=row["id"],
            contract_id=row["contract_id"],
            document_type=payload_snapshot.get("document_type"),
            template_id=row["template_id"],
            template_code=row.get("template_code") or template_used.get("template_code"),
            template_version=(
                row.get("template_version")
                or template_used.get("template_version")
            ),
            template_version_hash=row.get("template_version_hash")
            or rendered_json.get("template_version_hash"),
            rendered_text=row["rendered_text"],
            payload_snapshot=payload_snapshot,
            generation_metadata=generation_metadata,
            content_hash=row.get("content_hash"),
            pdf_storage_key=row.get("pdf_storage_key"),
            pdf_filename=row.get("pdf_filename"),
            pdf_content_hash=row.get("pdf_content_hash"),
            pdf_source_content_hash=row.get("pdf_source_content_hash"),
            pdf_generated_at=row.get("pdf_generated_at"),
            pdf_generation_metadata=row.get("pdf_generation_metadata") or {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=row["generation_status"],
        )


__all__ = ["PostgresGeneratedDocumentRepository"]
