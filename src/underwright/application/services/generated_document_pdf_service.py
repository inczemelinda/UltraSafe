from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from pathlib import Path

from underwright.application.ports import GeneratedDocumentRepository
from underwright.domain.generated_document_lifecycle import (
    GeneratedDocumentReadModel,
    PdfArtifactReadModel,
    PdfExportIssue,
    PdfExportResult,
)


@dataclass(frozen=True)
class PdfArtifactFile:
    artifact: PdfArtifactReadModel
    file_path: Path


class GeneratedDocumentPdfService:
    """Creates and serves PDFs from persisted generated document content."""

    def __init__(
        self,
        generated_document_repository: GeneratedDocumentRepository,
        pdf_renderer,
        pdf_storage,
    ) -> None:
        self.generated_document_repository = generated_document_repository
        self.pdf_renderer = pdf_renderer
        self.pdf_storage = pdf_storage

    def create_pdf(self, document_id: int) -> PdfExportResult:
        document = self.generated_document_repository.get_by_id(document_id)
        content = self._source_content(document)
        if not content:
            return PdfExportResult(
                status="failed",
                blocking_errors=[
                    PdfExportIssue(
                        code="GENERATED_DOCUMENT_CONTENT_MISSING",
                        field="rendered_text",
                        message="Generated document has no rendered content to export.",
                    )
                ],
            )

        source_content_hash = self._source_content_hash(document, content)
        if self._has_current_pdf(document, source_content_hash):
            return PdfExportResult(
                status="ready",
                artifact=self._artifact_from_document(document),
            )

        filename = self._filename(document)
        renderer_metadata = self._renderer_metadata(document)
        pdf_bytes = self.pdf_renderer.render_text_pdf(
            title="",
            text=content,
            metadata={},
        )
        pdf_storage_key = self.pdf_storage.write(filename, pdf_bytes)
        pdf_content_hash = hashlib.sha256(pdf_bytes).hexdigest()
        generated_at = datetime.now(timezone.utc)
        updated = self.generated_document_repository.update_pdf_metadata(
            document_id=document.id,
            pdf_storage_key=pdf_storage_key,
            pdf_filename=filename,
            pdf_content_hash=pdf_content_hash,
            pdf_source_content_hash=source_content_hash,
            pdf_generated_at=generated_at,
            pdf_generation_metadata=renderer_metadata,
        )
        return PdfExportResult(
            status="ready",
            artifact=self._artifact_from_document(updated),
        )

    def get_existing_pdf(self, document_id: int) -> PdfArtifactFile | None:
        document = self.generated_document_repository.get_by_id(document_id)
        artifact = self._artifact_from_document(document)
        if artifact is None:
            return None
        if not self.pdf_storage.exists(artifact.pdf_storage_key):
            return None
        return PdfArtifactFile(
            artifact=artifact,
            file_path=self.pdf_storage.path_for(artifact.pdf_storage_key),
        )

    def _has_current_pdf(
        self,
        document: GeneratedDocumentReadModel,
        source_content_hash: str,
    ) -> bool:
        return bool(
            document.pdf_storage_key
            and document.pdf_content_hash
            and document.pdf_source_content_hash == source_content_hash
            and self._has_current_renderer(document)
            and self.pdf_storage.exists(document.pdf_storage_key)
        )

    def _has_current_renderer(self, document: GeneratedDocumentReadModel) -> bool:
        metadata = document.pdf_generation_metadata or {}
        expected = self._renderer_metadata(document)
        return (
            metadata.get("renderer") == expected["renderer"]
            and metadata.get("renderer_version") == expected["renderer_version"]
            and metadata.get("source") == expected["source"]
        )

    def _artifact_from_document(
        self,
        document: GeneratedDocumentReadModel,
    ) -> PdfArtifactReadModel | None:
        if (
            not document.pdf_storage_key
            or not document.pdf_content_hash
            or not document.pdf_source_content_hash
            or document.pdf_generated_at is None
        ):
            return None
        return PdfArtifactReadModel(
            document_id=document.id,
            contract_id=document.contract_id,
            pdf_storage_key=document.pdf_storage_key,
            pdf_content_hash=document.pdf_content_hash,
            source_content_hash=document.pdf_source_content_hash,
            pdf_generated_at=document.pdf_generated_at,
            status="ready",
            filename=document.pdf_filename or self._filename(document),
        )

    def _source_content(self, document: GeneratedDocumentReadModel) -> str:
        return (document.rendered_html or document.rendered_text or "").strip()

    def _renderer_metadata(
        self,
        document: GeneratedDocumentReadModel,
    ) -> dict[str, str]:
        return {
            "renderer": self.pdf_renderer.__class__.__name__,
            "renderer_version": str(
                getattr(self.pdf_renderer, "renderer_version", "unversioned")
            ),
            "source": (
                "generated_document.rendered_html"
                if document.rendered_html
                else "generated_document.rendered_text"
            ),
        }

    def _source_content_hash(
        self,
        document: GeneratedDocumentReadModel,
        content: str,
    ) -> str:
        return document.content_hash or hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _filename(self, document: GeneratedDocumentReadModel) -> str:
        return f"contract-{self._slug(document.contract_id)}.pdf"

    def _slug(self, value) -> str:
        return re.sub(r"[^A-Za-z0-9_-]+", "-", str(value)).strip("-")


__all__ = ["GeneratedDocumentPdfService", "PdfArtifactFile"]
