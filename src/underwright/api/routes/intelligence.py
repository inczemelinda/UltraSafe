from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from underwright.api.auth_dependencies import require_underwriter_user
from underwright.api.intelligence_dependencies import (
    get_intelligence_insight_query_service,
    get_intelligence_service,
    get_legal_review_wording_impact_service,
    get_legal_template_review_candidate_repository,
    get_template_change_suggestion_service,
    get_template_review_query_service,
)
from underwright.application.services.legal_review_wording_impact_service import (
    LegalReviewWordingImpactService,
)
from underwright.application.services.intelligence_insight_query_service import (
    IntelligenceInsightQueryService,
)
from underwright.application.services.intelligence_service import IntelligenceService
from underwright.application.services.template_review_query_service import (
    TemplateReviewQueryService,
)
from underwright.application.services.template_change_suggestion_service import (
    TemplateDraftRevisionSubmissionError,
    TemplateDraftRevisionValidationError,
    TemplateChangeSuggestionService,
)
from underwright.domain.intelligence import (
    Alert,
    Correlation,
    EventDetail,
    Feedback,
    FeedbackType,
    IngestionRun,
    InsightCard,
    TemplateReviewCandidate,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewItem,
    TemplateChangeSuggestion,
    TemplateChangeSuggestionDetail,
    TemplateChangeSuggestionHunkStatus,
    TemplateDraftRevision,
)
from underwright.infrastructure.postgres.intelligence_repositories import (
    PostgresLegalDocumentTemplateReviewCandidateRepository,
)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


class FeedbackBody(BaseModel):
    user_id: str
    target_type: Literal["event", "alert", "correlation"]
    target_id: UUID
    feedback_type: FeedbackType
    comment: str | None = None


class IngestionRunBody(BaseModel):
    source_id: str = "asf_ro"


class TemplateChangeSuggestionHunkPatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_text: str | None = None
    status: TemplateChangeSuggestionHunkStatus | None = None
    reviewer_notes: str | None = None


@router.get("/events", response_model=list[InsightCard])
def list_events(
    country: str | None = None,
    source_id: str | None = None,
    line_of_business: str | None = None,
    topic: str | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    status: str | None = "classified",
    limit: int = 50,
    service: IntelligenceInsightQueryService = Depends(
        get_intelligence_insight_query_service
    ),
) -> list[InsightCard]:
    feed_status = None if status == "all" else status
    return service.list_insight_cards(
        country=country,
        source_id=source_id,
        line_of_business=line_of_business,
        topic=topic,
        event_type=event_type,
        severity=severity,
        status=feed_status,
        limit=limit,
    )


@router.get("/events/{event_id}", response_model=EventDetail)
def get_event_detail(
    event_id: UUID,
    service: IntelligenceService = Depends(get_intelligence_service),
) -> EventDetail:
    try:
        return service.get_event_detail(event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/document-review-candidates", response_model=list[Correlation])
def list_document_review_candidates(
    service: IntelligenceService = Depends(get_intelligence_service),
) -> list[Correlation]:
    return service.list_document_review_candidates()


@router.get(
    "/template-review-candidates",
    response_model=list[TemplateReviewCandidate],
)
def list_template_review_candidates(
    status: str | None = "candidate",
    limit: int = 50,
    service: TemplateReviewQueryService = Depends(get_template_review_query_service),
) -> list[TemplateReviewCandidate]:
    return service.list_candidates(status=status, limit=limit)


@router.get(
    "/legal-template-review-candidates",
    response_model=list[LegalDocumentTemplateReviewItem],
)
def list_legal_template_review_candidates(
    status: str | None = "needs_review",
    limit: int = 50,
    repository: PostgresLegalDocumentTemplateReviewCandidateRepository = Depends(
        get_legal_template_review_candidate_repository
    ),
    wording_impact_service: LegalReviewWordingImpactService = Depends(
        get_legal_review_wording_impact_service
    ),
) -> list[LegalDocumentTemplateReviewItem]:
    items = repository.list_review_items(status=status, limit=limit)
    return wording_impact_service.enrich_review_items(items)


@router.post(
    "/legal-template-review-candidates/{candidate_id}/suggestions",
    response_model=TemplateChangeSuggestion,
)
def create_template_change_suggestion(
    candidate_id: UUID,
    _underwriter: object = Depends(require_underwriter_user),
    service: TemplateChangeSuggestionService = Depends(
        get_template_change_suggestion_service
    ),
) -> TemplateChangeSuggestion:
    try:
        return service.create_suggestion(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/template-change-suggestions/{suggestion_id}",
    response_model=TemplateChangeSuggestionDetail,
)
def get_template_change_suggestion(
    suggestion_id: UUID,
    service: TemplateChangeSuggestionService = Depends(
        get_template_change_suggestion_service
    ),
) -> TemplateChangeSuggestionDetail:
    try:
        return service.get_suggestion_detail(suggestion_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch(
    "/template-change-suggestions/{suggestion_id}/hunks/{hunk_id}",
    response_model=TemplateChangeSuggestion,
)
def update_template_change_suggestion_hunk(
    suggestion_id: UUID,
    hunk_id: UUID,
    body: TemplateChangeSuggestionHunkPatchBody,
    _underwriter: object = Depends(require_underwriter_user),
    service: TemplateChangeSuggestionService = Depends(
        get_template_change_suggestion_service
    ),
) -> TemplateChangeSuggestion:
    try:
        return service.update_hunk(
            suggestion_id=suggestion_id,
            hunk_id=hunk_id,
            new_text=body.new_text,
            status=body.status,
            reviewer_notes=body.reviewer_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/template-change-suggestions/{suggestion_id}/hunks/{hunk_id}/accept",
    response_model=TemplateChangeSuggestion,
)
def accept_template_change_suggestion_hunk(
    suggestion_id: UUID,
    hunk_id: UUID,
    _underwriter: object = Depends(require_underwriter_user),
    service: TemplateChangeSuggestionService = Depends(
        get_template_change_suggestion_service
    ),
) -> TemplateChangeSuggestion:
    try:
        return service.accept_hunk(suggestion_id=suggestion_id, hunk_id=hunk_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/template-change-suggestions/{suggestion_id}/hunks/{hunk_id}/reject",
    response_model=TemplateChangeSuggestion,
)
def reject_template_change_suggestion_hunk(
    suggestion_id: UUID,
    hunk_id: UUID,
    _underwriter: object = Depends(require_underwriter_user),
    service: TemplateChangeSuggestionService = Depends(
        get_template_change_suggestion_service
    ),
) -> TemplateChangeSuggestion:
    try:
        return service.reject_hunk(suggestion_id=suggestion_id, hunk_id=hunk_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/template-change-suggestions/{suggestion_id}/create-draft-revision",
    response_model=TemplateDraftRevision,
)
def create_template_draft_revision_from_suggestion(
    suggestion_id: UUID,
    _underwriter: object = Depends(require_underwriter_user),
    service: TemplateChangeSuggestionService = Depends(
        get_template_change_suggestion_service
    ),
) -> TemplateDraftRevision:
    try:
        return service.create_draft_revision_from_suggestion(suggestion_id)
    except TemplateDraftRevisionValidationError as exc:
        raise HTTPException(status_code=409, detail=exc.validation_result) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/template-draft-revisions/{draft_revision_id}/submit-for-approval",
    response_model=TemplateDraftRevision,
)
def submit_template_draft_revision_for_approval(
    draft_revision_id: UUID,
    _underwriter: object = Depends(require_underwriter_user),
    service: TemplateChangeSuggestionService = Depends(
        get_template_change_suggestion_service
    ),
) -> TemplateDraftRevision:
    try:
        return service.submit_draft_revision_for_approval(draft_revision_id)
    except TemplateDraftRevisionSubmissionError as exc:
        raise HTTPException(status_code=409, detail=exc.validation_result) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/alerts", response_model=list[Alert])
def list_alerts(
    assigned_underwriter: str | None = None,
    status: str | None = "open",
    service: IntelligenceService = Depends(get_intelligence_service),
) -> list[Alert]:
    return service.list_alerts(
        assigned_underwriter=assigned_underwriter,
        status=status,
    )


@router.post("/feedback", response_model=Feedback)
def record_feedback(
    body: FeedbackBody,
    service: IntelligenceService = Depends(get_intelligence_service),
) -> Feedback:
    return service.record_feedback(
        user_id=body.user_id,
        target_type=body.target_type,
        target_id=body.target_id,
        feedback_type=body.feedback_type,
        comment=body.comment,
    )


@router.post("/ingestion-runs", response_model=IngestionRun)
def run_ingestion(
    body: IngestionRunBody,
    service: IntelligenceService = Depends(get_intelligence_service),
) -> IngestionRun:
    return service.run_ingestion(body.source_id)
