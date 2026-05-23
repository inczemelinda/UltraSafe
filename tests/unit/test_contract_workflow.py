from __future__ import annotations

from datetime import datetime, timezone
import unittest
from uuid import UUID

from underwright.application.modules.contract_drafting_module import (
    ContractDraftingModule,
)
from underwright.application.modules.review_screen_builder_module import (
    ReviewScreenBuilderModule,
)
from underwright.application.services.review_view_service import ReviewViewService
from underwright.application.services.audit_service import AuditService
from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.contract_data_service import ContractDataService
from underwright.application.services.template_service import TemplateService
from underwright.application.workflows.contract_workflow import ContractWorkflow
from underwright.domain.module_result import ModuleResult
from underwright.domain.models import Template
from underwright.infrastructure.templates.renderer import PadTemplateRenderer
from tests.unit.test_contract_payload_builder import make_source

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000001")


class FakeContractRepository:
    def get_contract_context_source(self, contract_id: UUID):
        return make_source()


class FakePayloadBuilder:
    payload = {
        "document_type": "insurance_contract",
        "generation_mode": "hybrid_template_plus_llm",
        "contract_meta": {"contract_id": "PAD-001"},
    }

    def build(self, case_context) -> ModuleResult:
        case_context.domain_payload.contract_generation_payload = self.payload
        return ModuleResult(
            module_name="ContractPayloadBuilder",
            status="success",
            summary="Built contract_generation_payload.",
            source_fields_used=["reference_data.contract_source"],
        )


class FakeTemplateRepository:
    def get_active_template(self, template_code: str) -> Template:
        return Template(
            id=22,
            template_code=template_code,
            name="PAD Standard RO",
            version="1.0",
            document_type="insurance_contract",
            content="Poliță: {{contract_meta.contract_id}}",
            created_at=datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
        )


class FakeGeneratedDocumentRepository:
    def __init__(self) -> None:
        self.saved_document = None

    def save(self, document):
        self.saved_document = document
        return document


class FakeCaseContextRepository:
    def __init__(self) -> None:
        self.saved_contexts = []

    def save_case_context(self, context) -> None:
        self.saved_contexts.append(context.model_copy(deep=True))

    def get_case_context_by_case_id(self, case_id: str):
        for context in self.saved_contexts:
            if context.case_metadata.case_id == case_id:
                return context
        raise ValueError(f"CaseContext with case_id {case_id} not found")


class FakeSupplementaryTextGenerator:
    def generate(self, context, rendered_template: str) -> str:
        return "unused when template has no supplementary placeholder"


class FailingPayloadBuilder:
    def build(self, case_context) -> ModuleResult:
        return ModuleResult(
            module_name="ContractPayloadBuilder",
            status="failed",
            summary="Missing required source data.",
            source_fields_used=["reference_data.contract_source"],
        )


def build_workflow(
    generated_document_repository: FakeGeneratedDocumentRepository,
    payload_builder=None,
    case_context_repository: FakeCaseContextRepository | None = None,
) -> ContractWorkflow:
    template_service = TemplateService(
        template_repository=FakeTemplateRepository(),
        template_renderer=PadTemplateRenderer(),
    )
    return ContractWorkflow(
        contract_data_service=ContractDataService(FakeContractRepository()),
        template_service=template_service,
        generated_document_repository=generated_document_repository,
        contract_payload_builder=payload_builder or FakePayloadBuilder(),
        contract_drafting_module=ContractDraftingModule(
            template_service=template_service,
            supplementary_text_generator=FakeSupplementaryTextGenerator(),
            audit_service=AuditService(),
        ),
        review_screen_builder_module=ReviewScreenBuilderModule(ReviewViewService()),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(
            case_context_repository or FakeCaseContextRepository()
        ),
        audit_service=AuditService(),
    )


class ContractWorkflowTestCase(unittest.TestCase):
    def test_run_executes_contract_drafting_vertical_slice(self) -> None:
        generated_document_repository = FakeGeneratedDocumentRepository()
        case_context_repository = FakeCaseContextRepository()
        workflow = build_workflow(
            generated_document_repository,
            case_context_repository=case_context_repository,
        )

        result = workflow.run(contract_id=CONTRACT_ID, template_code="PAD_STANDARD_RO")
        document = result.generated_document

        self.assertIs(document, generated_document_repository.saved_document)
        self.assertEqual(result.status, "success")
        self.assertIsNotNone(result.review_view)
        self.assertEqual(len(result.module_results), 3)
        self.assertEqual(
            [module_result.module_name for module_result in result.module_results],
            [
                "ContractPayloadBuilder",
                "ContractDraftingModule",
                "ReviewScreenBuilderModule",
            ],
        )
        self.assertEqual(result.case_context.source_inputs.contract_id, CONTRACT_ID)
        self.assertEqual(
            result.case_context.domain_payload.contract_generation_payload,
            FakePayloadBuilder.payload,
        )
        self.assertEqual(
            result.case_context.generated_outputs.contract_draft.generated_document_reference[
                "contract_id"
            ],
            document.contract_id,
        )
        self.assertEqual(document.rendered_text, "Poliță: PAD-001")
        self.assertNotIn("{{", document.rendered_text)
        self.assertNotIn("}}", document.rendered_text)
        self.assertEqual(
            document.rendered_json["contract_generation_payload"],
            FakePayloadBuilder.payload,
        )
        self.assertEqual(
            document.rendered_json["template_used"]["template_code"],
            "PAD_STANDARD_RO",
        )
        self.assertEqual(
            document.rendered_json["payload_reference"]["payload_path"],
            "contract_case_context.domain_payload.contract_generation_payload",
        )
        self.assertIsNotNone(
            result.case_context.generated_outputs.contract_draft.llm_drafting_summary
        )
        self.assertTrue(document.rendered_json["generation_metadata"])
        self.assertEqual(
            [
                entry["event_type"]
                for entry in document.rendered_json["audit_trail"]
            ],
            [
                "case_context_created",
                "workflow_started",
                "source_data_loaded",
                "contract_payload_attached",
                "payload_built",
                "template_loaded",
                "template_rendered",
                "draft_generated",
                "generated_document_saved",
            ],
        )
        self.assertEqual(
            document.rendered_json["audit_trail"][1]["module_or_service"],
            "ContractWorkflow",
        )
        self.assertIn("timestamp", document.rendered_json["audit_trail"][0])
        self.assertEqual(
            document.rendered_json["audit_trail"][5]["metadata"]["template_version"],
            "1.0",
        )
        self.assertEqual(len(case_context_repository.saved_contexts), 1)
        self.assertEqual(
            case_context_repository.saved_contexts[0].case_metadata.status,
            "success",
        )

    def test_run_stops_early_when_payload_builder_fails(self) -> None:
        generated_document_repository = FakeGeneratedDocumentRepository()
        case_context_repository = FakeCaseContextRepository()
        workflow = build_workflow(
            generated_document_repository,
            payload_builder=FailingPayloadBuilder(),
            case_context_repository=case_context_repository,
        )

        result = workflow.run(contract_id=CONTRACT_ID, template_code="PAD_STANDARD_RO")

        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.generated_document)
        self.assertEqual(len(result.module_results), 1)
        self.assertEqual(
            result.module_results[0].module_name,
            "ContractPayloadBuilder",
        )
        self.assertEqual(
            result.case_context.case_metadata.status,
            "failed",
        )
        self.assertEqual(len(case_context_repository.saved_contexts), 1)
        self.assertEqual(
            case_context_repository.saved_contexts[0].case_metadata.status,
            "failed",
        )
