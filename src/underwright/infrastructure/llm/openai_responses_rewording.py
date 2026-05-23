from __future__ import annotations

from typing import Any

import httpx

from underwright.application.services.claim_decision_rewording_service import (
    ClaimDecisionRewordingProviderError,
)


CLAIM_DECISION_REWORDING_SYSTEM_PROMPT = (
    "You rewrite insurance claim decision justifications for clarity and "
    "professionalism. Do not add facts. Do not remove material reasoning. "
    "Do not change the decision outcome. Return only the rewritten "
    "customer-facing decision justification. Do not critique, label, "
    "apologize for, or comment on the original wording. If the input is "
    "inappropriate, replace it with a neutral, professional explanation."
)


class OpenAIResponsesClaimDecisionRewordingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        api_base: str = "https://api.openai.com/v1",
        timeout_seconds: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client

    def reword_decision_justification(
        self,
        *,
        justification: str,
        decision: str | None = None,
    ) -> str:
        user_input = (
            f"Decision: {decision or 'not specified'}\n"
            "Original justification:\n"
            f"{justification}"
        )
        payload = {
            "model": self.model,
            "instructions": CLAIM_DECISION_REWORDING_SYSTEM_PROMPT,
            "input": user_input,
            "max_output_tokens": 220,
        }

        try:
            if self.client is not None:
                response = self.client.post(
                    f"{self.api_base}/responses",
                    headers=_headers(self.api_key),
                    json=payload,
                )
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        f"{self.api_base}/responses",
                        headers=_headers(self.api_key),
                        json=payload,
                    )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ClaimDecisionRewordingProviderError(
                "AI provider request timed out."
            ) from exc
        except httpx.HTTPError as exc:
            raise ClaimDecisionRewordingProviderError(
                "AI provider request failed."
            ) from exc

        output_text = _extract_output_text(response.json())
        if not output_text:
            raise ClaimDecisionRewordingProviderError(
                "AI provider returned an empty suggestion."
            )
        return output_text


def _extract_output_text(data: dict[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "\n".join(part.strip() for part in parts if part.strip()).strip()


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


__all__ = [
    "CLAIM_DECISION_REWORDING_SYSTEM_PROMPT",
    "OpenAIResponsesClaimDecisionRewordingProvider",
]
