from __future__ import annotations

from underwright.application.ports import ContractRequestRepository
from underwright.domain.contract_request import ContractRequest


class ContractRequestService:
    """Wraps contract request repository access for UI-facing flows."""

    def __init__(self, contract_request_repository: ContractRequestRepository) -> None:
        self.contract_request_repository = contract_request_repository

    def create_client_request(self, request: ContractRequest) -> ContractRequest:
        # Create a new client request.
        return self.contract_request_repository.create_request(request)

    def list_client_requests(self, client_id: int) -> list[ContractRequest]:
        return self.contract_request_repository.list_requests_by_client_id(client_id)

    def list_underwriter_queue_requests(
        self,
        request_status: str,
    ) -> list[ContractRequest]:
        return self.contract_request_repository.list_requests_by_status(request_status)

    def get_request_detail(self, request_id: int) -> ContractRequest:
        return self.contract_request_repository.get_request_by_id(request_id)

    def mark_pending(self, request_id: int) -> ContractRequest:
        return self.contract_request_repository.update_request_status(
            request_id,
            "pending",
        )

    def mark_drafting_started(self, request_id: int) -> ContractRequest:
        # Backward-compatible alias.
        return self.mark_pending(request_id)

    def mark_completed(self, request_id: int) -> ContractRequest:
        return self.contract_request_repository.update_request_status(
            request_id,
            "completed",
        )

    def mark_failed(self, request_id: int) -> ContractRequest:
        return self.contract_request_repository.update_request_status(
            request_id,
            "failed",
        )

    def update_request_status(
        self,
        request_id: int,
        request_status: str,
    ) -> ContractRequest:
        return self.contract_request_repository.update_request_status(
            request_id,
            request_status,
        )


__all__ = ["ContractRequestService"]

