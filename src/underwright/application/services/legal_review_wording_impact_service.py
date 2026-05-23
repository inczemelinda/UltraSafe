from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from underwright.application.services.policy_wording_service import (
    PolicyWordingRetrievalService,
)
from underwright.application.services.wording_document_service import (
    WordingVersionNotFoundError,
)
from underwright.domain.claim_analysis import PolicyWordingSection
from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewItem,
    NormalizedLegalDocument,
    WordingDocumentDraftComparison,
    WordingDocumentImpact,
    WordingDocumentProposedChange,
)
from underwright.domain.wording import WordingDocument, WordingDocumentVersion


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "by",
    "cu",
    "de",
    "din",
    "este",
    "for",
    "from",
    "in",
    "la",
    "legea",
    "nr",
    "of",
    "or",
    "pentru",
    "se",
    "si",
    "the",
    "to",
}


@dataclass(frozen=True)
class _Clause:
    clause_id: str | None
    title: str | None
    text: str
    legal_references: list[Any]


class LegalReviewWordingImpactService:
    """Finds review-only wording-document impacts for normalized legal changes."""

    def __init__(
        self,
        wording_document_service,
        *,
        policy_wording_service: PolicyWordingRetrievalService | None = None,
    ) -> None:
        self.wording_document_service = wording_document_service
        self.policy_wording_service = (
            policy_wording_service or PolicyWordingRetrievalService()
        )

    def enrich_review_items(
        self,
        items: list[LegalDocumentTemplateReviewItem],
    ) -> list[LegalDocumentTemplateReviewItem]:
        return [
            item.model_copy(
                update={
                    "wording_document_impacts": self.impacts_for_legal_document(
                        item.legal_document
                    )
                }
            )
            for item in items
        ]

    def impacts_for_legal_document(
        self,
        legal_document: NormalizedLegalDocument,
    ) -> list[WordingDocumentImpact]:
        impacts: list[WordingDocumentImpact] = []
        for document in self.wording_document_service.list_wording_documents():
            version = self._current_published_version(document)
            if version is None:
                continue
            impact = self._impact_for_version(
                legal_document=legal_document,
                document=document,
                version=version,
            )
            if impact is not None:
                impacts.append(impact)

        if impacts:
            return impacts
        return self._fallback_impacts(legal_document)

    def compare_draft_to_current(
        self,
        *,
        wording_document_id: int,
        draft_version_id: int,
    ) -> WordingDocumentDraftComparison:
        current = self.wording_document_service.get_current_published_version(
            wording_document_id
        )
        draft = self.wording_document_service.get_wording_version(draft_version_id)
        current_clauses = self._clauses_by_id(current)
        draft_clauses = self._clauses_by_id(draft)

        current_ids = set(current_clauses)
        draft_ids = set(draft_clauses)
        added = sorted(draft_ids - current_ids)
        removed = sorted(current_ids - draft_ids)
        modified = sorted(
            clause_id
            for clause_id in current_ids & draft_ids
            if current_clauses[clause_id].text != draft_clauses[clause_id].text
        )

        current_refs = self._canonical_values(current.legal_references_json or [])
        draft_refs = self._canonical_values(draft.legal_references_json or [])
        changed_refs = sorted(current_refs ^ draft_refs)
        changed_effective_dates = self._changed_effective_dates(current, draft)
        snippets = self._changed_full_text_snippets(current.full_text, draft.full_text)
        proposed_changes = [
            self._proposed_change(
                target="structured_clause",
                clause_id=clause_id,
                current_text=current_clauses[clause_id].text,
                proposed_text=draft_clauses[clause_id].text,
                rationale=(
                    "Draft wording clause differs from the current published "
                    "wording and requires legal review before publication."
                ),
            )
            for clause_id in modified
        ]

        if not proposed_changes and current.full_text != draft.full_text:
            proposed_changes.append(
                self._proposed_change(
                    target="full_text",
                    clause_id=None,
                    current_text=self._snippet(current.full_text),
                    proposed_text=self._snippet(draft.full_text),
                    rationale=(
                        "Draft wording full_text differs from the current "
                        "published wording and requires legal review."
                    ),
                )
            )

        return WordingDocumentDraftComparison(
            wording_document_id=wording_document_id,
            current_published_version_id=current.id,
            draft_version_id=draft_version_id,
            added_clauses=added,
            removed_clauses=removed,
            modified_clauses=modified,
            changed_legal_references=changed_refs,
            changed_effective_dates=changed_effective_dates,
            changed_full_text_snippets=snippets,
            content_hash_changed=current.content_hash != draft.content_hash,
            proposed_changes=proposed_changes,
        )

    def _current_published_version(
        self,
        document: WordingDocument,
    ) -> WordingDocumentVersion | None:
        if document.id is None:
            return None
        try:
            return self.wording_document_service.get_current_published_version(
                document.id
            )
        except WordingVersionNotFoundError:
            return None

    def _impact_for_version(
        self,
        *,
        legal_document: NormalizedLegalDocument,
        document: WordingDocument,
        version: WordingDocumentVersion,
    ) -> WordingDocumentImpact | None:
        legal_refs = self._legal_document_references(legal_document)
        version_refs = self._canonical_values(version.legal_references_json or [])
        matched_refs = sorted(legal_refs & version_refs)
        clauses = self._clauses(version)
        matched_clauses = self._matched_clauses(legal_document, legal_refs, clauses)

        if matched_refs:
            reason = "legal reference match"
            confidence = "high"
            score = 0.92
            terms = self._reference_terms(matched_refs)
        elif matched_clauses:
            reason = "clause semantic/text match"
            confidence = "medium"
            score = 0.78
            terms = list(self._legal_document_keywords(legal_document))
        else:
            overlap = self._full_text_overlap(legal_document, version.full_text)
            if overlap:
                reason = "full text keyword match"
                confidence = "medium"
                score = 0.68
                terms = sorted(overlap)
            elif self._product_coverage_match(legal_document, document):
                reason = "product coverage match"
                confidence = "low"
                score = 0.52
                terms = [document.product_line]
            else:
                return None

        snippets = self._snippets_for_terms(version.full_text, terms)
        if not snippets and matched_clauses:
            snippets = [self._snippet(clause.text) for clause in matched_clauses]
        if not snippets:
            snippets = [self._snippet(version.full_text)]

        affected_clause_ids = [
            clause.clause_id for clause in matched_clauses if clause.clause_id
        ]
        proposal_text = self._proposal_source_text(
            legal_document=legal_document,
            full_text=version.full_text,
            fallback=snippets[0],
        )
        proposed_changes = [
            self._wording_proposed_change(
                legal_document=legal_document,
                current_text=proposal_text,
                clause_id=affected_clause_ids[0] if affected_clause_ids else None,
                target="structured_clause" if affected_clause_ids else "full_text",
            )
        ]

        return WordingDocumentImpact(
            wording_document_id=document.id,
            wording_document_code=document.code,
            wording_document_title=document.title,
            current_published_version_id=version.id,
            effective_from=version.effective_from,
            effective_to=version.effective_to,
            affected_clause_ids=affected_clause_ids,
            affected_legal_references=matched_refs,
            matched_text_snippets=snippets,
            match_reason=reason,
            confidence=confidence,
            confidence_score=score,
            proposed_changes=proposed_changes,
            safe_to_auto_draft=False,
        )

    def _fallback_impacts(
        self,
        legal_document: NormalizedLegalDocument,
    ) -> list[WordingDocumentImpact]:
        sections = self.policy_wording_service.get_relevant_wording_sections(
            {"jurisdiction": legal_document.jurisdiction},
            claim_type=None,
            description=legal_document.full_text,
        )
        matched_sections = [
            section for section in sections if self._static_section_matches(legal_document, section)
        ]
        if not matched_sections:
            return []

        snippets = [self._snippet(section.text) for section in matched_sections[:3]]
        first_section = matched_sections[0]
        return [
            WordingDocumentImpact(
                wording_document_id=None,
                wording_document_code="STATIC_POLICY_WORDING_FALLBACK",
                wording_document_title="Static policy wording fallback",
                current_published_version_id=None,
                affected_clause_ids=[first_section.section_id],
                affected_legal_references=[],
                matched_text_snippets=snippets,
                match_reason="static policy wording fallback",
                confidence="low",
                confidence_score=0.45,
                proposed_changes=[
                    self._wording_proposed_change(
                        legal_document=legal_document,
                        current_text=snippets[0],
                        clause_id=first_section.section_id,
                        target="full_text",
                    )
                ],
                safe_to_auto_draft=False,
            )
        ]

    def _matched_clauses(
        self,
        legal_document: NormalizedLegalDocument,
        legal_refs: set[str],
        clauses: list[_Clause],
    ) -> list[_Clause]:
        legal_keywords = self._legal_document_keywords(legal_document)
        matched: list[_Clause] = []
        for clause in clauses:
            clause_refs = self._canonical_values(clause.legal_references)
            clause_text = " ".join(
                value for value in [clause.clause_id, clause.title, clause.text] if value
            )
            clause_keywords = self._keywords(clause_text)
            if legal_refs & clause_refs or len(legal_keywords & clause_keywords) >= 2:
                matched.append(clause)
        return matched

    def _legal_document_references(
        self,
        legal_document: NormalizedLegalDocument,
    ) -> set[str]:
        return (
            self._canonical_values(legal_document.legal_references)
            | self._canonical_values(legal_document.amends)
            | self._canonical_values(legal_document.repeals)
        )

    def _canonical_values(self, values: list[Any]) -> set[str]:
        canonical_values: set[str] = set()
        for value in values:
            if isinstance(value, str):
                canonical_values.add(value)
                continue
            if not isinstance(value, dict):
                continue
            canonical_value = value.get("canonical") or value.get(
                "canonical_reference"
            )
            if canonical_value:
                canonical_values.add(str(canonical_value))
                continue
            if {"type", "number", "year"} <= set(value):
                canonical_values.add(
                    f"ro:{value['type']}:{value['number']}:{value['year']}"
                )
        return canonical_values

    def _clauses(self, version: WordingDocumentVersion) -> list[_Clause]:
        raw = version.structured_clauses_json
        if raw is None:
            return []
        if isinstance(raw, dict):
            raw_clauses = (
                raw.get("clauses")
                or raw.get("sections")
                or raw.get("articles")
                or [raw]
            )
        else:
            raw_clauses = raw
        if not isinstance(raw_clauses, list):
            return []

        clauses: list[_Clause] = []
        for index, item in enumerate(raw_clauses):
            if not isinstance(item, dict):
                continue
            clause_id = item.get("id") or item.get("clause_id") or item.get(
                "section_id"
            )
            title = item.get("title") or item.get("name") or item.get("label")
            text = (
                item.get("text")
                or item.get("body")
                or item.get("content")
                or item.get("full_text")
                or ""
            )
            legal_references = item.get("legal_references") or item.get(
                "legal_references_json"
            ) or []
            clauses.append(
                _Clause(
                    clause_id=str(clause_id or f"clause-{index + 1}"),
                    title=str(title) if title is not None else None,
                    text=str(text),
                    legal_references=legal_references
                    if isinstance(legal_references, list)
                    else [legal_references],
                )
            )
        return clauses

    def _clauses_by_id(
        self,
        version: WordingDocumentVersion,
    ) -> dict[str, _Clause]:
        return {
            clause.clause_id: clause
            for clause in self._clauses(version)
            if clause.clause_id is not None
        }

    def _full_text_overlap(
        self,
        legal_document: NormalizedLegalDocument,
        full_text: str,
    ) -> set[str]:
        legal_keywords = self._legal_document_keywords(legal_document)
        text_keywords = self._keywords(full_text)
        overlap = legal_keywords & text_keywords
        return {word for word in overlap if len(word) >= 5}

    def _product_coverage_match(
        self,
        legal_document: NormalizedLegalDocument,
        document: WordingDocument,
    ) -> bool:
        if document.jurisdiction and document.jurisdiction != legal_document.jurisdiction:
            return False
        terms = self._keywords(
            f"{legal_document.title} {legal_document.summary or ''} {legal_document.full_text}"
        )
        product_terms = self._keywords(document.product_line)
        if product_terms & terms:
            return True
        if document.product_line == "property":
            return bool({"property", "locuinta", "locuinte", "pad"} & terms)
        return False

    def _static_section_matches(
        self,
        legal_document: NormalizedLegalDocument,
        section: PolicyWordingSection,
    ) -> bool:
        legal_keywords = self._legal_document_keywords(legal_document)
        section_text = " ".join(
            [
                section.section_id,
                section.title,
                section.text,
                " ".join(section.coverage_tags),
                " ".join(section.exclusion_tags),
            ]
        )
        return len(legal_keywords & self._keywords(section_text)) >= 2

    def _legal_document_keywords(
        self,
        legal_document: NormalizedLegalDocument,
    ) -> set[str]:
        return self._keywords(
            " ".join(
                [
                    legal_document.title,
                    legal_document.summary or "",
                    legal_document.full_text,
                    legal_document.instrument_type or "",
                    legal_document.external_identifier or "",
                ]
            )
        )

    def _keywords(self, value: str) -> set[str]:
        normalized = value.lower()
        normalized = normalized.replace("ă", "a").replace("â", "a")
        normalized = normalized.replace("î", "i").replace("ș", "s").replace("ş", "s")
        normalized = normalized.replace("ț", "t").replace("ţ", "t")
        return {
            token
            for token in re.findall(r"[a-z0-9]+", normalized)
            if len(token) >= 3 and token not in _STOP_WORDS
        }

    def _reference_terms(self, references: list[str]) -> list[str]:
        terms: list[str] = []
        for reference in references:
            terms.append(reference)
            match = re.search(r":(\d+):(\d{4})$", reference)
            if match:
                number, year = match.groups()
                terms.extend([f"{number}/{year}", f"legea nr. {number}/{year}"])
        return terms

    def _snippets_for_terms(self, text: str, terms: list[str]) -> list[str]:
        lowered_terms = [term.lower() for term in terms if term]
        snippets: list[str] = []
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for index, sentence in enumerate(sentences):
            lowered = sentence.lower()
            if any(term in lowered for term in lowered_terms):
                if len(sentence) < 40 and index > 0:
                    sentence = f"{sentences[index - 1]} {sentence}"
                snippets.append(self._snippet(sentence))
        return snippets[:3]

    def _changed_effective_dates(
        self,
        current: WordingDocumentVersion,
        draft: WordingDocumentVersion,
    ) -> list[str]:
        changes: list[str] = []
        if current.effective_from != draft.effective_from:
            changes.append("effective_from")
        if current.effective_to != draft.effective_to:
            changes.append("effective_to")
        return changes

    def _changed_full_text_snippets(self, current: str, draft: str) -> list[str]:
        if current == draft:
            return []
        return [self._snippet(current), self._snippet(draft)]

    def _wording_proposed_change(
        self,
        *,
        legal_document: NormalizedLegalDocument,
        current_text: str,
        clause_id: str | None,
        target: str,
    ) -> WordingDocumentProposedChange:
        proposed_text = self._proposed_text(current_text, legal_document)
        return self._proposed_change(
            target=target,
            clause_id=clause_id,
            current_text=current_text,
            proposed_text=proposed_text,
            rationale=(
                f"{legal_document.title} may require this wording to be updated "
                "before the next approved wording version is published."
            ),
        )

    def _proposed_change(
        self,
        *,
        target: str,
        clause_id: str | None,
        current_text: str,
        proposed_text: str,
        rationale: str,
    ) -> WordingDocumentProposedChange:
        return WordingDocumentProposedChange(
            target=target,
            clause_id=clause_id,
            current_text=current_text,
            proposed_text=proposed_text,
            rationale=rationale,
            diff=self._diff(current_text, proposed_text),
            safe_to_auto_draft=False,
        )

    def _proposed_text(
        self,
        current_text: str,
        legal_document: NormalizedLegalDocument,
    ) -> str:
        deadline = re.search(
            r"(?:from|de la|din)\s+(\d+)\s+(?:days|zile).*?(?:to|la)\s+(\d+)\s+(?:days|zile)",
            legal_document.full_text,
            flags=re.IGNORECASE,
        )
        if deadline:
            old_value, new_value = deadline.groups()
            return re.sub(
                rf"\b{re.escape(old_value)}\b",
                new_value,
                current_text,
                count=1,
            )
        return (
            f"{current_text}\n\n"
            f"Legal review note: align this wording with {legal_document.title}."
        )

    def _proposal_source_text(
        self,
        *,
        legal_document: NormalizedLegalDocument,
        full_text: str,
        fallback: str,
    ) -> str:
        deadline = re.search(
            r"(?:from|de la|din)\s+(\d+)\s+(?:days|zile).*?(?:to|la)\s+(\d+)\s+(?:days|zile)",
            legal_document.full_text,
            flags=re.IGNORECASE,
        )
        if deadline:
            old_value = deadline.group(1)
            for sentence in re.split(r"(?<=[.!?])\s+", full_text):
                if re.search(rf"\b{re.escape(old_value)}\b", sentence):
                    return self._snippet(sentence)
        return fallback

    def _diff(self, current_text: str, proposed_text: str) -> str:
        if current_text == proposed_text:
            return ""
        return f"--- current\n+++ proposed\n- {current_text}\n+ {proposed_text}"

    def _snippet(self, text: str, limit: int = 320) -> str:
        collapsed = re.sub(r"\s+", " ", text).strip()
        if len(collapsed) <= limit:
            return collapsed
        return f"{collapsed[: limit - 3].rstrip()}..."


__all__ = ["LegalReviewWordingImpactService"]
