from __future__ import annotations

from datetime import UTC, datetime
import re

from underwright.application.intelligence_ports import TemplateCandidateExplainer
from underwright.domain.intelligence import (
    AuditRecord,
    EvidenceSnippet,
    ExternalEvent,
    TemplateCorrelationBatchResult,
    TemplateReviewCandidate,
)
from underwright.domain.models import Template


LEGAL_REFERENCE_PATTERN = re.compile(
    r"\b(?:legea|lege|norma|regulamentul|ordinul)\s+(?:nr\.?\s*)?\d+\/\d{4}\b",
    re.IGNORECASE,
)

TOPIC_MATCH_TERMS = {
    "PAD / compulsory home insurance": ["pad", "legea 260/2008"],
    "residential property insurance": ["locuint", "locuin", "home"],
    "commercial property insurance": ["commercial", "property"],
    "coverage wording": ["clauz", "coverage", "wording"],
    "deductibles / limits": ["fransiz", "deductible", "limit"],
    "pricing / premium affordability": ["prima", "premium", "pricing"],
    "earthquake": ["cutremur", "earthquake"],
    "flood": ["inunda", "flood"],
    "fire": ["incend", "fire"],
    "storm / hail": ["furtuna", "grindin", "storm", "hail"],
}


class TemplateReviewCorrelationService:
    def __init__(
        self,
        event_repository,
        template_repository,
        candidate_repository,
        audit_repository=None,
        candidate_explainer: TemplateCandidateExplainer | None = None,
    ) -> None:
        self.event_repository = event_repository
        self.template_repository = template_repository
        self.candidate_repository = candidate_repository
        self.audit_repository = audit_repository
        self.candidate_explainer = candidate_explainer
        self.last_explainer_error: str | None = None

    def correlate_batch(
        self,
        limit: int = 50,
        source_id: str | None = None,
    ) -> TemplateCorrelationBatchResult:
        result = TemplateCorrelationBatchResult(
            source_id=source_id,
            status="success",
            started_at=datetime.now(UTC),
        )

        try:
            events = self.event_repository.list_for_template_review(
                limit=limit,
                source_id=source_id,
            )
            templates = self.template_repository.list_active()
        except Exception as exc:
            result.status = "failed"
            result.errors = [str(exc)]
            result.finished_at = datetime.now(UTC)
            return result

        result.events_seen = len(events)
        result.templates_seen = len(templates)

        for event in events:
            try:
                for template in templates:
                    candidate = self._match_event_to_template(event, template)
                    if candidate is None:
                        continue
                    if self.candidate_repository.save_if_new(candidate):
                        result.candidates_created += 1
                        self._audit(candidate)
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"{event.event_id}: {exc}")

        result.finished_at = datetime.now(UTC)
        return result

    def _match_event_to_template(
        self,
        event: ExternalEvent,
        template: Template,
    ) -> TemplateReviewCandidate | None:
        if not self._is_correlatable_event(event):
            return None

        legal_refs = self._legal_references(
            event.title,
            event.body_text,
            event.underwriter_summary,
            event.recommended_action,
        )
        template_text = self._template_text(template)
        template_legal_refs = self._legal_references(template_text)
        overlapping_refs = sorted(set(legal_refs) & set(template_legal_refs))

        rule_ids: list[str] = []
        score = 0.0
        evidence: list[EvidenceSnippet] = []
        if overlapping_refs:
            rule_ids.append("legal_reference_overlap")
            score = 0.95
            evidence.append(
                EvidenceSnippet(
                    snippet=", ".join(overlapping_refs),
                    reason="The event and template reference the same legal instrument.",
                )
            )

        matched_topics = self._matched_topics(event, template_text)
        if matched_topics:
            rule_ids.append("template_topic_overlap")
            score = max(score, min(0.75, 0.45 + 0.1 * len(matched_topics)))
            evidence.append(
                EvidenceSnippet(
                    snippet=", ".join(matched_topics),
                    reason="The event topics overlap with template text.",
                )
            )

        if not rule_ids:
            return None

        candidate = TemplateReviewCandidate(
            event_id=event.event_id,
            template_id=template.id or 0,
            template_code=template.template_code,
            template_name=template.name,
            template_version=template.version,
            event_title=event.title,
            source_url=event.original_url,
            legal_references_json=overlapping_refs or legal_refs,
            rule_ids_json=rule_ids,
            match_score=score,
            rationale=(
                "Review recommended. This template may reference a law or topic "
                "potentially affected by the external event."
            ),
            evidence_json=evidence or event.evidence_json,
            created_at=datetime.now(UTC),
        )
        return self._explain_candidate(event, template, candidate)

    def _is_correlatable_event(self, event: ExternalEvent) -> bool:
        if event.status != "classified":
            return False
        if event.event_type == "not_relevant":
            return False
        if not event.topics_json and not self._legal_references(
            event.title,
            event.body_text,
        ):
            return False
        return True

    def _legal_references(self, *texts: str) -> list[str]:
        references = set()
        for text in texts:
            for match in LEGAL_REFERENCE_PATTERN.findall(text or ""):
                references.add(self._normalize_legal_reference(match))
        return sorted(references)

    def _normalize_legal_reference(self, reference: str) -> str:
        return " ".join(reference.replace("nr.", "nr. ").split()).title()

    def _template_text(self, template: Template) -> str:
        return " ".join(
            [
                template.template_code,
                template.name,
                template.version,
                template.document_type,
                template.content,
            ]
        ).lower()

    def _matched_topics(self, event: ExternalEvent, template_text: str) -> list[str]:
        matched = []
        for topic in event.topics_json:
            terms = TOPIC_MATCH_TERMS.get(topic, [topic])
            if any(term.lower() in template_text for term in terms):
                matched.append(topic)
        return sorted(set(matched))

    def _explain_candidate(
        self,
        event: ExternalEvent,
        template: Template,
        candidate: TemplateReviewCandidate,
    ) -> TemplateReviewCandidate:
        self.last_explainer_error = None
        if self.candidate_explainer is None:
            return candidate

        try:
            return self.candidate_explainer.explain(event, template, candidate)
        except Exception as exc:
            self.last_explainer_error = f"{exc.__class__.__name__}: {exc}"
            return candidate

    def _audit(self, candidate: TemplateReviewCandidate) -> None:
        if self.audit_repository is None:
            return
        self.audit_repository.save(
            AuditRecord(
                entity_type="template_review_candidate",
                entity_id=candidate.candidate_id,
                action="template_review_candidate.created",
                raw_url=candidate.source_url,
                model_name=(
                    self.candidate_explainer.model_name
                    if self.candidate_explainer is not None
                    else None
                ),
                model_version=(
                    self.candidate_explainer.model_version
                    if self.candidate_explainer is not None
                    else None
                ),
                prompt_version=(
                    self.candidate_explainer.prompt_version
                    if self.candidate_explainer is not None
                    else None
                ),
                input_ref_json={
                    "candidate_explainer_error": self.last_explainer_error,
                },
                output_json=candidate.model_dump(mode="json"),
                rules_triggered_json=candidate.rule_ids_json,
                created_at=datetime.now(UTC),
            )
        )
