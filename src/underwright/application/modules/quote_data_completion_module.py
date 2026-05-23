from __future__ import annotations

from typing import Any

from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.module_result import ModuleResult
from underwright.domain.quote_request import QuoteRequest


class QuoteDataCompletionModule:
    """Checks required quote intake fields before final quote evaluation."""

    module_name = "QuoteDataCompletionModule"

    required_fields_by_step: dict[str, dict[str, list[str]]] = {
        "client_data": {
            "client_data": [
                "full_name",
                "email",
                "phone",
            ],
        },
        "asset_data": {
            "asset_data": [
                "asset_type",
                "usage_type",
                "construction_type",
                "year_built",
                "area_sqm",
                "declared_value",
                "occupancy",
            ],
        },
    }

    def evaluate(
        self,
        quote_request: QuoteRequest,
        case_context: QuoteCaseContext,
    ) -> ModuleResult:
        mandatory_data_status = self._build_mandatory_data_status(quote_request)
        is_complete = mandatory_data_status["is_complete"]

        quote_request.mandatory_data_status.clear()
        quote_request.mandatory_data_status.update(mandatory_data_status)

        case_context.domain_payload.quote_intake_payload = quote_request.model_dump(
            mode="json"
        )
        case_context.domain_payload.quote_evaluation["mandatory_data_status"] = (
            mandatory_data_status
        )

        case_context.checks_and_warnings.missing_required_fields = (
            mandatory_data_status["missing_fields"]
        )

        if is_complete:
            if quote_request.request_status in {"draft", "pricing_in_progress"}:
                quote_request.request_status = "quote_ready"
            case_context.case_metadata.status = "quote_ready"
            summary = "Quote mandatory data is complete."
        else:
            if quote_request.request_status not in {"draft", "pricing_in_progress"}:
                quote_request.request_status = "pricing_in_progress"
            case_context.case_metadata.status = quote_request.request_status
            summary = "Quote mandatory data is incomplete."

        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary=summary,
            source_fields_used=[
                "quote_request.client_data",
                "quote_request.asset_data",
                "quote_request.mandatory_data_status",
                "quote_case_context.domain_payload.quote_evaluation",
            ],
        )

    def _build_mandatory_data_status(
        self,
        quote_request: QuoteRequest,
    ) -> dict[str, Any]:
        completed_fields_by_step: dict[str, list[str]] = {}
        missing_fields_by_step: dict[str, list[str]] = {}
        flat_missing_fields: list[str] = []

        for step_name, sections in self.required_fields_by_step.items():
            completed_fields_by_step[step_name] = []
            missing_fields_by_step[step_name] = []

            for section_name, required_fields in sections.items():
                section_data = getattr(quote_request, section_name)

                for field_name in required_fields:
                    value = section_data.get(field_name)

                    if self._has_value(value):
                        completed_fields_by_step[step_name].append(field_name)
                    else:
                        missing_path = f"{section_name}.{field_name}"
                        missing_fields_by_step[step_name].append(missing_path)
                        flat_missing_fields.append(missing_path)

        return {
            "is_complete": len(flat_missing_fields) == 0,
            "completed_fields_by_step": completed_fields_by_step,
            "missing_fields_by_step": missing_fields_by_step,
            "missing_fields": flat_missing_fields,
        }

    def _has_value(self, value: Any) -> bool:
        return value is not None and value != "" and value != [] and value != {}
