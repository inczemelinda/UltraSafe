from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from underwright.application.services.wording_document_service import (
    PublishedWordingVersionImmutableError,
    WordingDocumentService,
)
from underwright.domain.wording import (
    WordingDocument,
    WordingDocumentCreate,
    WordingDocumentVersion,
    WordingDocumentVersionCreate,
)


def test_create_and_list_wording_document() -> None:
    repository = FakeWordingDocumentRepository()
    service = WordingDocumentService(repository)

    created = service.create_wording_document(_document_create())

    assert created.id == 1
    assert created.code == "DEMO_PAD_POLICY_WORDING_RO"
    assert service.list_wording_documents() == [created]


def test_create_and_list_wording_versions_calculates_content_hash() -> None:
    repository = FakeWordingDocumentRepository()
    service = WordingDocumentService(repository)
    document = service.create_wording_document(_document_create())

    created = service.create_wording_version(
        _version_create(document.id, full_text="Legal wording v1")
    )

    assert created.content_hash == service.calculate_content_hash("Legal wording v1")
    assert service.list_wording_versions(document.id) == [created]


def test_current_published_version_lookup_ignores_drafts() -> None:
    repository = FakeWordingDocumentRepository()
    service = WordingDocumentService(repository)
    document = service.create_wording_document(_document_create())
    published = service.create_wording_version(
        _version_create(
            document.id,
            version="1.0",
            status="published",
            full_text="Published terms",
            published_at=_now(),
        )
    )
    draft = service.create_wording_version(
        _version_create(document.id, version="1.1", full_text="Draft terms")
    )

    assert service.get_current_published_version(document.id) == published
    assert draft.status == "draft"


def test_unique_wording_document_code_constraint_is_enforced_by_repository() -> None:
    repository = FakeWordingDocumentRepository()
    service = WordingDocumentService(repository)

    service.create_wording_document(_document_create(code="DUPLICATE"))

    with pytest.raises(ValueError):
        service.create_wording_document(_document_create(code="DUPLICATE"))


def test_unique_wording_document_version_constraint_is_enforced_by_repository() -> None:
    repository = FakeWordingDocumentRepository()
    service = WordingDocumentService(repository)
    document = service.create_wording_document(_document_create())

    service.create_wording_version(_version_create(document.id, version="1.0"))

    with pytest.raises(ValueError):
        service.create_wording_version(_version_create(document.id, version="1.0"))


def test_published_wording_version_text_is_immutable() -> None:
    repository = FakeWordingDocumentRepository()
    service = WordingDocumentService(repository)
    document = service.create_wording_document(_document_create())
    published = service.create_wording_version(
        _version_create(
            document.id,
            status="published",
            full_text="Original legal terms",
            published_at=_now(),
        )
    )

    with pytest.raises(PublishedWordingVersionImmutableError):
        service.update_wording_version_full_text(published.id, "Changed terms")

    assert service.get_wording_version(published.id).full_text == "Original legal terms"


def test_draft_version_can_change_without_affecting_published_version() -> None:
    repository = FakeWordingDocumentRepository()
    service = WordingDocumentService(repository)
    document = service.create_wording_document(_document_create())
    published = service.create_wording_version(
        _version_create(
            document.id,
            version="1.0",
            status="published",
            full_text="Published terms",
            published_at=_now(),
        )
    )
    draft = service.create_wording_version(
        _version_create(document.id, version="1.1", full_text="Draft terms")
    )

    updated_draft = service.update_wording_version_full_text(
        draft.id,
        "Updated draft terms",
    )

    assert updated_draft.full_text == "Updated draft terms"
    assert service.get_current_published_version(document.id) == published


class FakeWordingDocumentRepository:
    def __init__(self) -> None:
        self.documents: list[WordingDocument] = []
        self.versions: list[WordingDocumentVersion] = []
        self.next_document_id = 1
        self.next_version_id = 1

    def list_wording_documents(self) -> list[WordingDocument]:
        return self.documents

    def get_wording_document(self, wording_document_id: int) -> WordingDocument:
        for document in self.documents:
            if document.id == wording_document_id:
                return document
        raise ValueError("Wording document not found")

    def create_wording_document(
        self,
        document: WordingDocumentCreate,
    ) -> WordingDocument:
        if any(existing.code == document.code for existing in self.documents):
            raise ValueError("duplicate wording document code")
        created = WordingDocument(
            id=self.next_document_id,
            created_at=_now(),
            updated_at=_now(),
            **document.model_dump(),
        )
        self.next_document_id += 1
        self.documents.append(created)
        return created

    def list_wording_versions(
        self,
        wording_document_id: int,
    ) -> list[WordingDocumentVersion]:
        return [
            version
            for version in self.versions
            if version.wording_document_id == wording_document_id
        ]

    def get_wording_version(self, wording_version_id: int) -> WordingDocumentVersion:
        for version in self.versions:
            if version.id == wording_version_id:
                return version
        raise ValueError("Wording version not found")

    def get_current_published_version(
        self,
        wording_document_id: int,
    ) -> WordingDocumentVersion | None:
        published = [
            version
            for version in self.versions
            if version.wording_document_id == wording_document_id
            and version.status == "published"
        ]
        return published[-1] if published else None

    def create_wording_version(
        self,
        version: WordingDocumentVersionCreate,
        *,
        content_hash: str,
    ) -> WordingDocumentVersion:
        if any(
            existing.wording_document_id == version.wording_document_id
            and existing.version == version.version
            for existing in self.versions
        ):
            raise ValueError("duplicate wording version")
        created = WordingDocumentVersion(
            id=self.next_version_id,
            content_hash=content_hash,
            created_at=_now(),
            updated_at=_now(),
            **version.model_dump(),
        )
        self.next_version_id += 1
        self.versions.append(created)
        return created

    def publish_wording_version(
        self,
        wording_version_id: int,
        *,
        published_at: datetime,
    ) -> WordingDocumentVersion:
        existing = self.get_wording_version(wording_version_id)
        updated = existing.model_copy(
            update={"status": "published", "published_at": published_at}
        )
        self._replace_version(updated)
        return updated

    def update_wording_version_full_text(
        self,
        wording_version_id: int,
        *,
        full_text: str,
        content_hash: str,
    ) -> WordingDocumentVersion:
        existing = self.get_wording_version(wording_version_id)
        if existing.status == "published":
            raise ValueError("Published wording versions are immutable")
        updated = existing.model_copy(
            update={"full_text": full_text, "content_hash": content_hash}
        )
        self._replace_version(updated)
        return updated

    def _replace_version(self, updated: WordingDocumentVersion) -> None:
        self.versions = [
            updated if version.id == updated.id else version
            for version in self.versions
        ]


def _document_create(code: str = "DEMO_PAD_POLICY_WORDING_RO") -> WordingDocumentCreate:
    return WordingDocumentCreate(
        code=code,
        title="PAD Property Insurance Wording RO",
        product_line="property",
        jurisdiction="RO",
        language="ro-RO",
        status="published",
    )


def _version_create(
    wording_document_id: int,
    *,
    version: str = "1.0",
    status: str = "draft",
    full_text: str = "Legal wording",
    published_at: datetime | None = None,
) -> WordingDocumentVersionCreate:
    return WordingDocumentVersionCreate(
        wording_document_id=wording_document_id,
        version=version,
        status=status,
        full_text=full_text,
        legal_references_json=["ro:lege:260:2008"],
        effective_from=date(2026, 5, 14),
        published_at=published_at,
    )


def _now() -> datetime:
    return datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc)
