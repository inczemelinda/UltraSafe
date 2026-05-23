from __future__ import annotations

from underwright.domain.auth_user_admin import AuthUserAdminRole, AuthUserSearchResult


class AuthUserSearchService:
    def __init__(self, auth_user_repository) -> None:
        self.auth_user_repository = auth_user_repository

    def search_auth_users(
        self,
        *,
        query: str = "",
        role: AuthUserAdminRole | None = "client",
        unlinked_only: bool = True,
        limit: int = 20,
    ) -> list[AuthUserSearchResult]:
        clamped_limit = max(1, min(limit, 50))
        return self.auth_user_repository.search_users(
            query=query.strip(),
            role=role,
            unlinked_only=unlinked_only,
            limit=clamped_limit,
        )


__all__ = ["AuthUserSearchService"]
