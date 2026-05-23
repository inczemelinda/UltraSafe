from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest

from underwright.domain.intelligence import (
    ClassificationInput,
    ClassificationOutput,
    EvidenceSnippet,
    ExternalEvent,
    TemplateReviewCandidate,
)
from underwright.domain.models import Template
from underwright.infrastructure.llm.intelligence_classifier import (
    OpenAICompatibleEventClassifier,
    OpenAICompatibleEventSummaryWriter,
    OpenAICompatibleTemplateCandidateExplainer,
)


def make_classification_input() -> ClassificationInput:
    return ClassificationInput(
        raw_item_id=UUID("40000000-0000-0000-0000-000000000001"),
        source_id="asf_ro",
        source_type="regulator",
        trust_tier="authoritative",
        original_url="https://asfromania.ro/comunicat-pad",
        published_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
        title="ASF comunicare PAD",
        body_text_ref="raw_source_item:40000000-0000-0000-0000-000000000001:extracted_text",
        body_text="ASF mentioneaza asigurari de locuinte PAD si Legea 260/2008.",
        original_language="ro",
        country="RO",
        jurisdiction="RO",
        source_url_host="asfromania.ro",
        allowed_source_hosts=["asfromania.ro"],
        is_allowed_source_url=True,
    )


def make_event() -> ExternalEvent:
    return ExternalEvent(
        event_id=UUID("50000000-0000-0000-0000-000000000001"),
        raw_item_id=UUID("40000000-0000-0000-0000-000000000001"),
        source_id="asf_ro",
        source_type="regulator",
        trust_tier="authoritative",
        original_url="https://asfromania.ro/comunicat-pad",
        ingested_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
        title="ASF actualizare Legea 260/2008",
        body_text="ASF mentioneaza PAD si Legea 260/2008.",
        original_language="ro",
        country="RO",
        jurisdiction="RO",
        event_type="regulatory_update",
        line_of_business="property",
        topics_json=["PAD / compulsory home insurance"],
        severity="medium",
        confidence=0.88,
        underwriter_summary="Potentially relevant to PAD.",
        recommended_action="Review recommended for potentially affected Romanian property work.",
        evidence_json=[
            EvidenceSnippet(
                snippet="Legea 260/2008",
                reason="The source references the legal instrument.",
            )
        ],
        status="classified",
    )


def make_classification_output() -> ClassificationOutput:
    return ClassificationOutput(
        is_insurance_relevant=True,
        is_property_relevant=True,
        event_type="regulatory_update",
        topics=["PAD / compulsory home insurance"],
        affected_products=["residential_property"],
        affected_perils=[],
        severity="medium",
        summary_for_underwriter="Deterministic PAD summary.",
        recommended_action="Deterministic review action.",
        confidence=0.78,
        evidence=[
            EvidenceSnippet(
                snippet="PAD si Legea 260/2008",
                reason="The source references PAD.",
            )
        ],
        reasons_for_suppression=[],
    )


def make_template() -> Template:
    return Template(
        id=22,
        template_code="PAD_STANDARD_RO",
        name="PAD Standard RO",
        version="1.0",
        document_type="insurance_contract",
        is_active=True,
        content="Contract PAD guvernat de Legea 260/2008.",
        created_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
    )


def make_candidate() -> TemplateReviewCandidate:
    return TemplateReviewCandidate(
        event_id=UUID("50000000-0000-0000-0000-000000000001"),
        template_id=22,
        template_code="PAD_STANDARD_RO",
        template_name="PAD Standard RO",
        template_version="1.0",
        event_title="ASF actualizare Legea 260/2008",
        source_url="https://asfromania.ro/comunicat-pad",
        legal_references_json=["Legea 260/2008"],
        rule_ids_json=["legal_reference_overlap"],
        match_score=0.95,
        rationale="Review recommended.",
        evidence_json=[],
        created_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
    )


def chat_response(content: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(content)}}]},
    )


def test_ai_event_classifier_returns_valid_classification() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        return chat_response(
            {
                "is_insurance_relevant": True,
                "is_property_relevant": True,
                "event_type": "regulatory_update",
                "topics": ["PAD / compulsory home insurance"],
                "affected_products": ["residential_property"],
                "affected_perils": [],
                "severity": "medium",
                "summary_for_underwriter": "ASF item is potentially relevant to PAD.",
                "recommended_action": "Review recommended for potentially affected Romanian property templates.",
                "confidence": 0.91,
                "evidence": [
                    {
                        "snippet": "PAD si Legea 260/2008",
                        "reason": "The source references PAD.",
                    }
                ],
                "reasons_for_suppression": [],
            }
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    classifier = OpenAICompatibleEventClassifier(
        api_key="test-key",
        model="test-model",
        api_base="https://ai.test/v1",
        client=client,
    )

    output = classifier.classify(make_classification_input())

    assert output.is_property_relevant is True
    assert output.event_type == "regulatory_update"
    assert output.summary_for_underwriter.startswith("ASF item")
    assert output.evidence[0].reason == "The source references PAD."


def test_ai_event_classifier_suppresses_off_source_items_after_model_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return chat_response(
            {
                "is_insurance_relevant": True,
                "is_property_relevant": True,
                "event_type": "regulatory_update",
                "topics": ["PAD / compulsory home insurance"],
                "affected_products": ["residential_property"],
                "affected_perils": [],
                "severity": "medium",
                "summary_for_underwriter": "The model tried to classify this.",
                "recommended_action": "Review recommended.",
                "confidence": 0.9,
                "evidence": [
                    {
                        "snippet": "PAD",
                        "reason": "The model found a property signal.",
                    }
                ],
                "reasons_for_suppression": [],
            }
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    classifier = OpenAICompatibleEventClassifier(
        api_key="test-key",
        model="test-model",
        api_base="https://ai.test/v1",
        client=client,
    )
    classification_input = make_classification_input().model_copy(
        update={
            "original_url": "https://linkedin.com/login",
            "source_url_host": "linkedin.com",
            "is_allowed_source_url": False,
        }
    )

    output = classifier.classify(classification_input)

    assert output.is_insurance_relevant is False
    assert output.is_property_relevant is False
    assert output.event_type == "not_relevant"
    assert output.topics == []
    assert output.evidence == []
    assert (
        "source URL is outside configured source hosts"
        in output.reasons_for_suppression
    )


def test_ai_event_classifier_rejects_invalid_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    classifier = OpenAICompatibleEventClassifier(
        api_key="test-key",
        model="test-model",
        api_base="https://ai.test/v1",
        client=client,
    )

    with pytest.raises(ValueError, match="not valid JSON"):
        classifier.classify(make_classification_input())


def test_ai_event_classifier_requires_api_key() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAICompatibleEventClassifier(api_key="")


def test_ai_event_summary_writer_replaces_presentation_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "summary-model"
        user_message = json.loads(payload["messages"][1]["content"])
        assert user_message["classification"]["event_type"] == "regulatory_update"
        assert any("Ground News-style headline" in rule for rule in user_message["rules"])
        assert any("INCDFP - Conducere" in rule for rule in user_message["rules"])
        return chat_response(
            {
                "display_title": (
                    "PAD wording update may affect Romanian residential property review"
                ),
                "summary_for_underwriter": (
                    "ASF references PAD wording that may affect Romanian home insurance review."
                ),
                "recommended_action": (
                    "Review recommended for PAD wording and affected property templates."
                ),
            }
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    writer = OpenAICompatibleEventSummaryWriter(
        api_key="test-key",
        model="summary-model",
        api_base="https://ai.test/v1",
        client=client,
    )
    classification = make_classification_output()

    output = writer.summarize(make_classification_input(), classification)

    assert output.event_type == classification.event_type
    assert output.topics == classification.topics
    assert output.display_title.startswith("PAD wording update")
    assert output.summary_for_underwriter.startswith("ASF references PAD")
    assert output.recommended_action.startswith("Review recommended")


def test_ai_event_summary_writer_rejects_invalid_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    writer = OpenAICompatibleEventSummaryWriter(
        api_key="test-key",
        model="summary-model",
        api_base="https://ai.test/v1",
        client=client,
    )

    with pytest.raises(ValueError, match="not valid JSON"):
        writer.summarize(make_classification_input(), make_classification_output())


def test_ai_event_summary_writer_requires_api_key() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAICompatibleEventSummaryWriter(api_key="")


def test_ai_template_candidate_explainer_updates_only_explanation_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        user_message = payload["messages"][1]["content"]
        assert "legal_reference_overlap" in user_message
        return chat_response(
            {
                "rationale": (
                    "Review recommended because the event and template both reference "
                    "Legea 260/2008, so the wording is potentially affected."
                ),
                "evidence": [
                    {
                        "snippet": "Legea 260/2008",
                        "reason": "The same legal reference appears in the event and template.",
                    }
                ],
            }
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    explainer = OpenAICompatibleTemplateCandidateExplainer(
        api_key="test-key",
        model="test-model",
        api_base="https://ai.test/v1",
        client=client,
    )
    candidate = make_candidate()

    explained = explainer.explain(make_event(), make_template(), candidate)

    assert explained.event_id == candidate.event_id
    assert explained.template_id == candidate.template_id
    assert explained.rule_ids_json == ["legal_reference_overlap"]
    assert "Review recommended" in explained.rationale
    assert explained.evidence_json[0].snippet == "Legea 260/2008"
