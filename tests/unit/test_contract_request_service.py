from __future__ import annotations

from datetime import datetime, timezone
import unittest

from underwright.application.services.contract_request_service import ContractRequestService
from underwright.domain.contract_request import ContractRequest


class FakeContractRequestRepository:
    def __init__(self) -> None:
        self.created_request = None
        self.client_id = None
        self.request_status = None
        self.updated = None

    def create_request(self, request: ContractRequest) -> ContractRequest:
        self.created_request = request
        return request

    def get_request_by_id(self, request_id: int) -> ContractRequest:
        return ContractRequest(
            request_id=request_id,
            client_id=77,
            created_at=datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
        )

    def list_requests_by_client_id(self, client_id: int) -> list[ContractRequest]:
        self.client_id = client_id
        return [
            ContractRequest(
                request_id=1,
                client_id=client_id,
                created_at=datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
            )
        ]

    def list_requests_by_status(self, request_status: str) -> list[ContractRequest]:
        self.request_status = request_status
        return [
            ContractRequest(
                request_id=2,
                client_id=99,
                request_status=request_status,
                created_at=datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
            )
        ]

    def update_request_status(
        self,
        request_id: int,
        request_status: str,
    ) -> ContractRequest:
        self.updated = (request_id, request_status)
        return ContractRequest(
            request_id=request_id,
            client_id=77,
            request_status=request_status,
            created_at=datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
        )


class ContractRequestServiceTestCase(unittest.TestCase):
    def test_create_client_request_wraps_repository(self) -> None:
        repository = FakeContractRequestRepository()
        service = ContractRequestService(repository)
        request = ContractRequest(
            request_id=10,
            client_id=20,
            created_at=datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
        )

        result = service.create_client_request(request)

        self.assertIs(result, request)
        self.assertIs(repository.created_request, request)

    def test_list_client_requests_wraps_repository(self) -> None:
        repository = FakeContractRequestRepository()
        service = ContractRequestService(repository)

        result = service.list_client_requests(20)

        self.assertEqual(repository.client_id, 20)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].client_id, 20)

    def test_list_underwriter_queue_requests_wraps_repository(self) -> None:
        repository = FakeContractRequestRepository()
        service = ContractRequestService(repository)

        result = service.list_underwriter_queue_requests("pending")

        self.assertEqual(repository.request_status, "pending")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].request_status, "pending")

    def test_mark_status_methods_delegate_to_repository(self) -> None:
        repository = FakeContractRequestRepository()
        service = ContractRequestService(repository)

        drafting_started = service.mark_pending(10)
        self.assertEqual(drafting_started.request_status, "pending")
        self.assertEqual(repository.updated, (10, "pending"))

        completed = service.mark_completed(11)
        self.assertEqual(completed.request_status, "completed")
        self.assertEqual(repository.updated, (11, "completed"))

        failed = service.mark_failed(12)
        self.assertEqual(failed.request_status, "failed")
        self.assertEqual(repository.updated, (12, "failed"))


if __name__ == "__main__":
    unittest.main()


