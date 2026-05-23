from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from underwright.api.dependencies import get_underwriting_rules_repository
from underwright.domain.underwriting_rules import UnderwritingRulesDocument
from underwright.infrastructure.postgres.underwriting_rules_repository import (
    PostgresUnderwritingRulesRepository,
)


router = APIRouter(prefix="/underwriting-rules", tags=["underwriting-rules"])


class UpdateUnderwritingRulesBody(BaseModel):
    document: UnderwritingRulesDocument
    updated_by: str | None = None


@router.get("", response_model=UnderwritingRulesDocument)
def get_underwriting_rules(
    repository: PostgresUnderwritingRulesRepository = Depends(
        get_underwriting_rules_repository
    ),
) -> UnderwritingRulesDocument:
    return repository.get_document()


@router.put("", response_model=UnderwritingRulesDocument)
def update_underwriting_rules(
    body: UpdateUnderwritingRulesBody,
    repository: PostgresUnderwritingRulesRepository = Depends(
        get_underwriting_rules_repository
    ),
) -> UnderwritingRulesDocument:
    return repository.update_document(body.document, updated_by=body.updated_by)


__all__ = ["router"]
