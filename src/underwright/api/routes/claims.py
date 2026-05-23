from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from html import escape
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from underwright.api.dependencies import (
    get_case_context_service,
    get_claim_attachment_processing_service,
    get_claim_attachment_storage_service,
    get_claim_decision_email_send_service,
    get_claim_decision_rewording_service,
    get_claim_evidence_ingestion_service,
    get_contract_query_service,
    get_claim_request_service,
    get_claim_review_query_service,
    get_claim_workflow,
    get_coverage_precheck_workflow,
    get_current_auth_user,
    get_current_client_user,
    get_current_employee_user,
    get_customer_profile_document_service,
    get_customer_profile_service,
    get_evidence_request_email_send_service,
    get_evidence_refresh_workflow,
    get_evidence_request_draft_service,
    require_internal_api_key,
)
from underwright.application.services.customer_profile_service import (
    CustomerProfileIncompleteError,
    CustomerProfileService,
)
from underwright.application.services.customer_profile_document_service import (
    CustomerProfileDocumentNotFoundError,
    CustomerProfileDocumentService,
)
from underwright.application.services.claim_attachment_storage_service import (
    ClaimAttachmentNotFoundError,
    ClaimAttachmentStorageService,
    ClaimAttachmentTooLargeError,
    EmptyClaimAttachmentError,
    UnsupportedClaimAttachmentContentTypeError,
)
from underwright.application.services.claim_attachment_processing_service import (
    ClaimAttachmentProcessingService,
)
from underwright.application.services.claim_decision_rewording_service import (
    ClaimDecisionRewordingNotConfiguredError,
    ClaimDecisionRewordingProviderError,
    ClaimDecisionRewordingService,
)
from underwright.application.services.claim_evidence_ingestion_service import (
    ClaimEvidenceIngestionService,
)
from underwright.application.services.case_context_service import CaseContextService
from underwright.application.services.claim_request_service import (
    ClaimDecisionError,
    ClaimRequestService,
)
from underwright.application.services.claim_review_query_service import (
    ClaimReviewQueryService,
)
from underwright.application.services.contract_query_service import ContractQueryService
from underwright.application.services.evidence_request_draft_service import (
    EvidenceRequestDraftAlreadySentError,
    EvidenceRequestEmailFailedError,
    EvidenceRequestDraftError,
    EvidenceRequestDraftInvalidError,
    EvidenceRequestDraftNotFoundError,
    EvidenceRequestDraftService,
)
from underwright.application.services.email_service import EmailService
from underwright.application.workflows.claim_workflow import ClaimWorkflow
from underwright.application.workflows.coverage_precheck_workflow import (
    CoveragePrecheckWorkflow,
)
from underwright.application.workflows.evidence_refresh_workflow import (
    EvidenceRefreshWorkflow,
)
from underwright.domain.claim_analysis import (
    EvidenceRequestDraft,
    ReceivedClaimEvidence,
    ReceivedEvidenceAttachment,
)
from underwright.domain.claim_request import ClaimAttachmentMetadata, ClaimRequest
from underwright.domain.contract_lifecycle import AddressSnapshot, ContractReadModel
from underwright.domain.email_message import EmailAttachment
from underwright.domain.auth_user import AuthUser
from underwright.domain.module_result import ModuleResult

router = APIRouter(prefix="/claims", tags=["claims"])
underwriter_router = APIRouter(
    prefix="/underwriter/claims",
    tags=["underwriter-claims"],
)
internal_router = APIRouter(
    prefix="/internal/claims",
    tags=["internal-claims"],
)
me_router = APIRouter(prefix="/me/claims", tags=["client-claims"])
logger = logging.getLogger(__name__)
EMPLOYEE_ROLES = {"employee", "underwriter", "admin"}


class CreateClaimRequestBody(BaseModel):
    request_id: UUID | None = None
    client_id: int | str | UUID
    request_status: str = "submitted"
    client_data: dict[str, Any] = Field(default_factory=dict)
    claim_data: dict[str, Any] = Field(default_factory=dict)
    attachments: list[ClaimAttachmentMetadata] = Field(default_factory=list)


class CreateMyClaimRequestBody(BaseModel):
    request_id: UUID | None = None
    request_status: str = "submitted"
    client_data: dict[str, Any] = Field(default_factory=dict)
    claim_data: dict[str, Any] = Field(default_factory=dict)
    attachments: list[ClaimAttachmentMetadata] = Field(default_factory=list)


class ModuleResultResponse(BaseModel):
    module_name: str
    status: str
    summary: str
    source_fields_used: list[str] = Field(default_factory=list)


class ClaimAnalysisResponse(BaseModel):
    case_id: UUID | None = None
    status: str
    claim_request: ClaimRequest
    review_view: dict[str, Any] | None = None
    module_results: list[ModuleResultResponse]


class EvidenceRequestDraftResponse(BaseModel):
    needed: bool
    message: str
    draft: EvidenceRequestDraft | None = None


class EvidenceRequestDraftUpdateRequest(BaseModel):
    subject: str
    body: str
    recipients: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    source_suggestion_id: str | None = None
    requested_document_type: str | None = None
    due_date: str | None = None


class EvidenceRequestDraftMutationResponse(BaseModel):
    message: str
    draft: EvidenceRequestDraft


class DemoInboundEmailResponse(BaseModel):
    message: str
    to_email: str
    subject: str
    provider_message_id: str | None = None
    reply_token: str
    attachment_file_name: str


class ClaimCommunicationSuggestionStateResponse(BaseModel):
    suggestion_id: str
    status: str
    message: str


class SentEmailResponse(BaseModel):
    id: UUID
    case_id: UUID | None = None
    direction: str
    from_email: str
    to_email: str
    subject: str
    body: str
    status: str
    provider_message_id: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    sent_at: datetime | None = None


class ClaimDecisionRequest(BaseModel):
    decision: str
    justification: str


class ClaimDecisionJustificationRewordRequest(BaseModel):
    justification: str
    decision: str | None = None


class ClaimDecisionJustificationRewordResponse(BaseModel):
    suggestion: str


class IncomingEvidenceAttachmentBody(BaseModel):
    filename: str
    storage_key: str | None = None
    document_id: UUID | str | None = None
    content_type: str | None = None


class IncomingEvidenceBody(BaseModel):
    evidence_request_id: UUID | str | None = None
    sender_email: str
    message_body: str | None = None
    attachments: list[IncomingEvidenceAttachmentBody] = Field(default_factory=list)
    claim_fact_updates: dict[str, Any] = Field(default_factory=dict)


class IncomingEvidenceResponse(BaseModel):
    request_id: UUID
    evidence_received: bool
    received_evidence_count: int
    refresh_status: str
    refresh_pending_reason: str | None = None
    coverage_assessment_reran: bool = False
    message: str


class ClaimReviewResponse(BaseModel):
    case_id: UUID | None = None
    status: str
    review_state: str
    claim_request: ClaimRequest
    review_view: dict[str, Any]
    evidence_request_draft: EvidenceRequestDraft | None = None


@router.post(
    "/attachments",
    response_model=list[ClaimAttachmentMetadata],
)
def upload_claim_attachments(
    files: list[UploadFile] = File(...),
    _current_user: AuthUser = Depends(get_current_auth_user),
) -> JSONResponse:
    for uploaded_file in files:
        uploaded_file.file.close()
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "CLAIM_ATTACHMENT_CLAIM_REQUIRED",
                "message": "Upload attachments through /claims/{claim_id}/attachments.",
            }
        },
    )


@router.get("/attachments/{storage_key}")
def download_claim_attachment(
    storage_key: str,
    _current_user: AuthUser = Depends(get_current_auth_user),
) -> JSONResponse:
    return _not_found(
        "CLAIM_ATTACHMENT_NOT_FOUND",
        "Claim attachment not found.",
    )


@router.post(
    "/{request_id}/attachments",
    response_model=list[ClaimAttachmentMetadata],
)
def upload_claim_attachments_for_claim(
    request_id: UUID,
    files: list[UploadFile] = File(...),
    document_roles: list[str] | None = Form(None),
    current_user: AuthUser = Depends(get_current_auth_user),
    claim_service: ClaimRequestService = Depends(get_claim_request_service),
    storage_service: ClaimAttachmentStorageService = Depends(
        get_claim_attachment_storage_service
    ),
    processing_service: ClaimAttachmentProcessingService = Depends(
        get_claim_attachment_processing_service
    ),
) -> list[ClaimAttachmentMetadata]:
    _claim_for_authenticated_user(request_id, current_user, claim_service)
    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one attachment file is required.",
        )

    normalized_roles = [str(role or "").strip() for role in list(document_roles or [])]
    if normalized_roles and len(normalized_roles) != len(files):
        raise HTTPException(
            status_code=400,
            detail="document_roles must contain one value for each uploaded file.",
        )

    attachments: list[ClaimAttachmentMetadata] = []
    for index, uploaded_file in enumerate(files):
        document_role = normalized_roles[index] if index < len(normalized_roles) else None
        try:
            stored = storage_service.save_attachment(
                file_name=uploaded_file.filename or "",
                content_type=uploaded_file.content_type,
                content=uploaded_file.file,
            )
            attachments.append(
                _claim_scoped_attachment_metadata(
                    request_id,
                    stored,
                    current_user,
                    document_role=document_role,
                )
            )
        except UnsupportedClaimAttachmentContentTypeError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        except ClaimAttachmentTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except EmptyClaimAttachmentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            uploaded_file.file.close()

    _append_claim_attachments(request_id, attachments, claim_service)
    processed_claim = _attempt_claim_attachment_processing(
        request_id,
        processing_service,
    )
    if processed_claim is None:
        return attachments

    new_attachment_ids = {
        str(item.metadata.get("attachment_id") or "")
        for item in attachments
    }
    return [
        item
        for item in _active_claim_attachments(processed_claim)
        if str(item.metadata.get("attachment_id") or "") in new_attachment_ids
    ]


@router.get(
    "/{request_id}/attachments",
    response_model=list[ClaimAttachmentMetadata],
)
def list_claim_attachments(
    request_id: UUID,
    current_user: AuthUser = Depends(get_current_auth_user),
    claim_service: ClaimRequestService = Depends(get_claim_request_service),
) -> list[ClaimAttachmentMetadata]:
    claim = _claim_for_authenticated_user(request_id, current_user, claim_service)
    return _active_claim_attachments(claim)


@router.get("/{request_id}/attachments/{attachment_id}")
def download_claim_attachment_for_claim(
    request_id: UUID,
    attachment_id: UUID,
    current_user: AuthUser = Depends(get_current_auth_user),
    claim_service: ClaimRequestService = Depends(get_claim_request_service),
    storage_service: ClaimAttachmentStorageService = Depends(
        get_claim_attachment_storage_service
    ),
) -> FileResponse:
    claim = _claim_for_authenticated_user(request_id, current_user, claim_service)
    attachment = _claim_attachment_by_id(claim, attachment_id)
    storage_key = str(attachment.metadata.get("storage_key") or "")
    try:
        stored_attachment = storage_service.get_attachment(storage_key)
    except ClaimAttachmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Attachment not found.") from exc

    return FileResponse(
        stored_attachment.path,
        media_type=stored_attachment.content_type,
        filename=stored_attachment.file_name,
    )


@router.get("/{request_id}/profile-documents/{document_id}")
def download_claim_profile_document(
    request_id: UUID,
    document_id: UUID,
    current_user: AuthUser = Depends(get_current_auth_user),
    claim_service: ClaimRequestService = Depends(get_claim_request_service),
    profile_document_service: CustomerProfileDocumentService = Depends(
        get_customer_profile_document_service
    ),
    storage_service: ClaimAttachmentStorageService = Depends(
        get_claim_attachment_storage_service
    ),
) -> FileResponse:
    claim = _claim_for_authenticated_user(request_id, current_user, claim_service)
    if not _claim_has_profile_document_attachment(claim, document_id):
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        document = profile_document_service.get_for_customer_id(
            customer_id=int(claim.client_id),
            document_id=document_id,
        )
        stored_attachment = storage_service.get_attachment(document.storage_key)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc
    except CustomerProfileDocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc
    except ClaimAttachmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document file not found.") from exc

    return FileResponse(
        stored_attachment.path,
        media_type=stored_attachment.content_type,
        filename=stored_attachment.file_name,
    )


@router.delete("/{request_id}/attachments/{attachment_id}", status_code=204)
def delete_claim_attachment_for_claim(
    request_id: UUID,
    attachment_id: UUID,
    current_user: AuthUser = Depends(get_current_auth_user),
    claim_service: ClaimRequestService = Depends(get_claim_request_service),
) -> Response:
    claim = _claim_for_authenticated_user(request_id, current_user, claim_service)
    updated = False
    now = _utc_iso()
    next_attachments: list[dict[str, Any]] = []
    for attachment in claim.attachments:
        data = attachment.model_dump(mode="json")
        metadata = dict(data.get("metadata") or {})
        if str(metadata.get("attachment_id") or "") == str(attachment_id):
            metadata["status"] = "deleted"
            metadata["deleted_at"] = now
            data["metadata"] = metadata
            updated = True
        next_attachments.append(data)
    if not updated:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    claim_service.update_request_attachments(request_id, next_attachments)
    return Response(status_code=204)


@router.post(
    "/decision-justification/reword",
    response_model=ClaimDecisionJustificationRewordResponse,
)
def reword_claim_decision_justification(
    body: ClaimDecisionJustificationRewordRequest,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: ClaimDecisionRewordingService = Depends(
        get_claim_decision_rewording_service
    ),
) -> ClaimDecisionJustificationRewordResponse | JSONResponse:
    try:
        suggestion = service.reword_decision_justification(
            justification=body.justification,
            decision=body.decision,
        )
    except ClaimDecisionRewordingNotConfiguredError:
        raise HTTPException(
            status_code=503,
            detail="AI rewording is not configured.",
        ) from None
    except ClaimDecisionRewordingProviderError:
        logger.exception("Claim decision AI rewording failed")
        raise HTTPException(
            status_code=502,
            detail="AI suggestion could not be generated.",
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ClaimDecisionJustificationRewordResponse(suggestion=suggestion)


@router.post("", response_model=ClaimRequest)
def create_claim_request(
    body: CreateClaimRequestBody,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: ClaimRequestService = Depends(get_claim_request_service),
    processing_service: ClaimAttachmentProcessingService = Depends(
        get_claim_attachment_processing_service
    ),
    coverage_precheck_workflow: CoveragePrecheckWorkflow = Depends(
        get_coverage_precheck_workflow
    ),
) -> ClaimRequest:
    request = ClaimRequest(
        request_id=body.request_id or uuid4(),
        client_id=body.client_id,
        request_status=body.request_status,
        client_data=body.client_data,
        claim_data=body.claim_data,
        attachments=body.attachments,
    )
    created_request = service.create_client_claim_request(request)
    created_request = _attempt_claim_attachment_processing(
        created_request.request_id,
        processing_service,
    ) or created_request
    try:
        return coverage_precheck_workflow.run(created_request.request_id).claim_request
    except Exception:
        logger.exception(
            "Initial coverage precheck failed after claim creation for "
            "claim_request_id=%s",
            created_request.request_id,
        )
        return created_request


@router.get("/client", response_model=list[ClaimRequest])
def list_client_claim_requests(
    client_id: int | str | UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: ClaimRequestService = Depends(get_claim_request_service),
) -> list[ClaimRequest]:
    return service.list_client_claim_requests(client_id)


@underwriter_router.get("", response_model=list[ClaimRequest])
def list_underwriter_claim_requests(
    status: str = "submitted",
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: ClaimRequestService = Depends(get_claim_request_service),
) -> list[ClaimRequest]:
    return service.list_underwriter_claim_queue_requests(status)


@me_router.get("", response_model=list[ClaimRequest])
def list_my_claim_requests(
    current_user: AuthUser = Depends(get_current_client_user),
    service: ClaimRequestService = Depends(get_claim_request_service),
) -> list[ClaimRequest]:
    if current_user.client_id is None:
        return []
    return service.list_client_claim_requests(current_user.client_id)


@me_router.post("", response_model=ClaimRequest)
def create_my_claim_request(
    body: CreateMyClaimRequestBody,
    current_user: AuthUser = Depends(get_current_client_user),
    service: ClaimRequestService = Depends(get_claim_request_service),
    processing_service: ClaimAttachmentProcessingService = Depends(
        get_claim_attachment_processing_service
    ),
    contract_query_service: ContractQueryService = Depends(get_contract_query_service),
    coverage_precheck_workflow: CoveragePrecheckWorkflow = Depends(
        get_coverage_precheck_workflow
    ),
    profile_service: CustomerProfileService = Depends(get_customer_profile_service),
) -> ClaimRequest | JSONResponse:
    try:
        profile_service.ensure_complete_profile(current_user)
    except CustomerProfileIncompleteError as exc:
        return _profile_incomplete(exc)

    contract = _claimable_contract_for_claim(
        body.claim_data,
        current_user,
        contract_query_service,
    )
    if isinstance(contract, JSONResponse):
        return contract

    request = ClaimRequest(
        request_id=body.request_id or uuid4(),
        client_id=current_user.client_id,
        request_status=body.request_status,
        client_data={
            "email": current_user.email,
            "full_name": current_user.full_name,
            **body.client_data,
        },
        claim_data=_canonical_claim_data(body.claim_data, contract),
        attachments=body.attachments,
    )
    created_request = service.create_client_claim_request(request)
    created_request = _attempt_claim_attachment_processing(
        created_request.request_id,
        processing_service,
    ) or created_request
    try:
        return coverage_precheck_workflow.run(created_request.request_id).claim_request
    except Exception:
        logger.exception(
            "Initial coverage precheck failed after claim creation for "
            "claim_request_id=%s",
            created_request.request_id,
        )
        return created_request


@me_router.get("/{request_id}", response_model=ClaimRequest)
def get_my_claim_request(
    request_id: UUID,
    current_user: AuthUser = Depends(get_current_client_user),
    service: ClaimRequestService = Depends(get_claim_request_service),
) -> ClaimRequest | JSONResponse:
    try:
        claim = service.get_claim_request_detail(request_id)
    except ValueError as exc:
        return _not_found("CLAIM_REQUEST_NOT_FOUND", "Claim request not found.", str(exc))
    if current_user.client_id is None or str(claim.client_id) != str(current_user.client_id):
        return _not_found("CLAIM_REQUEST_NOT_FOUND", "Claim request not found.")
    return claim


@underwriter_router.get("/{request_id}", response_model=ClaimRequest)
def get_underwriter_claim_request(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: ClaimRequestService = Depends(get_claim_request_service),
) -> ClaimRequest:
    return service.get_claim_request_detail(request_id)


@underwriter_router.post(
    "/{request_id}/start-review",
    response_model=ClaimRequest,
)
def start_underwriter_claim_review(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: ClaimRequestService = Depends(get_claim_request_service),
) -> ClaimRequest | JSONResponse:
    try:
        return service.start_underwriter_review(request_id)
    except ValueError as exc:
        return _not_found("CLAIM_REQUEST_NOT_FOUND", "Claim request not found.", str(exc))


@underwriter_router.get(
    "/{request_id}/review",
    response_model=ClaimReviewResponse,
)
def get_latest_claim_review(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    query_service: ClaimReviewQueryService = Depends(
        get_claim_review_query_service
    ),
) -> ClaimReviewResponse | JSONResponse:
    try:
        result = query_service.get_latest_claim_review(request_id)
    except ValueError as exc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "CLAIM_REQUEST_NOT_FOUND",
                    "message": "Claim request not found.",
                    "details": str(exc),
                }
            },
        )

    return ClaimReviewResponse(
        case_id=(
            result.case_context.case_metadata.case_id
            if result.case_context is not None
            else None
        ),
        status=result.status,
        review_state=result.review_state,
        claim_request=result.claim_request,
        review_view=result.review_view,
        evidence_request_draft=result.evidence_request_draft,
    )


@underwriter_router.post(
    "/{request_id}/start-analysis",
    response_model=ClaimAnalysisResponse,
)
def start_claim_analysis(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    workflow: ClaimWorkflow = Depends(get_claim_workflow),
    service: ClaimRequestService = Depends(get_claim_request_service),
) -> ClaimAnalysisResponse | JSONResponse:
    try:
        result = workflow.run(request_id)
        claim_request = service.get_claim_request_detail(request_id)
    except ValueError as exc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "CLAIM_REQUEST_NOT_FOUND",
                    "message": "Claim request not found.",
                    "details": str(exc),
                }
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "CLAIM_ANALYSIS_ERROR",
                    "message": "Failed to run claim analysis workflow.",
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
                    "code": "CLAIM_WORKFLOW_FAILED",
                    "message": "Claim analysis workflow failed.",
                    "module_results": [
                        item.model_dump(mode="json")
                        for item in serialized_module_results
                    ],
                },
                "case_id": str(result.case_context.case_metadata.case_id),
                "status": result.status,
            },
        )

    return ClaimAnalysisResponse(
        case_id=result.case_context.case_metadata.case_id,
        status=result.status,
        claim_request=claim_request,
        review_view=_review_view_data(result.review_view),
        module_results=serialized_module_results,
    )


@underwriter_router.post(
    "/{request_id}/attachments/refresh-analysis",
    response_model=ClaimReviewResponse,
)
def refresh_claim_attachment_analysis(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    processing_service: ClaimAttachmentProcessingService = Depends(
        get_claim_attachment_processing_service
    ),
    query_service: ClaimReviewQueryService = Depends(
        get_claim_review_query_service
    ),
) -> ClaimReviewResponse | JSONResponse:
    try:
        processing_service.process_request_attachments(request_id)
        result = query_service.get_latest_claim_review(request_id)
    except ValueError as exc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "CLAIM_REQUEST_NOT_FOUND",
                    "message": "Claim request not found.",
                    "details": str(exc),
                }
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "CLAIM_ATTACHMENT_ANALYSIS_REFRESH_ERROR",
                    "message": "Failed to refresh claim attachment AI analysis.",
                    "details": str(exc),
                }
            },
        )

    return ClaimReviewResponse(
        case_id=(
            result.case_context.case_metadata.case_id
            if result.case_context is not None
            else None
        ),
        status=result.status,
        review_state=result.review_state,
        claim_request=result.claim_request,
        review_view=result.review_view,
        evidence_request_draft=result.evidence_request_draft,
    )


@underwriter_router.post(
    "/{request_id}/evidence-request/draft",
    response_model=EvidenceRequestDraftResponse,
)
def create_evidence_request_draft(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    case_context_service: CaseContextService = Depends(get_case_context_service),
    draft_service: EvidenceRequestDraftService = Depends(
        get_evidence_request_draft_service
    ),
) -> EvidenceRequestDraftResponse | JSONResponse:
    try:
        case_context = (
            case_context_service.get_latest_claim_case_context_by_request_id(
                request_id
            )
        )
        draft = draft_service.generate_draft(case_context)
    except ValueError as exc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "CLAIM_REVIEW_NOT_FOUND",
                    "message": "Latest claim review findings were not found.",
                    "details": str(exc),
                }
            },
        )

    if draft is None:
        return EvidenceRequestDraftResponse(
            needed=False,
            message="No evidence request is needed for this claim review.",
            draft=None,
        )

    case_context_service.save_case_context(case_context)
    return EvidenceRequestDraftResponse(
        needed=True,
        message="Evidence request draft is ready for underwriter review.",
        draft=draft,
    )


@underwriter_router.patch(
    "/{request_id}/evidence-request/draft",
    response_model=EvidenceRequestDraftMutationResponse,
)
def update_evidence_request_draft(
    request_id: UUID,
    body: EvidenceRequestDraftUpdateRequest,
    _current_user: AuthUser = Depends(get_current_employee_user),
    case_context_service: CaseContextService = Depends(get_case_context_service),
    draft_service: EvidenceRequestDraftService = Depends(
        get_evidence_request_draft_service
    ),
) -> EvidenceRequestDraftMutationResponse | JSONResponse:
    try:
        case_context = (
            case_context_service.get_latest_claim_case_context_by_request_id(
                request_id
            )
        )
        draft = draft_service.save_draft(
            case_context,
            subject=body.subject,
            body=body.body,
            recipients=body.recipients,
            required_documents=body.required_documents,
            source_suggestion_id=body.source_suggestion_id,
            requested_document_type=body.requested_document_type,
            due_date=body.due_date,
        )
    except ValueError as exc:
        if isinstance(exc, EvidenceRequestDraftError):
            return _evidence_request_draft_error_response(exc)
        return _not_found("CLAIM_REVIEW_NOT_FOUND", "Claim review not found.", str(exc))

    case_context_service.save_case_context(case_context)
    return EvidenceRequestDraftMutationResponse(
        message="Evidence request draft saved.",
        draft=draft,
    )


@underwriter_router.post(
    "/{request_id}/evidence-request/draft/send",
    response_model=EvidenceRequestDraftMutationResponse,
)
def send_evidence_request_draft(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    case_context_service: CaseContextService = Depends(get_case_context_service),
    draft_service: EvidenceRequestDraftService = Depends(
        get_evidence_request_draft_service
    ),
    email_service: EmailService = Depends(get_evidence_request_email_send_service),
) -> EvidenceRequestDraftMutationResponse | JSONResponse:
    try:
        case_context = (
            case_context_service.get_latest_claim_case_context_by_request_id(
                request_id
            )
        )
        draft, recipient = draft_service.prepare_draft_send(case_context)
    except ValueError as exc:
        if isinstance(exc, EvidenceRequestDraftError):
            return _evidence_request_draft_error_response(exc)
        return _not_found("CLAIM_REVIEW_NOT_FOUND", "Claim review not found.", str(exc))

    try:
        email = email_service.send_case_email(
            case_id=request_id,
            request_id=request_id,
            to_email=recipient,
            subject=_evidence_request_reply_subject(draft.subject, draft.reply_token),
            body=draft.body,
            reply_to=_evidence_request_reply_to(draft.reply_token),
        )
    except Exception as exc:
        draft = draft_service.mark_draft_send_failed(
            case_context,
            sent_to=recipient,
            error_message=str(exc),
        )
        case_context_service.save_case_context(case_context)
        return _evidence_request_email_failed_response(draft.send_error_message)

    if email.status != "SENT":
        draft = draft_service.mark_draft_send_failed(
            case_context,
            email_message_id=email.id,
            provider_message_id=email.provider_message_id,
            sent_to=recipient,
            error_message=email.error_message or "Email delivery failed.",
        )
        case_context_service.save_case_context(case_context)
        return _evidence_request_email_failed_response(draft.send_error_message)

    draft = draft_service.mark_draft_sent(
        case_context,
        email_message_id=email.id,
        provider_message_id=email.provider_message_id,
        sent_at=email.sent_at,
        sent_to=recipient,
    )
    case_context_service.save_case_context(case_context)
    return EvidenceRequestDraftMutationResponse(
        message="Evidence request email sent.",
        draft=draft,
    )


@underwriter_router.post(
    "/{request_id}/communication/demo-inbound-email",
    response_model=DemoInboundEmailResponse,
)
def send_demo_inbound_claim_email(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    case_context_service: CaseContextService = Depends(get_case_context_service),
    draft_service: EvidenceRequestDraftService = Depends(
        get_evidence_request_draft_service
    ),
    email_service: EmailService = Depends(get_evidence_request_email_send_service),
) -> DemoInboundEmailResponse | JSONResponse:
    if not _configured_claim_inbound_email_address():
        return _demo_inbound_email_error_response(
            409,
            "CLAIM_INBOUND_EMAIL_ADDRESS_REQUIRED",
            (
                "Configure CLAIM_INBOUND_EMAIL_ADDRESS before triggering a demo "
                "inbound email."
            ),
        )

    try:
        case_context = (
            case_context_service.get_latest_claim_case_context_by_request_id(
                request_id
            )
        )
        draft = draft_service.prepare_demo_inbound_email(case_context)
    except ValueError as exc:
        if isinstance(exc, EvidenceRequestDraftError):
            return _evidence_request_draft_error_response(exc)
        return _not_found("CLAIM_REVIEW_NOT_FOUND", "Claim review not found.", str(exc))

    case_context_service.save_case_context(case_context)
    to_email = _evidence_request_reply_to(draft.reply_token)
    if not to_email:
        return _demo_inbound_email_error_response(
            409,
            "CLAIM_INBOUND_REPLY_ADDRESS_UNAVAILABLE",
            "Could not build the Postmark inbound reply address.",
        )

    subject = _evidence_request_reply_subject(
        f"Re: {draft.subject}",
        draft.reply_token,
    )
    attachment = _demo_inbound_email_attachment(request_id, draft)
    body = "\n\n".join(
        [
            "This is a demo client reply generated from Underwright.",
            "I attached the requested evidence so the claim review can continue.",
        ]
    )
    email = email_service.send_case_email(
        case_id=request_id,
        request_id=request_id,
        to_email=to_email,
        subject=subject,
        body=body,
        attachments=[attachment],
    )
    if email.status != "SENT":
        return _demo_inbound_email_error_response(
            502,
            "DEMO_INBOUND_EMAIL_FAILED",
            email.error_message or "Demo inbound email delivery failed.",
        )

    return DemoInboundEmailResponse(
        message="Demo inbound email sent through Postmark.",
        to_email=to_email,
        subject=subject,
        provider_message_id=email.provider_message_id,
        reply_token=draft.reply_token or "",
        attachment_file_name=attachment.file_name,
    )


@underwriter_router.post(
    "/{request_id}/communication-suggestions/{suggestion_id}/dismiss",
    response_model=ClaimCommunicationSuggestionStateResponse,
)
def dismiss_claim_communication_suggestion(
    request_id: UUID,
    suggestion_id: str,
    _current_user: AuthUser = Depends(get_current_employee_user),
    case_context_service: CaseContextService = Depends(get_case_context_service),
    draft_service: EvidenceRequestDraftService = Depends(
        get_evidence_request_draft_service
    ),
) -> ClaimCommunicationSuggestionStateResponse | JSONResponse:
    try:
        case_context = (
            case_context_service.get_latest_claim_case_context_by_request_id(
                request_id
            )
        )
        state = draft_service.dismiss_suggestion(case_context, suggestion_id)
    except ValueError as exc:
        if isinstance(exc, EvidenceRequestDraftError):
            return _evidence_request_draft_error_response(exc)
        return _not_found("CLAIM_REVIEW_NOT_FOUND", "Claim review not found.", str(exc))

    case_context_service.save_case_context(case_context)
    return ClaimCommunicationSuggestionStateResponse(
        suggestion_id=state.suggestion_id,
        status=state.status,
        message="AI follow-up suggestion dismissed.",
    )


@underwriter_router.post(
    "/{request_id}/decision",
    response_model=ClaimRequest,
)
def submit_claim_decision(
    request_id: UUID,
    body: ClaimDecisionRequest,
    current_user: AuthUser = Depends(get_current_employee_user),
    claim_service: ClaimRequestService = Depends(get_claim_request_service),
) -> ClaimRequest | JSONResponse:
    try:
        return claim_service.submit_claim_decision(
            request_id,
            decision=body.decision,
            justification=body.justification,
            decided_by_auth_user_id=current_user.id,
            decided_by_email=current_user.email,
        )
    except ValueError as exc:
        if isinstance(exc, ClaimDecisionError):
            return _decision_error_response(exc)
        return _not_found("CLAIM_REQUEST_NOT_FOUND", "Claim request not found.", str(exc))


@underwriter_router.post(
    "/{request_id}/decision-email",
    response_model=SentEmailResponse,
)
def send_claim_decision_email(
    request_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    claim_service: ClaimRequestService = Depends(get_claim_request_service),
    email_service: EmailService = Depends(get_claim_decision_email_send_service),
) -> SentEmailResponse | JSONResponse:
    try:
        claim = claim_service.get_claim_request_detail(request_id)
    except ValueError as exc:
        return _not_found("CLAIM_REQUEST_NOT_FOUND", "Claim request not found.", str(exc))

    decision_error = _claim_decision_email_blocker(claim)
    if decision_error is not None:
        return decision_error

    if _has_sent_claim_decision_email(claim, email_service):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "CLAIM_DECISION_EMAIL_ALREADY_SENT",
                    "message": "Claim decision email has already been sent.",
                }
            },
        )

    to_email = _claim_decision_recipient(claim)
    if not to_email:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "CLAIM_DECISION_EMAIL_RECIPIENT_REQUIRED",
                    "message": "Claim decision email recipient is missing.",
                }
            },
        )

    subject = "Your Underwright claim decision"
    text_body, html_body = _claim_decision_email_body(claim)
    email = email_service.send_case_email(
        case_id=request_id,
        to_email=to_email,
        subject=subject,
        body=text_body,
        html_body=html_body,
    )
    if email.status == "SENT" and email.sent_at is not None:
        claim_service.mark_decision_email_sent(
            request_id,
            email_message_id=email.id,
            sent_at=email.sent_at,
        )
    return SentEmailResponse(
        id=email.id,
        case_id=email.case_id,
        direction=email.direction,
        from_email=email.from_email,
        to_email=email.to_email,
        subject=email.subject,
        body=email.body,
        status=email.status,
        provider_message_id=email.provider_message_id,
        error_message=email.error_message,
        created_at=email.created_at,
        sent_at=email.sent_at,
    )


@internal_router.post(
    "/{request_id}/evidence",
    response_model=IncomingEvidenceResponse,
)
def receive_claim_evidence(
    request_id: UUID,
    body: IncomingEvidenceBody,
    _internal_access: bool = Depends(require_internal_api_key),
    evidence_service: ClaimEvidenceIngestionService = Depends(
        get_claim_evidence_ingestion_service
    ),
    refresh_workflow: EvidenceRefreshWorkflow = Depends(
        get_evidence_refresh_workflow
    ),
) -> IncomingEvidenceResponse | JSONResponse:
    evidence = ReceivedClaimEvidence(
        evidence_request_id=body.evidence_request_id,
        sender_email=body.sender_email,
        message_body=body.message_body,
        attachments=[
            ReceivedEvidenceAttachment(**attachment.model_dump())
            for attachment in body.attachments
        ],
    )
    try:
        case_context = evidence_service.record_received_evidence(
            request_id,
            evidence,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "CLAIM_REQUEST_NOT_FOUND",
                    "message": "Claim request not found.",
                    "details": str(exc),
                }
            },
        )

    try:
        refresh_result = refresh_workflow.run(
            request_id,
            claim_fact_updates=body.claim_fact_updates,
        )
    except Exception as exc:
        logger.exception(
            "Evidence refresh failed after evidence receipt for "
            "claim_request_id=%s",
            request_id,
        )
        return IncomingEvidenceResponse(
            request_id=request_id,
            evidence_received=True,
            received_evidence_count=len(case_context.reference_data.received_evidence),
            refresh_status="pending",
            refresh_pending_reason=str(exc),
            message=(
                "Evidence metadata was recorded; refresh is pending."
            ),
        )

    return IncomingEvidenceResponse(
        request_id=request_id,
        evidence_received=True,
        received_evidence_count=len(
            refresh_result.case_context.reference_data.received_evidence
        ),
        refresh_status=refresh_result.status,
        refresh_pending_reason=refresh_result.refresh_pending_reason,
        coverage_assessment_reran=refresh_result.coverage_assessment_reran,
        message=(
            "Evidence metadata was recorded and review findings were refreshed."
            if refresh_result.status == "completed"
            else "Evidence metadata was recorded; refresh is pending."
        ),
    )


def _claim_for_authenticated_user(
    request_id: UUID,
    current_user: AuthUser,
    service: ClaimRequestService,
) -> ClaimRequest:
    try:
        claim = service.get_claim_request_detail(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Claim not found.") from exc

    if current_user.role in EMPLOYEE_ROLES:
        return claim
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Claim access forbidden.")
    if current_user.client_id is None or str(claim.client_id) != str(current_user.client_id):
        raise HTTPException(status_code=404, detail="Claim not found.")
    return claim


def _claim_scoped_attachment_metadata(
    request_id: UUID,
    stored: ClaimAttachmentMetadata,
    current_user: AuthUser,
    document_role: str | None = None,
) -> ClaimAttachmentMetadata:
    attachment_id = uuid4()
    metadata = dict(stored.metadata or {})
    metadata.update(
        {
            "attachment_id": str(attachment_id),
            "claim_id": str(request_id),
            "uploaded_by_auth_user_id": current_user.id,
            "source": (
                "client_upload"
                if current_user.role == "client"
                else "employee_upload"
            ),
            "status": "uploaded",
            "created_at": _utc_iso(),
        }
    )
    if document_role:
        metadata["document_role"] = document_role

    return ClaimAttachmentMetadata(
        file_name=stored.file_name,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        file_url=f"/claims/{request_id}/attachments/{attachment_id}",
        metadata=metadata,
    )


def _append_claim_attachments(
    request_id: UUID,
    new_attachments: list[ClaimAttachmentMetadata],
    service: ClaimRequestService,
) -> ClaimRequest:
    claim = service.get_claim_request_detail(request_id)
    attachments = [
        attachment.model_dump(mode="json")
        for attachment in claim.attachments
    ]
    attachments.extend(
        attachment.model_dump(mode="json")
        for attachment in new_attachments
    )
    return service.update_request_attachments(request_id, attachments)


def _active_claim_attachments(claim: ClaimRequest) -> list[ClaimAttachmentMetadata]:
    return [
        attachment
        for attachment in claim.attachments
        if str(attachment.metadata.get("status") or "uploaded") != "deleted"
    ]


def _claim_attachment_by_id(
    claim: ClaimRequest,
    attachment_id: UUID,
) -> ClaimAttachmentMetadata:
    for attachment in _active_claim_attachments(claim):
        if str(attachment.metadata.get("attachment_id") or "") == str(attachment_id):
            return attachment
    raise HTTPException(status_code=404, detail="Attachment not found.")


def _claim_has_profile_document_attachment(
    claim: ClaimRequest,
    document_id: UUID,
) -> bool:
    return any(
        str(attachment.metadata.get("profile_document_id") or "") == str(document_id)
        for attachment in _active_claim_attachments(claim)
    )


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attempt_claim_attachment_processing(
    request_id: UUID,
    service: ClaimAttachmentProcessingService,
) -> ClaimRequest | None:
    try:
        return service.process_request_attachments(request_id)
    except Exception:
        logger.exception(
            "Attachment processing failed for claim_request_id=%s",
            request_id,
        )
        return None


def _review_view_data(review_view: Any) -> dict[str, Any] | None:
    if review_view is None:
        return None
    if hasattr(review_view, "model_dump"):
        return review_view.model_dump(mode="json")
    if isinstance(review_view, dict):
        return review_view
    return None


def _decision_error_response(error: ClaimDecisionError) -> JSONResponse:
    status_code = 409 if error.code == "CLAIM_DECISION_ALREADY_SUBMITTED" else 400
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": error.code, "message": error.message}},
    )


def _evidence_request_draft_error_response(
    error: EvidenceRequestDraftError,
) -> JSONResponse:
    if isinstance(error, EvidenceRequestDraftNotFoundError):
        status_code = 404
    elif isinstance(error, EvidenceRequestDraftAlreadySentError):
        status_code = 409
    elif isinstance(error, EvidenceRequestEmailFailedError):
        status_code = 502
    elif isinstance(error, EvidenceRequestDraftInvalidError):
        status_code = 400
    else:
        status_code = 400

    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": error.code, "message": str(error)}},
    )


def _evidence_request_email_failed_response(message: str | None) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={
            "error": {
                "code": "EVIDENCE_REQUEST_EMAIL_FAILED",
                "message": message or "Evidence request email delivery failed.",
            }
        },
    )


def _demo_inbound_email_error_response(
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _claim_decision_email_blocker(claim: ClaimRequest) -> JSONResponse | None:
    if _persisted_claim_decision(claim) is None:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "CLAIM_DECISION_REQUIRED",
                    "message": (
                        "Claim decision must be submitted before sending a "
                        "decision email."
                    ),
                }
            },
        )

    if not str(claim.claim_data.get("decision_justification") or "").strip():
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "CLAIM_DECISION_JUSTIFICATION_REQUIRED",
                    "message": (
                        "Claim decision justification is required before sending "
                        "a decision email."
                    ),
                }
            },
        )

    return None


def _evidence_request_reply_subject(
    subject: str,
    reply_token: str | None,
) -> str:
    clean_subject = subject.strip()
    if not reply_token:
        return clean_subject
    marker = f"[UW-CLAIM:{reply_token}]"
    if marker in clean_subject:
        return clean_subject
    return f"{marker} {clean_subject}".strip()


def _configured_claim_inbound_email_address() -> str | None:
    inbound_address = (os.environ.get("CLAIM_INBOUND_EMAIL_ADDRESS") or "").strip()
    local_part, separator, domain = inbound_address.partition("@")
    if separator and local_part and domain:
        return inbound_address
    return None


def _evidence_request_reply_to(reply_token: str | None) -> str | None:
    if not reply_token:
        return None
    inbound_address = _configured_claim_inbound_email_address()
    if inbound_address:
        local_part, _, domain = inbound_address.partition("@")
        return f"{local_part}+{reply_token}@{domain}"
    domain = (os.environ.get("CLAIM_INBOUND_EMAIL_DOMAIN") or "underwright.local").strip()
    if not domain:
        return None
    return f"claims+{reply_token}@{domain}"


def _demo_inbound_email_attachment(
    request_id: UUID,
    draft: EvidenceRequestDraft,
) -> EmailAttachment:
    document_names = ", ".join(draft.required_documents) or "requested evidence"
    content = (
        "%PDF-1.4\n"
        "% Underwright demo inbound evidence\n"
        f"Claim request: {request_id}\n"
        f"Evidence request: {draft.draft_id or 'current'}\n"
        f"Documents: {document_names}\n"
        "This file was sent through Postmark inbound email for a live demo.\n"
        "%%EOF\n"
    ).encode("utf-8")
    return EmailAttachment(
        file_name="demo-inbound-evidence.pdf",
        content_type="application/pdf",
        content=content,
    )


def _persisted_claim_decision(claim: ClaimRequest) -> str | None:
    decision = str(claim.claim_data.get("decision") or "").strip().lower()
    status = str(claim.claim_data.get("decision_status") or "").strip().lower()
    decided_at = str(claim.claim_data.get("decided_at") or "").strip()
    if (
        decision in {"approved", "denied", "inspection_requested"}
        and status not in {"", "pending"}
        and decided_at
    ):
        return decision
    return None


def _has_sent_claim_decision_email(
    claim: ClaimRequest,
    email_service: EmailService,
) -> bool:
    if str(claim.claim_data.get("decision_email_sent_at") or "").strip():
        return True
    for email in email_service.list_case_emails(claim.request_id):
        if (
            email.subject == "Your Underwright claim decision"
            and email.status.upper() == "SENT"
        ):
            return True
    return False


def _claim_decision_recipient(claim: ClaimRequest) -> str:
    demo_recipient = os.environ.get("EMAIL_DEMO_CLAIM_DECISION_TO")
    if demo_recipient and _claim_reference(claim) == "CLM-DEMO-ALEX-001":
        return demo_recipient.strip()
    return str(
        claim.client_data.get("email")
        or claim.claim_data.get("contact_email")
        or ""
    ).strip()


def _claim_decision_email_body(claim: ClaimRequest) -> tuple[str, str]:
    claim_reference = _claim_reference(claim)
    decision = _persisted_claim_decision(claim)
    if decision is None:
        raise ValueError("Claim decision is missing.")
    decision_label = _claim_decision_label(decision)
    justification = str(claim.claim_data.get("decision_justification") or "").strip()
    first_name = _first_name(
        str(
            claim.client_data.get("full_name")
            or claim.claim_data.get("customer_name")
            or ""
        )
    )
    text_body = (
        f"Hello {first_name},\n\n"
        f"We have completed the review of your claim {claim_reference}.\n\n"
        f"Decision: {decision_label}\n\n"
        "Decision justification:\n"
        f"{justification}\n\n"
        "This is a demo claim decision email sent from Underwright.\n\n"
        "Regards,\n"
        "Underwright Claims Team"
    )
    html_first_name = escape(first_name)
    html_claim_reference = escape(claim_reference)
    html_decision = escape(decision_label)
    html_justification = escape(justification)
    html_body = (
        "<!doctype html>"
        "<html><body>"
        f"<p>Hello {html_first_name},</p>"
        f"<p>We have completed the review of your claim <strong>{html_claim_reference}</strong>.</p>"
        f"<p><strong>Decision:</strong> {html_decision}</p>"
        f"<p><strong>Decision justification:</strong><br>{html_justification}</p>"
        "<p>This is a demo claim decision email sent from Underwright.</p>"
        "<p>Regards,<br>Underwright Claims Team</p>"
        "</body></html>"
    )
    return text_body, html_body


def _claim_decision_label(decision: str) -> str:
    if decision == "approved":
        return "Approved"
    if decision == "denied":
        return "Denied"
    return "On-site inspection requested"


def _claim_reference(claim: ClaimRequest) -> str:
    return str(
        claim.claim_data.get("display_claim_id")
        or claim.claim_data.get("claim_id")
        or claim.request_id
    )


def _first_name(value: str) -> str:
    name = value.strip()
    if not name:
        return "there"
    return name.split()[0]


def _claimable_contract_for_claim(
    claim_data: dict[str, Any],
    current_user: AuthUser,
    contract_query_service: ContractQueryService,
) -> ContractReadModel | JSONResponse:
    raw_contract_id = claim_data.get("contract_id")
    if raw_contract_id in (None, ""):
        return _bad_request(
            "CLAIM_CONTRACT_REQUIRED",
            "A claimable contract_id is required before submitting a claim.",
        )

    try:
        contract_id = UUID(str(raw_contract_id))
    except ValueError:
        return _bad_request(
            "CLAIM_CONTRACT_INVALID",
            "contract_id must be a valid contract UUID.",
        )

    if current_user.client_id is None:
        return _forbidden(
            "CLAIM_CONTRACT_NOT_CLAIMABLE",
            "Selected contract is not claimable for this client.",
        )

    try:
        return contract_query_service.get_claimable_contract_for_client(
            contract_id,
            current_user.client_id,
        )
    except ValueError:
        return _forbidden(
            "CLAIM_CONTRACT_NOT_CLAIMABLE",
            "Selected contract is not claimable for this client.",
        )


def _canonical_claim_data(
    claim_data: dict[str, Any],
    contract: ContractReadModel,
) -> dict[str, Any]:
    canonical = dict(claim_data)
    asset = contract.asset
    canonical["contract_id"] = str(contract.id)
    canonical["policy_number"] = contract.contract_number
    canonical["contract_display_id"] = (
        contract.display_id or contract.contract_number or str(contract.id)
    )
    if asset is not None:
        canonical["insured_asset_id"] = asset.id
        canonical["property_address"] = _address_full_text(asset.address)
        canonical["coverage_amount"] = _json_number(asset.declared_value)
    return canonical


def _address_full_text(address: AddressSnapshot | None) -> str:
    if address is None:
        return ""
    if address.full_text:
        return address.full_text
    return ", ".join(
        part
        for part in (
            f"{address.street} {address.number}".strip(),
            address.city,
            address.county,
            address.country,
            address.postal_code,
        )
        if part
    )


def _json_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _profile_incomplete(exc: CustomerProfileIncompleteError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "error": {
                "code": "CUSTOMER_PROFILE_INCOMPLETE",
                "message": "Complete your customer profile before submitting claims.",
                "status": exc.status,
                "missing_fields": exc.missing_fields,
            }
        },
    )


def _bad_request(code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": {"code": code, "message": message}},
    )


def _forbidden(code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": {"code": code, "message": message}},
    )


def _not_found(code: str, message: str, details: str | None = None) -> JSONResponse:
    content: dict[str, object] = {"error": {"code": code, "message": message}}
    if details:
        content["error"]["details"] = details
    return JSONResponse(status_code=404, content=content)


def _module_result_responses(
    module_results: list[ModuleResult],
) -> list[ModuleResultResponse]:
    return [
        ModuleResultResponse(**module_result.model_dump(mode="json"))
        for module_result in module_results
    ]


__all__ = ["internal_router", "me_router", "router", "underwriter_router"]
