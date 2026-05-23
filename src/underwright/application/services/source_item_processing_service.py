from __future__ import annotations

from datetime import UTC, datetime
import unicodedata
from urllib.parse import urlparse

from underwright.application.intelligence_ports import EventClassifier, EventSummaryWriter
from underwright.domain.intelligence import (
    AuditRecord,
    ClassificationInput,
    ClassificationOutput,
    EvidenceSnippet,
    ExternalEvent,
    ProcessingBatchResult,
    RawSourceItem,
    Source,
)


MAX_CLASSIFICATION_TEXT_CHARS = 12_000

PROPERTY_TOPICS = {
    "pad": "PAD / compulsory home insurance",
    "compulsory": "PAD / compulsory home insurance",
    "home": "residential property insurance",
    "locuin": "residential property insurance",
    "commercial": "commercial property insurance",
    "earthquake": "earthquake",
    "cutremur": "earthquake",
    "flood": "flood",
    "inunda": "flood",
    "fire": "fire",
    "incend": "fire",
    "storm": "storm / hail",
    "grindin": "storm / hail",
    "solvency": "solvency",
    "sanction": "insurer sanctions",
    "sanc": "insurer sanctions",
    "coverage": "coverage wording",
    "clauz": "coverage wording",
    "conditii de asigurare": "coverage wording",
    "wording": "coverage wording",
    "deductible": "deductibles / limits",
    "fransiz": "deductibles / limits",
    "premium": "pricing / premium affordability",
    "prima": "pricing / premium affordability",
    "broker": "insurance brokerage",
    "intermediar": "insurance brokerage",
    "claim": "claims handling",
    "daun": "claims handling",
    "despagub": "claims handling",
    "conformitate": "regulatory compliance",
    "reglement": "regulatory compliance",
    "obligat": "regulatory compliance",
    "polita": "contract template changes",
    "contract": "contract template changes",
}

SUPPRESSED_TOPICS = {
    "pension": "private pensions",
    "pensii": "private pensions",
    "capital market": "capital markets",
    "piata de capital": "capital markets",
    "investment fund": "investment funds",
    "fonduri": "investment funds",
    "life insurance": "life insurance",
    "asigurari de viata": "life insurance",
    "health": "health insurance",
    "sanatate": "health insurance",
    "rca": "RCA-only item",
}

GENERIC_SOURCE_TITLE_FRAGMENTS = {
    "avertizari nowcasting",
    "conducere",
    "incdfp -",
    "informatii de interes public",
    "integritate",
    "meteo romania |",
    "organizare",
    "organigrama",
}

HEADLINE_TOPIC_LABELS = {
    "PAD / compulsory home insurance": "PAD home insurance",
    "commercial property insurance": "commercial property insurance",
    "coverage wording": "coverage wording",
    "deductibles / limits": "deductibles and limits",
    "earthquake": "earthquake",
    "fire": "fire",
    "flood": "flood",
    "insurer sanctions": "insurer sanctions",
    "insurance brokerage": "insurance brokerage",
    "claims handling": "claims handling",
    "regulatory compliance": "regulatory compliance",
    "contract template changes": "contract template changes",
    "pricing / premium affordability": "property insurance pricing",
    "residential property insurance": "residential property insurance",
    "solvency": "insurer solvency",
    "storm / hail": "storm and hail",
}

HEADLINE_TOPIC_PRIORITY = [
    "storm / hail",
    "earthquake",
    "flood",
    "fire",
    "PAD / compulsory home insurance",
    "coverage wording",
    "contract template changes",
    "regulatory compliance",
    "claims handling",
    "insurance brokerage",
    "deductibles / limits",
    "pricing / premium affordability",
    "residential property insurance",
    "commercial property insurance",
]


class ClassificationPreprocessor:
    def __init__(self, max_text_chars: int = MAX_CLASSIFICATION_TEXT_CHARS) -> None:
        self.max_text_chars = max_text_chars

    def build(self, raw_item: RawSourceItem, source: Source) -> ClassificationInput:
        body_text = self._clean_text(raw_item.extracted_text)
        if len(body_text) > self.max_text_chars:
            body_text = body_text[: self.max_text_chars].rstrip()
        allowed_hosts = self._allowed_hosts(source)
        source_host = self._host(raw_item.original_url)

        return ClassificationInput(
            raw_item_id=raw_item.raw_item_id,
            source_id=source.source_id,
            source_type=source.source_type,
            trust_tier=source.trust_tier,
            original_url=raw_item.original_url,
            published_at=raw_item.published_at,
            title=self._clean_text(raw_item.title) or raw_item.canonical_url,
            body_text_ref=f"raw_source_item:{raw_item.raw_item_id}:extracted_text",
            body_text=body_text,
            original_language=source.language,
            country=source.country,
            jurisdiction=source.country,
            source_url_host=source_host,
            allowed_source_hosts=sorted(allowed_hosts),
            is_allowed_source_url=(
                not allowed_hosts
                or bool(source.config_json.get("allow_external_detail_urls", False))
                or source_host in allowed_hosts
            ),
        )

    def _clean_text(self, text: str) -> str:
        return " ".join(text.split())

    def _allowed_hosts(self, source: Source) -> set[str]:
        hosts = set()
        if source.config_json.get("list_url"):
            hosts.add(self._host(source.config_json["list_url"]))
        for url in source.config_json.get("detail_urls") or []:
            hosts.add(self._host(url))
        for host in source.config_json.get("allowed_detail_hosts") or []:
            hosts.add(host.lower().split(":")[0])
        return {host for host in hosts if host}

    def _host(self, url: str) -> str:
        return urlparse(url).netloc.lower().split("@")[-1].split(":")[0]


class DeterministicInsuranceClassifier:
    model_name = "deterministic-keyword-classifier"
    model_version = "mvp-1"
    prompt_version = None

    def classify(
        self,
        classification_input: ClassificationInput,
    ) -> ClassificationOutput:
        text = f"{classification_input.title}\n{classification_input.body_text}".lower()
        topics = sorted({topic for key, topic in PROPERTY_TOPICS.items() if key in text})
        suppression_reasons = [
            reason for key, reason in SUPPRESSED_TOPICS.items() if key in text
        ]
        is_property = bool(topics)
        is_insurance = is_property or "asigur" in text or "insurance" in text
        source_allowed = classification_input.is_allowed_source_url
        suppressed = not source_allowed or not is_insurance or not is_property

        event_type = (
            "not_relevant"
            if not source_allowed
            else self._classify_event_type(text, is_insurance, is_property)
        )
        severity = self._classify_severity(text, event_type)
        visible_topics = [] if suppressed else topics
        if not source_allowed:
            suppression_reasons.append("source URL is outside configured source hosts")

        return ClassificationOutput(
            is_insurance_relevant=is_insurance and source_allowed,
            is_property_relevant=is_property and source_allowed,
            event_type=event_type,
            topics=visible_topics,
            affected_products=self._affected_products(visible_topics),
            affected_perils=self._affected_perils(visible_topics),
            severity=severity,
            summary_for_underwriter=self._summary(
                classification_input=classification_input,
                topics=visible_topics,
                event_type=event_type,
                severity=severity,
                suppressed=suppressed,
            ),
            recommended_action=self._recommended_action(event_type, suppressed),
            confidence=0.78 if not suppressed else 0.62,
            evidence=[
                evidence
                for evidence in [
                    self._evidence(classification_input.body_text, visible_topics[0])
                    if visible_topics
                    else None
                ]
                if evidence is not None
            ],
            reasons_for_suppression=(
                sorted(set(suppression_reasons)) if suppressed else []
            ),
        )

    def _classify_event_type(
        self,
        text: str,
        is_insurance: bool,
        is_property: bool,
    ) -> str:
        if not is_insurance or not is_property:
            return "not_relevant"
        if "sanction" in text or "sanc" in text:
            return "sanction_or_enforcement"
        if "warning" in text or "avert" in text:
            return "public_warning"
        if "consult" in text or "draft" in text or "proiect" in text:
            return "consultation_or_draft_rule"
        if "report" in text or "raport" in text:
            return "market_report"
        if "claim" in text or "daun" in text:
            return "claims_update"
        if "solvency" in text or "stabilitate" in text:
            return "solvency_or_market_stability"
        return "regulatory_update"

    def _classify_severity(self, text: str, event_type: str) -> str:
        if event_type in {"sanction_or_enforcement", "public_warning"}:
            return "high"
        if any(term in text for term in ["earthquake", "cutremur", "flood", "inunda"]):
            return "medium"
        return "low"

    def _affected_products(self, topics: list[str]) -> list[str]:
        products = set()
        if any("commercial" in topic for topic in topics):
            products.add("commercial_property")
        if any("residential" in topic or "PAD" in topic for topic in topics):
            products.add("residential_property")
        if not products and topics:
            products.add("property")
        return sorted(products)

    def _affected_perils(self, topics: list[str]) -> list[str]:
        return [
            topic
            for topic in topics
            if topic in {"earthquake", "flood", "landslide", "fire", "storm / hail"}
        ]

    def _summary(
        self,
        classification_input: ClassificationInput,
        topics: list[str],
        event_type: str,
        severity: str,
        suppressed: bool,
    ) -> str:
        if suppressed:
            return "Source item was retained for audit but suppressed for the Romanian property MVP."
        topic_text = self._topic_text(topics)
        event_text = self._event_type_text(event_type)
        return (
            f"{classification_input.title} was classified as a {severity} severity "
            f"{event_text} involving {topic_text}."
        )

    def _recommended_action(self, event_type: str, suppressed: bool) -> str:
        if suppressed:
            return "No underwriter action recommended for the Romanian property MVP."
        actions = {
            "consultation_or_draft_rule": (
                "Review affected Romanian property wording and templates; track consultation deadlines or effective dates."
            ),
            "public_warning": (
                "Review open Romanian property quotes, renewals, and claims for exposed locations or perils."
            ),
            "market_report": (
                "Use the report as context for pricing, appetite, and exposure assumptions on Romanian property risks."
            ),
            "claims_update": (
                "Review claims handling guidance and monitor whether open Romanian property claims need updated treatment."
            ),
            "sanction_or_enforcement": (
                "Review affected counterparties, distribution controls, and any Romanian property submissions tied to the named firms."
            ),
            "solvency_or_market_stability": (
                "Review carrier stability context before relying on affected markets for Romanian property capacity."
            ),
        }
        return actions.get(
            event_type,
            "Review recommended for potentially affected Romanian property underwriting or document work.",
        )

    def _topic_text(self, topics: list[str]) -> str:
        if not topics:
            return "Romanian property insurance"
        if len(topics) == 1:
            return topics[0]
        return f"{', '.join(topics[:-1])}, and {topics[-1]}"

    def _event_type_text(self, event_type: str) -> str:
        labels = {
            "consultation_or_draft_rule": "draft rule or consultation",
            "public_warning": "public warning",
            "market_report": "market report",
            "claims_update": "claims update",
            "sanction_or_enforcement": "sanction or enforcement item",
            "solvency_or_market_stability": "solvency or market stability item",
            "product_or_coverage_update": "product or coverage update",
            "consumer_protection": "consumer protection item",
            "regulatory_update": "regulatory update",
        }
        return labels.get(event_type, event_type.replace("_", " "))

    def _evidence(self, body_text: str, topic: str) -> EvidenceSnippet:
        snippet = " ".join(body_text.strip().split()[:40])
        return EvidenceSnippet(
            snippet=snippet,
            reason=f"Source text matched Romanian property topic: {topic}.",
        )


class FallbackEventClassifier:
    def __init__(
        self,
        primary: EventClassifier,
        fallback: EventClassifier,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self._active_classifier = primary
        self.last_error: str | None = None

    @property
    def model_name(self) -> str:
        return self._active_classifier.model_name

    @property
    def model_version(self) -> str:
        return self._active_classifier.model_version

    @property
    def prompt_version(self) -> str | None:
        return self._active_classifier.prompt_version

    def classify(
        self,
        classification_input: ClassificationInput,
    ) -> ClassificationOutput:
        self.last_error = None
        try:
            classification = self.primary.classify(classification_input)
            self._active_classifier = self.primary
            return classification
        except Exception as exc:
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            self._active_classifier = self.fallback
            return self.fallback.classify(classification_input)


class SummaryWritingEventClassifier:
    def __init__(
        self,
        classifier: EventClassifier,
        summary_writer: EventSummaryWriter,
    ) -> None:
        self.classifier = classifier
        self.summary_writer = summary_writer
        self.last_error: str | None = None

    @property
    def model_name(self) -> str:
        return f"{self.classifier.model_name}+{self.summary_writer.model_name}"

    @property
    def model_version(self) -> str:
        return f"{self.classifier.model_version}+{self.summary_writer.model_version}"

    @property
    def prompt_version(self) -> str | None:
        classifier_prompt = self.classifier.prompt_version or "none"
        writer_prompt = self.summary_writer.prompt_version or "none"
        return f"{classifier_prompt}+{writer_prompt}"

    def classify(
        self,
        classification_input: ClassificationInput,
    ) -> ClassificationOutput:
        classification = self.classifier.classify(classification_input)
        base_error = getattr(self.classifier, "last_error", None)
        self.last_error = base_error

        if (
            not classification.is_insurance_relevant
            or not classification.is_property_relevant
        ):
            return classification

        try:
            return self.summary_writer.summarize(classification_input, classification)
        except Exception as exc:
            summary_error = f"{exc.__class__.__name__}: {exc}"
            self.last_error = (
                f"{base_error}; summary_error={summary_error}"
                if base_error
                else f"summary_error={summary_error}"
            )
            return classification


class SourceItemProcessingService:
    def __init__(
        self,
        source_repository,
        raw_item_repository,
        external_event_repository,
        classifier: EventClassifier,
        audit_repository=None,
        preprocessor: ClassificationPreprocessor | None = None,
    ) -> None:
        self.source_repository = source_repository
        self.raw_item_repository = raw_item_repository
        self.external_event_repository = external_event_repository
        self.classifier = classifier
        self.audit_repository = audit_repository
        self.preprocessor = preprocessor or ClassificationPreprocessor()

    def process_batch(
        self,
        limit: int = 50,
        source_id: str | None = None,
    ) -> ProcessingBatchResult:
        result = ProcessingBatchResult(
            source_id=source_id,
            status="success",
            started_at=datetime.now(UTC),
        )

        try:
            raw_items = self.raw_item_repository.list_unprocessed(
                limit=limit,
                source_id=source_id,
            )
        except Exception as exc:
            result.status = "failed"
            result.errors = [str(exc)]
            result.finished_at = datetime.now(UTC)
            return result

        result.raw_items_seen = len(raw_items)
        source_cache: dict[str, Source] = {}
        for raw_item in raw_items:
            try:
                source = source_cache.get(raw_item.source_id)
                if source is None:
                    source = self.source_repository.get_enabled(raw_item.source_id)
                    source_cache[source.source_id] = source

                classification_input = self.preprocessor.build(raw_item, source)
                classification = self.classifier.classify(classification_input)
                event = self._build_event(classification_input, classification)

                if self.external_event_repository.save_if_new(event):
                    result.events_created += 1
                    if event.status == "classified":
                        result.classified += 1
                    elif event.status == "suppressed":
                        result.suppressed += 1
                    self._audit(event, classification_input, classification)
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"{raw_item.raw_item_id}: {exc}")

        result.finished_at = datetime.now(UTC)
        return result

    def _build_event(
        self,
        classification_input: ClassificationInput,
        classification: ClassificationOutput,
    ) -> ExternalEvent:
        suppressed = (
            not classification.is_insurance_relevant
            or not classification.is_property_relevant
        )
        return ExternalEvent(
            raw_item_id=classification_input.raw_item_id,
            source_id=classification_input.source_id,
            source_type=classification_input.source_type,
            trust_tier=classification_input.trust_tier,
            original_url=classification_input.original_url,
            published_at=classification_input.published_at,
            ingested_at=datetime.now(UTC),
            title=self._event_title(classification_input, classification),
            body_text_ref=classification_input.body_text_ref,
            body_text=classification_input.body_text,
            original_language=classification_input.original_language,
            country=classification_input.country,
            jurisdiction=classification_input.jurisdiction,
            event_type=classification.event_type,
            line_of_business="property" if classification.is_property_relevant else None,
            product=(
                classification.affected_products[0]
                if classification.affected_products
                else None
            ),
            topics_json=classification.topics,
            perils_json=classification.affected_perils,
            severity=classification.severity,
            confidence=classification.confidence,
            underwriter_summary=classification.summary_for_underwriter,
            recommended_action=classification.recommended_action,
            evidence_json=classification.evidence,
            classification_json=classification,
            status="suppressed" if suppressed else "classified",
        )

    def _event_title(
        self,
        classification_input: ClassificationInput,
        classification: ClassificationOutput,
    ) -> str:
        display_title = (classification.display_title or "").strip()
        if display_title:
            return display_title
        if not classification.is_property_relevant:
            return classification_input.title
        if self._looks_like_source_label(classification_input.title):
            return self._fallback_display_title(classification_input, classification)
        return classification_input.title

    def _looks_like_source_label(self, title: str) -> bool:
        normalized = self._ascii_lower(title)
        return any(
            fragment in normalized for fragment in GENERIC_SOURCE_TITLE_FRAGMENTS
        )

    def _fallback_display_title(
        self,
        classification_input: ClassificationInput,
        classification: ClassificationOutput,
    ) -> str:
        if classification_input.source_type == "weather" and not self._has_weather_topic(
            classification.topics
        ):
            return "Nowcasting weather warnings issued for Romanian property exposure review"
        topic = self._headline_topic(classification.topics)
        subject = self._headline_subject(topic)
        if classification.event_type == "public_warning":
            return f"{subject} warning issued for Romanian property exposure review"
        if classification.event_type == "consultation_or_draft_rule":
            return f"{subject} consultation may affect Romanian property wording"
        if classification.event_type == "regulatory_update":
            return f"{subject} update may affect Romanian property underwriting"
        if classification.event_type == "market_report":
            return f"{subject} market report signals Romanian property underwriting context"
        if classification.event_type == "claims_update":
            return f"{subject} claims update may affect Romanian property review"
        if classification.event_type == "sanction_or_enforcement":
            return f"{subject} enforcement action may affect Romanian property review"
        return f"{subject} event may affect Romanian property underwriting"

    def _headline_subject(self, topic: str) -> str:
        return f"{topic[:1].upper()}{topic[1:]}"

    def _headline_topic(self, topics: list[str]) -> str:
        for topic in HEADLINE_TOPIC_PRIORITY:
            if topic in topics:
                return HEADLINE_TOPIC_LABELS[topic]
        if topics:
            return HEADLINE_TOPIC_LABELS.get(topics[0], topics[0])
        return "insurance"

    def _has_weather_topic(self, topics: list[str]) -> bool:
        return bool({"storm / hail", "flood", "fire"} & set(topics))

    def _ascii_lower(self, value: str) -> str:
        return (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
        )

    def _audit(
        self,
        event: ExternalEvent,
        classification_input: ClassificationInput,
        classification: ClassificationOutput,
    ) -> None:
        if self.audit_repository is None:
            return

        self.audit_repository.save(
            AuditRecord(
                entity_type="external_event",
                entity_id=event.event_id,
                action="classified",
                raw_url=event.original_url,
                raw_item_id=event.raw_item_id,
                model_name=self.classifier.model_name,
                model_version=self.classifier.model_version,
                prompt_version=self.classifier.prompt_version,
                input_ref_json={
                    "source_id": classification_input.source_id,
                    "body_text_ref": classification_input.body_text_ref,
                    "body_text_chars": len(classification_input.body_text),
                    "classifier_error": getattr(self.classifier, "last_error", None),
                },
                output_json=classification.model_dump(mode="json"),
                created_at=datetime.now(UTC),
            )
        )
