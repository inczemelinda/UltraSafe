from __future__ import annotations

import json
import os
from typing import Any
import unicodedata

import httpx
from dotenv import load_dotenv

from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewCandidate,
    NormalizedLegalDocument,
)
from underwright.domain.models import Template


load_dotenv()


class OpenAICompatibleTemplateChangeSuggestionGenerator:
    """AI adapter that drafts editable template change hunks."""

    model_name = "openai-compatible-template-change-suggestion-generator"
    prompt_version = "template-change-suggestion-v1"

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
            or os.getenv("TEMPLATE_CHANGE_SUGGESTION_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4o-mini"
        )
        self.api_base = (
            api_base or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1"
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client

        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for AI template change suggestions."
            )

    def generate(
        self,
        *,
        legal_document: NormalizedLegalDocument,
        template: Template,
        candidate: LegalDocumentTemplateReviewCandidate,
        relevant_template_content: str,
    ) -> dict[str, Any]:
        response = self._post_chat_completion(
            self._build_messages(
                legal_document=legal_document,
                template=template,
                candidate=candidate,
                relevant_template_content=relevant_template_content,
            )
        )
        return self._parse_json(self._extract_content(response))

    def _build_messages(
        self,
        *,
        legal_document: NormalizedLegalDocument,
        template: Template,
        candidate: LegalDocumentTemplateReviewCandidate,
        relevant_template_content: str,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You draft editable insurance template change suggestions as "
                    "strict JSON only. Do not claim the changes are legally final. "
                    "Do not modify templates. Suggest hunks that a human reviewer "
                    "can edit before accepting."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "Draft template change suggestion hunks.",
                        "output_schema": {
                            "overall_summary": "short summary",
                            "hunks": [
                                {
                                    "section_id": "optional stable section id",
                                    "section_label": "optional section label",
                                    "change_type": (
                                        "replace | insert_before | insert_after | "
                                        "delete | manual_review"
                                    ),
                                    "old_text": (
                                        "exact template text for replace/delete; "
                                        "anchor text for insert operations"
                                    ),
                                    "new_text": "draft replacement or insertion text",
                                    "rationale": "why this draft is suggested",
                                    "source_reference": (
                                        "source sentence or legal reference grounding it"
                                    ),
                                    "confidence": 0.0,
                                }
                            ],
                        },
                        "rules": [
                            "Return strict JSON only.",
                            "For replace/delete, old_text must be copied exactly from template_content.",
                            "Every hunk must include rationale and source_reference.",
                            "Use clause-level old_text and new_text so reviewers see context.",
                            "Prefer minimal hunks over rewriting large sections.",
                            "Draft text only; the user will decide whether to accept.",
                        ],
                        "legal_document": {
                            "title": legal_document.title,
                            "full_text": legal_document.full_text[:12_000],
                            "legal_references": legal_document.legal_references,
                            "amends": legal_document.amends,
                            "repeals": legal_document.repeals,
                        },
                        "candidate": {
                            "candidate_id": str(candidate.candidate_id),
                            "match_type": candidate.match_type,
                            "matched_reference": candidate.matched_reference,
                            "review_reason": candidate.review_reason,
                            "confidence": candidate.confidence,
                        },
                        "template": {
                            "template_id": template.id,
                            "title": template.name,
                            "template_code": template.template_code,
                            "version": template.version,
                            "legal_references": template.legal_references_json,
                            "template_content": relevant_template_content,
                        },
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
                "AI template change suggestion response did not contain content."
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI template change suggestion response content was empty.")
        return content

    def _parse_json(self, content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "AI template change suggestion response was not valid JSON."
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError("AI template change suggestion JSON must be an object.")
        return parsed


class DeterministicDemoTemplateChangeSuggestionGenerator:
    """Local fallback for the synthetic PAD demo when AI is not configured."""

    model_name = "deterministic-demo-template-change-suggestion-generator"
    model_version = "demo-v1"
    prompt_version = None

    def generate(
        self,
        *,
        legal_document: NormalizedLegalDocument,
        template: Template,
        candidate: LegalDocumentTemplateReviewCandidate,
        relevant_template_content: str,
    ) -> dict[str, Any]:
        del template
        scenario = _demo_scenario(
            legal_document=legal_document,
            candidate=candidate,
            relevant_template_content=relevant_template_content,
        )

        return {
            "overall_summary": scenario["overall_summary"],
            "hunks": [
                {
                    "section_id": None,
                    "section_label": scenario["section_label"],
                    "change_type": "replace",
                    "old_text": scenario["old_text"],
                    "new_text": scenario["new_text"],
                    "rationale": scenario["rationale"],
                    "source_reference": legal_document.title,
                    "confidence": 0.86,
                }
            ],
        }


def _demo_scenario(
    *,
    legal_document: NormalizedLegalDocument,
    candidate: LegalDocumentTemplateReviewCandidate,
    relevant_template_content: str,
) -> dict[str, str]:
    haystack = _ascii_fold(
        " ".join(
            [
                legal_document.title,
                legal_document.summary or "",
                legal_document.full_text,
                candidate.matched_reference or "",
                candidate.review_reason,
            ]
        )
    )
    scenarios = [
        {
            "token_sets": [["10 zile", "5 zile"], ["10 days", "5 days"]],
            "marker": "10 zile calendaristice",
            "section_label": "Claim notification deadline",
            "overall_summary": "Draft suggestion updates the claim notification deadline for human review.",
            "rationale": "The legal document states that the notification deadline changes from 10 days to 5 days.",
            "replace": lambda old_text: old_text.replace(
                "10 zile calendaristice",
                "5 zile calendaristice",
            ),
        },
        {
            "tokens": ["claim_notification_timeline"],
            "marker": "Asiguratul trebuie sa notifice dauna",
            "section_label": "Claim notification timeline",
            "overall_summary": "Draft suggestion clarifies how claim notification timelines are expressed.",
            "rationale": "The legal document requires claim notification timelines to state that deadlines are calendar days.",
            "append": " Termenul este exprimat in zile calendaristice si se calculeaza de la data producerii evenimentului.",
        },
        {
            "tokens": ["fire_exclusion"],
            "marker": "Incendiul este arderea cu flacara deschisa",
            "section_label": "Fire exclusion wording",
            "overall_summary": "Draft suggestion separates accidental fire coverage from intentional fire exclusions.",
            "rationale": "The legal document requires clearer distinction between accidental fire damage and intentionally caused fire damage.",
            "append": " Daunele provocate intentionat de Asigurat sunt tratate separat ca excluderi si nu limiteaza acoperirea incendiilor accidentale.",
        },
        {
            "tokens": ["policy_cancellation_notice"],
            "marker": "Contractul poate inceta inainte de termen",
            "section_label": "Cancellation notice wording",
            "overall_summary": "Draft suggestion expands early cancellation notice wording.",
            "rationale": "The legal document requires cancellation notices to include the end date, reason, and contact channel for disputes.",
            "append": " Notificarea de incetare trebuie sa indice data incetarii, motivul si canalul de contact pentru contestatii.",
        },
        {
            "tokens": ["document_retention"],
            "marker": "Datele pot fi comunicate prestatorilor",
            "section_label": "Document retention wording",
            "overall_summary": "Draft suggestion adds retention-period wording to the data protection clause.",
            "rationale": "The legal document highlights retention notices for policy and claim documents.",
            "append": " Informarea privind prelucrarea datelor va indica perioada de pastrare a documentelor de polita si de dauna.",
        },
        {
            "tokens": ["storm_deductible"],
            "marker": "Furtuna si grindina sunt fenomene atmosferice",
            "section_label": "Storm deductible disclosure",
            "overall_summary": "Draft suggestion places storm deductible disclosure beside the covered peril.",
            "rationale": "The legal document requires storm and hail deductibles to be visible next to covered peril descriptions.",
            "append": " Fransiza aplicabila pentru furtuna si grindina trebuie indicata langa descrierea riscului acoperit.",
        },
        {
            "tokens": ["renewal_notice"],
            "marker": "Reinnoirea contractului nu este automata",
            "section_label": "Renewal notice wording",
            "overall_summary": "Draft suggestion clarifies renewal notices and premium-change explanations.",
            "rationale": "The legal document requires renewal notices to explain premium changes and customer options in plain language.",
            "append": " Comunicarea de reinnoire trebuie sa explice orice modificare de prima si optiunile disponibile clientului.",
        },
        {
            "tokens": ["policyholder_notice"],
            "marker": "Reclamatiile privind administrarea contractului",
            "section_label": "Policyholder notice wording",
            "overall_summary": "Draft suggestion adds customer rights and escalation wording.",
            "rationale": "The legal document requires policyholder notices to include a short rights summary and escalation channel.",
            "append": " Informarea va include un rezumat al drepturilor clientului si canalul de escaladare disponibil.",
        },
        {
            "tokens": ["claims_escalation"],
            "marker": "In cazul respingerii totale sau partiale",
            "section_label": "Claims escalation wording",
            "overall_summary": "Draft suggestion adds response-timeline and dispute-channel wording to claims decisions.",
            "rationale": "The legal document requires claims communications to mention the insurer response timeline and dispute channel.",
            "append": " Comunicarea va mentiona termenul estimat de raspuns si canalul disponibil pentru contestarea deciziei.",
        },
    ]

    for scenario in scenarios:
        token_sets = scenario.get("token_sets")
        if token_sets is not None:
            matches = any(
                all(token in haystack for token in token_set)
                for token_set in token_sets
            )
        else:
            matches = all(token in haystack for token in scenario["tokens"])
        if not matches:
            continue
        old_text = _sentence_with_marker(relevant_template_content, scenario["marker"])
        if not old_text:
            break
        if "replace" in scenario:
            new_text = scenario["replace"](old_text)
        else:
            new_text = f"{old_text} {scenario['append'].strip()}"
        return {
            "section_label": scenario["section_label"],
            "old_text": old_text,
            "new_text": new_text,
            "overall_summary": scenario["overall_summary"],
            "rationale": scenario["rationale"],
        }

    return {
        "section_label": "Template wording",
        "old_text": "",
        "new_text": "",
        "overall_summary": "Draft suggestion requires manual template review.",
        "rationale": "The demo generator could not map this legal update to a deterministic wording scenario.",
    }


def _claim_notification_clause(content: str, marker: str) -> str:
    return _sentence_with_marker(content, marker) or marker


def _sentence_with_marker(content: str, marker: str) -> str | None:
    folded_marker = _ascii_fold(marker)
    for sentence in content.split("."):
        candidate = sentence.strip()
        if folded_marker in _ascii_fold(candidate):
            return f"{candidate}."
    return None


def _ascii_fold(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
