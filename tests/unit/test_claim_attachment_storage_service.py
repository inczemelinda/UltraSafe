from __future__ import annotations

from io import BytesIO

import pytest

from underwright.application.services.claim_attachment_storage_service import (
    ClaimAttachmentNotFoundError,
)
from underwright.infrastructure.storage.local_claim_attachment_storage import (
    LocalClaimAttachmentStorageService,
)


def test_local_claim_attachment_storage_saves_metadata_without_exposing_path(
    tmp_path,
) -> None:
    storage = LocalClaimAttachmentStorageService(tmp_path)
    content = b"%PDF-1.4\nclaim proof"

    attachment = storage.save_attachment(
        file_name="../unsafe proof.pdf",
        content_type="application/pdf",
        content=BytesIO(content),
    )

    storage_key = attachment.metadata["storage_key"]
    assert attachment.file_name == "unsafe-proof.pdf"
    assert attachment.size_bytes == len(content)
    assert attachment.file_url == f"/claims/attachments/{storage_key}"
    assert "/" not in storage_key
    assert str(tmp_path) not in attachment.file_url
    assert (tmp_path / storage_key).read_bytes() == content


def test_local_claim_attachment_storage_loads_existing_attachment(tmp_path) -> None:
    storage = LocalClaimAttachmentStorageService(tmp_path)
    content = b"\x89PNG\r\n"
    attachment = storage.save_attachment(
        file_name="damage.png",
        content_type="image/png",
        content=BytesIO(content),
    )

    stored = storage.get_attachment(str(attachment.metadata["storage_key"]))

    assert stored.path.read_bytes() == content
    assert stored.file_name == "damage.png"
    assert stored.content_type == "image/png"
    assert stored.size_bytes == len(content)


def test_local_claim_attachment_storage_rejects_path_traversal_key(
    tmp_path,
) -> None:
    storage = LocalClaimAttachmentStorageService(tmp_path)

    with pytest.raises(ClaimAttachmentNotFoundError):
        storage.get_attachment("../secret")
