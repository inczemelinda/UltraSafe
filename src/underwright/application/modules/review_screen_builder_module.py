from __future__ import annotations

from underwright.application.services.review_view_service import ReviewViewService
from underwright.domain.contract_case_context import ContractCaseContext
from underwright.domain.module_result import ModuleResult


class ReviewScreenBuilderModule:
    """Builds and stores the contract review screen model in case context."""

    def __init__(self, review_view_service: ReviewViewService | None = None) -> None:
        self.review_view_service = review_view_service or ReviewViewService()

    def build(self, case_context: ContractCaseContext) -> ModuleResult:
        view = self.review_view_service.build_contract_review_view(case_context)
        case_context.review_state.contract_review_view = view
        return ModuleResult(
            module_name="ReviewScreenBuilderModule",
            status="success",
            summary="Built contract review screen view.",
            source_fields_used=[
                "case_metadata",
                "source_inputs",
                "reference_data",
                "domain_payload.contract_generation_payload",
                "generated_outputs.contract_draft",
                "audit_trail",
            ],
        )


__all__ = ["ReviewScreenBuilderModule"]
