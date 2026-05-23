from __future__ import annotations

from datetime import timezone
from datetime import datetime
import hashlib
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from underwright.application.modules.contract_drafting_module import (
    ContractDraftingModule,
)
from underwright.application.modules.review_screen_builder_module import (
    ReviewScreenBuilderModule,
)
from underwright.application.ports import (
    ContractPayloadBuilderPort,
    GeneratedDocumentRepository,
)
from underwright.application.services.audit_service import AuditService
from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.contract_data_service import ContractDataService
from underwright.application.services.template_service import TemplateService
from underwright.domain.contract_case_context import ContractCaseContext
from underwright.domain.module_result import ModuleResult
from underwright.domain.models import GeneratedDocument
from underwright.domain.review_models import ContractReviewView


class ContractWorkflowResult(BaseModel):
    """Return object for the contract drafting vertical slice.

    Application code receives both the saved document and the case context that
    carried the workflow state.
    """

    case_context: ContractCaseContext
    generated_document: GeneratedDocument | None = None
    review_view: ContractReviewView | None = None
    module_results: list[ModuleResult] = Field(default_factory=list)
    status: str = "started"


class ContractWorkflow:
    """Orchestrates one contract drafting case.

    This class owns ordering only. It does not query Postgres directly, shape
    the payload itself, or render templates itself. Those jobs live in services
    and modules so the workflow stays easy to read as a vertical slice.
    """

    def __init__(
        self,
        contract_data_service: ContractDataService,
        template_service: TemplateService,
        generated_document_repository: GeneratedDocumentRepository,
        contract_payload_builder: ContractPayloadBuilderPort,
        contract_drafting_module: ContractDraftingModule,
        review_screen_builder_module: ReviewScreenBuilderModule,
        case_context_factory: CaseContextFactory,
        case_context_service: CaseContextService,
        audit_service: AuditService,
    ) -> None:
        self.contract_data_service = contract_data_service
        self.template_service = template_service
        self.generated_document_repository = generated_document_repository
        self.contract_payload_builder = contract_payload_builder
        self.contract_drafting_module = contract_drafting_module
        self.review_screen_builder_module = review_screen_builder_module
        self.case_context_factory = case_context_factory
        self.case_context_service = case_context_service
        self.audit_service = audit_service

    def run(
        self,
        contract_id: UUID,
        template_code: str = "",
    ) -> ContractWorkflowResult:
        """Run the architecture-aligned contract drafting slice.

        Path:
        contract id -> ContractCaseContext -> source data -> payload -> draft
        -> generated output in case context -> persisted GeneratedDocument.
        """
        # Factory creates ids; service persists and updates later.
        case_context = (
            self.case_context_factory.create_contract_case_context_from_contract_id(
                contract_id
            )
        )
        module_results: list[ModuleResult] = []
        # Log the contract UUID used by every layer.
        self.audit_service.workflow_started(
            case_context,
            {
                "contract_id": str(contract_id),
                "template_code": template_code,
            },
        )

        # Source data is attached to reference_data.
        self.contract_data_service.load_contract_source(case_context)
        self.audit_service.source_data_loaded(
            case_context,
            {
                "contract_id": str(contract_id),
            },
        )

        # Builder writes the canonical payload into domain_payload.
        payload_result = self.contract_payload_builder.build(case_context)
        module_results.append(payload_result)
        if payload_result.status == "failed":
            return self._failed_result(case_context, module_results)

        payload = case_context.domain_payload.contract_generation_payload
        # Audit the payload path used by templates.
        self.audit_service.contract_payload_attached(
            case_context,
            {
                "payload_path": (
                    "contract_case_context.domain_payload."
                    "contract_generation_payload"
                ),
                "top_level_sections": list(payload.keys()),
            },
        )
        self.audit_service.payload_built(
            case_context,
            {"top_level_sections": list(payload.keys())},
        )

        # Template becomes reference data for drafting.
        template = self.template_service.get_contract_template(template_code)
        template_metadata = self.template_service.get_template_metadata(template)
        self.case_context_service.update_section(
            case_context,
            "source_inputs",
            {"template_id": template.id},
        )
        self.case_context_service.update_section(
            case_context,
            "reference_data",
            {"contract_template": template},
        )
        self.audit_service.template_loaded(
            case_context,
            template_metadata,
        )

        # Drafting writes generated_outputs.contract_draft.
        drafting_result = self.contract_drafting_module.generate_draft(case_context)
        module_results.append(drafting_result)
        if drafting_result.status == "failed":
            return self._failed_result(case_context, module_results)

        draft_output = case_context.generated_outputs.contract_draft
        rendered_text = (
            draft_output.final_document_text or draft_output.draft_contract or ""
        )
        template_version_hash = self._template_version_hash(template)
        content_hash = self._content_hash(rendered_text)
        now = datetime.now(timezone.utc)

        # GeneratedDocument references the UUID contract row.
        document = GeneratedDocument(
            contract_id=contract_id,
            template_id=template.id,
            generation_status="success",
            rendered_text=rendered_text,
            rendered_json={
                "case_metadata": case_context.case_metadata.model_dump(mode="json"),
                "contract_generation_payload": payload,
                "template_used": draft_output.template_used,
                "template_version_hash": template_version_hash,
                "payload_reference": draft_output.mapped_input_fields,
                "generation_metadata": draft_output.generation_metadata,
                "generation_rationale": draft_output.generation_rationale,
                "llm_drafting_summary": draft_output.llm_drafting_summary,
                "audit_trail": self._serialized_audit_trail(case_context.audit_trail),
            },
            template_code=template.template_code,
            template_version=template.version,
            template_version_hash=template_version_hash,
            payload_snapshot=payload,
            generation_metadata=draft_output.generation_metadata,
            content_hash=content_hash,
            file_url=None,
            created_at=now,
            updated_at=now,
        )

        # Persist the rendered document before saving the case context.
        saved_document = self.generated_document_repository.save(document)
        self.audit_service.generated_document_saved(
            case_context,
            {"generated_document_id": saved_document.id},
        )
        draft_output.generated_document_reference = {
            "id": saved_document.id,
            # Same UUID used by the contract table.
            "contract_id": saved_document.contract_id,
            "template_id": saved_document.template_id,
            "file_url": saved_document.file_url,
        }
        # Final case status follows persisted document status.
        self.case_context_service.update_section(
            case_context,
            "case_metadata",
            {"status": saved_document.generation_status},
        )
        saved_document.rendered_json["audit_trail"] = self._serialized_audit_trail(
            case_context.audit_trail
        )
        # Keep returned document metadata aligned with the final case state.
        saved_document.rendered_json["case_metadata"] = (
            case_context.case_metadata.model_dump(mode="json")
        )

        # Review view is derived from the case context.
        review_result = self.review_screen_builder_module.build(case_context)
        module_results.append(review_result)
        if review_result.status == "failed":
            return self._failed_result(
                case_context,
                module_results,
                generated_document=saved_document,
            )

        # Save the full workflow state last.
        self.case_context_service.save_case_context(case_context)

        return ContractWorkflowResult(
            case_context=case_context,
            generated_document=saved_document,
            review_view=case_context.review_state.contract_review_view,
            module_results=module_results,
            status=module_results[-1].status,
        )

    def _failed_result(
        self,
        case_context: ContractCaseContext,
        module_results: list[ModuleResult],
        generated_document: GeneratedDocument | None = None,
    ) -> ContractWorkflowResult:
        self.case_context_service.update_section(
            case_context,
            "case_metadata",
            {"status": "failed"},
        )
        self.case_context_service.save_case_context(case_context)
        return ContractWorkflowResult(
            case_context=case_context,
            generated_document=generated_document,
            review_view=case_context.review_state.contract_review_view,
            module_results=module_results,
            status="failed",
        )

    def _serialized_audit_trail(self, audit_trail: list[Any]) -> list[dict[str, Any]]:
        return [
            entry.model_dump(mode="json") if hasattr(entry, "model_dump") else entry
            for entry in audit_trail
        ]

    def _template_version_hash(self, template) -> str:
        source = "|".join(
            [
                str(template.template_code),
                str(template.version),
                template.content,
            ]
        )
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def _content_hash(self, rendered_text: str) -> str:
        return hashlib.sha256(rendered_text.encode("utf-8")).hexdigest()


__all__ = ["ContractWorkflow", "ContractWorkflowResult"]
