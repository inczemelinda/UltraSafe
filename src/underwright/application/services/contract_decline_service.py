from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from underwright.application.ports import (
    ContractDeclineRepository,
    ContractRepository,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.contract_decline import (
    ContractDecline,
    ContractDeclineCreate,
    ContractDeclineInput,
)
from underwright.domain.contract_lifecycle import ContractReadModel


class ContractDeclineError(ValueError):
    pass


class ContractDeclineNotFoundError(ContractDeclineError):
    pass


class ContractDeclineOwnershipError(ContractDeclineError):
    pass


class ContractDeclineInvalidStatusError(ContractDeclineError):
    pass


class ContractDeclineService:
    def __init__(
        self,
        *,
        contract_repository: ContractRepository,
        contract_decline_repository: ContractDeclineRepository,
    ) -> None:
        self.contract_repository = contract_repository
        self.contract_decline_repository = contract_decline_repository

    def decline_contract_for_client(
        self,
        *,
        contract_id: UUID,
        user: AuthUser,
        decline_input: ContractDeclineInput,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ContractDecline:
        contract = self._contract_for_client(contract_id, user)
        existing = self.contract_decline_repository.get_by_contract_id(contract_id)
        if existing is not None:
            self._require_decline_owner(existing, user)
            if contract.status != "declined":
                self.contract_repository.mark_contract_declined(contract_id)
            return existing

        self._require_declinable_status(contract)
        decline = self.contract_decline_repository.create(
            ContractDeclineCreate(
                contract_id=contract.id,
                source_quote_request_id=contract.source_quote_request_id,
                declined_by_auth_user_id=user.id,
                declined_by_customer_id=int(user.client_id),
                reason=_clean(decline_input.reason),
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "contract_status_before_decline": contract.status,
                },
            )
        )
        updated = self.contract_repository.mark_contract_declined(contract_id)
        if updated is not None and updated.status != "declined":
            raise ContractDeclineInvalidStatusError(
                f"Contract status '{updated.status}' cannot be declined."
            )
        return decline

    def _contract_for_client(
        self,
        contract_id: UUID,
        user: AuthUser,
    ) -> ContractReadModel:
        if user.client_id is None:
            raise ContractDeclineOwnershipError("Contract not found.")
        try:
            return self.contract_repository.get_contract_by_id_for_client(
                contract_id,
                user.client_id,
            )
        except ValueError as exc:
            raise ContractDeclineOwnershipError("Contract not found.") from exc

    def _require_decline_owner(
        self,
        decline: ContractDecline,
        user: AuthUser,
    ) -> None:
        if user.client_id is None or str(decline.declined_by_customer_id) != str(
            user.client_id
        ):
            raise ContractDeclineOwnershipError("Contract decline not found.")

    def _require_declinable_status(self, contract: ContractReadModel) -> None:
        if contract.status != "generated":
            raise ContractDeclineInvalidStatusError(
                f"Contract status '{contract.status}' cannot be declined."
            )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


__all__ = [
    "ContractDeclineError",
    "ContractDeclineInvalidStatusError",
    "ContractDeclineNotFoundError",
    "ContractDeclineOwnershipError",
    "ContractDeclineService",
]
