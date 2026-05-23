from __future__ import annotations

from underwright.infrastructure.llm.claim_attachment_extraction import (
    CLAIM_ATTACHMENT_SUMMARY_SYSTEM_PROMPT,
    OpenAIClaimAttachmentSummaryGenerator,
)


class FakeOpenAIClient:
    def __init__(self, response_text: str = "Evidence signals:\n- Water is visible.") -> None:
        self.captured: dict = {}
        self.chat = FakeChat(self, response_text)


class FakeChat:
    def __init__(self, owner: FakeOpenAIClient, response_text: str) -> None:
        self.completions = FakeCompletions(owner, response_text)


class FakeCompletions:
    def __init__(self, owner: FakeOpenAIClient, response_text: str) -> None:
        self.owner = owner
        self.response_text = response_text

    def create(self, **kwargs):
        self.owner.captured = kwargs
        return type(
            "Response",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Message",
                                (),
                                {"content": self.response_text},
                            )()
                        },
                    )()
                ]
            },
        )()


def test_attachment_summary_prompt_requests_evidence_signals_not_generic_checklist() -> None:
    client = FakeOpenAIClient(
        "Evidence signals:\n- Living-room floor and furniture show water exposure."
    )
    generator = OpenAIClaimAttachmentSummaryGenerator(
        api_key="test-key",
        model="test-model",
        client=client,
    )

    summary = generator.summarize(
        [
            {
                "file_name": "living-room-flood-photo.png",
                "content_type": "image/png",
                "text": (
                    "- Visible damage: water on the living-room floor.\n"
                    "- Affected area: floor, plants, and furniture.\n"
                    "- Photo uncertainty: no exterior source is visible."
                ),
                "error": None,
            },
            {
                "file_name": "repair-invoice.pdf",
                "content_type": "application/pdf",
                "text": "Invoice lists water extraction and floor drying work.",
                "error": None,
            },
            {
                "file_name": "unreadable-report.pdf",
                "content_type": "application/pdf",
                "text": "",
                "error": "PDF text extraction failed.",
            },
        ],
        claim_context={
            "claim_type": "Fire",
            "description": "Kitchen fire caused smoke damage.",
            "incident_date": "2026-05-15",
            "estimated_damage": 12000,
        },
    )

    assert summary["summary"].startswith("Evidence signals:")
    assert client.captured["model"] == "test-model"
    assert client.captured["temperature"] == 0
    messages = client.captured["messages"]
    assert messages[0]["content"] == CLAIM_ATTACHMENT_SUMMARY_SYSTEM_PROMPT
    prompt = messages[1]["content"]
    assert "Produce 2-6 short signals" in prompt
    assert "Claim context for comparison:" in prompt
    assert "- Claim type: Fire" in prompt
    assert "- Claim description: Kitchen fire caused smoke damage." in prompt
    assert "- Incident date: 2026-05-15" in prompt
    assert "- Estimated damage: 12000" in prompt
    assert "Deterministic consistency checks:" in prompt
    assert "MUST include this mismatch under Out of place / needs review" in prompt
    assert "claim reason is Fire" in prompt
    assert "primarily describe water/flood damage" in prompt
    assert "living-room-flood-photo.png" in prompt
    assert "Attachment type: photo" in prompt
    assert "repair-invoice.pdf" in prompt
    assert "Attachment type: document" in prompt
    assert "Extraction issue: PDF text extraction failed." in prompt
    assert "Do not output generic checklist categories" in prompt
    assert "Do not write Not specified." in prompt
    assert "one section label on its own line ending with a colon" in prompt
    assert "Never put bullets inline after a section label." in prompt
    assert "Summarize key parties, dates, amounts" not in prompt


def test_attachment_summary_prompt_flags_evidence_claim_mismatch() -> None:
    client = FakeOpenAIClient(
        "Out of place / needs review:\n- Fire claim is supported by water-damage photos."
    )
    generator = OpenAIClaimAttachmentSummaryGenerator(
        api_key="test-key",
        model="test-model",
        client=client,
    )

    generator.summarize(
        [
            {
                "file_name": "damage-photo.jpg",
                "content_type": "image/jpeg",
                "text": (
                    "- Visible damage: standing water across a living-room floor.\n"
                    "- Affected area: floor, furniture, and plants.\n"
                    "- Relevant conditions: no smoke, burn marks, or fire damage are visible."
                ),
                "error": None,
            }
        ],
        claim_context={
            "claim_type": "Fire",
            "description": "Client filed a claim for a kitchen fire.",
        },
    )

    prompt = client.captured["messages"][1]["content"]
    assert "- Claim type: Fire" in prompt
    assert "standing water across a living-room floor" in prompt
    assert "no smoke, burn marks, or fire damage are visible" in prompt
    assert "Compare the evidence to the claim context" in prompt
    assert "photos do not appear related to the reported fire event" in prompt
    assert "how the water damage resulted from the fire response" in prompt


def test_attachment_summary_normalizes_inline_sections_and_bullets() -> None:
    generator = OpenAIClaimAttachmentSummaryGenerator(
        api_key="test-key",
        model="test-model",
        client=FakeOpenAIClient(
            'Evidence signals: - The photo "flooded.png" shows indoor flooding. '
            "- No visible signs of fire damage are present. Out of place / needs "
            "review: - The claim reason is Fire, but the evidence describes water damage. "
            "Follow-up: - Clarification is needed on how the water damage relates to the fire."
        ),
    )

    summary = generator.summarize(
        [
            {
                "file_name": "flooded.png",
                "content_type": "image/png",
                "text": "Photo shows standing water in a living room.",
                "error": None,
            }
        ],
        claim_context={"claim_type": "Fire"},
    )

    assert summary["summary"] == (
        "Evidence signals:\n"
        '- The photo "flooded.png" shows indoor flooding.\n'
        "- No visible signs of fire damage are present.\n"
        "Out of place / needs review:\n"
        "- The claim reason is Fire, but the evidence describes water damage.\n"
        "Follow-up:\n"
        "- Clarification is needed on how the water damage relates to the fire."
    )


def test_attachment_summary_returns_concise_empty_state_without_observations() -> None:
    generator = OpenAIClaimAttachmentSummaryGenerator(
        api_key="test-key",
        model="test-model",
        client=FakeOpenAIClient(),
    )

    summary = generator.summarize(
        [
            {
                "file_name": "blank.pdf",
                "content_type": "application/pdf",
                "text": "",
                "error": None,
            }
        ]
    )

    assert summary == {
        "summary": "No claim evidence signals were extracted.",
        "key_info": {},
        "error": None,
    }
