from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from underwright.application.modules.contract_drafting_module import ContractDraftingModule
from underwright.application.modules.review_screen_builder_module import ReviewScreenBuilderModule
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


class FakeTemplateRepository:
    called = False

    def get_active_template(self, template_code: str) -> Template:
        self.called = True
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

    def save_case_context(self, context):
        self.saved_contexts.append(context.model_copy(deep=True))
        return context


class FailingPayloadBuilder:
    def build(self, case_context) -> ModuleResult:
        return ModuleResult(
            module_name="ContractPayloadBuilder",
            status="failed",
            summary="Missing required source data.",
            source_fields_used=["reference_data.contract_source"],
        )


def test_workflow_fails_fast_when_required_payload_input_is_missing():
    template_repository = FakeTemplateRepository()
    generated_document_repository = FakeGeneratedDocumentRepository()
    case_context_repository = FakeCaseContextRepository()

    template_service = TemplateService(
        template_repository=template_repository,
        template_renderer=PadTemplateRenderer(),
    )

    workflow = ContractWorkflow(
        contract_data_service=ContractDataService(FakeContractRepository()),
        template_service=template_service,
        generated_document_repository=generated_document_repository,
        contract_payload_builder=FailingPayloadBuilder(),
        contract_drafting_module=ContractDraftingModule(
            template_service=template_service,
            supplementary_text_generator=None,
            audit_service=AuditService(),
        ),
        review_screen_builder_module=ReviewScreenBuilderModule(),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(case_context_repository),
        audit_service=AuditService(),
    )

    result = workflow.run(contract_id=CONTRACT_ID, template_code="PAD_STANDARD_RO")

    assert result.status == "failed"
    assert result.generated_document is None
    assert result.review_view is None

    assert len(result.module_results) == 1
    failed_result = result.module_results[0]
    assert failed_result.module_name == "ContractPayloadBuilder"
    assert failed_result.status == "failed"
    assert failed_result.summary == "Missing required source data."

    assert generated_document_repository.saved_document is None
    assert template_repository.called is False

    assert len(case_context_repository.saved_contexts) == 1
    saved_context = case_context_repository.saved_contexts[0]
    assert saved_context.case_metadata.status == "failed"
