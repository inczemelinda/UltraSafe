from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from underwright.domain.module_result import ModuleResult


class GeneratedDocumentReadModel(BaseModel):
    id: int
    contract_id: UUID
    document_type: str | None = None
    template_id: int
    template_code: str | None = None
    template_version: str | None = None
    template_version_hash: str | None = None
    rendered_text: str
    rendered_html: str | None = None
    payload_snapshot: dict[str, Any] = Field(default_factory=dict)
    generation_metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str | None = None
    pdf_storage_key: str | None = None
    pdf_filename: str | None = None
    pdf_content_hash: str | None = None
    pdf_source_content_hash: str | None = None
    pdf_generated_at: datetime | None = None
    pdf_generation_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    status: str


class ContractGenerationIssue(BaseModel):
    code: str
    message: str
    field: str | None = None


class ContractGenerationValidation(BaseModel):
    can_generate: bool
    blocking_errors: list[ContractGenerationIssue] = Field(default_factory=list)
    warnings: list[ContractGenerationIssue] = Field(default_factory=list)


class ContractDocumentGenerationResult(BaseModel):
    status: str
    document: GeneratedDocumentReadModel | None = None
    validation: ContractGenerationValidation
    module_results: list[ModuleResult] = Field(default_factory=list)


class PdfArtifactReadModel(BaseModel):
    document_id: int
    contract_id: UUID
    pdf_storage_key: str
    pdf_content_hash: str
    source_content_hash: str
    pdf_generated_at: datetime
    status: str
    filename: str


class PdfExportIssue(BaseModel):
    code: str
    message: str
    field: str | None = None


class PdfExportResult(BaseModel):
    status: str
    artifact: PdfArtifactReadModel | None = None
    blocking_errors: list[PdfExportIssue] = Field(default_factory=list)


__all__ = [
    "ContractDocumentGenerationResult",
    "ContractGenerationIssue",
    "ContractGenerationValidation",
    "GeneratedDocumentReadModel",
    "PdfArtifactReadModel",
    "PdfExportIssue",
    "PdfExportResult",
]
