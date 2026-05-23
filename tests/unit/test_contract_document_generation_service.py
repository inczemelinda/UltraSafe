from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from underwright.application.services.contract_document_generation_service import (
    ContractDocumentGenerationService,
)
from underwright.domain.generated_document_lifecycle import GeneratedDocumentReadModel
from underwright.domain.models import GeneratedDocument
from underwright.domain.module_result import ModuleResult
from tests.unit.test_contract_query_service import _contract as contract_read_model
from tests.unit.test_contract_payload_builder import make_source

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000011")


class FakeContractRepository:
    def __init__(self, *, source_complete: bool = True) -> None:
        self.source_complete = source_complete

    def get_contract_by_id(self, contract_id: UUID):
        return contract_read_model()

    def get_contract_context_source(self, contract_id: UUID):
        if not self.source_complete:
            raise ValueError("Pricing not found")
        return make_source()


class FakeWorkflow:
    def __init__(
        self,
        document: GeneratedDocument | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self.document = document or _document()
        self.raises = raises
        self.calls: list[tuple[UUID, str]] = []

    def run(self, contract_id: UUID, template_code: str):
        self.calls.append((contract_id, template_code))
        if self.raises is not None:
            raise self.raises
        return SimpleNamespace(
            generated_document=self.document,
            module_results=[
                ModuleResult(
                    module_name="ContractPayloadBuilder",
                    status="success",
                    summary="Built payload.",
                )
            ],
        )


def test_generation_service_uses_contract_workflow() -> None:
    workflow = FakeWorkflow()
    service = ContractDocumentGenerationService(
        contract_repository=FakeContractRepository(),
        contract_workflow=workflow,
    )

    result = service.generate(CONTRACT_ID, template_code="PAD_PROPERTY_RO")

    assert result.status == "success"
    assert workflow.calls == [(CONTRACT_ID, "PAD_PROPERTY_RO")]
    assert result.document is not None
    assert result.document.contract_id == CONTRACT_ID


def test_generation_service_returns_persisted_metadata() -> None:
    service = ContractDocumentGenerationService(
        contract_repository=FakeContractRepository(),
        contract_workflow=FakeWorkflow(),
    )

    result = service.generate(CONTRACT_ID, template_code="PAD_PROPERTY_RO")

    assert isinstance(result.document, GeneratedDocumentReadModel)
    assert result.document.template_code == "PAD_PROPERTY_RO"
    assert result.document.template_version == "1.0"
    assert result.document.template_version_hash == "template-hash"
    assert result.document.content_hash == "content-hash"
    assert result.document.payload_snapshot["document_type"] == "insurance_contract"
    assert result.document.generation_metadata["generation_mode"] == "template"


def test_generation_service_failure_does_not_return_partial_document() -> None:
    workflow = FakeWorkflow(raises=KeyError("missing placeholder"))
    service = ContractDocumentGenerationService(
        contract_repository=FakeContractRepository(),
        contract_workflow=workflow,
    )

    result = service.generate(CONTRACT_ID, template_code="PAD_PROPERTY_RO")

    assert result.status == "failed"
    assert result.document is None
    assert result.validation.can_generate is False
    assert result.validation.blocking_errors[-1].code == "TEMPLATE_PLACEHOLDER_MISSING"


def test_generation_service_blocks_incomplete_contract_source_before_workflow() -> None:
    workflow = FakeWorkflow()
    service = ContractDocumentGenerationService(
        contract_repository=FakeContractRepository(source_complete=False),
        contract_workflow=workflow,
    )

    result = service.generate(CONTRACT_ID, template_code="PAD_PROPERTY_RO")

    assert result.status == "failed"
    assert result.document is None
    assert workflow.calls == []
    assert result.validation.blocking_errors[-1].code == "CONTRACT_SOURCE_INCOMPLETE"


def test_generation_service_requires_persisted_document_id() -> None:
    document = _document()
    document.id = None
    service = ContractDocumentGenerationService(
        contract_repository=FakeContractRepository(),
        contract_workflow=FakeWorkflow(document=document),
    )

    with pytest.raises(ValueError, match="GeneratedDocument id is required"):
        service.generate(CONTRACT_ID, template_code="PAD_PROPERTY_RO")


def _document() -> GeneratedDocument:
    now = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
    payload = {"document_type": "insurance_contract"}
    metadata = {"generation_mode": "template"}
    return GeneratedDocument(
        id=77,
        contract_id=CONTRACT_ID,
        template_id=22,
        generation_status="success",
        rendered_text="Rendered contract",
        rendered_json={
            "contract_generation_payload": payload,
            "template_used": {
                "template_code": "PAD_PROPERTY_RO",
                "template_version": "1.0",
            },
            "template_version_hash": "template-hash",
            "generation_metadata": metadata,
        },
        template_code="PAD_PROPERTY_RO",
        template_version="1.0",
        template_version_hash="template-hash",
        payload_snapshot=payload,
        generation_metadata=metadata,
        content_hash="content-hash",
        created_at=now,
        updated_at=now,
    )
