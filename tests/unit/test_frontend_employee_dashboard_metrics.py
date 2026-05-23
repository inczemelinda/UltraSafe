from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_employee_pages_source() -> str:
    return (ROOT / "frontend/src/pages/EmployeePages.tsx").read_text(
        encoding="utf-8"
    )


def component_source(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_employee_dashboard_renders_operational_metrics() -> None:
    source = read_employee_pages_source()
    dashboard = component_source(
        source,
        "export function EmployeeHomePage()",
        "type DashboardPeriod",
    )

    assert "Open quote backlog" in dashboard
    assert "Open claim backlog" in dashboard
    assert "Premium opportunity" in dashboard
    assert "Claim exposure" in dashboard
    assert "Quote decision mix" in dashboard
    assert "Claim outcome mix" in dashboard
    assert "Claim type mix" in dashboard
    assert "Quote review queue" in dashboard
    assert "Claim action queue" in dashboard
    assert "formatCurrency(metrics.premiumOpportunityTotal)" in dashboard
    assert "formatCurrency(metrics.claimExposureTotal)" in dashboard
    assert "buildQuoteAttentionQueue(quotes)" in dashboard
    assert "buildClaimAttentionQueue(claims)" in dashboard


def test_employee_dashboard_metrics_are_derived_from_existing_quote_claim_data() -> None:
    source = read_employee_pages_source()
    metrics = component_source(
        source,
        "function buildDashboardMetrics",
        "function buildDateSeries",
    )

    assert 'new Set<QuoteStatus>(["submitted", "in_review"])' in source
    assert 'new Set<ClaimStatus>(["submitted", "in_review", "inspection_requested"])' in source
    assert 'new Set<QuoteStatus>(["rejected", "declined_by_client"])' in source
    assert "getQuotePremium(quote)" in metrics
    assert "isQuotePricingBackendDriven(quote)" in metrics
    assert "quoteDecisionCount ? approvedQuotes / quoteDecisionCount : 0" in metrics
    assert "Number.isFinite(value) && value > 0" in metrics
    assert "isQuoteRiskBackendDriven(quote)" in metrics
    assert "quote.requiresManualReview === true" in metrics
    assert 'const claimTypeOrder: ClaimType[] = ["Fire", "Water damage", "Theft", "Storm", "Other"]' in source


def test_employee_dashboard_uses_defensive_average_helpers() -> None:
    source = read_employee_pages_source()
    helpers = component_source(
        source,
        "function sumNumbers",
        "function buildDateSeries",
    )

    assert "Number.isFinite(value) ? value : 0" in helpers
    assert "return count ? total / count : 0;" in helpers
    assert "averageQuotePremium: averageNumber(premiumOpportunityTotal, premiumOpportunityQuotes.length)" in source
    assert "averageClaimDamage: averageNumber(claimExposureTotal, claimDamageValues.length)" in source


def test_employee_dashboard_attention_queues_prioritize_actionable_items() -> None:
    source = read_employee_pages_source()
    quote_queue = component_source(
        source,
        "function buildQuoteAttentionQueue",
        "function buildClaimAttentionQueue",
    )
    claim_queue = component_source(
        source,
        "function buildClaimAttentionQueue",
        "function dateTimeMs",
    )
    attention_panel = component_source(
        source,
        "function DashboardAttentionPanel",
        "const openQuoteStatuses",
    )

    assert "openQuoteStatuses.has(quote.status)" in quote_queue
    assert "Number(isHighRiskQuote(second)) - Number(isHighRiskQuote(first))" in quote_queue
    assert "quoteRiskSortScore(first) - quoteRiskSortScore(second)" in quote_queue
    assert "dateTimeMs(second.createdAt) - dateTimeMs(first.createdAt)" in quote_queue
    assert ".slice(0, 5)" in quote_queue
    assert "openClaimStatuses.has(claim.status)" in claim_queue
    assert "second.estimatedDamage - first.estimatedDamage" in claim_queue
    assert "dateTimeMs(second.createdAt) - dateTimeMs(first.createdAt)" in claim_queue
    assert '<Link' in attention_panel
    assert "to={item.href}" in attention_panel
