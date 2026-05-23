from __future__ import annotations

from uuid import UUID

from underwright.application.ports import ContractRepository, GeneratedDocumentRepository
from underwright.domain.generated_document_lifecycle import GeneratedDocumentReadModel


class GeneratedDocumentQueryService:
    """Read-only access to persisted generated contract documents."""

    def __init__(
        self,
        contract_repository: ContractRepository,
        generated_document_repository: GeneratedDocumentRepository,
    ) -> None:
        self.contract_repository = contract_repository
        self.generated_document_repository = generated_document_repository

    def get_latest_for_contract(
        self,
        contract_id: UUID,
    ) -> GeneratedDocumentReadModel | None:
        self.contract_repository.get_contract_by_id(contract_id)
        return self.generated_document_repository.get_latest_by_contract_id(
            contract_id
        )

    def get_document(self, document_id: int) -> GeneratedDocumentReadModel:
        return self.generated_document_repository.get_by_id(document_id)


__all__ = ["GeneratedDocumentQueryService"]
