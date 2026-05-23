from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from underwright.application.legal_intelligence_ports import (
    LegalDocumentParserRegistry,
)
from underwright.domain.intelligence import RawSourceItem, Source
from underwright.domain.legal_intelligence import (
    LegalDocumentNormalizationBatchResult,
    LegalDocumentNormalizationResult,
    NormalizedLegalDocument,
    SuppressionResult,
)


class LegalDocumentNormalizationService:
    def __init__(
        self,
        *,
        source_repository: Any,
        legal_document_repository: Any,
        parser_registry: LegalDocumentParserRegistry,
    ) -> None:
        self.source_repository = source_repository
        self.legal_document_repository = legal_document_repository
        self.parser_registry = parser_registry

    def process_pending(
        self,
        *,
        limit: int = 50,
        source_id: str | None = None,
    ) -> LegalDocumentNormalizationBatchResult:
        result = LegalDocumentNormalizationBatchResult(source_id=source_id)
        raw_items = self.legal_document_repository.list_pending_legal_raw_items(
            limit=limit,
            source_id=source_id,
        )
        result.raw_items_seen = len(raw_items)

        for raw_item in raw_items:
            try:
                self._process_one(raw_item, result)
            except Exception as exc:
                self._save_parser_failed_result(raw_item, exc)
                result.failed += 1
                result.errors.append(f"{raw_item.raw_item_id}: {exc}")

        if result.failed and result.normalized + result.suppressed:
            result.status = "partial_failure"
        elif result.failed:
            result.status = "failed"
        return result

    def _process_one(
        self,
        raw_item: RawSourceItem,
        batch_result: LegalDocumentNormalizationBatchResult,
    ) -> None:
        source = self._get_source(raw_item.source_id)
        parser = self.parser_registry.parser_for_source(source)
        parsed = parser.parse(raw_item, source)

        if isinstance(parsed, NormalizedLegalDocument):
            saved_document = self.legal_document_repository.save(parsed)
            status = (
                "normalized"
                if saved_document.raw_source_item_id == raw_item.raw_item_id
                else "duplicate_unchanged"
            )
            self.legal_document_repository.save_normalization_result(
                self._normalization_result(
                    raw_item=raw_item,
                    source=source,
                    parser_id=parsed.parser_id,
                    status=status,
                    normalized_legal_document_id=saved_document.id,
                    reason=None
                    if status == "normalized"
                    else "Duplicate unchanged legal document.",
                    parser_warnings=parsed.parser_warnings,
                    source_metadata=parsed.source_metadata,
                )
            )
            if status == "normalized":
                batch_result.normalized += 1
            else:
                batch_result.duplicate_unchanged += 1
            return

        self.legal_document_repository.save_normalization_result(
            self._suppression_result(parsed)
        )
        if parsed.status == "skipped_missing_required_fields":
            batch_result.skipped_missing_required_fields += 1
        else:
            batch_result.suppressed += 1

    def _get_source(self, source_id: str) -> Source:
        if hasattr(self.source_repository, "get_by_id"):
            return self.source_repository.get_by_id(source_id)
        return self.source_repository.get_enabled(source_id)

    def _save_parser_failed_result(
        self,
        raw_item: RawSourceItem,
        exc: Exception,
    ) -> None:
        now = datetime.now(UTC)
        try:
            source = self._get_source(raw_item.source_id)
            parser_id = str(source.config_json.get("parser_id") or "unknown")
            source_metadata = {
                "source_id": source.source_id,
                "parser_id": parser_id,
            }
        except Exception:
            parser_id = "unknown"
            source_metadata = {"source_id": raw_item.source_id}

        self.legal_document_repository.save_normalization_result(
            LegalDocumentNormalizationResult(
                raw_source_item_id=raw_item.raw_item_id,
                source_id=raw_item.source_id,
                parser_id=parser_id,
                normalized_legal_document_id=None,
                status="parser_failed",
                reason=str(exc),
                parser_warnings=[],
                source_metadata=source_metadata,
                created_at=now,
                updated_at=now,
            )
        )

    def _normalization_result(
        self,
        *,
        raw_item: RawSourceItem,
        source: Source,
        parser_id: str,
        status: str,
        normalized_legal_document_id,
        reason: str | None,
        parser_warnings: list[str],
        source_metadata: dict[str, Any],
    ) -> LegalDocumentNormalizationResult:
        now = datetime.now(UTC)
        return LegalDocumentNormalizationResult(
            raw_source_item_id=raw_item.raw_item_id,
            source_id=source.source_id,
            parser_id=parser_id,
            normalized_legal_document_id=normalized_legal_document_id,
            status=status,
            reason=reason,
            parser_warnings=parser_warnings,
            source_metadata=source_metadata,
            created_at=now,
            updated_at=now,
        )

    def _suppression_result(
        self,
        suppression: SuppressionResult,
    ) -> LegalDocumentNormalizationResult:
        now = datetime.now(UTC)
        return LegalDocumentNormalizationResult(
            raw_source_item_id=suppression.raw_source_item_id,
            source_id=suppression.source_id,
            parser_id=suppression.parser_id,
            normalized_legal_document_id=None,
            status=suppression.status,
            reason=suppression.reason,
            parser_warnings=suppression.parser_warnings,
            source_metadata=suppression.source_metadata,
            created_at=now,
            updated_at=now,
        )
