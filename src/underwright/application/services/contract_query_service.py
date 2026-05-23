from __future__ import annotations

from uuid import UUID

from underwright.application.ports import ContractRepository
from underwright.domain.contract_lifecycle import ContractReadModel


# TODO: Product should confirm whether generated demo contracts should be
# promoted to issued automatically before clients can file claims.
CLAIMABLE_CONTRACT_STATUSES = {"issued"}


class ContractQueryService:
    """Read-only contract access for API/UI views."""

    def __init__(self, contract_repository: ContractRepository) -> None:
        self.contract_repository = contract_repository

    def list_contracts(self) -> list[ContractReadModel]:
        return self.contract_repository.list_contracts()

    def get_contract(self, contract_id: UUID) -> ContractReadModel:
        return self.contract_repository.get_contract_by_id(contract_id)

    def find_by_source_quote_request_id(
        self,
        quote_request_id: UUID,
    ) -> ContractReadModel | None:
        return self.contract_repository.get_contract_by_source_quote_request_id(
            quote_request_id
        )

    def list_claimable_contracts_for_client(
        self,
        client_id: int | str | UUID,
    ) -> list[ContractReadModel]:
        return self.contract_repository.list_claimable_contracts_by_client_id(
            client_id,
            CLAIMABLE_CONTRACT_STATUSES,
        )

    def list_contracts_for_client(
        self,
        client_id: int | str | UUID,
    ) -> list[ContractReadModel]:
        return self.contract_repository.list_contracts_by_client_id(client_id)

    def get_contract_for_client(
        self,
        contract_id: UUID,
        client_id: int | str | UUID,
    ) -> ContractReadModel:
        return self.contract_repository.get_contract_by_id_for_client(
            contract_id,
            client_id,
        )

    def get_claimable_contract_for_client(
        self,
        contract_id: UUID,
        client_id: int | str | UUID,
    ) -> ContractReadModel:
        return self.contract_repository.get_claimable_contract_by_id_for_client(
            contract_id,
            client_id,
            CLAIMABLE_CONTRACT_STATUSES,
        )


__all__ = ["CLAIMABLE_CONTRACT_STATUSES", "ContractQueryService"]
