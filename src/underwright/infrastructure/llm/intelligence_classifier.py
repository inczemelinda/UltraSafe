from __future__ import annotations

import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv

from underwright.domain.intelligence import (
    ClassificationInput,
    ClassificationOutput,
    EvidenceSnippet,
    ExternalEvent,
    SummaryOutput,
    TemplateReviewCandidate,
)
from underwright.domain.models import Template


load_dotenv()


PROMPT_VERSION = "intelligence-classifier-v1"
SUMMARY_PROMPT_VERSION = "intelligence-summary-writer-v1"

ALLOWED_EVENT_TYPES = [
    "regulatory_update",
    "market_report",
    "sanction_or_enforcement",
    "consumer_protection",
    "claims_update",
    "solvency_or_market_stability",
    "product_or_coverage_update",
    "public_warning",
    "consultation_or_draft_rule",
    "not_relevant",
]

ALLOWED_TOPICS = [
    "PAD / compulsory home insurance",
    "voluntary home insurance",
    "commercial property insurance",
    "residential property insurance",
    "claims",
    "claims handling",
    "natural catastrophe",
    "earthquake",
    "flood",
    "landslide",
    "fire",
    "storm / hail",
    "policyholder protection",
    "distribution / conduct",
    "insurer sanctions",
    "market stability",
    "solvency",
    "coverage wording",
    "deductibles / limits",
    "pricing / premium affordability",
]


class OpenAICompatibleEventClassifier:
    """AI-backed classifier adapter for the intelligence ingestion pipeline."""

    model_name = "openai-compatible-event-classifier"
    prompt_version = PROMPT_VERSION

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        api_base: str | None = None,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_version = (
            model
            or os.getenv("INTELLIGENCE_AI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4o-mini"
        )
        self.api_base = (
            api_base or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1"
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for AI classification.")

    def classify(
        self,
        classification_input: ClassificationInput,
    ) -> ClassificationOutput:
        response = self._post_chat_completion(
            self._build_messages(classification_input)
        )
        content = self._extract_content(response)
        data = self._parse_json(content)
        classification = ClassificationOutput.model_validate(data)
        return self._apply_safety_guardrails(classification_input, classification)

    def _build_messages(
        self,
        classification_input: ClassificationInput,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You classify external insurance intelligence for Romanian "
                    "property underwriters. Return only valid JSON matching the "
                    "requested schema. Stay source-grounded. Use cautious language: "
                    "say 'review recommended' or 'potentially affected', never say "
                    "a contract must change. Suppress off-source, non-insurance, "
                    "and non-property items."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "Classify this source item for the Romanian property insurance MVP.",
                        "output_schema": {
                            "is_insurance_relevant": "boolean",
                            "is_property_relevant": "boolean",
                            "event_type": ALLOWED_EVENT_TYPES,
                            "topics": ALLOWED_TOPICS,
                            "affected_products": [
                                "property",
                                "residential_property",
                                "commercial_property",
                            ],
                            "affected_perils": [
                                "earthquake",
                                "flood",
                                "landslide",
                                "fire",
                                "storm / hail",
                            ],
                            "severity": ["low", "medium", "high"],
                            "summary_for_underwriter": "one or two short paragraphs",
                            "recommended_action": "cautious underwriter review action",
                            "confidence": "number from 0 to 1",
                            "evidence": [
                                {
                                    "snippet": "short source-grounded quote or paraphrase from the item",
                                    "reason": "why this supports the classification",
                                }
                            ],
                            "reasons_for_suppression": [
                                "required when not relevant or suppressed"
                            ],
                        },
                        "rules": [
                            "If is_allowed_source_url is false, return event_type not_relevant.",
                            "Use only the allowed event_type values.",
                            "Use only allowed Romanian property topics when possible.",
                            "If not property relevant, topics and affected_perils must be empty.",
                            "Do not invent legal changes, affected documents, or affected work items.",
                            "Evidence must come from the title or body text.",
                        ],
                        "input": classification_input.model_dump(mode="json"),
                    },
                    ensure_ascii=True,
                ),
            },
        ]

    def _post_chat_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        close_client = False
        client = self.client
        if client is None:
            client = httpx.Client(timeout=self.timeout_seconds)
            close_client = True

        try:
            response = client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_version,
                    "messages": messages,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            return response.json()
        finally:
            if close_client:
                client.close()

    def _extract_content(self, response: dict[str, Any]) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("AI classification response did not contain content.") from exc

        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI classification response content was empty.")
        return content

    def _parse_json(self, content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("AI classification response was not valid JSON.") from exc

        if not isinstance(parsed, dict):
            raise ValueError("AI classification response JSON must be an object.")
        return parsed

    def _apply_safety_guardrails(
        self,
        classification_input: ClassificationInput,
        classification: ClassificationOutput,
    ) -> ClassificationOutput:
        if not classification_input.is_allowed_source_url:
            return classification.model_copy(
                update={
                    "is_insurance_relevant": False,
                    "is_property_relevant": False,
                    "event_type": "not_relevant",
                    "topics": [],
                    "affected_products": [],
                    "affected_perils": [],
                    "recommended_action": (
                        "No underwriter action recommended for the Romanian property MVP."
                    ),
                    "confidence": min(classification.confidence, 0.5),
                    "evidence": [],
                    "reasons_for_suppression": sorted(
                        set(
                            classification.reasons_for_suppression
                            + ["source URL is outside configured source hosts"]
                        )
                    ),
                }
            )

        if (
            not classification.is_insurance_relevant
            or not classification.is_property_relevant
        ):
            return classification.model_copy(
                update={
                    "event_type": "not_relevant",
                    "topics": [],
                    "affected_products": [],
                    "affected_perils": [],
                }
            )

        return classification.model_copy(
            update={
                "topics": [
                    topic for topic in classification.topics if topic in ALLOWED_TOPICS
                ],
                "affected_perils": [
                    peril
                    for peril in classification.affected_perils
                    if peril
                    in {"earthquake", "flood", "landslide", "fire", "storm / hail"}
                ],
            }
        )


class OpenAICompatibleEventSummaryWriter:
    """AI adapter that rewrites deterministic event summaries for underwriters."""

    model_name = "openai-compatible-event-summary-writer"
    prompt_version = SUMMARY_PROMPT_VERSION

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        api_base: str | None = None,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_version = (
            model
            or os.getenv("INTELLIGENCE_SUMMARY_MODEL")
            or os.getenv("INTELLIGENCE_AI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4o-mini"
        )
        self.api_base = (
            api_base or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1"
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for AI summaries.")

    def summarize(
        self,
        classification_input: ClassificationInput,
        classification: ClassificationOutput,
    ) -> ClassificationOutput:
        if (
            not classification.is_insurance_relevant
            or not classification.is_property_relevant
        ):
            return classification

        response = self._post_chat_completion(
            self._build_messages(classification_input, classification)
        )
        content = self._extract_content(response)
        data = self._parse_json(content)
        summary = SummaryOutput.model_validate(data)
        return self._apply_summary(classification, summary)

    def _build_messages(
        self,
        classification_input: ClassificationInput,
        classification: ClassificationOutput,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You write employee-facing underwriting intelligence summaries "
                    "for Romanian property insurance. The relevance, event type, "
                    "severity, topics, and confidence were already decided by a "
                    "separate classifier. Do not change those decisions. Return only "
                    "valid JSON. Stay source-grounded, use cautious language, and "
                    "never say that a policy or contract must change."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": (
                            "Rewrite the deterministic title and summary into "
                            "three concise underwriter-facing fields."
                        ),
                        "output_schema": {
                            "display_title": (
                                "one concise news headline saying what happened "
                                "or what warning/update was issued"
                            ),
                            "summary_for_underwriter": (
                                "one concise sentence explaining what happened and "
                                "why it may matter for Romanian property underwriting"
                            ),
                            "recommended_action": (
                                "one cautious action sentence beginning with or "
                                "including 'review recommended' when appropriate"
                            ),
                        },
                        "rules": [
                            "Use only the source title, source text, and given classification.",
                            "Write display_title in a Ground News-style headline: concrete subject, active verb, factual outcome.",
                            "Do not use source navigation labels or section names as the headline.",
                            "Bad display_title examples: 'INCDFP - Conducere', 'INCDFP - Integritate', 'Meteo Romania | Avertizari Nowcasting'.",
                            "Good display_title examples: 'Storm and hail warning issued for Romanian property exposure review', 'PAD wording update may affect residential property review'.",
                            "If the source text does not describe a concrete event, make display_title state the concrete page content instead of inventing a warning.",
                            "Do not invent legal changes, deadlines, impacted accounts, or affected templates.",
                            "Do not mention internal terms such as classified, deterministic, pipeline, or MVP.",
                            "Do not output markdown bullets.",
                            "Keep display_title under 120 characters.",
                            "Keep summary_for_underwriter and recommended_action under 220 characters each.",
                        ],
                        "source_item": {
                            "source_id": classification_input.source_id,
                            "source_type": classification_input.source_type,
                            "trust_tier": classification_input.trust_tier,
                            "title": classification_input.title,
                            "original_url": classification_input.original_url,
                            "published_at": (
                                classification_input.published_at.isoformat()
                                if classification_input.published_at
                                else None
                            ),
                            "body_text": classification_input.body_text[:8_000],
                        },
                        "classification": classification.model_dump(mode="json"),
                    },
                    ensure_ascii=True,
                ),
            },
        ]

    def _post_chat_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        close_client = False
        client = self.client
        if client is None:
            client = httpx.Client(timeout=self.timeout_seconds)
            close_client = True

        try:
            response = client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_version,
                    "messages": messages,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            return response.json()
        finally:
            if close_client:
                client.close()

    def _extract_content(self, response: dict[str, Any]) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("AI summary response did not contain content.") from exc

        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI summary response content was empty.")
        return content

    def _parse_json(self, content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("AI summary response was not valid JSON.") from exc

        if not isinstance(parsed, dict):
            raise ValueError("AI summary response JSON must be an object.")
        return parsed

    def _apply_summary(
        self,
        classification: ClassificationOutput,
        summary: SummaryOutput,
    ) -> ClassificationOutput:
        display_title = summary.display_title.strip()
        summary_text = summary.summary_for_underwriter.strip()
        action_text = summary.recommended_action.strip()
        if not display_title or not summary_text or not action_text:
            raise ValueError("AI summary fields must not be blank.")

        return classification.model_copy(
            update={
                "display_title": self._truncate_title(display_title),
                "summary_for_underwriter": summary_text,
                "recommended_action": action_text,
            }
        )

    def _truncate_title(self, title: str) -> str:
        if len(title) <= 120:
            return title
        return f"{title[:117].rstrip()}..."


class OpenAICompatibleTemplateCandidateExplainer:
    """AI adapter that explains deterministic template review candidates."""

    model_name = "openai-compatible-template-candidate-explainer"
    prompt_version = "template-candidate-explainer-v1"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        api_base: str | None = None,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_version = (
            model
            or os.getenv("INTELLIGENCE_AI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4o-mini"
        )
        self.api_base = (
            api_base or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1"
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for AI candidate explanation.")

    def explain(
        self,
        event: ExternalEvent,
        template: Template,
        candidate: TemplateReviewCandidate,
    ) -> TemplateReviewCandidate:
        response = self._post_chat_completion(
            self._build_messages(event, template, candidate)
        )
        content = self._extract_content(response)
        data = self._parse_json(content)

        rationale = str(data.get("rationale", "")).strip()
        if not rationale:
            raise ValueError("AI candidate explanation did not include rationale.")

        evidence = self._parse_evidence(data.get("evidence"))
        return candidate.model_copy(
            update={
                "rationale": rationale,
                "evidence_json": evidence or candidate.evidence_json,
            }
        )

    def _build_messages(
        self,
        event: ExternalEvent,
        template: Template,
        candidate: TemplateReviewCandidate,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You explain deterministic template review candidates for "
                    "Romanian property insurance underwriters. The candidate already "
                    "exists because rules matched it. Do not add affected templates, "
                    "do not claim that a contract must change, and do not invent legal "
                    "changes. Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": (
                            "Write a cautious rationale for why this template is "
                            "potentially affected by the event."
                        ),
                        "output_schema": {
                            "rationale": (
                                "one short paragraph using 'review recommended' or "
                                "'potentially affected'"
                            ),
                            "evidence": [
                                {
                                    "snippet": "short source-grounded evidence",
                                    "reason": "why this supports review",
                                }
                            ],
                        },
                        "rules": [
                            "Keep the existing candidate target unchanged.",
                            "Do not say the template must change.",
                            "Use only event, template, and candidate data.",
                            "Prefer legal reference overlap over broad topic overlap.",
                        ],
                        "event": {
                            "event_id": str(event.event_id),
                            "title": event.title,
                            "source_url": event.original_url,
                            "event_type": event.event_type,
                            "topics": event.topics_json,
                            "severity": event.severity,
                            "summary": event.underwriter_summary,
                            "recommended_action": event.recommended_action,
                            "body_text": event.body_text[:8_000],
                        },
                        "template": {
                            "template_id": template.id,
                            "template_code": template.template_code,
                            "name": template.name,
                            "version": template.version,
                            "document_type": template.document_type,
                            "content": template.content[:8_000],
                        },
                        "candidate": candidate.model_dump(mode="json"),
                    },
                    ensure_ascii=True,
                ),
            },
        ]

    def _post_chat_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        close_client = False
        client = self.client
        if client is None:
            client = httpx.Client(timeout=self.timeout_seconds)
            close_client = True

        try:
            response = client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_version,
                    "messages": messages,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            return response.json()
        finally:
            if close_client:
                client.close()

    def _extract_content(self, response: dict[str, Any]) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(
                "AI candidate explanation response did not contain content."
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI candidate explanation response content was empty.")
        return content

    def _parse_json(self, content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "AI candidate explanation response was not valid JSON."
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError("AI candidate explanation JSON must be an object.")
        return parsed

    def _parse_evidence(self, raw_evidence: Any) -> list[EvidenceSnippet]:
        if not isinstance(raw_evidence, list):
            return []

        evidence = []
        for item in raw_evidence:
            if not isinstance(item, dict):
                continue
            evidence.append(EvidenceSnippet.model_validate(item))
        return evidence
