from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from underwright.api.dependencies import (
    get_current_employee_user,
    get_wording_document_service,
)
from underwright.application.services.wording_document_service import (
    WordingDocumentNotFoundError,
    WordingDocumentService,
    WordingVersionNotFoundError,
)
from underwright.domain.wording import WordingDocument, WordingDocumentVersion


router = APIRouter(
    tags=["wording-documents"],
    dependencies=[Depends(get_current_employee_user)],
)


@router.get("/wording-documents", response_model=list[WordingDocument])
def list_wording_documents(
    service: WordingDocumentService = Depends(get_wording_document_service),
) -> list[WordingDocument]:
    return service.list_wording_documents()


@router.get(
    "/wording-documents/{wording_document_id}",
    response_model=WordingDocument,
)
def get_wording_document(
    wording_document_id: int,
    service: WordingDocumentService = Depends(get_wording_document_service),
) -> WordingDocument | JSONResponse:
    try:
        return service.get_wording_document(wording_document_id)
    except WordingDocumentNotFoundError as exc:
        return _not_found("WORDING_DOCUMENT_NOT_FOUND", "Wording document not found.", str(exc))


@router.get(
    "/wording-documents/{wording_document_id}/versions",
    response_model=list[WordingDocumentVersion],
)
def list_wording_versions(
    wording_document_id: int,
    service: WordingDocumentService = Depends(get_wording_document_service),
) -> list[WordingDocumentVersion] | JSONResponse:
    try:
        return service.list_wording_versions(wording_document_id)
    except WordingDocumentNotFoundError as exc:
        return _not_found("WORDING_DOCUMENT_NOT_FOUND", "Wording document not found.", str(exc))


@router.get(
    "/wording-documents/{wording_document_id}/versions/current",
    response_model=WordingDocumentVersion,
)
def get_current_wording_version(
    wording_document_id: int,
    service: WordingDocumentService = Depends(get_wording_document_service),
) -> WordingDocumentVersion | JSONResponse:
    try:
        return service.get_current_published_version(wording_document_id)
    except WordingDocumentNotFoundError as exc:
        return _not_found("WORDING_DOCUMENT_NOT_FOUND", "Wording document not found.", str(exc))
    except WordingVersionNotFoundError as exc:
        return _not_found("WORDING_VERSION_NOT_FOUND", "Wording version not found.", str(exc))


@router.get(
    "/wording-document-versions/{wording_version_id}",
    response_model=WordingDocumentVersion,
)
def get_wording_version(
    wording_version_id: int,
    service: WordingDocumentService = Depends(get_wording_document_service),
) -> WordingDocumentVersion | JSONResponse:
    try:
        return service.get_wording_version(wording_version_id)
    except WordingVersionNotFoundError as exc:
        return _not_found("WORDING_VERSION_NOT_FOUND", "Wording version not found.", str(exc))


def _not_found(code: str, message: str, details: str | None = None) -> JSONResponse:
    content: dict[str, object] = {"error": {"code": code, "message": message}}
    if details:
        content["error"]["details"] = details
    return JSONResponse(status_code=404, content=content)


__all__ = ["router"]
