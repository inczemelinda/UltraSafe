from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_frontend_source(relative_path: str) -> str:
    return (ROOT / "frontend" / relative_path).read_text(encoding="utf-8")


def test_legal_review_workflow_uses_claim_detail_tab_system() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    routes = read_frontend_source("src/routes/AppRoutes.tsx")
    workflow_tabs = source.split("function LegalReviewWorkflowTabs", 1)[1].split(
        "function workflowStepFromPath",
        1,
    )[0]
    workflow_layout = source.split("function LegalReviewWorkflowLayout", 1)[1].split(
        "function LegalReviewPanelTabs",
        1,
    )[0]
    queue_view = source.split("export function LegalReviewQueueView", 1)[1].split(
        "export function LegalReviewUpdateDetailView",
        1,
    )[0]
    queue = source.split("function LawChangeQueue", 1)[1].split(
        "function QueueMeta",
        1,
    )[0]

    assert "const LegalReviewTabsContext = createContext<ReactNode>(null);" in source
    assert 'type LegalReviewQueueTab = "active" | "processed";' in source
    assert 'getLegalChanges("processed")' in source
    assert 'path=":updateId/documents"' in routes
    assert 'path=":updateId/documents/:templateId/changes"' in routes
    assert 'path=":updateId/documents/:templateId/draft"' in routes
    assert 'path=":updateId/templates"' in routes
    assert 'LegalReviewTemplatesRedirect' in routes
    assert "<LegalReviewQueueTabs" not in queue_view
    assert "<LegalReviewQueueTabs" in queue
    assert '{ id: "what-changed", label: "Change" }' in source
    assert '{ id: "what-affected", label: "Documents" }' in source
    assert 'to: `${updatePath}/documents`' in source
    assert "/templates/${encodeURIComponent" not in source
    assert '{ id: "review-wording", label: "Wording" }' in source
    assert '{ id: "create-draft", label: "Draft" }' in source
    assert 'aria-label="Legal review tabs"' in workflow_tabs
    assert 'role="tablist"' in workflow_tabs
    assert 'role="tab"' in workflow_tabs
    assert "tabIndex={0}" in workflow_layout
    assert 'event.key === "Enter" || event.key === " " || event.key === "Spacebar"' in workflow_tabs
    assert "flex h-12 shrink-0 items-end overflow-y-hidden border-b border-slate-200 bg-slate-50/80 px-5 pt-2 sm:px-6" in workflow_tabs
    assert "min-w-0 max-w-full overflow-x-auto overflow-y-hidden pb-px scrollbar-none" in workflow_tabs
    assert "inline-flex min-w-max items-end gap-1" in workflow_tabs
    assert "relative -mb-px inline-flex h-10 items-center justify-center rounded-t-lg border px-4" in workflow_tabs
    assert "focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-blue-100" in workflow_tabs
    assert "border-slate-200 border-b-white bg-white font-bold text-blue-800 shadow-sm" in workflow_tabs
    assert "after:inset-x-4 after:top-0 after:h-0.5 after:rounded-full after:bg-blue-600" in workflow_tabs
    assert "border-transparent bg-slate-100/70 font-semibold text-slate-600 hover:bg-slate-200/70 hover:text-slate-950" in workflow_tabs
    assert 'aria-selected={selected ? "true" : undefined}' in workflow_tabs
    assert "to={step.to}" in workflow_tabs
    assert "handleKeyDown" in workflow_tabs
    assert "<ProgressStepper" not in workflow_tabs
    assert "<EmployeePageHeader" in workflow_layout
    assert 'onClick={() => navigate("/legal-review")}' in workflow_layout
    assert 'variant="secondary"' in workflow_layout
    assert "Back to queue" in workflow_layout
    assert "<LegalReviewSummaryStrip" in workflow_layout
    assert "</EmployeePageHeader>" in workflow_layout
    assert "<LegalReviewTabsContext.Provider value={workflowTabs}>" in workflow_layout
    assert "<LegalReviewPanelTabs />" in source


def test_legal_review_ui_stays_task_first_and_quiet() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    workflow_layout = source.split("function LegalReviewWorkflowLayout", 1)[1].split(
        "function LegalReviewPanelTabs",
        1,
    )[0]
    queue = source.split("function LawChangeQueue", 1)[1].split(
        "function QueueMeta",
        1,
    )[0]
    change = source.split("function LegalUpdateDetailPanel", 1)[1].split(
        "function TemplateImpactPanel",
        1,
    )[0]
    wording = source.split("function SuggestionDiffEditor", 1)[1].split(
        "type TemplateContext",
        1,
    )[0]
    templates = source.split("function TemplateImpactPanel", 1)[1].split(
        "function ImpactDetail",
        1,
    )[0]
    draft = source.split("function DraftCreationPanel", 1)[1].split(
        "type BadgeTone",
        1,
    )[0]

    assert "border-t border-slate-200 pt-3" in source
    assert "Confidence {formatPercent(item.highest_confidence)}" not in workflow_layout
    assert "Detected risk" not in templates
    assert "Document affected by change" in templates
    assert "Review wording" in templates
    assert "Review proposed wording" not in templates
    assert 'ClaimWorkspaceSection title="Legal update"' in change
    assert 'ClaimWorkspaceSection title="Publication details"' in change
    assert 'ClaimWorkspaceSection title="Reference details"' in change
    assert 'ClaimWorkspaceSection title="Source excerpt"' in change
    assert "Show source excerpt" not in change
    assert "Show technical details" not in change
    assert "status === \"Needs review\" ? \"Start review\" : \"Continue\"" in queue
    assert "<Badge" not in queue
    assert "Wording changes" in wording
    assert "{reviewedHunks}/{suggestion.hunks.length} reviewed" not in wording
    assert ">Accept<" not in wording
    assert "Accept" in wording
    assert "Reject" in wording
    assert "changeSummaryForHunk(hunk)" not in wording
    assert "Wording context" in source
    assert "Current wording" in source
    assert "Suggested wording" in source
    assert "trimContextAfter(content.slice(index + exactText.length, afterEnd))" in source
    assert "return trimmed.trim() ? trimmed : undefined;" in source
    assert "needsContextJoiner(context.changedText, context.afterContext)" in source
    assert "{context.afterContext ? <span> {context.afterContext}</span> : null}" not in source
    assert "<summary className=\"cursor-pointer text-sm font-bold text-blue-700\">Context</summary>" not in source
    assert "Show technical diff" not in wording
    assert "Review remaining changes" in draft
    assert "Create draft" in draft
    assert "Send for legal approval" in draft
    assert "onSubmitDraftRevisionForApproval" in draft
    assert "Responsible institution" in draft
    assert "LegalWordingPdfComparison" in draft
    assert "Current wording PDF" not in draft
    assert "Draft wording PDF" not in draft
    assert "Submitted wording PDF" not in draft
    assert "afterTitle={documentTitle}" in draft
    assert "beforeTitle={documentTitle}" in draft
    assert "afterHighlights={afterHighlights}" in draft
    assert "beforeHighlights={beforeHighlights}" in draft
    assert "buildDraftPreviewContent(baseWordingContent, suggestion.hunks)" in draft
    assert "legalWordingPdfFilename(revision.template_code" in draft
    assert "createLegalWordingPdfBlob" in draft
    assert "context.fillText(filename" not in draft
    assert "const isFirstPage = pages.length === 0;" in draft
    assert "if (isFirstPage)" in draft
    assert "let y = isFirstPage ? topMargin + 88 : topMargin;" in draft
    assert 'type: "application/pdf"' in draft
    assert "URL.createObjectURL(blob)" in draft
    assert "<iframe" in draft
    assert "buildPdfFromJpegPages" in draft
    assert "max-h-32 overflow-y-auto whitespace-pre-wrap" not in draft
    assert "highlightPhrase" not in draft


def test_client_claim_wizard_stepper_stays_local_to_claim_flow() -> None:
    wizard_stepper = read_frontend_source("src/components/client/WizardStepper.tsx")

    assert "export function WizardStepper" in wizard_stepper
    assert "rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-4 shadow-sm sm:px-4" in wizard_stepper
    assert "border-emerald-500 bg-emerald-500 text-white" in wizard_stepper
