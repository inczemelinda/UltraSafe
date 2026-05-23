from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


WordingDocumentStatus = Literal["draft", "published", "archived"]
WordingDocumentVersionStatus = Literal[
    "draft",
    "published",
    "superseded",
    "archived",
]


class WordingDocument(BaseModel):
    id: int | None = None
    code: str
    title: str
    product_line: str
    jurisdiction: str
    language: str
    insurer_id: int | None = None
    status: WordingDocumentStatus
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class WordingDocumentCreate(BaseModel):
    code: str
    title: str
    product_line: str
    jurisdiction: str
    language: str
    insurer_id: int | None = None
    status: WordingDocumentStatus = "draft"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class WordingDocumentVersion(BaseModel):
    id: int | None = None
    wording_document_id: int
    version: str
    status: WordingDocumentVersionStatus
    full_text: str
    content_hash: str
    legal_references_json: list[dict[str, Any] | str] | None = None
    structured_clauses_json: dict[str, Any] | list[dict[str, Any]] | None = None
    file_url: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WordingDocumentVersionCreate(BaseModel):
    wording_document_id: int
    version: str
    status: WordingDocumentVersionStatus = "draft"
    full_text: str
    legal_references_json: list[dict[str, Any] | str] | None = None
    structured_clauses_json: dict[str, Any] | list[dict[str, Any]] | None = None
    file_url: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    published_at: datetime | None = None


__all__ = [
    "WordingDocument",
    "WordingDocumentCreate",
    "WordingDocumentStatus",
    "WordingDocumentVersion",
    "WordingDocumentVersionCreate",
    "WordingDocumentVersionStatus",
]
