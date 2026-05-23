from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from underwright.domain.case_context_base import _utc_now


class CustomerProfileDocumentCreate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    customer_id: int
    label: str
    document_type: str
    file_name: str
    content_type: str
    size_bytes: int
    storage_key: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CustomerProfileDocument(BaseModel):
    id: UUID
    customer_id: int
    label: str
    document_type: str
    file_name: str
    content_type: str
    size_bytes: int
    storage_key: str
    file_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


__all__ = [
    "CustomerProfileDocument",
    "CustomerProfileDocumentCreate",
]
