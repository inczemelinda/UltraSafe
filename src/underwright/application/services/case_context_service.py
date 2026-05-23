from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from underwright.domain.case_context_base import (
    AuditEntry,
    BaseCaseContext,
)
from underwright.domain.claim_case_context import (
    ClaimCaseContext,
    ClaimDomainPayload,
    ClaimGeneratedOutputs,
    ClaimSourceInputs,
)
from underwright.domain.contract_case_context import (
    ContractCaseContext,
    ContractDomainPayload,
    ContractGeneratedOutputs,
    ContractSourceInputs,
)
from underwright.domain.quote_case_context import (
    QuoteCaseContext,
    QuoteDomainPayload,
    QuoteGeneratedOutputs,
    QuoteSourceInputs,
)


class CaseContextFactory:
    """Creates in-memory Underwright case contexts."""

    def create_contract_case_context_from_payload(
        self,
        payload: dict[str, Any],
        *,
        contract_id: UUID | None = None,
        case_id: UUID | None = None,
    ) -> ContractCaseContext:
        # Use caller ids when replaying an existing case.
        public_contract_id = contract_id or uuid4()
        # Template payloads still carry the contract number here.
        contract_number = payload.get("contract_meta", {}).get("contract_id")
        context = ContractCaseContext(
            source_inputs=ContractSourceInputs(contract_id=public_contract_id),
            domain_payload=ContractDomainPayload(
                contract_generation_payload=payload,
            ),
            generated_outputs=ContractGeneratedOutputs(),
        )
        # Case id tracks the workflow instance.
        context.case_metadata.case_id = case_id or uuid4()
        context.case_metadata.status = "payload_ready"
        # Record both ids for audit/debugging.
        self.append_audit_entry(
            context,
            event_type="case_context_created",
            module_or_service="CaseContextFactory",
            summary="Contract case context created from payload.",
            metadata={
                "contract_id": str(public_contract_id),
                "contract_number": contract_number,
            },
        )
        self.append_audit_entry(
            context,
            event_type="contract_payload_attached",
            module_or_service="CaseContextFactory",
            summary="Canonical contract generation payload attached.",
            metadata={
                "payload_path": (
                    "contract_case_context.domain_payload.contract_generation_payload"
                ),
                "top_level_sections": list(payload.keys()),
            },
        )
        return context

    def create_contract_case_context_from_contract_id(
        self,
        contract_id: UUID,
        *,
        case_id: UUID | None = None,
        status: str = "started",
    ) -> ContractCaseContext:
        context = ContractCaseContext(
            source_inputs=ContractSourceInputs(
                # Same id is used by the workflow and DB.
                contract_id=contract_id,
            ),
            domain_payload=ContractDomainPayload(),
            generated_outputs=ContractGeneratedOutputs(),
        )
        # Every workflow run gets its own case id.
        context.case_metadata.case_id = case_id or uuid4()
        context.case_metadata.status = status
        # Keep the contract id visible in audit metadata.
        self.append_audit_entry(
            context,
            event_type="case_context_created",
            module_or_service="CaseContextFactory",
            summary="Contract case context created from contract ID.",
            metadata={
                "contract_id": str(contract_id),
            },
        )
        return context

    def create_quote_case_context_from_request_id(
        self,
        request_id: UUID,
        *,
        client_id: int | str | UUID | None = None,
        case_id: UUID | None = None,
        status: str = "started",
    ) -> QuoteCaseContext:
        context = QuoteCaseContext(
            source_inputs=QuoteSourceInputs(
                request_id=request_id,
                client_id=client_id,
            ),
            domain_payload=QuoteDomainPayload(),
            generated_outputs=QuoteGeneratedOutputs(),
        )
        context.case_metadata.case_id = case_id or uuid4()
        context.case_metadata.status = status
        self.append_audit_entry(
            context,
            event_type="case_context_created",
            module_or_service="CaseContextFactory",
            summary="Quote case context created from quote request ID.",
            metadata={
                "request_id": str(request_id),
                "client_id": str(client_id) if client_id is not None else None,
            },
        )
        return context

    def create_claim_case_context_from_request_id(
        self,
        request_id: UUID,
        *,
        client_id: int | str | UUID | None = None,
        case_id: UUID | None = None,
        status: str = "started",
    ) -> ClaimCaseContext:
        context = ClaimCaseContext(
            source_inputs=ClaimSourceInputs(
                request_id=request_id,
                client_id=client_id,
            ),
            domain_payload=ClaimDomainPayload(),
            generated_outputs=ClaimGeneratedOutputs(),
        )
        context.case_metadata.case_id = case_id or uuid4()
        context.case_metadata.status = status
        self.append_audit_entry(
            context,
            event_type="case_context_created",
            module_or_service="CaseContextFactory",
            summary="Claim case context created from claim request ID.",
            metadata={
                "request_id": str(request_id),
                "client_id": str(client_id) if client_id is not None else None,
            },
        )
        return context

    def append_audit_entry(
        self,
        context: BaseCaseContext,
        *,
        event_type: str,
        module_or_service: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        # Audit entries are part of the case context state.
        entry = AuditEntry(
            event_type=event_type,
            module_or_service=module_or_service,
            summary=summary,
            metadata=metadata or {},
        )
        context.audit_trail.append(entry)
        return entry


class CaseContextService:
    """Persists and updates existing Underwright case contexts."""

    def __init__(self, case_context_repository):
        self.case_context_repository = case_context_repository

    def save_case_context(self, context: BaseCaseContext) -> BaseCaseContext:
        if self.case_context_repository is None:
            raise RuntimeError(
                "CaseContext repository is not configured for persistence."
            )
        return self.case_context_repository.save_case_context(context)

    def get_case_context(self, case_id: UUID | str) -> BaseCaseContext:
        return self.case_context_repository.get_case_context_by_case_id(case_id)

    def get_latest_claim_case_context_by_request_id(
        self,
        request_id: UUID | str,
    ) -> ClaimCaseContext:
        return (
            self.case_context_repository.get_latest_claim_case_context_by_request_id(
                request_id
            )
        )

    def get_latest_claim_case_context_by_evidence_reply_token(
        self,
        reply_token: str,
    ) -> ClaimCaseContext:
        return self.case_context_repository.get_latest_claim_case_context_by_evidence_reply_token(
            reply_token
        )

    def update_section(
        self,
        context: BaseCaseContext,
        section_name: str,
        values: dict[str, Any],
    ) -> BaseCaseContext:
        # Sections are Pydantic models on concrete contexts.
        section = getattr(context, section_name, None)
        if section is None:
            raise ValueError(f"Unknown case context section: {section_name}")

        self._assign_values(section, values)
        return context

    def _assign_values(self, target: object, values: dict[str, Any]) -> None:
        # Keep updates explicit at the section boundary.
        for key, value in values.items():
            setattr(target, key, value)


__all__ = ["CaseContextFactory", "CaseContextService"]
