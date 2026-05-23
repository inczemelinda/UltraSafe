from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from underwright.domain.wording import (
    WordingDocument,
    WordingDocumentCreate,
    WordingDocumentVersion,
    WordingDocumentVersionCreate,
)


class WordingDocumentError(ValueError):
    pass


class WordingDocumentNotFoundError(WordingDocumentError):
    pass


class WordingVersionNotFoundError(WordingDocumentError):
    pass


class PublishedWordingVersionImmutableError(WordingDocumentError):
    pass


class WordingDocumentService:
    """Owns wording version lifecycle rules before generation is wired in."""

    def __init__(self, wording_document_repository) -> None:
        self.wording_document_repository = wording_document_repository

    def list_wording_documents(self) -> list[WordingDocument]:
        return self.wording_document_repository.list_wording_documents()

    def get_wording_document(self, wording_document_id: int) -> WordingDocument:
        try:
            return self.wording_document_repository.get_wording_document(
                wording_document_id
            )
        except ValueError as exc:
            raise WordingDocumentNotFoundError("Wording document not found.") from exc

    def list_wording_versions(
        self,
        wording_document_id: int,
    ) -> list[WordingDocumentVersion]:
        self.get_wording_document(wording_document_id)
        return self.wording_document_repository.list_wording_versions(
            wording_document_id
        )

    def get_wording_version(self, wording_version_id: int) -> WordingDocumentVersion:
        try:
            return self.wording_document_repository.get_wording_version(
                wording_version_id
            )
        except ValueError as exc:
            raise WordingVersionNotFoundError("Wording version not found.") from exc

    def get_current_published_version(
        self,
        wording_document_id: int,
    ) -> WordingDocumentVersion:
        self.get_wording_document(wording_document_id)
        version = self.wording_document_repository.get_current_published_version(
            wording_document_id
        )
        if version is None:
            raise WordingVersionNotFoundError(
                "Current published wording version not found."
            )
        return version

    def create_wording_document(
        self,
        document: WordingDocumentCreate,
    ) -> WordingDocument:
        return self.wording_document_repository.create_wording_document(document)

    def create_wording_version(
        self,
        version: WordingDocumentVersionCreate,
    ) -> WordingDocumentVersion:
        self.get_wording_document(version.wording_document_id)
        return self.wording_document_repository.create_wording_version(
            version,
            content_hash=self.calculate_content_hash(version.full_text),
        )

    def publish_wording_version(
        self,
        wording_version_id: int,
        *,
        published_at: datetime | None = None,
    ) -> WordingDocumentVersion:
        self.get_wording_version(wording_version_id)
        return self.wording_document_repository.publish_wording_version(
            wording_version_id,
            published_at=published_at or datetime.now(timezone.utc),
        )

    def update_wording_version_full_text(
        self,
        wording_version_id: int,
        full_text: str,
    ) -> WordingDocumentVersion:
        existing = self.get_wording_version(wording_version_id)
        if existing.status == "published":
            raise PublishedWordingVersionImmutableError(
                "Published wording versions are immutable."
            )
        return self.wording_document_repository.update_wording_version_full_text(
            wording_version_id,
            full_text=full_text,
            content_hash=self.calculate_content_hash(full_text),
        )

    @staticmethod
    def calculate_content_hash(full_text: str) -> str:
        return hashlib.sha256(full_text.encode("utf-8")).hexdigest()


__all__ = [
    "PublishedWordingVersionImmutableError",
    "WordingDocumentNotFoundError",
    "WordingDocumentService",
    "WordingVersionNotFoundError",
]
