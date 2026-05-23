from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_employee_pages_source() -> str:
    return (ROOT / "frontend/src/pages/EmployeePages.tsx").read_text(
        encoding="utf-8"
    )


def test_communicate_tab_removes_duplicate_heading_and_uses_start_panel() -> None:
    source = read_employee_pages_source()
    communicate_tab = source.split("function ClaimCommunicateTab", 1)[1].split(
        "function CommunicationStartPanel",
        1,
    )[0]

    assert ">Communicate</h2>" not in communicate_tab
    assert "Send document requests, track reminders, and review inbound client emails." not in communicate_tab
    assert 'title="Email"' in communicate_tab
    assert "action={" in communicate_tab
    assert "emptyWorkspace ?" in communicate_tab
    assert "CommunicationStartPanel" in communicate_tab
    assert "CommunicationStatusStrip" not in source


def test_communicate_empty_states_have_operational_copy_and_primary_action() -> None:
    source = read_employee_pages_source()

    assert "Client communication" in source
    assert "No active client requests are currently open for this claim." in source
    assert "Create document request" in source
    assert "No document requests have been sent for this claim." in source
    assert "No replies yet" in source
    assert "Client replies and attachments will appear here." in source


def test_communicate_tab_has_top_write_email_action() -> None:
    source = read_employee_pages_source()
    communicate_tab = source.split("function ClaimCommunicateTab", 1)[1].split(
        "function CommunicationComposeBar",
        1,
    )[0]
    email_editor = source.split("function EvidenceRequestEmailEditorModal", 1)[1].split(
        "function AiDraftEditorField",
        1,
    )[0]

    assert "CommunicationComposeBar" in communicate_tab
    assert "justify-end" not in source.split("function CommunicationComposeBar", 1)[1].split(
        "function CommunicationStartPanel",
        1,
    )[0]
    assert "Write email" in source
    assert 'kind: "write_email"' in source
    assert "EvidenceRequestEmailEditorModal" in source
    assert "Save email draft" in source
    assert "max-h-[92vh] w-full max-w-6xl" in source
    assert 'label="Email subject"' in email_editor
    assert 'label="Email message"' in email_editor
    assert 'label="Requested document"' in email_editor
    assert 'label="Due date"' in email_editor
    assert email_editor.count("showLabel") == 4
    assert "writeEmailDisabledReason" not in source


def test_communicate_tab_uses_short_equal_communication_columns() -> None:
    source = read_employee_pages_source()
    communicate_tab = source.split("function ClaimCommunicateTab", 1)[1].split(
        "function CommunicationComposeBar",
        1,
    )[0]

    assert 'xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]' in communicate_tab
    assert 'title="Requests"' in communicate_tab
    assert 'title="Replies"' in communicate_tab
    assert 'title="Requested documents"' not in communicate_tab
    assert 'title="Client replies"' not in communicate_tab


def test_communicate_tab_removes_internal_empty_copy() -> None:
    source = read_employee_pages_source()

    assert "No email-hook evidence has been received." not in source
    assert "No open evidence requirements in the latest review." not in source
    assert "No open client document requests are present in the latest claim review." not in source
    assert "No inbound client emails have been received." not in source
    assert "No document requests are currently open." not in source


def test_communication_timeline_is_compact() -> None:
    source = read_employee_pages_source()
    timeline = source.split("function CommunicationTimeline", 1)[1].split(
        "function CommunicationMiniBadge",
        1,
    )[0]

    assert "whitespace-nowrap" in timeline
    assert "text-xs leading-5" in timeline
    assert "CommunicationMiniBadge" in timeline
    assert "—" in timeline


def test_communicate_tab_has_ai_follow_up_suggestion_scaffolding() -> None:
    source = read_employee_pages_source()
    suggestions_section = source.split("function AiFollowUpSuggestionsSection", 1)[1].split(
        "function AiFollowUpSuggestionModal",
        1,
    )[0]
    suggestion_modal = source.split("function AiFollowUpSuggestionModal", 1)[1].split(
        "function AiSuggestionDraftEditorModal",
        1,
    )[0]

    assert "Follow-up suggestions" in source
    assert 'kind: "review_ai_suggestion"' in suggestions_section
    assert "Review suggestion" not in suggestions_section
    assert "Create request" not in suggestions_section
    assert "Edit draft" not in suggestions_section
    assert "Dismiss" not in suggestions_section
    assert "recommendedRequest" not in suggestions_section
    assert "suggestedEmailSubject" not in suggestions_section
    assert "suggestedEmailBody" not in suggestions_section
    assert "claimSummaryPreviewText(suggestion.reason)" in suggestions_section
    assert "max-h-[92vh] w-full max-w-7xl" in suggestion_modal
    assert "Reason" in suggestion_modal
    assert '<FormattedClaimSummary className="mt-2 text-slate-800" text={suggestion.reason} />' in suggestion_modal
    assert "Context" not in suggestion_modal
    assert "aiSuggestionContextText" not in source
    assert "suggestion.fullReasoning || suggestion.recommendedRequest" not in suggestion_modal
    assert "Proposal" in suggestion_modal
    assert "Create request" in suggestion_modal
    assert "Edit draft" in suggestion_modal
    assert "Dismiss" in suggestion_modal
    assert "AI suggestions are advisory only. The request is never sent automatically." not in source
    assert "dismissClaimAiSuggestion" in source
    assert "updateEvidenceRequestDraft" in source
    assert "sendEvidenceRequestDraft" in source
    assert "sendDemoInboundClaimEmail" in source
    assert "isInactiveAiSuggestion" in source
    assert "aiSuggestionStatusIsSent" in source
    assert 'status.includes("sent")' not in source
    assert "evidenceRequestDraftIsSent(matchingDraft)" in source
    assert "dismissed for this session" not in source
    assert "TODO: Persist dismissed AI suggestions" not in source
    assert "TODO: Persist edited AI suggestion drafts" not in source
    assert "normalizeClaimSummaryTextForDisplay" in source
    assert "canonicalClaimSummarySectionLabel" in source


def test_ai_follow_up_save_draft_opens_saved_draft_and_surfaces_errors() -> None:
    source = read_employee_pages_source()
    save_handler = source.split("async function handleSaveAiSuggestionDraft", 1)[1].split(
        "async function handleSaveEvidenceRequestEmailDraft",
        1,
    )[0]
    draft_editor = source.split("function AiSuggestionDraftEditorModal", 1)[1].split(
        "function EvidenceRequestEmailEditorModal",
        1,
    )[0]

    assert "const savedDraft = await updateEvidenceRequestDraft" in save_handler
    assert "setSelectedEvidenceRequestDraft(savedDraft);" in save_handler
    assert "setSelectedAiSuggestion(null);" in save_handler
    assert "setEditingAiSuggestion(null);" in save_handler
    assert "Email request draft saved. It has not been sent." in save_handler
    assert "getLatestClaimReview(claim.id)" in save_handler
    assert "keep the saved draft visible even if refresh is unavailable" in save_handler
    assert "throw new Error(message);" in save_handler
    assert "saveError" in draft_editor
    assert "setSaveError(undefined);" in draft_editor
    assert "await onSaveDraft(suggestion, draft);" in draft_editor
    assert "Could not save the email request draft." in draft_editor
    assert "loading={pending}" in draft_editor


def test_communicate_tab_hides_duplicate_backend_metadata_labels() -> None:
    source = read_employee_pages_source()
    communicate_tab = source.split("function ClaimCommunicateTab", 1)[1].split(
        "function EvidenceRequestDraftModal",
        1,
    )[0]
    request_table = source.split("function RequestedDocumentsCommunicationTable", 1)[1].split(
        "function InboundEmailIngestionList",
        1,
    )[0]
    draft_modal = source.split("function EvidenceRequestDraftModal", 1)[1].split(
        "function ClaimWorkspaceSection",
        1,
    )[0]

    assert "Email automation" not in communicate_tab
    assert "Template" not in communicate_tab
    assert "Reminder reason" not in communicate_tab
    assert "Advisory only" not in communicate_tab
    assert "Request email" not in communicate_tab
    assert "Attachments:" not in communicate_tab
    assert "From {email.sender}" not in communicate_tab
    assert ">Reason<" not in request_table
    assert ">Draft<" not in communicate_tab
    assert '"Last email"' not in request_table
    assert '"Client response"' not in request_table
    assert '"Next reminder"' not in request_table
    assert '"Source"' not in request_table
    assert "Request details" not in draft_modal
    assert "Delivery failed:" not in draft_modal
    assert "Email record" not in draft_modal
    assert "claimRequestId" not in draft_modal


def test_sent_email_surfaces_have_visible_titles() -> None:
    source = read_employee_pages_source()
    automation_card = source.split("function ClaimEmailAutomationCard", 1)[1].split(
        "function RequestedDocumentsCommunicationTable",
        1,
    )[0]
    draft_modal = source.split("function EvidenceRequestDraftModal", 1)[1].split(
        "function ClaimWorkspaceSection",
        1,
    )[0]

    assert "Sent email" in automation_card
    assert "Email draft" in automation_card
    assert "Email delivery failed" in automation_card
    assert "const modalTitle = sent ? \"Sent email\" : \"Evidence request\";" in draft_modal
    assert "Email title" in draft_modal


def test_communicate_tab_auto_runs_analysis_before_draft_creation() -> None:
    source = read_employee_pages_source()
    backend_service = (ROOT / "frontend/src/services/backend/claimService.ts").read_text(
        encoding="utf-8"
    )

    assert "Latest claim review findings were not found." not in source
    assert "startClaimAnalysis" in source
    assert "claimNeedsCommunicationAnalysis" in source
    assert "autoCommunicationAnalysisClaimIds" in source
    assert "autoCommunicationAnalysisClaimIds.current.has(claim.id)" in source
    assert "hasCommunicationAnalysisOutput(claim)" in source
    assert 'reviewState === "not started" || reviewState === "coverage precheck only"' in source
    assert 'return !reviewState && Boolean(claim.availableActions?.includes("start_analysis"));' in source
    assert "Running claim analysis so missing evidence can be identified." in source
    assert "AI review findings are not available yet." not in source
    assert "isMissingClaimReviewFindingsError" in backend_service


def test_evidence_tab_request_buttons_are_wired_to_email_actions() -> None:
    source = read_employee_pages_source()
    backend_service = (ROOT / "frontend/src/services/backend/claimService.ts").read_text(
        encoding="utf-8"
    )
    claim_service = (ROOT / "frontend/src/services/claimService.ts").read_text(
        encoding="utf-8"
    )
    mock_service = (ROOT / "frontend/src/services/mock/claimService.ts").read_text(
        encoding="utf-8"
    )
    handler = source.split("async function handleCommunicationAction", 1)[1].split(
        "async function handleSaveAiSuggestionDraft",
        1,
    )[0]
    row = source.split("function ClaimEvidenceItemRow", 1)[1].split(
        "function evidenceUploadTone",
        1,
    )[0]

    assert "onAction={handleCommunicationAction}" in source
    assert "pendingActionId={communicationPendingAction}" in source
    assert 'if (action.kind === "send_reminder")' not in handler
    assert "sendEvidenceRequestReminder" not in source
    assert "Evidence request reminder sent." not in source
    assert "Send reminder" not in row
    assert "onClick={() => onAction(action)}" in row
    assert "pending ? \"Working...\" : item.primaryAction" in row
    assert "evidenceRequestDraftForRequirement(claim, requirement)" in source
    assert "evidenceRequestDraftMatchesRequirement" in source
    assert "evidenceRequirementWasSent(claim, requirement, index)" in source
    assert "function normalizeEvidenceText(value: unknown)" in source
    assert "String(value ?? \"\")" in source
    assert 'primaryAction: requestSent || priorRequestSent ? "Sent" : requestExists ? "View request" : "Request"' in source
    assert 'priorRequestSent\n          ? "unsupported"' in source
    assert "/evidence-request/draft/reminder" not in backend_service
    assert "sendEvidenceRequestReminder" not in claim_service
    assert "sendEvidenceRequestReminder" not in mock_service
    assert "sameEvidenceRequestScope" in mock_service
    assert "Run claim analysis before creating an evidence request draft." in backend_service


def test_communicate_tab_demo_inbound_button_is_wired_to_real_postmark_send() -> None:
    source = read_employee_pages_source()
    backend_service = (ROOT / "frontend/src/services/backend/claimService.ts").read_text(
        encoding="utf-8"
    )
    claim_service = (ROOT / "frontend/src/services/claimService.ts").read_text(
        encoding="utf-8"
    )
    mock_service = (ROOT / "frontend/src/services/mock/claimService.ts").read_text(
        encoding="utf-8"
    )
    handler = source.split("async function handleCommunicationAction", 1)[1].split(
        "async function handleSaveAiSuggestionDraft",
        1,
    )[0]

    assert "Send demo reply" in source
    assert '"trigger_demo_inbound_email"' in source
    assert 'if (action.kind === "trigger_demo_inbound_email")' in handler
    assert "const response = await sendDemoInboundClaimEmail(claim.id);" in handler
    assert "Waiting for the inbound webhook." in handler
    assert "/communication/demo-inbound-email" in backend_service
    assert "export const sendDemoInboundClaimEmail" in claim_service
    assert "export async function sendDemoInboundClaimEmail" in mock_service


def test_evidence_reminder_is_not_part_of_communication_history() -> None:
    source = read_employee_pages_source()
    timeline_builder = source.split("function buildCommunicationTimeline", 1)[1].split(
        "function findEvidenceItemForRequirement",
        1,
    )[0]

    assert "reminder" not in timeline_builder.lower()


def test_ai_analysis_keeps_evidence_box_but_hides_empty_communicate_component() -> None:
    source = read_employee_pages_source()
    types_source = (ROOT / "frontend/src/types.ts").read_text(encoding="utf-8")
    communicate_tab = source.split("function ClaimCommunicateTab", 1)[1].split(
        "function CommunicationComposeBar",
        1,
    )[0]
    evidence_tab = source.split("function ClaimEvidenceTab", 1)[1].split(
        "function ClaimEvidenceItemRow",
        1,
    )[0]
    suggestions_builder = source.split("function buildClaimAiFollowUpSuggestions", 1)[1].split(
        "function applyCommunicationSuggestionLifecycle",
        1,
    )[0]
    suggestion_filter = source.split("function shouldCreateAiFollowUpSuggestion", 1)[1].split(
        "function aiFollowUpSuggestionFromRequirement",
        1,
    )[0]

    assert "AI analysis" in source
    assert "AiDocumentAnalysisPanel" in source
    assert "visibleClaimEvidenceFindings(aiFindings)" in evidence_tab
    assert "onRefreshAnalysis" in evidence_tab
    assert "refreshClaimAttachmentAnalysis(claim.id)" in source
    assert "No AI analysis is available yet." in evidence_tab
    assert 'title="AI analysis"' in evidence_tab
    assert 'normalizeEvidenceText(finding.findingType) !== "document summary"' not in source
    assert "aiFindings" in evidence_tab
    assert "showFollowUpSuggestions" in communicate_tab
    assert "workspace.aiFollowUpSuggestions.length > 0" in communicate_tab
    assert 'normalizeAiStatus(workspace.aiReviewStatus) === "processing"' in communicate_tab
    assert "claim.aiFollowUpSuggestions" in suggestions_builder
    assert "const backendSuggestions = claim.aiFollowUpSuggestions ?? [];" in suggestions_builder
    assert (
        "const generatedSuggestions = buildGeneratedClaimAiFollowUpSuggestions(claim, aiFindings);"
        in suggestions_builder
    )
    assert "uniqueAiFollowUpSuggestions([...backendSuggestions, ...generatedSuggestions])" in suggestions_builder
    assert "const findingSuggestions = aiFindings" in suggestions_builder
    assert "uniqueAiFollowUpSuggestions([...requirementSuggestions, ...findingSuggestions])" in suggestions_builder
    assert "const followUpText = claimSummarySectionText(finding.description, [\"Follow-up\", \"Follow up\"]);" in source
    assert 'const subject = followUpText ? "Clarification needed for your claim"' in source
    assert 'title: followUpText ? "Request clarification"' in source
    assert "evidenceRequestDraftMatchesAiSuggestion" in source
    assert "draft.requiredDocuments ?? []" in source
    assert "if (claim.aiFollowUpSuggestions?.length)" not in suggestions_builder
    assert "if (requirementSuggestions.length)" not in suggestions_builder
    assert "aiFollowUpSuggestionFromFinding" in suggestions_builder
    assert '"follow up"' in suggestion_filter
    assert '"clarification needed"' in suggestion_filter
    assert '"clarify"' in suggestion_filter
    assert "followUpFindingIds" not in suggestions_builder
    assert "isClaimEvidenceDocumentForEvidenceTab" in source
    assert "AiReviewFinding" in types_source
    assert "AiFollowUpSuggestion" in types_source
    assert "SuggestedEmailDraft" in types_source


def test_claim_evidence_preview_hides_extraction_pipeline_details() -> None:
    source = read_employee_pages_source()
    backend_service = (ROOT / "frontend/src/services/backend/claimService.ts").read_text(
        encoding="utf-8"
    )
    preview_modal = source.split("function ClaimEvidencePreviewModal", 1)[1].split(
        "function ClientDocumentPreviewModal",
        1,
    )[0]

    assert "claimEvidenceExtractionInfo(selectedDocument)" in source
    assert "Evidence details" in preview_modal
    assert "Document interpretation" not in preview_modal
    assert "Upload status" not in preview_modal
    assert "Extraction provenance" not in preview_modal
    assert "Extraction state" not in preview_modal
    assert "Extraction source" not in preview_modal
    assert "AI / review status" not in preview_modal
    assert "Classification confidence" not in preview_modal
    assert "FormattedClaimSummary" not in preview_modal
    assert "item.extractionMessage" not in preview_modal
    assert "extractedPreview" not in source
    assert "item.extractedText" not in source
    assert "mergeAttachmentExtractionMetadata" in backend_service
    assert "extractedDocumentsByAttachmentIdentity" in backend_service
    assert "extraction_provenance" in backend_service


def test_decision_tab_exposes_claim_decision_email_state() -> None:
    source = read_employee_pages_source()

    assert "Claim decision email" in source
    assert "claimDecisionEmailStatus" in source
    assert "Ready to send" in source
    assert "Message ID" in source


def test_decision_ai_rewording_uses_shiny_loading_and_modal_suggestion() -> None:
    source = read_employee_pages_source()

    assert "function ShinyText" in source
    assert 'text="Thinking..."' in source
    assert 'title="AI suggested wording"' in source
    assert "onDismissSuggestion();" in source
