from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_employee_pages_source() -> str:
    return (ROOT / "frontend/src/pages/EmployeePages.tsx").read_text(
        encoding="utf-8"
    )


def read_quote_service_source() -> str:
    return (ROOT / "frontend/src/services/quoteService.ts").read_text(
        encoding="utf-8"
    )


def component_source(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_employee_quote_detail_renders_decision_audit_panel() -> None:
    source = read_employee_pages_source()
    detail = component_source(
        source,
        "export function EmployeeQuoteDetailPage()",
        "export function EmployeeContractsPage()",
    )

    assert "getQuoteDecisionAudit" in detail
    assert "QuoteDecisionAuditPanel" in detail
    assert "Decision audit" in detail
    assert "No underwriter decision has been recorded for this quote yet." in detail
    assert "setDecisionAudit(auditItems)" in detail


def test_employee_quote_decision_stays_on_detail_and_refreshes_audit() -> None:
    source = read_employee_pages_source()
    detail = component_source(
        source,
        "export function EmployeeQuoteDetailPage()",
        "function QuoteDecisionAuditPanel",
    )

    assert "showToast(\"Quote approved and sent to client.\");\n    navigate" not in detail
    assert "showToast(\"Quote rejected and sent to client.\");\n    navigate" not in detail
    assert "await employeeApproveQuote(quote.id, approvalReason)" in detail
    assert "await employeeRejectQuote(quote.id, reason)" in detail
    assert "setQuote(updatedQuote)" in detail
    assert 'refreshedQuote?.status === "approved"' in detail
    assert 'refreshedQuote?.status === "rejected"' in detail
    assert "Quote approved. The decision was saved." in detail
    assert "Quote rejected. The decision was saved." in detail
    assert "await refreshQuoteDetail()" in detail
    assert "Decision note" in detail
    assert "(optional)" in detail


def test_employee_quote_decision_buttons_show_pending_state() -> None:
    source = read_employee_pages_source()
    detail = component_source(
        source,
        "export function EmployeeQuoteDetailPage()",
        "function QuoteDecisionAuditPanel",
    )

    assert 'const [decisionSubmitting, setDecisionSubmitting]' in detail
    assert 'setDecisionSubmitting("approve")' in detail
    assert 'setDecisionSubmitting("reject")' in detail
    assert 'loading={decisionSubmitting === "approve"}' in detail
    assert 'loading={decisionSubmitting === "reject"}' in detail
    assert "Approving" in detail
    assert "Rejecting" in detail


def test_quote_service_exports_decision_audit_loader() -> None:
    source = read_quote_service_source()

    assert "export const getQuoteDecisionAudit = quoteService.getQuoteDecisionAudit;" in source
