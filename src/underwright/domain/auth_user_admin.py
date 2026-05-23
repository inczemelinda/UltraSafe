from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


AuthUserAdminRole = Literal["client", "employee", "underwriter", "admin"]
CustomerAuthUserLinkAuditAction = Literal["link", "unlink", "relink"]


class AuthUserSearchResult(BaseModel):
    id: int
    email: str
    role: AuthUserAdminRole
    full_name: str
    client_id: int | None = None
    customer_full_name: str | None = None
    is_active: bool = True
    status: str = "active"
    created_at: datetime | None = None


class CustomerAuthUserLinkAuditRecord(BaseModel):
    id: int | None = None
    auth_user_id: int
    old_customer_id: int | None = None
    old_customer_name: str | None = None
    new_customer_id: int | None = None
    new_customer_name: str | None = None
    action: CustomerAuthUserLinkAuditAction
    reason: str | None = None
    changed_by_auth_user_id: int | None = None
    changed_at: datetime


class CustomerAuthUserRelinkResult(BaseModel):
    auth_user_id: int
    auth_user_email: str
    old_customer_id: int | None = None
    old_customer_name: str | None = None
    new_customer_id: int
    new_customer_name: str | None = None
    reason: str
    changed_by_auth_user_id: int | None = None
    changed_at: datetime


__all__ = [
    "AuthUserAdminRole",
    "AuthUserSearchResult",
    "CustomerAuthUserLinkAuditAction",
    "CustomerAuthUserLinkAuditRecord",
    "CustomerAuthUserRelinkResult",
]
