from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from underwright.api.dependencies import (
    get_contract_document_generation_service,
    get_contract_decline_service,
    get_contract_query_service,
    get_current_client_user,
    get_current_employee_user,
    get_generated_document_pdf_service,
    get_generated_document_query_service,
    get_quote_to_contract_conversion_service,
    get_quote_request_service,
    get_quote_workflow,
)
from underwright.application.services.contract_document_generation_service import (
    DEFAULT_CONTRACT_TEMPLATE_CODE,
    ContractDocumentGenerationService,
)
from underwright.application.services.contract_decline_service import (
    ContractDeclineInvalidStatusError,
    ContractDeclineOwnershipError,
    ContractDeclineService,
)
from underwright.application.services.contract_query_service import ContractQueryService
from underwright.application.services.generated_document_query_service import (
    GeneratedDocumentQueryService,
)
from underwright.application.services.generated_document_pdf_service import (
    GeneratedDocumentPdfService,
)
from underwright.application.services.quote_to_contract_conversion_service import (
    QuoteToContractConversionService,
)
from underwright.application.services.quote_request_service import QuoteRequestService
from underwright.application.workflows.quote_workflow import (
    DEFAULT_QUOTE_CONTRACT_TEMPLATE_CODE,
    QuoteWorkflow,
)
from underwright.domain.contract_lifecycle import (
    AddressSnapshot,
    ContractReadModel,
    QuoteContractResolution,
    QuoteToContractConversionResult,
)
from underwright.domain.contract_decline import (
    ContractDecline,
    ContractDeclineInput,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.generated_document_lifecycle import GeneratedDocumentReadModel
from underwright.domain.generated_document_lifecycle import PdfArtifactReadModel
from underwright.domain.generated_document_lifecycle import PdfExportResult

router = APIRouter(prefix="/contracts", tags=["contracts"])
me_router = APIRouter(prefix="/me", tags=["client-contracts"])
quote_contract_router = APIRouter(prefix="/quotes", tags=["quote-contracts"])
generated_documents_router = APIRouter(
    prefix="/generated-documents",
    tags=["generated-documents"],
)


class GenerateContractDocumentRequest(BaseModel):
    template_code: str = DEFAULT_CONTRACT_TEMPLATE_CODE


class ClaimableContractItem(BaseModel):
    contract_id: UUID
    contract_number: str
    display_id: str
    policy_number: str
    status: str
    effective_date: date
    expiration_date: date | None = None
    insured_asset_id: int | None = None
    address: AddressSnapshot | None = None
    coverage_amount: Decimal | None = None


class ClaimableContractsResponse(BaseModel):
    items: list[ClaimableContractItem]


@router.get("", response_model=list[ContractReadModel])
def list_contracts(
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: ContractQueryService = Depends(get_contract_query_service),
) -> list[ContractReadModel]:
    return service.list_contracts()


@me_router.get("/contracts", response_model=list[ContractReadModel])
def list_my_contracts(
    current_user: AuthUser = Depends(get_current_client_user),
    service: ContractQueryService = Depends(get_contract_query_service),
) -> list[ContractReadModel]:
    if current_user.client_id is None:
        return []
    return service.list_contracts_for_client(current_user.client_id)


@me_router.get("/contracts/{contract_id}", response_model=ContractReadModel)
def get_my_contract(
    contract_id: str,
    current_user: AuthUser = Depends(get_current_client_user),
    service: ContractQueryService = Depends(get_contract_query_service),
) -> ContractReadModel | JSONResponse:
    parsed_contract_id = _parse_uuid(contract_id)
    if parsed_contract_id is None or current_user.client_id is None:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.")
    try:
        return service.get_contract_for_client(
            parsed_contract_id,
            current_user.client_id,
        )
    except ValueError:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.")


@me_router.post("/contracts/{contract_id}/decline", response_model=ContractDecline)
def decline_my_contract(
    contract_id: str,
    request: Request,
    body: ContractDeclineInput | None = None,
    current_user: AuthUser = Depends(get_current_client_user),
    service: ContractDeclineService = Depends(get_contract_decline_service),
) -> ContractDecline | JSONResponse:
    parsed_contract_id = _parse_uuid(contract_id)
    if parsed_contract_id is None or current_user.client_id is None:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.")

    try:
        return service.decline_contract_for_client(
            contract_id=parsed_contract_id,
            user=current_user,
            decline_input=body or ContractDeclineInput(),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ContractDeclineOwnershipError as exc:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.", str(exc))
    except ContractDeclineInvalidStatusError as exc:
        return _bad_request(
            "CONTRACT_NOT_DECLINABLE",
            "Contract is not eligible for decline.",
            str(exc),
        )


@me_router.get("/claimable-contracts", response_model=ClaimableContractsResponse)
def list_my_claimable_contracts(
    current_user: AuthUser = Depends(get_current_client_user),
    service: ContractQueryService = Depends(get_contract_query_service),
) -> ClaimableContractsResponse:
    if current_user.client_id is None:
        return ClaimableContractsResponse(items=[])
    contracts = service.list_claimable_contracts_for_client(current_user.client_id)
    return ClaimableContractsResponse(
        items=[_claimable_contract_item(contract) for contract in contracts],
    )


@router.post(
    "/{contract_id}/generated-documents",
    response_model=GeneratedDocumentReadModel,
)
def generate_contract_document(
    contract_id: str,
    body: GenerateContractDocumentRequest | None = None,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: ContractDocumentGenerationService = Depends(
        get_contract_document_generation_service
    ),
) -> GeneratedDocumentReadModel | JSONResponse:
    parsed_contract_id = _parse_uuid(contract_id)
    if parsed_contract_id is None:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.")

    request = body or GenerateContractDocumentRequest()
    try:
        result = service.generate(
            parsed_contract_id,
            template_code=request.template_code,
        )
    except ValueError as exc:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.", str(exc))

    if result.document is None:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "CONTRACT_DOCUMENT_GENERATION_FAILED",
                    "message": "Contract document generation failed.",
                    "validation": result.validation.model_dump(mode="json"),
                    "module_results": [
                        module_result.model_dump(mode="json")
                        for module_result in result.module_results
                    ],
                },
                "status": result.status,
            },
        )
    return result.document


@router.get(
    "/{contract_id}/generated-documents/latest",
    response_model=GeneratedDocumentReadModel,
)
def get_latest_contract_generated_document(
    contract_id: str,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: GeneratedDocumentQueryService = Depends(
        get_generated_document_query_service
    ),
) -> GeneratedDocumentReadModel | JSONResponse:
    parsed_contract_id = _parse_uuid(contract_id)
    if parsed_contract_id is None:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.")

    try:
        document = service.get_latest_for_contract(parsed_contract_id)
    except ValueError as exc:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.", str(exc))

    if document is None:
        return _not_found(
            "GENERATED_DOCUMENT_NOT_FOUND",
            "No generated document exists for this contract.",
        )
    return document


@me_router.get(
    "/contracts/{contract_id}/generated-documents/latest",
    response_model=GeneratedDocumentReadModel,
)
def get_latest_my_contract_generated_document(
    contract_id: str,
    current_user: AuthUser = Depends(get_current_client_user),
    contract_service: ContractQueryService = Depends(get_contract_query_service),
    document_service: GeneratedDocumentQueryService = Depends(
        get_generated_document_query_service
    ),
) -> GeneratedDocumentReadModel | JSONResponse:
    parsed_contract_id = _parse_uuid(contract_id)
    if parsed_contract_id is None or current_user.client_id is None:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.")

    try:
        contract_service.get_contract_for_client(
            parsed_contract_id,
            current_user.client_id,
        )
        document = document_service.get_latest_for_contract(parsed_contract_id)
    except ValueError:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.")

    if document is None:
        return _not_found(
            "GENERATED_DOCUMENT_NOT_FOUND",
            "No generated document exists for this contract.",
        )
    return document


@router.get("/{contract_id}", response_model=ContractReadModel)
def get_contract(
    contract_id: str,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: ContractQueryService = Depends(get_contract_query_service),
) -> ContractReadModel | JSONResponse:
    parsed_contract_id = _parse_uuid(contract_id)
    if parsed_contract_id is None:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.")

    try:
        return service.get_contract(parsed_contract_id)
    except ValueError:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.")


@quote_contract_router.get(
    "/{quote_id}/contract",
    response_model=QuoteContractResolution,
)
def resolve_quote_contract(
    quote_id: str,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteToContractConversionService = Depends(
        get_quote_to_contract_conversion_service
    ),
) -> QuoteContractResolution | JSONResponse:
    parsed_quote_id = _parse_uuid(quote_id)
    if parsed_quote_id is None:
        return _not_found("QUOTE_REQUEST_NOT_FOUND", "Quote request not found.")

    try:
        return service.resolve_quote_contract(parsed_quote_id)
    except ValueError as exc:
        return _not_found(
            "QUOTE_REQUEST_NOT_FOUND",
            "Quote request not found.",
            str(exc),
        )


@quote_contract_router.post(
    "/{quote_id}/contract",
    response_model=QuoteToContractConversionResult,
)
def convert_quote_to_contract(
    quote_id: str,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: QuoteToContractConversionService = Depends(
        get_quote_to_contract_conversion_service
    ),
) -> QuoteToContractConversionResult | JSONResponse:
    parsed_quote_id = _parse_uuid(quote_id)
    if parsed_quote_id is None:
        return _not_found("QUOTE_REQUEST_NOT_FOUND", "Quote request not found.")

    try:
        result = service.convert_quote(parsed_quote_id)
    except ValueError as exc:
        return _not_found(
            "QUOTE_REQUEST_NOT_FOUND",
            "Quote request not found.",
            str(exc),
        )

    if result.result == "blocked":
        return JSONResponse(
            status_code=400,
            content=result.model_dump(mode="json"),
        )
    return result


@me_router.get(
    "/quotes/{quote_id}/contract",
    response_model=QuoteContractResolution,
)
def resolve_my_quote_contract(
    quote_id: str,
    current_user: AuthUser = Depends(get_current_client_user),
    quote_service: QuoteRequestService = Depends(get_quote_request_service),
    service: QuoteToContractConversionService = Depends(
        get_quote_to_contract_conversion_service
    ),
) -> QuoteContractResolution | JSONResponse:
    parsed_quote_id = _client_owned_quote_id(
        quote_id,
        current_user=current_user,
        quote_service=quote_service,
    )
    if isinstance(parsed_quote_id, JSONResponse):
        return parsed_quote_id

    try:
        return service.resolve_quote_contract(parsed_quote_id)
    except ValueError as exc:
        return _not_found(
            "QUOTE_REQUEST_NOT_FOUND",
            "Quote request not found.",
            str(exc),
        )


@me_router.post(
    "/quotes/{quote_id}/contract",
    response_model=QuoteToContractConversionResult,
)
def convert_my_quote_to_contract(
    quote_id: str,
    current_user: AuthUser = Depends(get_current_client_user),
    quote_service: QuoteRequestService = Depends(get_quote_request_service),
    service: QuoteToContractConversionService = Depends(
        get_quote_to_contract_conversion_service
    ),
    quote_workflow: QuoteWorkflow = Depends(get_quote_workflow),
    contract_document_service: ContractDocumentGenerationService = Depends(
        get_contract_document_generation_service
    ),
    generated_document_service: GeneratedDocumentQueryService = Depends(
        get_generated_document_query_service
    ),
    generated_document_pdf_service: GeneratedDocumentPdfService = Depends(
        get_generated_document_pdf_service
    ),
) -> QuoteToContractConversionResult | JSONResponse:
    parsed_quote_id = _client_owned_quote_id(
        quote_id,
        current_user=current_user,
        quote_service=quote_service,
    )
    if isinstance(parsed_quote_id, JSONResponse):
        return parsed_quote_id

    return _publish_client_quote_contract_for_signing(
        parsed_quote_id,
        service=service,
        quote_workflow=quote_workflow,
        contract_document_service=contract_document_service,
        generated_document_service=generated_document_service,
        generated_document_pdf_service=generated_document_pdf_service,
    )


@generated_documents_router.get(
    "/{document_id}",
    response_model=GeneratedDocumentReadModel,
)
def get_generated_document(
    document_id: int,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: GeneratedDocumentQueryService = Depends(
        get_generated_document_query_service
    ),
) -> GeneratedDocumentReadModel | JSONResponse:
    try:
        return service.get_document(document_id)
    except ValueError as exc:
        return _not_found(
            "GENERATED_DOCUMENT_NOT_FOUND",
            "Generated document not found.",
            str(exc),
        )


@generated_documents_router.post(
    "/{document_id}/pdf",
    response_model=PdfArtifactReadModel,
)
def create_generated_document_pdf(
    document_id: int,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: GeneratedDocumentPdfService = Depends(
        get_generated_document_pdf_service
    ),
) -> PdfArtifactReadModel | JSONResponse:
    try:
        result = service.create_pdf(document_id)
    except ValueError as exc:
        return _not_found(
            "GENERATED_DOCUMENT_NOT_FOUND",
            "Generated document not found.",
            str(exc),
        )

    if result.artifact is None:
        return _pdf_export_failed(result)
    return result.artifact


@me_router.post(
    "/generated-documents/{document_id}/pdf",
    response_model=PdfArtifactReadModel,
)
def create_my_generated_document_pdf(
    document_id: int,
    current_user: AuthUser = Depends(get_current_client_user),
    contract_service: ContractQueryService = Depends(get_contract_query_service),
    document_service: GeneratedDocumentQueryService = Depends(
        get_generated_document_query_service
    ),
    pdf_service: GeneratedDocumentPdfService = Depends(
        get_generated_document_pdf_service
    ),
) -> PdfArtifactReadModel | JSONResponse:
    if current_user.client_id is None:
        return _not_found(
            "GENERATED_DOCUMENT_NOT_FOUND",
            "Generated document not found.",
        )

    try:
        document = document_service.get_document(document_id)
        contract_service.get_contract_for_client(
            document.contract_id,
            current_user.client_id,
        )
        result = pdf_service.create_pdf(document_id)
    except ValueError:
        return _not_found(
            "GENERATED_DOCUMENT_NOT_FOUND",
            "Generated document not found.",
        )

    if result.artifact is None:
        return _pdf_export_failed(result)
    return result.artifact


@generated_documents_router.get("/{document_id}/pdf", response_model=None)
def get_generated_document_pdf(
    document_id: int,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: GeneratedDocumentPdfService = Depends(
        get_generated_document_pdf_service
    ),
) -> FileResponse | JSONResponse:
    try:
        artifact_file = service.get_existing_pdf(document_id)
    except ValueError as exc:
        return _not_found(
            "GENERATED_DOCUMENT_NOT_FOUND",
            "Generated document not found.",
            str(exc),
        )

    if artifact_file is None:
        return _not_found(
            "GENERATED_DOCUMENT_PDF_NOT_FOUND",
            "No PDF artifact exists for this generated document.",
        )
    return FileResponse(
        path=artifact_file.file_path,
        media_type="application/pdf",
        filename=artifact_file.artifact.filename,
    )


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


@me_router.get("/generated-documents/{document_id}/pdf", response_model=None)
def get_my_generated_document_pdf(
    document_id: int,
    current_user: AuthUser = Depends(get_current_client_user),
    contract_service: ContractQueryService = Depends(get_contract_query_service),
    document_service: GeneratedDocumentQueryService = Depends(
        get_generated_document_query_service
    ),
    pdf_service: GeneratedDocumentPdfService = Depends(
        get_generated_document_pdf_service
    ),
) -> FileResponse | JSONResponse:
    if current_user.client_id is None:
        return _not_found(
            "GENERATED_DOCUMENT_NOT_FOUND",
            "Generated document not found.",
        )

    try:
        document = document_service.get_document(document_id)
        contract_service.get_contract_for_client(
            document.contract_id,
            current_user.client_id,
        )
        artifact_file = pdf_service.get_existing_pdf(document_id)
    except ValueError:
        return _not_found(
            "GENERATED_DOCUMENT_NOT_FOUND",
            "Generated document not found.",
        )

    if artifact_file is None:
        return _not_found(
            "GENERATED_DOCUMENT_PDF_NOT_FOUND",
            "No PDF artifact exists for this generated document.",
        )
    return FileResponse(
        path=artifact_file.file_path,
        media_type="application/pdf",
        filename=artifact_file.artifact.filename,
    )


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


def _client_owned_quote_id(
    quote_id: str,
    *,
    current_user: AuthUser,
    quote_service: QuoteRequestService,
) -> UUID | JSONResponse:
    parsed_quote_id = _parse_uuid(quote_id)
    if parsed_quote_id is None or current_user.client_id is None:
        return _not_found("QUOTE_REQUEST_NOT_FOUND", "Quote request not found.")

    try:
        quote = quote_service.get_quote_request_detail(parsed_quote_id)
    except ValueError as exc:
        return _not_found(
            "QUOTE_REQUEST_NOT_FOUND",
            "Quote request not found.",
            str(exc),
        )

    if str(quote.client_id) != str(current_user.client_id):
        return _not_found("QUOTE_REQUEST_NOT_FOUND", "Quote request not found.")
    return parsed_quote_id


def _not_found(
    code: str,
    message: str,
    details: str | None = None,
) -> JSONResponse:
    content: dict[str, object] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        content["error"]["details"] = details
    return JSONResponse(status_code=404, content=content)


def _bad_request(
    code: str,
    message: str,
    details: str | None = None,
) -> JSONResponse:
    content: dict[str, object] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        content["error"]["details"] = details
    return JSONResponse(status_code=400, content=content)


def _publish_client_quote_contract_for_signing(
    quote_id: UUID,
    *,
    service: QuoteToContractConversionService,
    quote_workflow: QuoteWorkflow,
    contract_document_service: ContractDocumentGenerationService,
    generated_document_service: GeneratedDocumentQueryService,
    generated_document_pdf_service: GeneratedDocumentPdfService,
) -> QuoteToContractConversionResult | JSONResponse:
    try:
        quote_document = service.latest_successful_quote_document(quote_id)
        if quote_document is None:
            workflow_result = quote_workflow.run(
                request_id=quote_id,
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
                                "The quote was approved but the quote document "
                                "could not be generated."
                            ),
                            "module_results": [
                                module_result.model_dump(mode="json")
                                for module_result in workflow_result.module_results
                            ],
                        },
                        "status": workflow_result.status,
                    },
                )

        result = service.publish_approved_quote(
            quote_id,
            quote_document=quote_document,
        )
    except ValueError as exc:
        return _not_found(
            "QUOTE_REQUEST_NOT_FOUND",
            "Quote request not found.",
            str(exc),
        )

    if result.result == "blocked" or result.contract is None:
        return JSONResponse(
            status_code=400,
            content=result.model_dump(mode="json"),
        )

    document = _ensure_contract_document_for_signing(
        result.contract.id,
        contract_document_service=contract_document_service,
        generated_document_service=generated_document_service,
    )
    if isinstance(document, JSONResponse):
        return document
    pdf_error = _ensure_generated_document_pdf(
        document.id,
        generated_document_pdf_service=generated_document_pdf_service,
    )
    if pdf_error is not None:
        return pdf_error
    return result


def _ensure_contract_document_for_signing(
    contract_id: UUID,
    *,
    contract_document_service: ContractDocumentGenerationService,
    generated_document_service: GeneratedDocumentQueryService,
) -> GeneratedDocumentReadModel | JSONResponse:
    try:
        existing_document = generated_document_service.get_latest_for_contract(
            contract_id
        )
    except ValueError as exc:
        return _not_found("CONTRACT_NOT_FOUND", "Contract not found.", str(exc))

    if existing_document is not None:
        return existing_document

    generation_result = contract_document_service.generate(
        contract_id,
        template_code=DEFAULT_CONTRACT_TEMPLATE_CODE,
    )
    if generation_result.document is not None:
        return generation_result.document

    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "CONTRACT_DOCUMENT_GENERATION_FAILED",
                "message": (
                    "The quote was published as a contract, but the contract "
                    "document could not be generated."
                ),
                "validation": generation_result.validation.model_dump(mode="json"),
                "module_results": [
                    module_result.model_dump(mode="json")
                    for module_result in generation_result.module_results
                ],
            },
            "status": generation_result.status,
        },
    )


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


def _claimable_contract_item(contract: ContractReadModel) -> ClaimableContractItem:
    asset = contract.asset
    return ClaimableContractItem(
        contract_id=contract.id,
        contract_number=contract.contract_number,
        display_id=contract.display_id or contract.contract_number or str(contract.id),
        policy_number=contract.contract_number,
        status=contract.status,
        effective_date=contract.effective_date,
        expiration_date=contract.expiration_date,
        insured_asset_id=asset.id if asset is not None else None,
        address=asset.address if asset is not None else None,
        coverage_amount=asset.declared_value if asset is not None else None,
    )


__all__ = ["generated_documents_router", "me_router", "quote_contract_router", "router"]
