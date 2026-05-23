from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from underwright.domain.claim_request import ClaimAttachmentMetadata


ALLOWED_CLAIM_ATTACHMENT_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)


@dataclass(frozen=True)
class StoredClaimAttachment:
    path: Path
    file_name: str
    content_type: str
    size_bytes: int


class ClaimAttachmentStorageError(Exception):
    """Base error for claim attachment storage failures."""


class EmptyClaimAttachmentError(ClaimAttachmentStorageError):
    pass


class ClaimAttachmentTooLargeError(ClaimAttachmentStorageError):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"Claim attachment exceeds {max_bytes} bytes.")
        self.max_bytes = max_bytes


class UnsupportedClaimAttachmentContentTypeError(ClaimAttachmentStorageError):
    def __init__(self, content_type: str) -> None:
        super().__init__(f"Unsupported claim attachment content type: {content_type}")
        self.content_type = content_type


class ClaimAttachmentNotFoundError(ClaimAttachmentStorageError):
    pass


class ClaimAttachmentStorageService(Protocol):
    def save_attachment(
        self,
        *,
        file_name: str,
        content_type: str | None,
        content: BinaryIO,
    ) -> ClaimAttachmentMetadata: ...

    def get_attachment(self, storage_key: str) -> StoredClaimAttachment: ...


__all__ = [
    "ALLOWED_CLAIM_ATTACHMENT_CONTENT_TYPES",
    "ClaimAttachmentNotFoundError",
    "ClaimAttachmentStorageError",
    "ClaimAttachmentStorageService",
    "ClaimAttachmentTooLargeError",
    "EmptyClaimAttachmentError",
    "StoredClaimAttachment",
    "UnsupportedClaimAttachmentContentTypeError",
]
