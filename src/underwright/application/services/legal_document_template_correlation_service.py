from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import hashlib
from typing import Any

from underwright.application.services.legal_reference_extraction_service import (
    LegalReferenceExtractionService,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateCorrelationBatchResult,
    LegalDocumentTemplateMatchType,
    LegalDocumentTemplateReviewCandidate,
    NormalizedLegalDocument,
)
from underwright.domain.models import Template


DEFAULT_PRODUCT_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "property_insurance": (
        "pad",
        "locuint",
        "asigurare obligatorie",
        "property insurance",
    ),
    "policy_wording": (
        "clauz",
        "conditii de asigurare",
        "wording",
        "polita",
    ),
    "claims": (
        "dauna",
        "despagub",
        "notificare",
        "claims",
    ),
    "brokerage": (
        "broker",
        "intermediar",
    ),
    "regulatory_compliance": (
        "conformitate",
        "reglement",
        "obligatie",
    ),
    "contract_template_changes": (
        "contract",
        "template",
        "formular",
    ),
}


class LegalDocumentTemplateCorrelationService:
    def __init__(
        self,
        *,
        legal_document_repository,
        template_repository,
        candidate_repository,
        product_topic_keywords: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self.legal_document_repository = legal_document_repository
        self.template_repository = template_repository
        self.candidate_repository = candidate_repository
        self.product_topic_keywords = (
            dict(DEFAULT_PRODUCT_TOPIC_KEYWORDS)
            if product_topic_keywords is None
            else dict(product_topic_keywords)
        )
        self.reference_service = LegalReferenceExtractionService()

    def correlate_batch(
        self,
        *,
        limit: int = 50,
        source_id: str | None = None,
    ) -> LegalDocumentTemplateCorrelationBatchResult:
        result = LegalDocumentTemplateCorrelationBatchResult(source_id=source_id)
        legal_documents = self.legal_document_repository.list_for_template_correlation(
            limit=limit,
            source_id=source_id,
        )
        templates = self.template_repository.list_active()
        result.legal_documents_seen = len(legal_documents)
        result.templates_seen = len(templates)

        for legal_document in legal_documents:
            try:
                for template in templates:
                    result.candidates_created += self._correlate_pair(
                        legal_document,
                        template,
                    )
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"{legal_document.id}: {exc}")

        if result.failed and result.candidates_created:
            result.status = "partial_failure"
        elif result.failed:
            result.status = "failed"
        return result

    def _correlate_pair(
        self,
        legal_document: NormalizedLegalDocument,
        template: Template,
    ) -> int:
        if template.id is None:
            return 0

        candidates = self._candidate_matches(legal_document, template)
        created = 0
        for candidate in candidates:
            if self.candidate_repository.save_if_new(candidate):
                created += 1
        return created

    def _candidate_matches(
        self,
        legal_document: NormalizedLegalDocument,
        template: Template,
    ) -> list[LegalDocumentTemplateReviewCandidate]:
        template_references = self._template_references(template)
        candidates: list[LegalDocumentTemplateReviewCandidate] = []

        candidates.extend(
            self._reference_candidates(
                legal_document=legal_document,
                template=template,
                template_references=template_references,
                document_references=self._canonical_values(legal_document.amends),
                match_type="amended_reference",
                confidence=0.95,
            )
        )
        candidates.extend(
            self._reference_candidates(
                legal_document=legal_document,
                template=template,
                template_references=template_references,
                document_references=self._canonical_values(legal_document.repeals),
                match_type="repealed_reference",
                confidence=0.97,
            )
        )
        candidates.extend(
            self._reference_candidates(
                legal_document=legal_document,
                template=template,
                template_references=template_references,
                document_references=self._canonical_values(
                    legal_document.legal_references
                ),
                match_type="direct_reference",
                confidence=0.84,
            )
        )

        if not candidates:
            keyword_candidate = self._keyword_candidate(legal_document, template)
            if keyword_candidate is not None:
                candidates.append(keyword_candidate)

        return candidates

    def _reference_candidates(
        self,
        *,
        legal_document: NormalizedLegalDocument,
        template: Template,
        template_references: set[str],
        document_references: set[str],
        match_type: LegalDocumentTemplateMatchType,
        confidence: float,
    ) -> list[LegalDocumentTemplateReviewCandidate]:
        matched_references = sorted(template_references & document_references)
        return [
            self._candidate(
                legal_document=legal_document,
                template=template,
                match_type=match_type,
                matched_reference=matched_reference,
                confidence=confidence,
                review_reason=self._review_reason(
                    legal_document=legal_document,
                    template=template,
                    match_type=match_type,
                    matched_reference=matched_reference,
                ),
            )
            for matched_reference in matched_references
        ]

    def _keyword_candidate(
        self,
        legal_document: NormalizedLegalDocument,
        template: Template,
    ) -> LegalDocumentTemplateReviewCandidate | None:
        if not self.product_topic_keywords:
            return None
        if template.jurisdiction != legal_document.jurisdiction:
            return None

        document_text = f"{legal_document.title}\n{legal_document.full_text}".lower()
        template_text = f"{template.name}\n{template.content}".lower()
        for topic, keywords in sorted(self.product_topic_keywords.items()):
            normalized_keywords = [keyword.lower() for keyword in keywords]
            if not normalized_keywords:
                continue
            if any(keyword in document_text for keyword in normalized_keywords) and any(
                keyword in template_text for keyword in normalized_keywords
            ):
                return self._candidate(
                    legal_document=legal_document,
                    template=template,
                    match_type="keyword_topic",
                    matched_reference=topic,
                    confidence=0.62,
                    review_reason=(
                        f"{legal_document.title} and template "
                        f"{template.template_code} share configured "
                        f"jurisdiction/topic keywords for {topic}."
                    ),
                )
        return None

    def _candidate(
        self,
        *,
        legal_document: NormalizedLegalDocument,
        template: Template,
        match_type: LegalDocumentTemplateMatchType,
        matched_reference: str | None,
        confidence: float,
        review_reason: str,
    ) -> LegalDocumentTemplateReviewCandidate:
        now = datetime.now(UTC)
        return LegalDocumentTemplateReviewCandidate(
            normalized_legal_document_id=legal_document.id,
            template_id=template.id or 0,
            template_code=template.template_code,
            template_name=template.name,
            template_version=template.version,
            template_version_hash=self._template_version_hash(template),
            match_type=match_type,
            matched_reference=matched_reference,
            review_reason=review_reason,
            confidence=confidence,
            status="needs_review",
            source_metadata=self._source_metadata(legal_document, template),
            created_at=now,
            updated_at=now,
        )

    def _review_reason(
        self,
        *,
        legal_document: NormalizedLegalDocument,
        template: Template,
        match_type: LegalDocumentTemplateMatchType,
        matched_reference: str,
    ) -> str:
        if match_type == "amended_reference":
            action = "amends"
        elif match_type == "repealed_reference":
            action = "repeals"
        else:
            action = "references"
        return (
            f"{legal_document.title} {action} {matched_reference}, which is "
            f"referenced by template {template.template_code}."
        )

    def _template_references(self, template: Template) -> set[str]:
        if template.legal_references_json:
            return self._canonical_values(template.legal_references_json)
        return set(self.reference_service.extract_references(template.content))

    def _canonical_values(self, values: list[Any]) -> set[str]:
        canonical_values: set[str] = set()
        for value in values:
            if isinstance(value, str):
                canonical_values.add(value)
                continue
            if not isinstance(value, dict):
                continue

            canonical_value = value.get("canonical") or value.get("canonical_reference")
            if canonical_value:
                canonical_values.add(str(canonical_value))
                continue

            if {"type", "number", "year"} <= set(value):
                canonical_values.add(
                    f"ro:{value['type']}:{value['number']}:{value['year']}"
                )
        return canonical_values

    def _template_version_hash(self, template: Template) -> str:
        payload = (
            f"{template.template_code}\n{template.version}\n{template.content}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _source_metadata(
        self,
        legal_document: NormalizedLegalDocument,
        template: Template,
    ) -> dict[str, Any]:
        legal_metadata = legal_document.source_metadata
        template_metadata = template.metadata_json
        is_synthetic = bool(
            legal_metadata.get("is_synthetic")
            or legal_metadata.get("synthetic")
            or template_metadata.get("is_synthetic")
            or template_metadata.get("synthetic")
        )
        return {
            "is_synthetic": is_synthetic,
            "demo_dataset": legal_metadata.get("demo_dataset")
            or template_metadata.get("demo_dataset"),
            "legal_document_source_key": legal_document.source_key,
            "deterministic_rule_set": "legal_document_template_correlation_v1",
        }
