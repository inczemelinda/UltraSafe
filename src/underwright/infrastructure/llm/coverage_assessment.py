from __future__ import annotations

import json
import os
from typing import Any

import httpx

from underwright.domain.claim_analysis import (
    CoverageAssessmentResult,
    PolicyWordingSection,
)


PROMPT_VERSION = "claim-coverage-fit-v1"


class OpenAICompatibleCoverageAssessmentLLMService:
    """OpenAI-compatible adapter for claim coverage-fit assessment."""

    model_name = "openai-compatible-coverage-assessment"
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
            or os.getenv("CLAIM_COVERAGE_AI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4o-mini"
        )
        self.api_base = (
            api_base or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1"
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for coverage assessment.")

    def assess_coverage(
        self,
        *,
        claim_type: str,
        incident_description: str,
        incident_date: str | None,
        wording_sections: list[PolicyWordingSection],
        policy_profile: dict[str, Any],
    ) -> CoverageAssessmentResult:
        response = self._post_chat_completion(
            self._build_messages(
                claim_type=claim_type,
                incident_description=incident_description,
                incident_date=incident_date,
                wording_sections=wording_sections,
                policy_profile=policy_profile,
            )
        )
        content = self._extract_content(response)
        data = self._parse_json(content)
        return CoverageAssessmentResult.model_validate(data)

    def _build_messages(
        self,
        *,
        claim_type: str,
        incident_description: str,
        incident_date: str | None,
        wording_sections: list[PolicyWordingSection],
        policy_profile: dict[str, Any],
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You perform a cautious insurance coverage-fit pre-check. "
                    "Return only valid JSON matching the requested schema. "
                    "Do not make final claim decisions. Do not use accepted, "
                    "rejected, approve, deny, paid, or dismissed language. "
                    "Use only the provided claim facts and wording sections. "
                    "Cite wording section ids in matched_wording_sections. "
                    "Separate possible exclusions from coverage matches. "
                    "Distinguish insufficient_information from not_covered: "
                    "use insufficient_information when facts are vague or missing. "
                    "Return high confidence only when wording support is explicit."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "Assess whether the incident appears to fit the retrieved policy wording sections.",
                        "output_schema": {
                            "coverage_status": [
                                "potentially_covered",
                                "not_covered",
                                "excluded",
                                "unclear",
                                "insufficient_information",
                            ],
                            "matched_wording_sections": [
                                "wording section ids used, never final claim decisions"
                            ],
                            "possible_exclusions": [
                                "section id plus short exclusion reason, if any"
                            ],
                            "rationale": "short cautious explanation for an underwriter",
                            "confidence": ["high", "medium", "low"],
                        },
                        "rules": [
                            "Return JSON only.",
                            "Do not say the claim is accepted or rejected.",
                            "Do not recommend payment or dismissal.",
                            "Use potentially_covered only when provided wording may fit the incident.",
                            "Use excluded only when the wording sections explicitly point to an exclusion.",
                            "Use not_covered only when facts are clear and no provided wording can fit.",
                            "Use unclear when facts are plausible but wording support is ambiguous.",
                            "Use insufficient_information when the description is too vague or missing key facts.",
                            "Cite section_id values from wording_sections in matched_wording_sections.",
                        ],
                        "input": {
                            "claim_type": claim_type,
                            "incident_description": incident_description,
                            "incident_date": incident_date,
                            "policy_profile": policy_profile,
                            "wording_sections": [
                                section.model_dump(mode="json")
                                for section in wording_sections
                            ],
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
            raise ValueError("Coverage assessment response did not contain content.") from exc

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Coverage assessment response content was empty.")
        return content

    def _parse_json(self, content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Coverage assessment response was not valid JSON.") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Coverage assessment response JSON must be an object.")
        return parsed


__all__ = ["OpenAICompatibleCoverageAssessmentLLMService"]
