from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AuthUser(BaseModel):
    id: int | None = None
    email: str
    password_hash: str
    role: Literal["client", "employee", "underwriter", "admin"]
    full_name: str
    phone: str | None = None
    client_id: int | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
