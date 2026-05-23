from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from underwright.application.modules.quote_approval_module import QuoteApprovalModule
from underwright.application.modules.quote_data_completion_module import (
    QuoteDataCompletionModule,
)
from underwright.application.modules.quote_document_generation_module import (
    QuoteDocumentGenerationModule,
)
from underwright.application.modules.quote_payload_builder import QuotePayloadBuilder
from underwright.application.modules.policy_rules_module import PolicyRulesModule
from underwright.application.modules.pricing_calculation_module import (
    PricingCalculationModule,
)
from underwright.application.ports import QuoteDocumentRepository
from underwright.application.services.audit_service import AuditService
from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.quote_data_service import QuoteDataService
from underwright.application.services.quote_request_service import QuoteRequestService
from underwright.application.services.template_service import TemplateService
from underwright.domain.module_result import ModuleResult
from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.quote_document import QuoteDocument


DEFAULT_QUOTE_CONTRACT_TEMPLATE_CODE = "PAD_STANDARD_RO"


class QuoteWorkflowResult(BaseModel):
    """Return object for the quote-first generation workflow."""

    case_context: QuoteCaseContext
    quote_document: QuoteDocument | None = None
    module_results: list[ModuleResult] = Field(default_factory=list)
    status: str = "started"


class QuoteWorkflow:
    """Orchestrates one quote generation case.

    Quote is the active pre-contract lifecycle. A quote document is unsigned;
    after signing, a later workflow can create the contract artifact.
    """

    def __init__(
        self,
        quote_request_service: QuoteRequestService,
        quote_data_service: QuoteDataService,
        template_service: TemplateService,
        quote_document_repository: QuoteDocumentRepository,
        quote_data_completion_module: QuoteDataCompletionModule,
        policy_rules_module: PolicyRulesModule,
        pricing_calculation_module: PricingCalculationModule,
        quote_approval_module: QuoteApprovalModule,
        quote_payload_builder: QuotePayloadBuilder,
        quote_document_generation_module: QuoteDocumentGenerationModule,
        case_context_factory: CaseContextFactory,
        case_context_service: CaseContextService,
        audit_service: AuditService,
    ) -> None:
        self.quote_request_service = quote_request_service
        self.quote_data_service = quote_data_service
        self.template_service = template_service
        self.quote_document_repository = quote_document_repository
        self.quote_data_completion_module = quote_data_completion_module
        self.policy_rules_module = policy_rules_module
        self.pricing_calculation_module = pricing_calculation_module
        self.quote_approval_module = quote_approval_module
        self.quote_payload_builder = quote_payload_builder
        self.quote_document_generation_module = quote_document_generation_module
        self.case_context_factory = case_context_factory
        self.case_context_service = case_context_service
        self.audit_service = audit_service

    def run(
        self,
        request_id: UUID,
        template_code: str,
    ) -> QuoteWorkflowResult:
        quote_request = self.quote_request_service.get_quote_request_detail(request_id)
        original_status = quote_request.request_status
        case_context = (
            self.case_context_factory.create_quote_case_context_from_request_id(
                request_id,
                client_id=quote_request.client_id,
            )
        )
        module_results: list[ModuleResult] = []

        self.audit_service.quote_workflow_started(
            case_context,
            {
                "request_id": str(request_id),
                "template_code": template_code,
            },
        )

        self.quote_data_service.attach_quote_request(case_context, quote_request)
        self.audit_service.quote_request_loaded(
            case_context,
            {"request_id": str(request_id)},
        )

        completion_result = self.quote_data_completion_module.evaluate(
            quote_request,
            case_context,
        )
        module_results.append(completion_result)
        if completion_result.status == "failed":
            return self._failed_result(case_context, quote_request.request_id, module_results)

        rules_result = self.policy_rules_module.evaluate(case_context)
        module_results.append(rules_result)
        if rules_result.status == "failed":
            return self._failed_result(case_context, quote_request.request_id, module_results)

        pricing_result = self.pricing_calculation_module.calculate(
            quote_request,
            case_context,
        )
        module_results.append(pricing_result)
        if pricing_result.status == "failed":
            return self._failed_result(case_context, quote_request.request_id, module_results)

        if not quote_request.mandatory_data_status.get("is_complete", False):
            self.quote_request_service.save_step_updates(quote_request)
            self.case_context_service.save_case_context(case_context)
            return QuoteWorkflowResult(
                case_context=case_context,
                quote_document=None,
                module_results=module_results,
                status=quote_request.request_status,
            )

        approval_result = self.quote_approval_module.evaluate(
            quote_request,
            case_context,
        )
        module_results.append(approval_result)
        if approval_result.status == "failed":
            return self._failed_result(case_context, quote_request.request_id, module_results)
        self._record_system_decision_if_needed(
            quote_request,
            case_context,
            previous_status=original_status,
        )

        payload_result = self.quote_payload_builder.build(case_context)
        module_results.append(payload_result)
        if payload_result.status == "failed":
            return self._failed_result(case_context, quote_request.request_id, module_results)

        self.audit_service.quote_payload_built(
            case_context,
            {
                "payload_path": (
                    "quote_case_context.domain_payload.quote_generation_payload"
                ),
                "top_level_sections": list(
                    case_context.domain_payload.quote_generation_payload.keys()
                ),
            },
        )

        template = self.template_service.get_template(template_code)
        template_metadata = self.template_service.get_template_metadata(template)
        self.case_context_service.update_section(
            case_context,
            "source_inputs",
            {"template_id": template.id},
        )
        self.case_context_service.update_section(
            case_context,
            "reference_data",
            {"quote_template": template},
        )
        self.audit_service.record(
            case_context,
            event_type="template_loaded",
            module_or_service="TemplateService",
            summary="Quote template loaded.",
            metadata=template_metadata,
        )

        generation_result = self.quote_document_generation_module.generate_document(
            case_context
        )
        module_results.append(generation_result)
        if generation_result.status == "failed":
            return self._failed_result(case_context, quote_request.request_id, module_results)

        document_output = case_context.generated_outputs.quote_document
        quote_document = QuoteDocument(
            quote_request_id=request_id,
            template_id=int(template.id or 0),
            generation_status="success",
            rendered_text=(
                document_output.final_document_text
                or document_output.draft_quote
                or ""
            ),
            rendered_json={
                "case_metadata": case_context.case_metadata.model_dump(mode="json"),
                "quote_generation_payload": (
                    case_context.domain_payload.quote_generation_payload
                ),
                "approval_decision": case_context.domain_payload.approval_decision,
                "template_used": document_output.template_used,
                "payload_reference": document_output.mapped_input_fields,
                "generation_metadata": document_output.generation_metadata,
                "generation_rationale": document_output.generation_rationale,
                "llm_drafting_summary": document_output.llm_drafting_summary,
                "audit_trail": self._serialized_audit_trail(
                    case_context.audit_trail
                ),
            },
        )

        saved_document = self.quote_document_repository.save(quote_document)
        self.audit_service.quote_document_saved(
            case_context,
            {"quote_document_id": saved_document.id},
        )
        document_output.quote_document_reference = {
            "id": saved_document.id,
            "quote_request_id": str(saved_document.quote_request_id),
            "template_id": saved_document.template_id,
            "file_url": saved_document.file_url,
        }
        saved_document.rendered_json["audit_trail"] = self._serialized_audit_trail(
            case_context.audit_trail
        )
        saved_document.rendered_json["case_metadata"] = (
            case_context.case_metadata.model_dump(mode="json")
        )

        self.case_context_service.update_section(
            case_context,
            "case_metadata",
            {"status": quote_request.request_status},
        )
        self.quote_request_service.save_step_updates(quote_request)
        self.case_context_service.save_case_context(case_context)

        return QuoteWorkflowResult(
            case_context=case_context,
            quote_document=saved_document,
            module_results=module_results,
            status=quote_request.request_status,
        )

    def _failed_result(
        self,
        case_context: QuoteCaseContext,
        request_id: UUID,
        module_results: list[ModuleResult],
    ) -> QuoteWorkflowResult:
        self.case_context_service.update_section(
            case_context,
            "case_metadata",
            {"status": "failed"},
        )
        self.quote_request_service.mark_failed(request_id)
        self.case_context_service.save_case_context(case_context)
        return QuoteWorkflowResult(
            case_context=case_context,
            quote_document=None,
            module_results=module_results,
            status="failed",
        )

    def _record_system_decision_if_needed(
        self,
        quote_request,
        case_context: QuoteCaseContext,
        *,
        previous_status: str,
    ) -> None:
        if quote_request.request_status != "disapproved":
            return
        if previous_status == "disapproved":
            return

        approval_decision = case_context.domain_payload.approval_decision
        if approval_decision.get("decision_source") != "policy_rules_module":
            return

        reasons = approval_decision.get("reasons") or []
        reason = (
            "Hard quote eligibility rule failed: " + ", ".join(map(str, reasons))
            if reasons
            else "Hard quote eligibility rule failed."
        )
        self.quote_request_service.record_system_decision(
            quote_request.request_id,
            previous_status=previous_status,
            decision_status="disapproved",
            reason=reason,
            metadata={
                "decision_source": "policy_rules_module",
                "approval_decision": approval_decision,
                "rule_outcomes": case_context.domain_payload.rule_outcomes,
            },
        )

    def _serialized_audit_trail(self, audit_trail: list[Any]) -> list[dict[str, Any]]:
        return [
            entry.model_dump(mode="json") if hasattr(entry, "model_dump") else entry
            for entry in audit_trail
        ]


__all__ = ["QuoteWorkflow", "QuoteWorkflowResult"]
