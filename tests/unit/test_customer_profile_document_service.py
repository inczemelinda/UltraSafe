from __future__ import annotations

from uuid import UUID

import pytest

from underwright.application.services.customer_profile_document_service import (
    CustomerProfileDocumentNotFoundError,
    CustomerProfileDocumentOwnershipError,
    CustomerProfileDocumentService,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.claim_request import ClaimAttachmentMetadata
from underwright.domain.customer_profile_document import (
    CustomerProfileDocument,
    CustomerProfileDocumentCreate,
)


class FakeCustomerProfileDocumentRepository:
    def __init__(self) -> None:
        self.created: CustomerProfileDocumentCreate | None = None
        self.requested_customer_id: int | None = None

    def list_by_customer_id(self, customer_id: int) -> list[CustomerProfileDocument]:
        self.requested_customer_id = customer_id
        return []

    def create(
        self,
        document: CustomerProfileDocumentCreate,
    ) -> CustomerProfileDocument:
        self.created = document
        return CustomerProfileDocument(
            id=document.id,
            customer_id=document.customer_id,
            label=document.label,
            document_type=document.document_type,
            file_name=document.file_name,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            storage_key=document.storage_key,
            file_url=f"/me/customer-profile/documents/{document.id}/download",
            metadata=document.metadata,
        )

    def get_for_customer(
        self,
        *,
        document_id: UUID,
        customer_id: int,
    ) -> CustomerProfileDocument:
        self.requested_customer_id = customer_id
        raise ValueError("missing")

    def delete_for_customer(self, *, document_id: UUID, customer_id: int) -> bool:
        self.requested_customer_id = customer_id
        return False


def test_profile_document_service_uses_linked_customer_as_owner() -> None:
    repository = FakeCustomerProfileDocumentRepository()
    service = CustomerProfileDocumentService(repository)

    document = service.create_for_user(
        user=_client_user(customer_id=101),
        label="Identity document",
        document_type="identity",
        stored_attachment=ClaimAttachmentMetadata(
            file_name="identity.pdf",
            content_type="application/pdf",
            size_bytes=128,
            metadata={"storage_key": "profile-documents/identity.pdf"},
        ),
    )

    assert document.customer_id == 101
    assert repository.created is not None
    assert repository.created.customer_id == 101
    assert repository.created.metadata["source"] == "client_profile"


def test_profile_document_service_rejects_unlinked_clients() -> None:
    service = CustomerProfileDocumentService(FakeCustomerProfileDocumentRepository())

    with pytest.raises(CustomerProfileDocumentOwnershipError):
        service.list_for_user(_client_user(customer_id=None))


def test_profile_document_service_hides_documents_outside_customer_boundary() -> None:
    repository = FakeCustomerProfileDocumentRepository()
    service = CustomerProfileDocumentService(repository)

    with pytest.raises(CustomerProfileDocumentNotFoundError):
        service.get_for_user(
            user=_client_user(customer_id=101),
            document_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        )

    assert repository.requested_customer_id == 101


def _client_user(customer_id: int | None) -> AuthUser:
    return AuthUser(
        id=1,
        email="client@example.test",
        password_hash="hash",
        role="client",
        full_name="Client User",
        client_id=customer_id,
        is_active=True,
    )
