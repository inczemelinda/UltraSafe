from __future__ import annotations

from uuid import UUID

from underwright.domain.auth_user import AuthUser
from underwright.domain.claim_request import ClaimAttachmentMetadata
from underwright.domain.customer_profile_document import (
    CustomerProfileDocument,
    CustomerProfileDocumentCreate,
)


class CustomerProfileDocumentError(ValueError):
    pass


class CustomerProfileDocumentNotFoundError(CustomerProfileDocumentError):
    pass


class CustomerProfileDocumentOwnershipError(CustomerProfileDocumentError):
    pass


class CustomerProfileDocumentService:
    def __init__(self, repository) -> None:
        self.repository = repository

    def list_for_user(self, user: AuthUser) -> list[CustomerProfileDocument]:
        customer_id = self._customer_id(user)
        return self.repository.list_by_customer_id(customer_id)

    def create_for_user(
        self,
        *,
        user: AuthUser,
        label: str,
        document_type: str | None,
        stored_attachment: ClaimAttachmentMetadata,
    ) -> CustomerProfileDocument:
        customer_id = self._customer_id(user)
        storage_key = str(stored_attachment.metadata.get("storage_key") or "").strip()
        clean_label = label.strip()
        if not clean_label:
            raise CustomerProfileDocumentError("Document label is required.")
        if not storage_key:
            raise CustomerProfileDocumentError("Stored document key is missing.")

        return self.repository.create(
            CustomerProfileDocumentCreate(
                customer_id=customer_id,
                label=clean_label,
                document_type=(document_type or clean_label).strip() or clean_label,
                file_name=stored_attachment.file_name,
                content_type=stored_attachment.content_type,
                size_bytes=stored_attachment.size_bytes,
                storage_key=storage_key,
                metadata={
                    **(stored_attachment.metadata or {}),
                    "label": clean_label,
                    "source": "client_profile",
                },
            )
        )

    def get_for_user(
        self,
        *,
        user: AuthUser,
        document_id: UUID,
    ) -> CustomerProfileDocument:
        customer_id = self._customer_id(user)
        try:
            return self.repository.get_for_customer(
                document_id=document_id,
                customer_id=customer_id,
            )
        except ValueError as exc:
            raise CustomerProfileDocumentNotFoundError(
                "Customer profile document not found."
            ) from exc

    def get_for_customer_id(
        self,
        *,
        customer_id: int,
        document_id: UUID,
    ) -> CustomerProfileDocument:
        try:
            return self.repository.get_for_customer(
                document_id=document_id,
                customer_id=customer_id,
            )
        except ValueError as exc:
            raise CustomerProfileDocumentNotFoundError(
                "Customer profile document not found."
            ) from exc

    def delete_for_user(
        self,
        *,
        user: AuthUser,
        document_id: UUID,
    ) -> None:
        customer_id = self._customer_id(user)
        if not self.repository.delete_for_customer(
            document_id=document_id,
            customer_id=customer_id,
        ):
            raise CustomerProfileDocumentNotFoundError(
                "Customer profile document not found."
            )

    def _customer_id(self, user: AuthUser) -> int:
        if user.role != "client" or user.client_id is None:
            raise CustomerProfileDocumentOwnershipError(
                "Customer profile document access requires a linked client profile."
            )
        return int(user.client_id)


__all__ = [
    "CustomerProfileDocumentError",
    "CustomerProfileDocumentNotFoundError",
    "CustomerProfileDocumentOwnershipError",
    "CustomerProfileDocumentService",
]
