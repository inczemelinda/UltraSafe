from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from underwright.api.dependencies import get_auth_service
from underwright.application.services.auth_service import AuthService
from underwright.domain.auth_user import AuthUser


bearer_scheme = HTTPBearer(auto_error=False)


def require_underwriter_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ] = None,
    demo_role: Annotated[str | None, Header(alias="X-UltraSafe-Role")] = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthUser | dict[str, str]:
    if credentials is not None:
        try:
            user = auth_service.get_user_from_access_token(credentials.credentials)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid access token") from exc
        if user.role != "underwriter":
            raise HTTPException(status_code=403, detail="Underwriter role required")
        return user

    if _allow_demo_role_header() and demo_role == "underwriter":
        return {"role": "underwriter", "auth_mode": "demo_header"}

    if demo_role is not None:
        raise HTTPException(status_code=403, detail="Underwriter role required")
    raise HTTPException(status_code=401, detail="Authentication required")


def _allow_demo_role_header() -> bool:
    raw = os.environ.get("UNDERWRIGHT_ALLOW_DEMO_ROLE_HEADER", "true")
    return raw.strip().lower() in {"1", "true", "yes", "on"}
