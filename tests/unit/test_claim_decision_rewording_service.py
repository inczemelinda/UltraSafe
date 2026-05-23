from __future__ import annotations

import httpx
import pytest

from underwright.application.services.claim_decision_rewording_service import (
    ClaimDecisionRewordingNotConfiguredError,
    ClaimDecisionRewordingProviderError,
    ClaimDecisionRewordingService,
    fallback_decision_justification,
    is_meta_comment_suggestion,
)
from underwright.infrastructure.llm.openai_responses_rewording import (
    CLAIM_DECISION_REWORDING_SYSTEM_PROMPT,
    OpenAIResponsesClaimDecisionRewordingProvider,
)


class FakeProvider:
    def __init__(self, suggestion: str = "Clear professional wording.") -> None:
        self.calls: list[dict] = []
        self.suggestion = suggestion

    def reword_decision_justification(self, *, justification, decision=None):
        self.calls.append({"justification": justification, "decision": decision})
        return self.suggestion


def test_rewording_service_requires_provider() -> None:
    service = ClaimDecisionRewordingService()

    with pytest.raises(ClaimDecisionRewordingNotConfiguredError):
        service.reword_decision_justification(
            justification="Covered loss.",
            decision="approved",
        )


def test_rewording_service_validates_input() -> None:
    service = ClaimDecisionRewordingService(FakeProvider())

    with pytest.raises(ValueError):
        service.reword_decision_justification(justification=" ", decision="denied")

    with pytest.raises(ValueError):
        service.reword_decision_justification(
            justification="Covered loss.",
            decision="changed_decision",
        )


def test_rewording_service_returns_provider_suggestion() -> None:
    provider = FakeProvider("The claim is denied because receipts do not match.")
    service = ClaimDecisionRewordingService(provider)

    suggestion = service.reword_decision_justification(
        justification="receipts do not match",
        decision="denied",
    )

    assert suggestion == "The claim is denied because receipts do not match."
    assert provider.calls == [
        {"justification": "receipts do not match", "decision": "denied"}
    ]


def test_rewording_service_replaces_meta_feedback_with_fallback() -> None:
    provider = FakeProvider(
        "The justification provided is inappropriate and lacks professionalism."
    )
    service = ClaimDecisionRewordingService(provider)

    suggestion = service.reword_decision_justification(
        justification="deny this nonsense",
        decision="denied",
    )

    assert suggestion == fallback_decision_justification("denied")
    assert "inappropriate" not in suggestion.lower()
    assert "lacks professionalism" not in suggestion.lower()
    assert "claim has therefore been denied" in suggestion


def test_meta_comment_guard_detects_unusable_suggestions() -> None:
    assert is_meta_comment_suggestion("Please provide a professional explanation.")
    assert is_meta_comment_suggestion("I cannot reword this as written.")
    assert not is_meta_comment_suggestion(
        "The claim is denied because the submitted receipts do not support the claimed loss."
    )


def test_openai_responses_provider_calls_responses_api_with_safe_prompt() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["json"] = json_payload = request.read().decode()
        assert "full email" not in json_payload.lower()
        assert "Decision: denied" in json_payload
        return httpx.Response(200, json={"output_text": "Professional wording."})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIResponsesClaimDecisionRewordingProvider(
        api_key="test-key",
        model="gpt-test",
        api_base="https://api.openai.test/v1",
        client=client,
    )

    suggestion = provider.reword_decision_justification(
        justification="receipts do not match",
        decision="denied",
    )

    assert suggestion == "Professional wording."
    assert captured["url"] == "https://api.openai.test/v1/responses"
    assert captured["authorization"] == "Bearer test-key"
    assert "Do not change the decision outcome" in captured["json"]
    assert "Return only the rewritten customer-facing decision justification" in captured["json"]
    assert "Do not critique, label, apologize for, or comment on the original wording" in captured["json"]
    assert "If the input is inappropriate, replace it with a neutral, professional explanation" in captured["json"]
    assert CLAIM_DECISION_REWORDING_SYSTEM_PROMPT in captured["json"]


def test_openai_responses_provider_hides_provider_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "raw provider detail"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIResponsesClaimDecisionRewordingProvider(
        api_key="test-key",
        model="gpt-test",
        api_base="https://api.openai.test/v1",
        client=client,
    )

    with pytest.raises(ClaimDecisionRewordingProviderError) as exc:
        provider.reword_decision_justification(
            justification="Covered loss.",
            decision="approved",
        )

    assert "raw provider detail" not in str(exc.value)
