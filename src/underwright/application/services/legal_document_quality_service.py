from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from underwright.domain.legal_intelligence import (
    LegalDocumentNormalizationResult,
    NormalizedLegalDocument,
)


@dataclass(frozen=True)
class LegalDocumentQualityExpectation:
    source_key: str
    legal_references: tuple[str, ...] = ()
    amends: tuple[str, ...] = ()
    repeals: tuple[str, ...] = ()
    publication_date: date | None = None
    instrument_type: str | None = None


@dataclass(frozen=True)
class LegalDocumentQualityReport:
    metrics: dict[str, float]


class LegalDocumentQualityService:
    """Measure deterministic legal-document normalization quality."""

    _MEASURED_EXTRACTION_FIELDS = (
        "title",
        "issuer",
        "jurisdiction",
        "instrument_type",
        "instrument_number",
        "instrument_year",
        "publication_date",
        "effective_date",
        "legal_references",
        "amends",
        "repeals",
        "full_text",
        "canonical_url",
        "document_hash",
    )

    def evaluate(
        self,
        *,
        documents: list[NormalizedLegalDocument],
        normalization_results: list[LegalDocumentNormalizationResult],
        expectations: list[LegalDocumentQualityExpectation],
    ) -> LegalDocumentQualityReport:
        documents_by_source_key = {document.source_key: document for document in documents}

        return LegalDocumentQualityReport(
            metrics={
                "required_field_extraction_rate": self._field_extraction_rate(
                    documents,
                ),
                "legal_reference_extraction_accuracy": self._collection_accuracy(
                    documents_by_source_key,
                    expectations,
                    "legal_references",
                ),
                "amendment_relationship_accuracy": self._relationship_accuracy(
                    documents_by_source_key,
                    expectations,
                ),
                "publication_date_extraction_accuracy": self._scalar_accuracy(
                    documents_by_source_key,
                    expectations,
                    "publication_date",
                ),
                "instrument_type_accuracy": self._scalar_accuracy(
                    documents_by_source_key,
                    expectations,
                    "instrument_type",
                ),
                "deduplication_accuracy": self._deduplication_accuracy(documents),
                "parser_failure_rate": self._status_rate(
                    normalization_results,
                    "parser_failed",
                ),
                "normalization_rate": self._status_rate(
                    normalization_results,
                    "normalized",
                ),
                "synthetic_document_marking_rate": self._synthetic_marking_rate(
                    documents,
                ),
            }
        )

    def _field_extraction_rate(
        self,
        documents: list[NormalizedLegalDocument],
    ) -> float:
        if not documents:
            return 1.0

        field_total = len(documents) * len(self._MEASURED_EXTRACTION_FIELDS)
        present_total = 0
        for document in documents:
            for field_name in self._MEASURED_EXTRACTION_FIELDS:
                if self._field_present(getattr(document, field_name)):
                    present_total += 1

        return present_total / field_total

    def _collection_accuracy(
        self,
        documents_by_source_key: dict[str, NormalizedLegalDocument],
        expectations: list[LegalDocumentQualityExpectation],
        field_name: str,
    ) -> float:
        expected_total = 0
        matched_total = 0
        for expectation in expectations:
            expected_values = set(getattr(expectation, field_name))
            if not expected_values:
                continue

            expected_total += len(expected_values)
            document = documents_by_source_key.get(expectation.source_key)
            actual_values = (
                self._canonical_values(getattr(document, field_name))
                if document is not None
                else set()
            )
            matched_total += len(expected_values & actual_values)

        return matched_total / expected_total if expected_total else 1.0

    def _relationship_accuracy(
        self,
        documents_by_source_key: dict[str, NormalizedLegalDocument],
        expectations: list[LegalDocumentQualityExpectation],
    ) -> float:
        expected_total = 0
        matched_total = 0
        for expectation in expectations:
            document = documents_by_source_key.get(expectation.source_key)
            for field_name in ("amends", "repeals"):
                expected_values = set(getattr(expectation, field_name))
                if not expected_values:
                    continue

                expected_total += len(expected_values)
                actual_values = (
                    self._canonical_values(getattr(document, field_name))
                    if document is not None
                    else set()
                )
                matched_total += len(expected_values & actual_values)

        return matched_total / expected_total if expected_total else 1.0

    def _scalar_accuracy(
        self,
        documents_by_source_key: dict[str, NormalizedLegalDocument],
        expectations: list[LegalDocumentQualityExpectation],
        field_name: str,
    ) -> float:
        expected_total = 0
        matched_total = 0
        for expectation in expectations:
            expected_value = getattr(expectation, field_name)
            if expected_value is None:
                continue

            expected_total += 1
            document = documents_by_source_key.get(expectation.source_key)
            actual_value = getattr(document, field_name) if document is not None else None
            if actual_value == expected_value:
                matched_total += 1

        return matched_total / expected_total if expected_total else 1.0

    def _deduplication_accuracy(
        self,
        documents: list[NormalizedLegalDocument],
    ) -> float:
        if not documents:
            return 1.0

        dedupe_keys = [self._dedupe_key(document) for document in documents]
        return len(set(dedupe_keys)) / len(dedupe_keys)

    def _status_rate(
        self,
        normalization_results: list[LegalDocumentNormalizationResult],
        status: str,
    ) -> float:
        if not normalization_results:
            return 0.0

        matching_results = [
            result for result in normalization_results if result.status == status
        ]
        return len(matching_results) / len(normalization_results)

    def _synthetic_marking_rate(
        self,
        documents: list[NormalizedLegalDocument],
    ) -> float:
        if not documents:
            return 1.0

        marked_documents = [
            document
            for document in documents
            if self._is_synthetic_metadata(document.source_metadata)
        ]
        return len(marked_documents) / len(documents)

    def _canonical_values(self, values: list[Any]) -> set[str]:
        canonical_values: set[str] = set()
        for value in values:
            if isinstance(value, str):
                canonical_values.add(value)
                continue

            canonical_value = value.get("canonical") or value.get("canonical_reference")
            if canonical_value:
                canonical_values.add(str(canonical_value))

        return canonical_values

    def _dedupe_key(self, document: NormalizedLegalDocument) -> str:
        if document.external_identifier:
            return f"{document.source_id}:external:{document.external_identifier}"
        if document.canonical_url:
            return f"{document.source_id}:url:{document.canonical_url}"
        return f"{document.source_id}:hash:{document.document_hash}"

    def _is_synthetic_metadata(self, metadata: dict[str, Any]) -> bool:
        return metadata.get("synthetic") is True or metadata.get("dataset") == "demo"

    def _field_present(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True
