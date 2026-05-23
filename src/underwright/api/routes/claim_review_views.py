from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from underwright.api.dependencies import get_case_context_service
from underwright.application.services.case_context_service import CaseContextService

router = APIRouter(prefix="/claim-review-views", tags=["claim-review-views"])


class ClaimReviewViewResponse(BaseModel):
    case_id: UUID | None = None
    workflow_status: str
    review_view: dict[str, Any] | None = None


@router.get("/{case_id}", response_model=ClaimReviewViewResponse)
def get_claim_review_view(
    case_id: str,
    service: CaseContextService = Depends(get_case_context_service),
) -> ClaimReviewViewResponse | JSONResponse:
    try:
        case_context = service.get_case_context(case_id)
    except ValueError as exc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "CASE_CONTEXT_NOT_FOUND",
                    "message": "Claim case context not found.",
                    "details": str(exc),
                }
            },
        )

    workflow_status = case_context.case_metadata.status
    review_state = getattr(case_context, "review_state", None)
    review_view = None
    if review_state is not None:
        review_view = getattr(review_state, "claim_review_view", None)
        if review_view is None and isinstance(review_state, dict):
            review_view = review_state.get("claim_review_view")

    if review_view is None and workflow_status != "draft":
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "MISSING_CLAIM_REVIEW_VIEW",
                    "message": f"Claim review view not available for case {case_id}.",
                    "details": (
                        f"Case is in '{workflow_status}' status but review view is missing."
                    ),
                }
            },
        )

    return ClaimReviewViewResponse(
        case_id=case_context.case_metadata.case_id,
        workflow_status=workflow_status,
        review_view=_review_view_data(review_view),
    )


def _review_view_data(review_view: Any) -> dict[str, Any] | None:
    if review_view is None:
        return None
    if hasattr(review_view, "model_dump"):
        return review_view.model_dump(mode="json")
    if isinstance(review_view, dict):
        return review_view
    return None


__all__ = ["router"]
