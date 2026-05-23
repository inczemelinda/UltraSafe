from __future__ import annotations

from uuid import UUID, uuid4

from underwright.application.services.evidence_request_draft_service import (
    EvidenceRequestDraftAlreadySentError,
    EvidenceRequestDraftService,
)
from underwright.domain.claim_analysis import (
    EvidenceRequirement,
    EvidenceRequirementResult,
    EvidenceRequestDraft,
)
from underwright.domain.claim_case_context import ClaimCaseContext


REQUEST_ID = UUID("82000000-0000-0000-0000-000000000001")


def test_fire_evidence_requirement_generates_editable_draft() -> None:
    context = make_context(
        [
            EvidenceRequirement(
                requirement_type="official_fire_incident_confirmation",
                reason="Fire incident needs official confirmation.",
                acceptable_documents=[
                    "fire_service_report",
                    "emergency_report",
                    "official_incident_confirmation",
                ],
                severity="high",
                status="missing",
                suggested_next_action="request_evidence",
            )
        ]
    )

    draft = EvidenceRequestDraftService().generate_draft(context)

    assert draft is not None
    assert draft.claim_request_id == REQUEST_ID
    assert draft.status == "draft"
    assert draft.subject == "Additional evidence required for your fire claim"
    assert "fire service report" in draft.required_documents
    assert "emergency intervention report" in draft.required_documents
    assert "police report" in draft.required_documents
    assert "authority-issued incident confirmation" in draft.required_documents
    assert "incident reference number" in draft.required_documents
    assert "fire service report" in draft.body
    assert "incident reference number" in draft.body
    assert context.generated_outputs.evidence_request_draft is draft


def test_additional_incident_details_are_included_in_draft_body() -> None:
    context = make_context(
        [
            EvidenceRequirement(
                requirement_type="additional_incident_details",
                reason="Incident description is too short.",
                acceptable_documents=[
                    "claimant_statement",
                    "written_incident_description",
                ],
                severity="medium",
                status="missing",
                suggested_next_action="request_evidence",
            )
        ]
    )

    draft = EvidenceRequestDraftService().generate_draft(context)

    assert draft is not None
    assert draft.subject == "Additional evidence required for your claim"
    assert "additional incident details" in draft.required_documents
    assert "what happened, when it happened, where it happened" in draft.body


def test_no_required_evidence_returns_no_draft() -> None:
    context = make_context([])

    draft = EvidenceRequestDraftService().generate_draft(context)

    assert draft is None
    assert context.generated_outputs.evidence_request_draft is None


def test_existing_draft_is_not_returned_when_latest_review_needs_no_evidence() -> None:
    context = make_context([])
    context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
        claim_request_id=REQUEST_ID,
        subject="Additional evidence required for your claim",
        body="Old draft.",
        required_documents=["old document"],
    )

    draft = EvidenceRequestDraftService().generate_draft(context)

    assert draft is None


def test_save_draft_persists_underwriter_edits_and_due_date() -> None:
    context = make_context(
        [
            EvidenceRequirement(
                requirement_type="additional_incident_details",
                reason="Incident description is too short.",
                acceptable_documents=["claimant_statement"],
                status="missing",
            )
        ]
    )

    draft = EvidenceRequestDraftService().save_draft(
        context,
        subject="Edited subject",
        body="Edited body",
        recipients=["client@example.test"],
        required_documents=["claimant statement"],
        source_suggestion_id="ai-follow-up-1",
        requested_document_type="claimant statement",
        due_date="2026-05-30",
    )

    assert context.generated_outputs.evidence_request_draft is draft
    assert draft.subject == "Edited subject"
    assert draft.body == "Edited body"
    assert draft.recipients == ["client@example.test"]
    assert draft.due_date == "2026-05-30"
    assert (
        context.generated_outputs.communication_suggestion_states[
            "ai-follow-up-1"
        ].status
        == "draft_created"
    )


def test_dismiss_suggestion_persists_backend_lifecycle_state() -> None:
    context = make_context([])

    state = EvidenceRequestDraftService().dismiss_suggestion(
        context,
        "ai-follow-up-1",
    )

    assert state.status == "dismissed"
    assert state.dismissed_at is not None
    assert (
        context.generated_outputs.communication_suggestion_states[
            "ai-follow-up-1"
        ]
        is state
    )


def test_sent_draft_marks_lifecycle_state_and_allows_new_request_scope() -> None:
    context = make_context(
        [
            EvidenceRequirement(
                requirement_type="additional_incident_details",
                reason="Incident description is too short.",
                acceptable_documents=["claimant_statement"],
                status="missing",
            )
        ]
    )
    service = EvidenceRequestDraftService()
    service.save_draft(
        context,
        subject="Edited subject",
        body="Edited body",
        recipients=["client@example.test"],
        required_documents=["fire service report"],
        source_suggestion_id="ai-follow-up-fire",
    )

    draft, recipient = service.prepare_draft_send(context)
    sent = service.mark_draft_sent(
        context,
        email_message_id=uuid4(),
        provider_message_id="provider-message-id",
        sent_at=None,
        sent_to=recipient,
    )

    assert sent.status == "sent"
    assert sent.send_status == "sent"
    assert sent.sent_to == ["client@example.test"]
    assert sent.provider_message_id == "provider-message-id"
    assert draft is sent
    assert sent.sent_at is not None
    assert (
        context.generated_outputs.communication_suggestion_states[
            "ai-follow-up-fire"
        ].status
        == "sent"
    )
    try:
        service.save_draft(
            context,
            subject="Edited after send",
            body="Should fail",
            required_documents=["fire service report"],
            source_suggestion_id="ai-follow-up-fire",
        )
    except EvidenceRequestDraftAlreadySentError:
        pass
    else:
        raise AssertionError("Sent drafts should not be editable.")

    new_draft = service.save_draft(
        context,
        subject="Claimant statement needed",
        body="Please send a claimant statement.",
        recipients=["client@example.test"],
        required_documents=["claimant statement"],
        source_suggestion_id="ai-follow-up-claimant-statement",
        requested_document_type="claimant statement",
    )

    assert new_draft is context.generated_outputs.evidence_request_draft
    assert new_draft is not sent
    assert new_draft.status == "draft"
    assert new_draft.send_status == "not_sent"
    assert new_draft.sent_at is None
    assert new_draft.sent_to == []
    assert new_draft.required_documents == ["claimant statement"]
    assert new_draft.source_suggestion_id == "ai-follow-up-claimant-statement"
    assert (
        context.generated_outputs.communication_suggestion_states[
            "ai-follow-up-fire"
        ].status
        == "sent"
    )
    assert (
        context.generated_outputs.communication_suggestion_states[
            "ai-follow-up-claimant-statement"
        ].status
        == "draft_created"
    )


def make_context(
    required_evidence: list[EvidenceRequirement],
) -> ClaimCaseContext:
    context = ClaimCaseContext(source_inputs={"request_id": REQUEST_ID})
    context.reference_data.claim_request = {
        "request_id": str(REQUEST_ID),
        "client_id": 1001,
        "client_data": {"full_name": "Ion Popescu"},
        "claim_data": {
            "claim_type": "Fire",
            "description": "Kitchen fire with smoke damage.",
        },
        "attachments": [],
    }
    context.generated_outputs.evidence_requirements = EvidenceRequirementResult(
        required_evidence=required_evidence,
        suggested_next_action=(
            "request_evidence" if required_evidence else "underwriter_review"
        ),
    )
    return context
