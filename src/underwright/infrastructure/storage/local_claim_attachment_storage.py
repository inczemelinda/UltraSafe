from __future__ import annotations

import json
import re
from pathlib import Path, PurePath
from typing import BinaryIO
from uuid import uuid4

from underwright.application.services.claim_attachment_storage_service import (
    ALLOWED_CLAIM_ATTACHMENT_CONTENT_TYPES,
    ClaimAttachmentNotFoundError,
    ClaimAttachmentTooLargeError,
    EmptyClaimAttachmentError,
    StoredClaimAttachment,
    UnsupportedClaimAttachmentContentTypeError,
)
from underwright.domain.claim_request import ClaimAttachmentMetadata


DEFAULT_CLAIM_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_CLAIM_UPLOAD_DIR = Path("/tmp/underwright-claim-uploads")
_CHUNK_SIZE = 1024 * 1024
_STORAGE_KEY_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class LocalClaimAttachmentStorageService:
    """Stores claim attachment bytes on the local filesystem.

    The generated storage key is the only lookup handle exposed to the API.
    Original filenames are stored as metadata, never used as paths.
    """

    def __init__(
        self,
        upload_dir: Path | str = DEFAULT_CLAIM_UPLOAD_DIR,
        max_bytes: int = DEFAULT_CLAIM_UPLOAD_MAX_BYTES,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero")
        self.upload_dir = Path(upload_dir)
        self.max_bytes = max_bytes

    def save_attachment(
        self,
        *,
        file_name: str,
        content_type: str | None,
        content: BinaryIO,
    ) -> ClaimAttachmentMetadata:
        normalized_content_type = (content_type or "").strip().lower()
        if normalized_content_type not in ALLOWED_CLAIM_ATTACHMENT_CONTENT_TYPES:
            raise UnsupportedClaimAttachmentContentTypeError(
                normalized_content_type or "unknown"
            )

        safe_file_name = self._sanitize_file_name(file_name)
        storage_key = uuid4().hex
        file_path = self._path_for_storage_key(storage_key)
        metadata_path = self._metadata_path_for_storage_key(storage_key)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        size_bytes = 0
        try:
            with file_path.open("wb") as destination:
                while True:
                    chunk = content.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > self.max_bytes:
                        raise ClaimAttachmentTooLargeError(self.max_bytes)
                    destination.write(chunk)
        except Exception:
            file_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            raise

        if size_bytes == 0:
            file_path.unlink(missing_ok=True)
            raise EmptyClaimAttachmentError("Claim attachment is empty.")

        metadata = {
            "file_name": safe_file_name,
            "content_type": normalized_content_type,
            "size_bytes": size_bytes,
        }
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        return ClaimAttachmentMetadata(
            file_name=safe_file_name,
            content_type=normalized_content_type,
            size_bytes=size_bytes,
            file_url=f"/claims/attachments/{storage_key}",
            metadata={"storage_key": storage_key},
        )

    def get_attachment(self, storage_key: str) -> StoredClaimAttachment:
        if not self._is_valid_storage_key(storage_key):
            raise ClaimAttachmentNotFoundError("Claim attachment not found.")

        file_path = self._path_for_storage_key(storage_key)
        if not file_path.is_file():
            raise ClaimAttachmentNotFoundError("Claim attachment not found.")

        metadata = self._read_metadata(storage_key)
        return StoredClaimAttachment(
            path=file_path,
            file_name=str(metadata.get("file_name") or "claim-attachment"),
            content_type=str(
                metadata.get("content_type") or "application/octet-stream"
            ),
            size_bytes=int(metadata.get("size_bytes") or file_path.stat().st_size),
        )

    def _read_metadata(self, storage_key: str) -> dict[str, object]:
        metadata_path = self._metadata_path_for_storage_key(storage_key)
        if not metadata_path.is_file():
            return {}
        try:
            value = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def _path_for_storage_key(self, storage_key: str) -> Path:
        path = (self.upload_dir / storage_key).resolve()
        upload_root = self.upload_dir.resolve()
        if upload_root != path and upload_root not in path.parents:
            raise ClaimAttachmentNotFoundError("Claim attachment not found.")
        return path

    def _metadata_path_for_storage_key(self, storage_key: str) -> Path:
        return self._path_for_storage_key(f"{storage_key}.json")

    def _is_valid_storage_key(self, storage_key: str) -> bool:
        return bool(_STORAGE_KEY_PATTERN.fullmatch(storage_key))

    def _sanitize_file_name(self, file_name: str) -> str:
        base_name = PurePath(file_name or "").name.strip()
        safe_name = _SAFE_FILENAME_PATTERN.sub("-", base_name).strip("._-")
        if not safe_name:
            return "claim-attachment"
        return safe_name[:180]


__all__ = [
    "DEFAULT_CLAIM_UPLOAD_DIR",
    "DEFAULT_CLAIM_UPLOAD_MAX_BYTES",
    "LocalClaimAttachmentStorageService",
]
