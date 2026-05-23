from __future__ import annotations

from underwright.application.ports import ContractRepository
from underwright.domain.contract_case_context import ContractCaseContext


class ContractDataService:
    """Loads repository data into the contract case context."""

    def __init__(self, contract_repository: ContractRepository) -> None:
        self.contract_repository = contract_repository

    def load_contract_source(
        self,
        case_context: ContractCaseContext,
    ) -> ContractCaseContext:
        # Repository reads the same UUID carried by the case context.
        contract_id = case_context.source_inputs.contract_id
        if contract_id is None:
            raise ValueError("contract_id is required to load contract source data.")

        source = self.contract_repository.get_contract_context_source(contract_id)
        # Store normalized source data on the context.
        case_context.reference_data.contract_source = source
        # Copy useful ids for downstream review screens.
        case_context.source_inputs.client_id = source.contract.customer_id
        case_context.source_inputs.insured_asset_id = source.contract.insured_asset_id
        case_context.source_inputs.language = (
            case_context.source_inputs.language or "ro-RO"
        )
        case_context.source_inputs.generation_mode = (
            case_context.source_inputs.generation_mode
            or "hybrid_template_plus_llm"
        )
        case_context.source_inputs.effective_date = source.contract.effective_date
        return case_context


__all__ = ["ContractDataService"]
