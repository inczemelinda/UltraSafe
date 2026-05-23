from __future__ import annotations

from typing import Any

from underwright.domain.case_context_base import AuditEntry, BaseCaseContext
from underwright.domain.contract_case_context import ContractCaseContext


class AuditService:
    """Creates lightweight audit entries for workflows."""

    def case_context_created(
        self,
        context: ContractCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="case_context_created",
            module_or_service="CaseContextService",
            summary="Contract case context created.",
            metadata=metadata,
        )

    def contract_payload_attached(
        self,
        context: ContractCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="contract_payload_attached",
            module_or_service="CaseContextService",
            summary="Canonical contract generation payload attached.",
            metadata=metadata,
        )

    def workflow_started(
        self,
        context: ContractCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="workflow_started",
            module_or_service="ContractWorkflow",
            summary="Contract drafting workflow started.",
            metadata=metadata,
        )

    def source_data_loaded(
        self,
        context: ContractCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="source_data_loaded",
            module_or_service="ContractDataService",
            summary="Normalized contract source data loaded.",
            metadata=metadata,
        )

    def payload_built(
        self,
        context: ContractCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="payload_built",
            module_or_service="ContractPayloadBuilder",
            summary="Canonical contract generation payload built.",
            metadata=metadata,
        )

    def template_loaded(
        self,
        context: ContractCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="template_loaded",
            module_or_service="TemplateService",
            summary="Contract template loaded.",
            metadata=metadata,
        )

    def template_rendered(
        self,
        context: ContractCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="template_rendered",
            module_or_service="TemplateService",
            summary="Contract template rendered with canonical payload.",
            metadata=metadata,
        )

    def draft_generated(
        self,
        context: ContractCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="draft_generated",
            module_or_service="ContractDraftingModule",
            summary="Contract draft generated.",
            metadata=metadata,
        )

    def generated_document_saved(
        self,
        context: ContractCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="generated_document_saved",
            module_or_service="GeneratedDocumentRepository",
            summary="Generated document saved.",
            metadata=metadata,
        )

    def quote_workflow_started(
        self,
        context: BaseCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="workflow_started",
            module_or_service="QuoteWorkflow",
            summary="Quote generation workflow started.",
            metadata=metadata,
        )

    def quote_request_loaded(
        self,
        context: BaseCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="quote_request_loaded",
            module_or_service="QuoteDataService",
            summary="Quote request data loaded.",
            metadata=metadata,
        )

    def quote_payload_built(
        self,
        context: BaseCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="quote_payload_built",
            module_or_service="QuotePayloadBuilder",
            summary="Quote generation payload built.",
            metadata=metadata,
        )

    def quote_document_generated(
        self,
        context: BaseCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="quote_document_generated",
            module_or_service="QuoteDocumentGenerationModule",
            summary="Unsigned quote document generated.",
            metadata=metadata,
        )

    def quote_document_saved(
        self,
        context: BaseCaseContext,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.record(
            context,
            event_type="quote_document_saved",
            module_or_service="QuoteDocumentRepository",
            summary="Quote document saved.",
            metadata=metadata,
        )

    def record(
        self,
        context: BaseCaseContext,
        event_type: str,
        module_or_service: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            event_type=event_type,
            module_or_service=module_or_service,
            summary=summary,
            metadata=metadata or {},
        )
        context.audit_trail.append(entry)
        return entry


__all__ = ["AuditService"]
