from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from underwright.application.services.generated_document_pdf_service import (
    GeneratedDocumentPdfService,
)
from underwright.domain.generated_document_lifecycle import GeneratedDocumentReadModel

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000041")


class FakeGeneratedDocumentRepository:
    def __init__(self, document: GeneratedDocumentReadModel) -> None:
        self.document = document
        self.updates: list[dict] = []

    def get_by_id(self, document_id: int) -> GeneratedDocumentReadModel:
        if document_id != self.document.id:
            raise ValueError("GeneratedDocument not found")
        return self.document

    def update_pdf_metadata(self, **kwargs) -> GeneratedDocumentReadModel:
        self.updates.append(kwargs)
        self.document = self.document.model_copy(
            update={
                "pdf_storage_key": kwargs["pdf_storage_key"],
                "pdf_filename": kwargs["pdf_filename"],
                "pdf_content_hash": kwargs["pdf_content_hash"],
                "pdf_source_content_hash": kwargs["pdf_source_content_hash"],
                "pdf_generated_at": kwargs["pdf_generated_at"],
                "pdf_generation_metadata": kwargs["pdf_generation_metadata"],
            }
        )
        return self.document


class FakePdfRenderer:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def render_text_pdf(self, *, title: str, text: str, metadata: dict | None = None):
        self.calls.append({"title": title, "text": text, "metadata": metadata})
        return b"%PDF-1.4\nrendered\n%%EOF\n"


class FakeStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def write(self, filename: str, content: bytes) -> str:
        self.files[filename] = content
        return filename

    def exists(self, storage_key: str) -> bool:
        return storage_key in self.files

    def path_for(self, storage_key: str) -> Path:
        return Path("/tmp") / storage_key


def test_pdf_service_creates_pdf_from_persisted_rendered_text() -> None:
    repository = FakeGeneratedDocumentRepository(_document())
    renderer = FakePdfRenderer()
    storage = FakeStorage()
    service = GeneratedDocumentPdfService(repository, renderer, storage)

    result = service.create_pdf(77)

    assert result.status == "ready"
    assert result.artifact is not None
    assert result.artifact.document_id == 77
    assert result.artifact.filename == f"contract-{CONTRACT_ID}.pdf"
    assert renderer.calls[0]["title"] == ""
    assert renderer.calls[0]["text"] == "Persisted contract text"
    assert renderer.calls[0]["metadata"] == {}
    assert repository.updates[0]["pdf_source_content_hash"] == "source-hash"
    assert repository.updates[0]["pdf_content_hash"]
    assert list(storage.files) == [f"contract-{CONTRACT_ID}.pdf"]


def test_pdf_service_blocks_when_document_has_no_rendered_content() -> None:
    repository = FakeGeneratedDocumentRepository(_document(rendered_text=" "))
    service = GeneratedDocumentPdfService(
        repository,
        FakePdfRenderer(),
        FakeStorage(),
    )

    result = service.create_pdf(77)

    assert result.status == "failed"
    assert result.artifact is None
    assert result.blocking_errors[0].code == "GENERATED_DOCUMENT_CONTENT_MISSING"
    assert repository.updates == []


def test_pdf_service_is_idempotent_when_existing_pdf_matches_source_hash() -> None:
    document = _document(
        pdf_storage_key="generated-document-77.pdf",
        pdf_content_hash="pdf-hash",
        pdf_source_content_hash="source-hash",
        pdf_generated_at=datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc),
        pdf_generation_metadata={
            "renderer": "FakePdfRenderer",
            "renderer_version": "unversioned",
            "source": "generated_document.rendered_text",
        },
    )
    repository = FakeGeneratedDocumentRepository(document)
    renderer = FakePdfRenderer()
    storage = FakeStorage()
    storage.files["generated-document-77.pdf"] = b"%PDF-1.4\nexisting\n%%EOF\n"
    service = GeneratedDocumentPdfService(repository, renderer, storage)

    result = service.create_pdf(77)

    assert result.status == "ready"
    assert result.artifact is not None
    assert result.artifact.pdf_content_hash == "pdf-hash"
    assert renderer.calls == []
    assert repository.updates == []


def test_pdf_service_regenerates_when_existing_pdf_source_hash_is_stale() -> None:
    document = _document(
        pdf_storage_key="generated-document-77.pdf",
        pdf_content_hash="old-pdf-hash",
        pdf_source_content_hash="old-source-hash",
        pdf_generated_at=datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc),
    )
    repository = FakeGeneratedDocumentRepository(document)
    renderer = FakePdfRenderer()
    storage = FakeStorage()
    storage.files["generated-document-77.pdf"] = b"%PDF-1.4\nold\n%%EOF\n"
    service = GeneratedDocumentPdfService(repository, renderer, storage)

    result = service.create_pdf(77)

    assert result.status == "ready"
    assert renderer.calls
    assert repository.updates[0]["pdf_source_content_hash"] == "source-hash"
    assert result.artifact is not None
    assert result.artifact.pdf_content_hash != "old-pdf-hash"


def test_pdf_service_regenerates_when_renderer_metadata_is_stale() -> None:
    document = _document(
        pdf_storage_key="generated-document-77.pdf",
        pdf_content_hash="old-pdf-hash",
        pdf_source_content_hash="source-hash",
        pdf_generated_at=datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc),
        pdf_generation_metadata={"renderer": "OldRenderer"},
    )
    repository = FakeGeneratedDocumentRepository(document)
    renderer = FakePdfRenderer()
    storage = FakeStorage()
    storage.files["generated-document-77.pdf"] = b"%PDF-1.4\nold\n%%EOF\n"
    service = GeneratedDocumentPdfService(repository, renderer, storage)

    result = service.create_pdf(77)

    assert result.status == "ready"
    assert renderer.calls
    assert repository.updates[0]["pdf_generation_metadata"] == {
        "renderer": "FakePdfRenderer",
        "renderer_version": "unversioned",
        "source": "generated_document.rendered_text",
    }


def test_pdf_service_get_existing_pdf_does_not_generate_or_update() -> None:
    document = _document(
        pdf_storage_key="generated-document-77.pdf",
        pdf_content_hash="pdf-hash",
        pdf_source_content_hash="source-hash",
        pdf_generated_at=datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc),
    )
    repository = FakeGeneratedDocumentRepository(document)
    renderer = FakePdfRenderer()
    storage = FakeStorage()
    storage.files["generated-document-77.pdf"] = b"%PDF-1.4\nexisting\n%%EOF\n"
    service = GeneratedDocumentPdfService(repository, renderer, storage)

    artifact_file = service.get_existing_pdf(77)

    assert artifact_file is not None
    assert artifact_file.artifact.document_id == 77
    assert renderer.calls == []
    assert repository.updates == []


def test_pdf_export_does_not_alter_contract_document_content_fields() -> None:
    original = _document()
    repository = FakeGeneratedDocumentRepository(original)
    service = GeneratedDocumentPdfService(
        repository,
        FakePdfRenderer(),
        FakeStorage(),
    )

    service.create_pdf(77)

    assert repository.document.rendered_text == original.rendered_text
    assert repository.document.payload_snapshot == original.payload_snapshot
    assert repository.document.template_code == original.template_code
    assert repository.document.template_version == original.template_version
    assert repository.document.content_hash == original.content_hash


def _document(
    *,
    rendered_text: str = "Persisted contract text",
    pdf_storage_key: str | None = None,
    pdf_content_hash: str | None = None,
    pdf_source_content_hash: str | None = None,
    pdf_generated_at: datetime | None = None,
    pdf_generation_metadata: dict | None = None,
) -> GeneratedDocumentReadModel:
    now = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
    return GeneratedDocumentReadModel(
        id=77,
        contract_id=CONTRACT_ID,
        document_type="insurance_contract",
        template_id=22,
        template_code="PAD_PROPERTY_RO",
        template_version="1.0",
        template_version_hash="template-hash",
        rendered_text=rendered_text,
        payload_snapshot={"document_type": "insurance_contract"},
        generation_metadata={"generation_mode": "template"},
        content_hash="source-hash",
        pdf_storage_key=pdf_storage_key,
        pdf_filename=pdf_storage_key,
        pdf_content_hash=pdf_content_hash,
        pdf_source_content_hash=pdf_source_content_hash,
        pdf_generated_at=pdf_generated_at,
        pdf_generation_metadata=pdf_generation_metadata or {},
        created_at=now,
        updated_at=now,
        status="success",
    )
