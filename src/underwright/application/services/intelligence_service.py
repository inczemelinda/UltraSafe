from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from underwright.application.intelligence_ports import SourceConnector
from underwright.domain.intelligence import (
    Alert,
    AuditRecord,
    ClassificationOutput,
    CorrelationTargetType,
    Correlation,
    DocumentAsset,
    EvidenceSnippet,
    EventDetail,
    ExternalEvent,
    Feedback,
    FeedbackType,
    IngestionRun,
    IntelligenceFeedCard,
    RawSourceItem,
    Source,
    UnderwritingWorkItem,
)


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
    "deductible": "deductibles / limits",
    "fransiz": "deductibles / limits",
    "premium": "pricing / premium affordability",
    "prima": "pricing / premium affordability",
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


class IntelligenceService:
    """Application service for the insurance intelligence MVP.

    The service keeps correlation deterministic: language models can improve
    summaries later, but they never create affected targets.
    """

    def __init__(
        self,
        sources: list[Source] | None = None,
        raw_items: list[RawSourceItem] | None = None,
        events: list[ExternalEvent] | None = None,
        document_assets: list[DocumentAsset] | None = None,
        work_items: list[UnderwritingWorkItem] | None = None,
        correlations: list[Correlation] | None = None,
        alerts: list[Alert] | None = None,
        feedback: list[Feedback] | None = None,
        audit_records: list[AuditRecord] | None = None,
        connectors: dict[str, SourceConnector] | None = None,
    ) -> None:
        self.sources = {source.source_id: source for source in sources or []}
        self.raw_items = {item.raw_item_id: item for item in raw_items or []}
        self.events = {event.event_id: event for event in events or []}
        self.document_assets = {
            document.document_id: document for document in document_assets or []
        }
        self.work_items = {item.work_item_id: item for item in work_items or []}
        self.correlations = {
            correlation.correlation_id: correlation
            for correlation in correlations or []
        }
        self.alerts = {alert.alert_id: alert for alert in alerts or []}
        self.feedback = {entry.feedback_id: entry for entry in feedback or []}
        self.audit_records = {
            record.audit_id: record for record in audit_records or []
        }
        self.connectors = connectors or {}
        self.ingestion_runs: dict[UUID, IngestionRun] = {}

    def list_feed_cards(
        self,
        country: str | None = None,
        source_id: str | None = None,
        line_of_business: str | None = None,
        topic: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
    ) -> list[IntelligenceFeedCard]:
        events = [
            event
            for event in self.events.values()
            if event.status == "classified"
            and (country is None or event.country == country)
            and (source_id is None or event.source_id == source_id)
            and (line_of_business is None or event.line_of_business == line_of_business)
            and (topic is None or topic in event.topics_json)
            and (event_type is None or event.event_type == event_type)
            and (severity is None or event.severity == severity)
        ]
        return [self._build_feed_card(event) for event in events]

    def get_event_detail(self, event_id: UUID) -> EventDetail:
        event = self.events.get(event_id)
        if event is None:
            raise ValueError("ExternalEvent not found")
        source = self.sources[event.source_id]
        return EventDetail(
            event=event,
            source=source,
            alerts=[
                alert for alert in self.alerts.values() if alert.event_id == event_id
            ],
            document_correlations=[
                correlation
                for correlation in self.correlations.values()
                if correlation.event_id == event_id
                and correlation.target_type == "document_asset"
            ],
            audit_records=[
                record
                for record in self.audit_records.values()
                if record.entity_id in {event_id, str(event_id)}
                or record.raw_item_id == event.raw_item_id
            ],
        )

    def list_document_review_candidates(self) -> list[Correlation]:
        return [
            correlation
            for correlation in self.correlations.values()
            if correlation.target_type == "document_asset"
            and correlation.status == "candidate"
        ]

    def list_alerts(
        self,
        assigned_underwriter: str | None = None,
        status: str | None = "open",
    ) -> list[Alert]:
        return [
            alert
            for alert in self.alerts.values()
            if (assigned_underwriter is None or alert.assigned_underwriter == assigned_underwriter)
            and (status is None or alert.status == status)
        ]

    def record_feedback(
        self,
        user_id: str,
        target_type: str,
        target_id: UUID,
        feedback_type: FeedbackType,
        comment: str | None = None,
    ) -> Feedback:
        now = datetime.now(UTC)
        entry = Feedback(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            feedback_type=feedback_type,
            comment=comment,
            created_at=now,
        )
        self.feedback[entry.feedback_id] = entry
        self._audit(
            entity_type=target_type,
            entity_id=target_id,
            action=f"feedback.{feedback_type}",
            user_id=user_id,
            output_json=entry.model_dump(mode="json"),
        )
        return entry

    def run_ingestion(self, source_id: str = "asf_ro") -> IngestionRun:
        now = datetime.now(UTC)
        run = IngestionRun(source_id=source_id, status="started", started_at=now)
        self.ingestion_runs[run.run_id] = run
        source = self.sources.get(source_id)
        if source is None:
            run.status = "failed"
            run.errors.append(f"Source {source_id} is not configured")
            run.finished_at = datetime.now(UTC)
            return run

        connector = self.connectors.get(source.connector_type)
        try:
            fetched_items = (
                connector.fetch_items(source)
                if connector is not None
                else [self._demo_raw_item(source_id)]
            )
        except Exception as exc:
            run.status = "failed"
            run.errors.append(str(exc))
            run.finished_at = datetime.now(UTC)
            self._audit(
                entity_type="source",
                entity_id=source.source_id,
                action="ingestion_failed",
                output_json={"error": str(exc)},
            )
            return run
        existing_urls = {item.canonical_url for item in self.raw_items.values()}
        existing_hashes = {item.content_hash for item in self.raw_items.values()}
        run.raw_items_seen = len(fetched_items)
        for raw_item in fetched_items:
            if (
                raw_item.canonical_url in existing_urls
                or raw_item.content_hash in existing_hashes
            ):
                continue
            self.raw_items[raw_item.raw_item_id] = raw_item
            existing_urls.add(raw_item.canonical_url)
            existing_hashes.add(raw_item.content_hash)
            event = self.normalize(raw_item, source)
            self.classify(event)
            self.events[event.event_id] = event
            run.raw_items_created += 1
            run.events_created += 1
            run.alerts_created += self.correlate_event(event)
        run.status = "success"
        run.finished_at = datetime.now(UTC)
        return run

    def get_ingestion_run(self, run_id: UUID) -> IngestionRun:
        run = self.ingestion_runs.get(run_id)
        if run is None:
            raise ValueError("IngestionRun not found")
        return run

    def normalize(self, raw_item: RawSourceItem, source: Source) -> ExternalEvent:
        return ExternalEvent(
            raw_item_id=raw_item.raw_item_id,
            source_id=source.source_id,
            source_type=source.source_type,
            trust_tier=source.trust_tier,
            original_url=raw_item.original_url,
            published_at=raw_item.published_at,
            ingested_at=datetime.now(UTC),
            title=raw_item.title,
            body_text_ref=f"raw_source_item:{raw_item.raw_item_id}:extracted_text",
            body_text=raw_item.extracted_text,
            original_language=source.language,
            country=source.country,
            jurisdiction=source.country,
        )

    def classify(self, event: ExternalEvent) -> ClassificationOutput:
        text = f"{event.title}\n{event.body_text}".lower()
        topics = sorted({topic for key, topic in PROPERTY_TOPICS.items() if key in text})
        suppression_reasons = [
            reason for key, reason in SUPPRESSED_TOPICS.items() if key in text
        ]
        is_property = bool(topics)
        is_insurance = is_property or "asigur" in text or "insurance" in text

        event_type = self._classify_event_type(text, is_insurance, is_property)
        severity = self._classify_severity(text, event_type)
        perils = [
            topic
            for topic in topics
            if topic in {"earthquake", "flood", "landslide", "fire", "storm / hail"}
        ]
        suppressed = not is_insurance or not is_property

        classification = ClassificationOutput(
            is_insurance_relevant=is_insurance,
            is_property_relevant=is_property,
            event_type=event_type,
            topics=[] if suppressed else topics,
            affected_products=self._affected_products(topics),
            affected_perils=perils,
            severity=severity,
            summary_for_underwriter=self._summary(
                event=event,
                topics=[] if suppressed else topics,
                event_type=event_type,
                severity=severity,
                suppressed=suppressed,
            ),
            recommended_action=self._recommended_action(event_type, suppressed),
            confidence=0.78 if not suppressed else 0.62,
            evidence=[
                evidence
                for evidence in [
                    self._evidence(event.body_text, topics[0]) if topics else None
                ]
                if evidence is not None
            ],
            reasons_for_suppression=suppression_reasons if suppressed else [],
        )
        event.classification_json = classification
        event.event_type = classification.event_type
        event.line_of_business = "property" if classification.is_property_relevant else None
        event.product = classification.affected_products[0] if classification.affected_products else None
        event.topics_json = classification.topics
        event.perils_json = classification.affected_perils
        event.severity = classification.severity
        event.confidence = classification.confidence
        event.underwriter_summary = classification.summary_for_underwriter
        event.recommended_action = classification.recommended_action
        event.evidence_json = classification.evidence
        event.status = "suppressed" if suppressed else "classified"
        self._audit(
            entity_type="external_event",
            entity_id=event.event_id,
            action="classified",
            raw_url=event.original_url,
            raw_item_id=event.raw_item_id,
            model_name="deterministic-keyword-classifier",
            model_version="mvp-1",
            prompt_version=None,
            output_json=classification.model_dump(mode="json"),
        )
        return classification

    def correlate_event(self, event: ExternalEvent) -> int:
        if event.status != "classified" or event.line_of_business != "property":
            return 0

        created_alerts = 0
        for document in self.document_assets.values():
            overlap = sorted(set(event.topics_json) & set(document.topics_json))
            if document.country == "RO" and document.line_of_business == "property" and overlap:
                correlation = self._correlation(
                    event=event,
                    target_type="document_asset",
                    target_id=document.document_id,
                    rule_ids=["document_topic_overlap"],
                    match_score=min(1.0, 0.5 + 0.1 * len(overlap)),
                    rationale=(
                        "Review recommended because the ASF event topics overlap "
                        f"with {document.name}: {', '.join(overlap)}."
                    ),
                )
                self.correlations[correlation.correlation_id] = correlation

        today = date.today()
        horizon = today + timedelta(days=120)
        for item in self.work_items.values():
            if (
                item.country == "RO"
                and item.line_of_business == "property"
                and item.status == "open"
                and today <= item.renewal_date <= horizon
            ):
                correlation = self._correlation(
                    event=event,
                    target_type="underwriting_work_item",
                    target_id=item.work_item_id,
                    rule_ids=["ro_property_renewal_120_days"],
                    match_score=0.7,
                    rationale=(
                        "Potentially affected renewal because the event is relevant "
                        "to Romanian property and the renewal is open within 120 days."
                    ),
                )
                self.correlations[correlation.correlation_id] = correlation
                alert = Alert(
                    event_id=event.event_id,
                    work_item_id=item.work_item_id,
                    assigned_underwriter=item.assigned_underwriter,
                    title=event.title,
                    summary=event.underwriter_summary,
                    why_it_matters=correlation.rationale,
                    recommended_action=event.recommended_action,
                    severity=event.severity,
                    confidence=event.confidence,
                    created_at=datetime.now(UTC),
                )
                self.alerts[alert.alert_id] = alert
                created_alerts += 1

        self._audit(
            entity_type="external_event",
            entity_id=event.event_id,
            action="correlated",
            raw_url=event.original_url,
            raw_item_id=event.raw_item_id,
            rules_triggered_json=["document_topic_overlap", "ro_property_renewal_120_days"],
        )
        return created_alerts

    def _build_feed_card(self, event: ExternalEvent) -> IntelligenceFeedCard:
        event_alerts = [
            alert for alert in self.alerts.values() if alert.event_id == event.event_id
        ]
        document_names = []
        for correlation in self.correlations.values():
            if (
                correlation.event_id == event.event_id
                and correlation.target_type == "document_asset"
            ):
                document = self.document_assets.get(correlation.target_id)
                if document is not None:
                    document_names.append(document.name)
        return IntelligenceFeedCard(
            event_id=event.event_id,
            title=event.title,
            asf_source_link=event.original_url,
            published_at=event.published_at,
            event_type=event.event_type,
            topics=event.topics_json,
            severity=event.severity,
            summary=event.underwriter_summary,
            why_it_matters="Potentially affects open Romanian property renewals or document assets.",
            affected_renewals_count=len(event_alerts),
            affected_documents=sorted(document_names),
            recommended_action=event.recommended_action,
            confidence=event.confidence,
        )

    def _correlation(
        self,
        event: ExternalEvent,
        target_type: CorrelationTargetType,
        target_id: UUID,
        rule_ids: list[str],
        match_score: float,
        rationale: str,
    ) -> Correlation:
        return Correlation(
            event_id=event.event_id,
            target_type=target_type,
            target_id=target_id,
            rule_ids_json=rule_ids,
            match_score=match_score,
            rationale=rationale,
            evidence_json=event.evidence_json,
            created_at=datetime.now(UTC),
        )

    def _audit(
        self,
        entity_type: str,
        entity_id: UUID | str,
        action: str,
        raw_url: str | None = None,
        raw_item_id: UUID | None = None,
        model_name: str | None = None,
        model_version: str | None = None,
        prompt_version: str | None = None,
        input_ref_json: dict | None = None,
        output_json: dict | None = None,
        rules_triggered_json: list[str] | None = None,
        user_id: str | None = None,
    ) -> None:
        record = AuditRecord(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            raw_url=raw_url,
            raw_item_id=raw_item_id,
            model_name=model_name,
            model_version=model_version,
            prompt_version=prompt_version,
            input_ref_json=input_ref_json or {},
            output_json=output_json or {},
            rules_triggered_json=rules_triggered_json or [],
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        self.audit_records[record.audit_id] = record

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

    def _summary(
        self,
        event: ExternalEvent,
        topics: list[str],
        event_type: str,
        severity: str,
        suppressed: bool,
    ) -> str:
        if suppressed:
            return "ASF item was retained for audit but suppressed for the Romanian property MVP."
        topic_text = self._topic_text(topics)
        event_text = self._event_type_text(event_type)
        return (
            f"{event.title} was classified as a {severity} severity "
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
        words = body_text.strip().split()
        snippet = " ".join(words[:40])
        return EvidenceSnippet(
            snippet=snippet,
            reason=f"Source text matched Romanian property topic: {topic}.",
        )

    def _demo_raw_item(self, source_id: str) -> RawSourceItem:
        now = datetime.now(UTC)
        text = (
            "ASF a publicat o comunicare privind asigurarile de locuinte, "
            "PAD, riscul de cutremur si recomandari pentru protectia "
            "asiguratilor in cazul politelelor de proprietate."
        )
        return RawSourceItem(
            source_id=source_id,
            original_url="https://asfromania.ro/demo/romanian-property-pad-cutremur",
            canonical_url="https://asfromania.ro/demo/romanian-property-pad-cutremur",
            published_at=now,
            fetched_at=now,
            title="ASF comunicare privind asigurarile de locuinte si PAD",
            extracted_text=text,
            content_hash=sha256(text.encode("utf-8")).hexdigest(),
            created_at=now,
        )


def build_demo_intelligence_service() -> IntelligenceService:
    now = datetime.now(UTC)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    documents = [
        DocumentAsset(
            name="Romania Residential Property Wording Template",
            type="wording_template",
            country="RO",
            line_of_business="property",
            product="residential_property",
            topics_json=[
                "residential property insurance",
                "PAD / compulsory home insurance",
                "earthquake",
                "coverage wording",
            ],
            owner="underwriting-ops",
            created_at=now,
            updated_at=now,
        ),
        DocumentAsset(
            name="Romania Nat Cat Clause Library",
            type="clause_library",
            country="RO",
            line_of_business="property",
            product="property",
            topics_json=["natural catastrophe", "earthquake", "flood", "storm / hail"],
            owner="wording-team",
            created_at=now,
            updated_at=now,
        ),
    ]
    work_items = [
        UnderwritingWorkItem(
            type="renewal",
            account_name="Dacia Offices SRL",
            country="RO",
            county="Bucuresti",
            city="Bucuresti",
            line_of_business="property",
            product="commercial_property",
            insured_value=2_500_000,
            perils_json=["earthquake", "fire", "flood"],
            renewal_date=date.today() + timedelta(days=45),
            assigned_underwriter="ana.ionescu",
            status="open",
            created_at=now,
            updated_at=now,
        )
    ]
    service = IntelligenceService(
        sources=[source],
        document_assets=documents,
        work_items=work_items,
    )
    service.run_ingestion("asf_ro")
    return service
