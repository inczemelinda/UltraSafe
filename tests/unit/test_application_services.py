from __future__ import annotations

from datetime import date
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from uuid import UUID

from underwright.application.services.audit_service import AuditService
from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.contract_data_service import ContractDataService
from underwright.application.services.template_service import TemplateService
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.models import Template
from underwright.infrastructure.templates.renderer import PadTemplateRenderer

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000001")


class FakeContractRepository:
    def __init__(self) -> None:
        self.requested_contract_id = None

    def get_contract_context_source(self, contract_id: UUID):
        self.requested_contract_id = contract_id
        return SimpleNamespace(
            contract=SimpleNamespace(
                customer_id=11,
                insured_asset_id=22,
                effective_date=date(2026, 5, 1),
            )
        )


class FakeTemplateRepository:
    def get_active_template(self, template_code: str) -> Template:
        return Template(
            id=3,
            template_code=template_code,
            name="PAD Standard RO",
            version="1.0",
            document_type="insurance_contract",
            content="Poliță: {{contract_meta.contract_id}}",
            created_at=datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
        )


class FakeCaseContextRepository:
    def __init__(self) -> None:
        self.saved_context = None

    def save_case_context(self, context) -> None:
        self.saved_context = context

    def get_case_context_by_case_id(self, case_id: str):
        if self.saved_context is None:
            raise ValueError(f"CaseContext with case_id {case_id} not found")
        return self.saved_context

    def get_latest_claim_case_context_by_request_id(self, request_id: str):
        if self.saved_context is None:
            raise ValueError(f"ClaimCaseContext with request_id {request_id} not found")
        return self.saved_context


class ApplicationServicesTestCase(unittest.TestCase):
    def test_contract_data_service_wraps_contract_repository(self) -> None:
        repository = FakeContractRepository()
        service = ContractDataService(repository)
        context = CaseContextFactory().create_contract_case_context_from_contract_id(
            CONTRACT_ID
        )

        result = service.load_contract_source(context)

        self.assertIs(result, context)
        self.assertEqual(repository.requested_contract_id, CONTRACT_ID)
        self.assertIsNotNone(context.reference_data.contract_source)
        self.assertEqual(context.source_inputs.client_id, 11)
        self.assertEqual(context.source_inputs.insured_asset_id, 22)

    def test_template_service_loads_metadata_and_delegates_rendering(self) -> None:
        service = TemplateService(
            template_repository=FakeTemplateRepository(),
            template_renderer=PadTemplateRenderer(),
        )

        template = service.get_contract_template("PAD_STANDARD_RO")
        rendered = service.render(
            template.content,
            {"contract_meta": {"contract_id": "PAD-001"}},
        )
        metadata = service.get_template_metadata(template)

        self.assertEqual(rendered, "Poliță: PAD-001")
        self.assertEqual(metadata["template_code"], "PAD_STANDARD_RO")
        self.assertEqual(metadata["template_version"], "1.0")

    def test_case_context_and_audit_services_update_in_memory_context(self) -> None:
        case_context_factory = CaseContextFactory()
        case_context_service = CaseContextService(FakeCaseContextRepository())
        audit_service = AuditService()
        context = case_context_factory.create_contract_case_context_from_contract_id(
            CONTRACT_ID,
        )

        case_context_service.update_section(
            context,
            "domain_payload",
            {"contract_generation_payload": {"document_type": "insurance_contract"}},
        )
        entry = audit_service.payload_built(context, {"sections": ["document_type"]})

        self.assertIsInstance(context.case_metadata.case_id, UUID)
        self.assertEqual(context.source_inputs.contract_id, CONTRACT_ID)
        self.assertEqual(
            context.domain_payload.contract_generation_payload["document_type"],
            "insurance_contract",
        )
        self.assertEqual(entry.event_type, "payload_built")
        self.assertEqual(entry.module_or_service, "ContractPayloadBuilder")
        self.assertEqual(entry.summary, "Canonical contract generation payload built.")
        self.assertIn("timestamp", entry.model_dump(mode="json"))
        self.assertEqual(
            [audit_entry.event_type for audit_entry in context.audit_trail],
            ["case_context_created", "payload_built"],
        )

    def test_case_context_service_persists_and_loads_via_repository(self) -> None:
        repository = FakeCaseContextRepository()
        case_context_factory = CaseContextFactory()
        case_context_service = CaseContextService(repository)
        context = case_context_factory.create_contract_case_context_from_contract_id(
            CONTRACT_ID
        )

        case_context_service.save_case_context(context)
        loaded = case_context_service.get_case_context(context.case_metadata.case_id)

        self.assertIs(loaded, context)
        self.assertIs(repository.saved_context, context)

    def test_case_context_service_loads_latest_claim_context_by_request_id(
        self,
    ) -> None:
        repository = FakeCaseContextRepository()
        case_context_service = CaseContextService(repository)
        context = ClaimCaseContext(source_inputs={"request_id": CONTRACT_ID})
        repository.save_case_context(context)

        loaded = case_context_service.get_latest_claim_case_context_by_request_id(
            CONTRACT_ID
        )

        self.assertIs(loaded, context)
