from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from underwright.api.dependencies import (
    get_claim_attachment_storage_service,
    get_current_client_user,
    get_customer_profile_document_service,
    get_customer_profile_service,
)
from underwright.application.services.claim_attachment_storage_service import (
    ClaimAttachmentNotFoundError,
    ClaimAttachmentStorageService,
    ClaimAttachmentTooLargeError,
    EmptyClaimAttachmentError,
    UnsupportedClaimAttachmentContentTypeError,
)
from underwright.application.services.customer_profile_document_service import (
    CustomerProfileDocumentError,
    CustomerProfileDocumentNotFoundError,
    CustomerProfileDocumentOwnershipError,
    CustomerProfileDocumentService,
)
from underwright.application.services.customer_profile_service import (
    CustomerProfileIncompleteError,
    CustomerProfileNotFoundError,
    CustomerProfileService,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.customer_profile_document import CustomerProfileDocument
from underwright.domain.customer_profile import (
    CustomerProfileReadModel,
    CustomerProfileUpdate,
)

router = APIRouter(prefix="/me/customer-profile", tags=["client-profile"])


@router.get("", response_model=CustomerProfileReadModel)
def get_my_customer_profile(
    current_user: AuthUser = Depends(get_current_client_user),
    service: CustomerProfileService = Depends(get_customer_profile_service),
) -> CustomerProfileReadModel | JSONResponse:
    try:
        return service.get_profile(current_user)
    except CustomerProfileNotFoundError as exc:
        return _not_found("CUSTOMER_PROFILE_NOT_FOUND", "Customer profile not found.", str(exc))


@router.put("", response_model=CustomerProfileReadModel)
def update_my_customer_profile(
    body: CustomerProfileUpdate,
    current_user: AuthUser = Depends(get_current_client_user),
    service: CustomerProfileService = Depends(get_customer_profile_service),
) -> CustomerProfileReadModel | JSONResponse:
    try:
        return service.update_profile(user=current_user, update=body)
    except CustomerProfileIncompleteError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "CUSTOMER_PROFILE_INCOMPLETE",
                    "message": "Customer profile is incomplete.",
                    "status": exc.status,
                    "missing_fields": exc.missing_fields,
                }
            },
        )
    except CustomerProfileNotFoundError as exc:
        return _not_found("CUSTOMER_PROFILE_NOT_FOUND", "Customer profile not found.", str(exc))


@router.get("/documents", response_model=list[CustomerProfileDocument])
def list_my_customer_profile_documents(
    current_user: AuthUser = Depends(get_current_client_user),
    service: CustomerProfileDocumentService = Depends(
        get_customer_profile_document_service
    ),
) -> list[CustomerProfileDocument]:
    try:
        return service.list_for_user(current_user)
    except CustomerProfileDocumentOwnershipError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents", response_model=CustomerProfileDocument)
def upload_my_customer_profile_document(
    label: str = Form(...),
    document_type: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(get_current_client_user),
    service: CustomerProfileDocumentService = Depends(
        get_customer_profile_document_service
    ),
    storage_service: ClaimAttachmentStorageService = Depends(
        get_claim_attachment_storage_service
    ),
) -> CustomerProfileDocument:
    try:
        stored = storage_service.save_attachment(
            file_name=file.filename or "",
            content_type=file.content_type,
            content=file.file,
        )
        return service.create_for_user(
            user=current_user,
            label=label,
            document_type=document_type,
            stored_attachment=stored,
        )
    except UnsupportedClaimAttachmentContentTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ClaimAttachmentTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except (EmptyClaimAttachmentError, CustomerProfileDocumentError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        file.file.close()


@router.get("/documents/{document_id}/download")
def download_my_customer_profile_document(
    document_id: UUID,
    current_user: AuthUser = Depends(get_current_client_user),
    service: CustomerProfileDocumentService = Depends(
        get_customer_profile_document_service
    ),
    storage_service: ClaimAttachmentStorageService = Depends(
        get_claim_attachment_storage_service
    ),
) -> FileResponse:
    try:
        document = service.get_for_user(user=current_user, document_id=document_id)
        stored = storage_service.get_attachment(document.storage_key)
    except CustomerProfileDocumentOwnershipError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CustomerProfileDocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc
    except ClaimAttachmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document file not found.") from exc

    return FileResponse(
        stored.path,
        media_type=stored.content_type,
        filename=stored.file_name,
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_my_customer_profile_document(
    document_id: UUID,
    current_user: AuthUser = Depends(get_current_client_user),
    service: CustomerProfileDocumentService = Depends(
        get_customer_profile_document_service
    ),
) -> Response:
    try:
        service.delete_for_user(user=current_user, document_id=document_id)
    except CustomerProfileDocumentOwnershipError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CustomerProfileDocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc
    return Response(status_code=204)


def _not_found(code: str, message: str, details: str | None = None) -> JSONResponse:
    content: dict[str, object] = {"error": {"code": code, "message": message}}
    if details:
        content["error"]["details"] = details
    return JSONResponse(status_code=404, content=content)


__all__ = ["router"]
