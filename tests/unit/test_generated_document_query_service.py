from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from underwright.application.services.generated_document_query_service import (
    GeneratedDocumentQueryService,
)
from underwright.domain.generated_document_lifecycle import GeneratedDocumentReadModel
from tests.unit.test_contract_query_service import _contract as contract_read_model

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000011")


class FakeContractRepository:
    def __init__(self) -> None:
        self.lookups: list[UUID] = []

    def get_contract_by_id(self, contract_id: UUID):
        self.lookups.append(contract_id)
        if contract_id != CONTRACT_ID:
            raise ValueError("Contract not found")
        return contract_read_model()


class FakeGeneratedDocumentRepository:
    def __init__(
        self,
        latest_document: GeneratedDocumentReadModel | None = None,
    ) -> None:
        self.latest_document = latest_document
        self.get_by_id_calls: list[int] = []

    def get_latest_by_contract_id(
        self,
        contract_id: UUID,
    ) -> GeneratedDocumentReadModel | None:
        return self.latest_document

    def get_by_id(self, document_id: int) -> GeneratedDocumentReadModel:
        self.get_by_id_calls.append(document_id)
        if self.latest_document is None or self.latest_document.id != document_id:
            raise ValueError("GeneratedDocument not found")
        return self.latest_document


def test_query_service_returns_latest_document_after_contract_lookup() -> None:
    contract_repository = FakeContractRepository()
    document_repository = FakeGeneratedDocumentRepository(_document(9))
    service = GeneratedDocumentQueryService(
        contract_repository=contract_repository,
        generated_document_repository=document_repository,
    )

    document = service.get_latest_for_contract(CONTRACT_ID)

    assert document is not None
    assert document.id == 9
    assert contract_repository.lookups == [CONTRACT_ID]


def test_query_service_returns_none_when_contract_has_no_document() -> None:
    service = GeneratedDocumentQueryService(
        contract_repository=FakeContractRepository(),
        generated_document_repository=FakeGeneratedDocumentRepository(None),
    )

    assert service.get_latest_for_contract(CONTRACT_ID) is None


def test_query_service_gets_document_by_id_without_contract_regeneration() -> None:
    document_repository = FakeGeneratedDocumentRepository(_document(12))
    service = GeneratedDocumentQueryService(
        contract_repository=FakeContractRepository(),
        generated_document_repository=document_repository,
    )

    document = service.get_document(12)

    assert document.id == 12
    assert document_repository.get_by_id_calls == [12]


def test_query_service_raises_for_missing_document() -> None:
    service = GeneratedDocumentQueryService(
        contract_repository=FakeContractRepository(),
        generated_document_repository=FakeGeneratedDocumentRepository(None),
    )

    with pytest.raises(ValueError, match="GeneratedDocument not found"):
        service.get_document(99)


def _document(document_id: int) -> GeneratedDocumentReadModel:
    now = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
    return GeneratedDocumentReadModel(
        id=document_id,
        contract_id=CONTRACT_ID,
        document_type="insurance_contract",
        template_id=22,
        template_code="PAD_PROPERTY_RO",
        template_version="1.0",
        template_version_hash="template-hash",
        rendered_text="Rendered contract",
        payload_snapshot={"document_type": "insurance_contract"},
        generation_metadata={"generation_mode": "template"},
        content_hash="content-hash",
        created_at=now,
        updated_at=now,
        status="success",
    )
