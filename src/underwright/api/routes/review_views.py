"""
Contract review view routes for Underwright API.

Exposes GET /review-views/{case_id} which retrieves the persisted review view
for a contract case, including workflow status and module results if available.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from underwright.api.dependencies import get_case_context_service
from underwright.application.services.case_context_service import CaseContextService
from underwright.domain.review_models import ContractReviewView

router = APIRouter(prefix="/review-views", tags=["review-views"])


class ModuleResultResponse(BaseModel):
    module_name: str
    status: str
    summary: str
    source_fields_used: list[str]


class ReviewViewResponse(BaseModel):
    case_id: UUID | None = None
    workflow_status: str
    review_view: dict[str, Any] | None = None
    module_results: list[ModuleResultResponse] | None = None


@router.get("/{case_id}", response_model=ReviewViewResponse)
def get_review_view(
    case_id: str,
    service: CaseContextService = Depends(get_case_context_service),
):
    """Retrieve the latest review view for a drafted contract case.

    Fetches the persisted CaseContext by case_id and returns:
    - The contract review view (if available)
    - Workflow status from case metadata
    - Module results if the workflow was completed

    Returns 404 if case context not found.
    Returns 400 if review view is missing from the case context.
    """
    try:
        case_context = service.get_case_context(case_id)
    except ValueError as exc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "CASE_CONTEXT_NOT_FOUND",
                    "message": "Contract case context not found.",
                    "details": str(exc),
                }
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "RETRIEVE_REVIEW_VIEW_ERROR",
                    "message": "Failed to retrieve review view.",
                    "details": str(exc),
                }
            },
        )

    workflow_status = case_context.case_metadata.status
    review_view_data = None

    # Extract stored review view if available.
    if case_context.review_state.contract_review_view is not None:
        review_view = case_context.review_state.contract_review_view
        # Pydantic models handle UUID JSON conversion.
        if isinstance(review_view, ContractReviewView):
            review_view_data = review_view.model_dump(mode="json")
        else:
            review_view_data = review_view

    # Completed cases should already have a review view.
    if review_view_data is None and workflow_status != "draft":
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "MISSING_REVIEW_VIEW",
                    "message": f"Review view not available for case {case_id}.",
                    "details": f"Case is in '{workflow_status}' status but review view is missing.",
                }
            },
        )

    return ReviewViewResponse(
        # Response model serializes the UUID.
        case_id=case_context.case_metadata.case_id,
        workflow_status=workflow_status,
        review_view=review_view_data,
        module_results=None,  # Module results are not persisted in case context
    )
