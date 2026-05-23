from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from underwright.api.dependencies import (
    get_auth_user_search_service,
    get_current_employee_user,
)
from underwright.application.services.auth_user_search_service import (
    AuthUserSearchService,
)
from underwright.domain.auth_user_admin import AuthUserAdminRole, AuthUserSearchResult

router = APIRouter(
    prefix="/auth-users",
    tags=["auth-users"],
    dependencies=[Depends(get_current_employee_user)],
)


@router.get("", response_model=list[AuthUserSearchResult])
def search_auth_users(
    q: str = Query(default="", max_length=120),
    role: AuthUserAdminRole | None = Query(default="client"),
    unlinked_only: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=50),
    service: AuthUserSearchService = Depends(get_auth_user_search_service),
) -> list[AuthUserSearchResult]:
    return service.search_auth_users(
        query=q,
        role=role,
        unlinked_only=unlinked_only,
        limit=limit,
    )


__all__ = ["router"]
