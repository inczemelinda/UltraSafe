from __future__ import annotations

from uuid import UUID

from underwright.application.services.quote_request_service import QuoteRequestService
from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.quote_request import QuoteRequest


class QuoteDataService:
    """Loads quote request data and attaches it to QuoteCaseContext."""

    def __init__(self, quote_request_service: QuoteRequestService) -> None:
        self.quote_request_service = quote_request_service

    def attach_quote_request_data(
        self,
        context: QuoteCaseContext,
        request_id: UUID,
    ) -> QuoteCaseContext:
        quote_request = self.quote_request_service.get_quote_request_detail(request_id)
        return self.attach_quote_request(context, quote_request)

    def attach_quote_request(
        self,
        context: QuoteCaseContext,
        quote_request: QuoteRequest,
    ) -> QuoteCaseContext:
        context.source_inputs.request_id = quote_request.request_id
        context.source_inputs.client_id = quote_request.client_id

        context.reference_data.quote_request = quote_request.model_dump(mode="json")
        context.reference_data.client_profile = quote_request.client_data
        context.reference_data.asset_profile = quote_request.asset_data

        context.domain_payload.quote_intake_payload = {
            "request_id": str(quote_request.request_id),
            "client_id": quote_request.client_id,
            "request_status": quote_request.request_status,
            "client_data": quote_request.client_data,
            "asset_data": quote_request.asset_data,
            "quote_steps": quote_request.quote_steps,
            "mandatory_data_status": quote_request.mandatory_data_status,
            "attachments": [
                attachment.model_dump(mode="json")
                for attachment in quote_request.attachments
            ],
            "pricing_preview": quote_request.pricing_preview,
        }

        context.domain_payload.quote_evaluation["mandatory_data_status"] = (
            quote_request.mandatory_data_status
        )

        context.generated_outputs.pricing_outputs.pricing_metadata = (
            quote_request.pricing_preview
        )

        return context


__all__ = ["QuoteDataService"]
