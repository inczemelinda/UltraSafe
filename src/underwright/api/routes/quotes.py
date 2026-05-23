from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from underwright.api.dependencies import (
    get_contract_document_generation_service,
    get_current_client_user,
    get_current_employee_user,
    get_customer_profile_service,
    get_generated_document_pdf_service,
    get_generated_document_query_service,
    get_quote_acceptance_service,
    get_quote_request_service,
    get_quote_to_contract_conversion_service,
    get_quote_workflow,
)
from underwright.application.services.contract_document_generation_service import (
    DEFAULT_CONTRACT_TEMPLATE_CODE,
    ContractDocumentGenerationService,
)
from underwright.application.services.generated_document_pdf_service import (
    GeneratedDocumentPdfService,
)
from underwright.application.services.generated_document_query_service import (
    GeneratedDocumentQueryService,
)
from underwright.application.services.quote_acceptance_service import (
    QuoteAcceptanceDocumentMissingError,
    QuoteAcceptanceInvalidStatusError,
    QuoteAcceptanceNotFoundError,
    QuoteAcceptanceOwnershipError,
    QuoteAcceptanceService,
    QuoteAcceptanceValidationError,
)
from underwright.application.services.customer_profile_service import (
    CustomerProfileIncompleteError,
    CustomerProfileService,
)
from underwright.domain.customer_profile import CustomerProfileReadModel
from underwright.application.services.quote_request_service import QuoteRequestService
from underwright.application.services.quote_to_contract_conversion_service import (
    QuoteToContractConversionService,
)
from underwright.application.workflows.quote_workflow import (
    DEFAULT_QUOTE_CONTRACT_TEMPLATE_CODE,
    QuoteWorkflow,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.module_result import ModuleResult
from underwright.domain.generated_document_lifecycle import PdfExportResult
from underwright.domain.quote_acceptance import QuoteAcceptance, QuoteAcceptanceInput
from underwright.domain.quote_decision_audit import QuoteDecisionAuditRecord
from underwright.domain.quote_request import QuoteAttachmentMetadata, QuoteRequest

router = APIRouter(prefix="/quotes", tags=["quotes"])
underwriter_router = APIRouter(
    prefix="/underwriter/quotes", tags=["underwriter-quotes"]
)
me_router = APIRouter(prefix="/me/quotes", tags=["client-quotes"])


class CreateQuoteRequestBody(BaseModel):
    request_id: UUID | None = None
    client_id: int | str | UUID
    request_status: str = "draft"
    client_data: dict[str, Any] = Field(default_factory=dict)
    asset_data: dict[str, Any] = Field(default_factory=dict)
    quote_steps: list[dict[str, Any]] = Field(default_factory=list)
    mandatory_data_status: dict[str, Any] = Field(default_factory=dict)
    attachments: list[QuoteAttachmentMetadata] = Field(default_factory=list)
    pricing_preview: dict[str, Any] = Field(default_factory=dict)


class CreateMyQuoteRequestBody(BaseModel):
    request_id: UUID | None = None
    request_status: str = "underwriter_review"
    client_data: dict[str, Any] = Field(default_factory=dict)
    asset_data: dict[str, Any] = Field(default_factory=dict)
    quote_steps: list[dict[str, Any]] = Field(default_factory=list)
    mandatory_data_status: dict[str, Any] = Field(default_factory=dict)
    attachments: list[QuoteAttachmentMetadata] = Field(default_factory=list)
    pricing_preview: dict[str, Any] = Field(default_factory=dict)


class UpdateQuoteRequestBody(BaseModel):
    request_status: str | None = None
    client_data: dict[str, Any] | None = None
    asset_data: dict[str, Any] | None = None
    quote_steps: list[dict[str, Any]] | None = None
    mandatory_data_status: dict[str, Any] | None = None
    attachments: list[QuoteAttachmentMetadata] | None = None
    pricing_preview: dict[str, Any] | None = None


class GenerateQuoteRequest(BaseModel):
    template_code: str


class ModuleResultResponse(BaseModel):
    module_name: str
    status: str
    summary: str
    source_fields_used: list[str] = Field(default_factory=list)


class GenerateQuoteResponse(BaseModel):
    case_id: UUID | None = None
    status: str
    quote_document_id: int | None = None
    module_results: list[ModuleResultResponse]


class UpdateQuoteDecisionBody(BaseModel):
    status: Literal["approved", "disapproved", "field_review_required"]
    reason: str | None = None


class AcceptQuoteBody(BaseModel):
    signer_name: str
    signer_email: str
    signer_role: str | None = None
    acceptance_statement: str


@router.post("", response_model=QuoteRequest)
def create_quote_request(
    body: CreateQuoteRequestBody,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
) -> QuoteRequest:
    request = QuoteRequest(
        request_id=body.request_id or uuid4(),
        client_id=body.client_id,
        request_status=body.request_status,
        client_data=body.client_data,
        asset_data=body.asset_data,
        quote_steps=body.quote_steps,
        mandatory_data_status=body.mandatory_data_status,
        attachments=body.attachments,
        pricing_preview=body.pricing_preview,
    )
    return service.create_quote_request(request)


@router.patch("/{request_id}", response_model=QuoteRequest)
def update_quote_request(
    request_id: UUID,
    body: UpdateQuoteRequestBody,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
) -> QuoteRequest:
    request = service.get_quote_request_detail(request_id)
    updates = body.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(request, field_name, value)
    return service.save_step_updates(request)


@router.get("/client", response_model=list[QuoteRequest])
def list_client_quote_requests(
    client_id: int | str | UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
) -> list[QuoteRequest]:
    return service.list_client_quote_requests(client_id)


@router.get("/{request_id}", response_model=QuoteRequest)
def get_quote_request(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
) -> QuoteRequest:
    return service.get_quote_request_detail(request_id)


@router.get("/{request_id}/acceptance", response_model=QuoteAcceptance)
def get_quote_acceptance(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteAcceptanceService = Depends(get_quote_acceptance_service),
) -> QuoteAcceptance | JSONResponse:
    try:
        return service.get_acceptance(request_id)
    except QuoteAcceptanceNotFoundError as exc:
        return _not_found(
            "QUOTE_ACCEPTANCE_NOT_FOUND",
            "Quote acceptance not found.",
            str(exc),
        )


@router.post("/{request_id}/generate", response_model=GenerateQuoteResponse)
def generate_quote_document(
    request_id: UUID,
    request: GenerateQuoteRequest,
    _current_user: AuthUser = Depends(get_current_employee_user),
    workflow: QuoteWorkflow = Depends(get_quote_workflow),
) -> GenerateQuoteResponse | JSONResponse:
    try:
        result = workflow.run(
            request_id=request_id,
            template_code=request.template_code,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "QUOTE_REQUEST_NOT_FOUND",
                    "message": "Quote request not found.",
                    "details": str(exc),
                }
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "QUOTE_GENERATION_ERROR",
                    "message": "Failed to run quote generation workflow.",
                    "details": str(exc),
                }
            },
        )

    serialized_module_results = _module_result_responses(result.module_results)
    if result.status == "failed":
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "QUOTE_WORKFLOW_FAILED",
                    "message": "Quote generation workflow failed.",
                    "module_results": [
                        module_result.model_dump(mode="json")
                        for module_result in serialized_module_results
                    ],
                },
                "case_id": str(result.case_context.case_metadata.case_id),
                "status": result.status,
            },
        )

    return GenerateQuoteResponse(
        case_id=result.case_context.case_metadata.case_id,
        status=result.status,
        quote_document_id=(
            result.quote_document.id if result.quote_document is not None else None
        ),
        module_results=serialized_module_results,
    )


@underwriter_router.get("", response_model=list[QuoteRequest])
def list_underwriter_quote_requests(
    status: str = "underwriter_review",
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
) -> list[QuoteRequest]:
    return service.list_quote_requests_by_status(status)


@underwriter_router.get("/{request_id}", response_model=QuoteRequest)
def get_underwriter_quote_request(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
) -> QuoteRequest:
    return service.get_quote_request_detail(request_id)


@underwriter_router.patch("/{request_id}/decision", response_model=QuoteRequest)
def update_underwriter_quote_decision(
    request_id: UUID,
    body: UpdateQuoteDecisionBody,
    current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
    quote_workflow: QuoteWorkflow = Depends(get_quote_workflow),
    contract_conversion_service: QuoteToContractConversionService = Depends(
        get_quote_to_contract_conversion_service
    ),
    contract_document_service: ContractDocumentGenerationService = Depends(
        get_contract_document_generation_service
    ),
    generated_document_service: GeneratedDocumentQueryService = Depends(
        get_generated_document_query_service
    ),
    generated_document_pdf_service: GeneratedDocumentPdfService = Depends(
        get_generated_document_pdf_service
    ),
) -> QuoteRequest | JSONResponse:
    updated = service.update_underwriter_decision(
        request_id,
        body.status,
        reason=body.reason,
        user=current_user,
    )
    if body.status == "approved":
        publication_error = _publish_approved_quote_contract(
            request_id,
            quote_workflow=quote_workflow,
            contract_conversion_service=contract_conversion_service,
            contract_document_service=contract_document_service,
            generated_document_service=generated_document_service,
            generated_document_pdf_service=generated_document_pdf_service,
        )
        if publication_error is not None:
            return publication_error
        return service.get_quote_request_detail(request_id)
    return updated


@underwriter_router.get(
    "/{request_id}/decision-audit",
    response_model=list[QuoteDecisionAuditRecord],
)
def list_underwriter_quote_decision_audit(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
) -> list[QuoteDecisionAuditRecord]:
    return service.list_decision_audit(request_id)


def _publish_approved_quote_contract(
    request_id: UUID,
    *,
    quote_workflow: QuoteWorkflow,
    contract_conversion_service: QuoteToContractConversionService,
    contract_document_service: ContractDocumentGenerationService,
    generated_document_service: GeneratedDocumentQueryService,
    generated_document_pdf_service: GeneratedDocumentPdfService,
) -> JSONResponse | None:
    quote_document = contract_conversion_service.latest_successful_quote_document(
        request_id
    )
    if quote_document is None:
        workflow_result = quote_workflow.run(
            request_id=request_id,
            template_code=DEFAULT_QUOTE_CONTRACT_TEMPLATE_CODE,
        )
        quote_document = workflow_result.quote_document
        if workflow_result.status == "failed" or quote_document is None:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "QUOTE_CONTRACT_PUBLICATION_FAILED",
                        "message": (
                            "Quote was approved but the quote document could not "
                            "be generated."
                        ),
                        "module_results": [
                            module_result.model_dump(mode="json")
                            for module_result in _module_result_responses(
                                workflow_result.module_results
                            )
                        ],
                    },
                    "status": workflow_result.status,
                },
            )

    conversion_result = contract_conversion_service.publish_approved_quote(
        request_id,
        quote_document=quote_document,
    )
    if conversion_result.result == "blocked" or conversion_result.contract is None:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "QUOTE_CONTRACT_PUBLICATION_BLOCKED",
                    "message": "Quote was approved but could not be published as a contract.",
                },
                **conversion_result.model_dump(mode="json"),
            },
        )

    document = generated_document_service.get_latest_for_contract(
        conversion_result.contract.id
    )
    if document is None:
        generation_result = contract_document_service.generate(
            conversion_result.contract.id,
            template_code=DEFAULT_CONTRACT_TEMPLATE_CODE,
        )
        document = generation_result.document
    if document is None:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "CONTRACT_DOCUMENT_GENERATION_FAILED",
                    "message": (
                        "Quote was approved and published, but the contract "
                        "document could not be generated."
                    ),
                    "validation": generation_result.validation.model_dump(
                        mode="json"
                    ),
                    "module_results": [
                        module_result.model_dump(mode="json")
                        for module_result in generation_result.module_results
                    ],
                },
                "status": generation_result.status,
            },
        )
    return _ensure_generated_document_pdf(
        document.id,
        generated_document_pdf_service=generated_document_pdf_service,
    )


@me_router.get("", response_model=list[QuoteRequest])
def list_my_quote_requests(
    current_user: AuthUser = Depends(get_current_client_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
) -> list[QuoteRequest]:
    if current_user.client_id is None:
        return []
    return service.list_client_quote_requests(current_user.client_id)


@me_router.post("", response_model=QuoteRequest)
def create_my_quote_request(
    body: CreateMyQuoteRequestBody,
    current_user: AuthUser = Depends(get_current_client_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
    profile_service: CustomerProfileService = Depends(get_customer_profile_service),
    workflow: QuoteWorkflow = Depends(get_quote_workflow),
    contract_conversion_service: QuoteToContractConversionService = Depends(
        get_quote_to_contract_conversion_service
    ),
    contract_document_service: ContractDocumentGenerationService = Depends(
        get_contract_document_generation_service
    ),
    generated_document_service: GeneratedDocumentQueryService = Depends(
        get_generated_document_query_service
    ),
    generated_document_pdf_service: GeneratedDocumentPdfService = Depends(
        get_generated_document_pdf_service
    ),
) -> QuoteRequest | JSONResponse:
    try:
        profile = profile_service.ensure_complete_profile(current_user)
    except CustomerProfileIncompleteError as exc:
        return _profile_incomplete(exc)

    request = QuoteRequest(
        request_id=body.request_id or uuid4(),
        client_id=current_user.client_id,
        request_status=body.request_status,
        client_data=_quote_client_data_from_profile(
            profile,
            current_user,
            body.client_data,
        ),
        asset_data=body.asset_data,
        quote_steps=body.quote_steps,
        mandatory_data_status=body.mandatory_data_status,
        attachments=body.attachments,
        pricing_preview=body.pricing_preview,
    )
    saved = service.create_quote_request(request)
    result = _run_client_quote_workflow(
        saved.request_id,
        service=service,
        workflow=workflow,
    )
    if isinstance(result, JSONResponse):
        return result
    if result.request_status == "auto_accepted":
        publication_error = _publish_approved_quote_contract(
            result.request_id,
            quote_workflow=workflow,
            contract_conversion_service=contract_conversion_service,
            contract_document_service=contract_document_service,
            generated_document_service=generated_document_service,
            generated_document_pdf_service=generated_document_pdf_service,
        )
        if publication_error is not None:
            return publication_error
        return service.get_quote_request_detail(result.request_id)
    return result


@me_router.get("/{request_id}", response_model=QuoteRequest)
def get_my_quote_request(
    request_id: UUID,
    current_user: AuthUser = Depends(get_current_client_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
) -> QuoteRequest | JSONResponse:
    try:
        quote = service.get_quote_request_detail(request_id)
    except ValueError as exc:
        return _not_found("QUOTE_REQUEST_NOT_FOUND", "Quote request not found.", str(exc))
    if current_user.client_id is None or str(quote.client_id) != str(current_user.client_id):
        return _not_found("QUOTE_REQUEST_NOT_FOUND", "Quote request not found.")
    return quote


@me_router.get("/{request_id}/acceptance", response_model=QuoteAcceptance)
def get_my_quote_acceptance(
    request_id: UUID,
    current_user: AuthUser = Depends(get_current_client_user),
    service: QuoteAcceptanceService = Depends(get_quote_acceptance_service),
) -> QuoteAcceptance | JSONResponse:
    try:
        return service.get_acceptance_for_client(
            quote_id=request_id,
            user=current_user,
        )
    except (
        ValueError,
        QuoteAcceptanceNotFoundError,
        QuoteAcceptanceOwnershipError,
    ) as exc:
        return _not_found(
            "QUOTE_ACCEPTANCE_NOT_FOUND",
            "Quote acceptance not found.",
            str(exc),
        )


@me_router.post("/{request_id}/acceptance", response_model=QuoteAcceptance)
def accept_my_quote(
    request_id: UUID,
    body: AcceptQuoteBody,
    request: Request,
    current_user: AuthUser = Depends(get_current_client_user),
    service: QuoteAcceptanceService = Depends(get_quote_acceptance_service),
) -> QuoteAcceptance | JSONResponse:
    try:
        return service.accept_quote_for_client(
            quote_id=request_id,
            user=current_user,
            signer_input=QuoteAcceptanceInput(**body.model_dump()),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except CustomerProfileIncompleteError as exc:
        return _profile_incomplete(exc)
    except (ValueError, QuoteAcceptanceOwnershipError) as exc:
        return _not_found("QUOTE_REQUEST_NOT_FOUND", "Quote request not found.", str(exc))
    except QuoteAcceptanceInvalidStatusError as exc:
        return _bad_request(
            "QUOTE_NOT_ACCEPTABLE",
            "Quote is not eligible for client acceptance.",
            str(exc),
        )
    except QuoteAcceptanceDocumentMissingError as exc:
        return _bad_request(
            "QUOTE_DOCUMENT_MISSING",
            "A successful quote document is required before acceptance.",
            str(exc),
        )
    except QuoteAcceptanceValidationError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "QUOTE_ACCEPTANCE_SIGNER_REQUIRED",
                    "message": "Signer details are required before quote acceptance.",
                    "missing_fields": exc.missing_fields,
                }
            },
        )


@me_router.patch("/{request_id}", response_model=QuoteRequest)
def update_my_quote_request(
    request_id: UUID,
    body: UpdateQuoteRequestBody,
    current_user: AuthUser = Depends(get_current_client_user),
    service: QuoteRequestService = Depends(get_quote_request_service),
    profile_service: CustomerProfileService = Depends(get_customer_profile_service),
) -> QuoteRequest | JSONResponse:
    try:
        profile_service.ensure_complete_profile(current_user)
    except CustomerProfileIncompleteError as exc:
        return _profile_incomplete(exc)

    result = get_my_quote_request(request_id, current_user, service)
    if isinstance(result, JSONResponse):
        return result
    updates = body.model_dump(exclude_unset=True)
    if updates.get("request_status") in {"approved", "auto_accepted"}:
        return _bad_request(
            "QUOTE_ACCEPTANCE_ENDPOINT_REQUIRED",
            "Use /me/quotes/{quote_id}/acceptance to accept a quote.",
        )
    for field_name, value in updates.items():
        setattr(result, field_name, value)
    return service.save_step_updates(result)


def _profile_incomplete(exc: CustomerProfileIncompleteError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "error": {
                "code": "CUSTOMER_PROFILE_INCOMPLETE",
                "message": "Complete your customer profile before submitting quote changes.",
                "status": exc.status,
                "missing_fields": exc.missing_fields,
            }
        },
    )


def _quote_client_data_from_profile(
    profile: CustomerProfileReadModel | None,
    current_user: AuthUser,
    submitted_client_data: dict,
) -> dict:
    if profile is None:
        return {
            "email": current_user.email,
            "full_name": current_user.full_name,
            **submitted_client_data,
        }

    client_data = dict(submitted_client_data)
    client_data.update(
        {
            "type": profile.type or submitted_client_data.get("type") or "individual",
            "full_name": profile.full_name or current_user.full_name,
            "national_id": profile.national_id,
            "company_id": profile.company_id,
            "email": profile.email or current_user.email,
            "phone": profile.phone or current_user.phone,
            "address": _profile_address_payload(profile),
        }
    )
    return client_data


def _profile_address_payload(profile: CustomerProfileReadModel) -> dict | str | None:
    if profile.address is None:
        return None
    address = profile.address.model_dump(mode="json", exclude_none=True)
    if not address.get("full_text"):
        parts = [
            " ".join(
                str(value).strip()
                for value in [address.get("street"), address.get("number")]
                if value
            ),
            address.get("city"),
            address.get("county"),
            address.get("country"),
            address.get("postal_code"),
        ]
        address["full_text"] = ", ".join(str(part).strip() for part in parts if part)
    return address


def _ensure_generated_document_pdf(
    document_id: int,
    *,
    generated_document_pdf_service: GeneratedDocumentPdfService,
) -> JSONResponse | None:
    try:
        result = generated_document_pdf_service.create_pdf(document_id)
    except ValueError as exc:
        return _not_found(
            "GENERATED_DOCUMENT_NOT_FOUND",
            "Generated document not found.",
            str(exc),
        )

    if result.artifact is None:
        return _pdf_export_failed(result)
    return None


def _pdf_export_failed(result: PdfExportResult) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "GENERATED_DOCUMENT_PDF_EXPORT_FAILED",
                "message": "Generated document PDF export failed.",
                "blocking_errors": [
                    error.model_dump(mode="json")
                    for error in result.blocking_errors
                ],
            },
            "status": result.status,
        },
    )


def _run_client_quote_workflow(
    request_id: UUID,
    *,
    service: QuoteRequestService,
    workflow: QuoteWorkflow,
) -> QuoteRequest | JSONResponse:
    try:
        workflow.run(
            request_id=request_id,
            template_code=DEFAULT_QUOTE_CONTRACT_TEMPLATE_CODE,
        )
        return service.get_quote_request_detail(request_id)
    except ValueError as exc:
        try:
            return service.get_quote_request_detail(request_id)
        except ValueError:
            return _not_found(
                "QUOTE_REQUEST_NOT_FOUND",
                "Quote request not found.",
                str(exc),
            )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "QUOTE_WORKFLOW_ERROR",
                    "message": "Quote was submitted but backend evaluation failed.",
                    "details": str(exc),
                }
            },
        )


def _not_found(code: str, message: str, details: str | None = None) -> JSONResponse:
    content: dict[str, object] = {"error": {"code": code, "message": message}}
    if details:
        content["error"]["details"] = details
    return JSONResponse(status_code=404, content=content)


def _bad_request(code: str, message: str, details: str | None = None) -> JSONResponse:
    content: dict[str, object] = {"error": {"code": code, "message": message}}
    if details:
        content["error"]["details"] = details
    return JSONResponse(status_code=400, content=content)


def _module_result_responses(
    module_results: list[ModuleResult],
) -> list[ModuleResultResponse]:
    return [
        ModuleResultResponse(**module_result.model_dump(mode="json"))
        for module_result in module_results
    ]


__all__ = ["me_router", "router", "underwriter_router"]
