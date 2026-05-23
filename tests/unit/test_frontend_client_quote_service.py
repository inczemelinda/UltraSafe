import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_frontend_source(relative_path: str) -> str:
    return (ROOT / "frontend" / relative_path).read_text(encoding="utf-8")


def test_client_quote_submit_uses_client_owned_backend_routes() -> None:
    source = read_frontend_source("src/services/backend/quoteService.ts")
    create_quote_body = source.split("export async function createQuote", 1)[1].split(
        "export async function getMyQuoteAcceptance",
        1,
    )[0]

    assert 'apiRequest<BackendQuoteRequest>("/me/quotes"' in create_quote_body
    assert "/generate" not in create_quote_body
    assert "getRawQuote(createdId)" not in create_quote_body
    assert "updateRawQuote(createdId" not in create_quote_body


def test_client_quote_wizard_starts_with_coverage_step() -> None:
    source = read_frontend_source("src/pages/ClientPages.tsx")
    step_config = source.split("const quoteStepDefinitions = [", 1)[1].split(
        "] as const;",
        1,
    )[0]
    quote_step = source.split("function QuoteStep", 1)[1].split(
        "function TextInput",
        1,
    )[0]

    assert re.findall(r'id: "([^"]+)"', step_config) == [
        "coverage",
        "propertyType",
        "address",
        "age",
        "size",
        "construction",
        "use",
        "claims",
        "security",
        "contact",
    ]
    assert re.findall(r'label: "([^"]+)"', step_config)[:2] == [
        "Coverage",
        "Property Type",
    ]
    assert "stepId: getQuoteStepId(step)" in source
    assert 'if (!hasValidQuoteCoverageAmount(saved.draft)) return getQuoteStepIndex("coverage");' in source
    assert 'if (currentStepId === "coverage"' in source
    assert '<QuoteStep draft={draft} stepId={currentQuoteStepId}' in source
    assert 'if (stepId === "coverage")' in quote_step
    assert "step === 6" not in quote_step


def test_backend_quote_steps_send_coverage_first() -> None:
    source = read_frontend_source("src/services/backend/quoteService.ts")
    build_steps = source.split("function buildQuoteSteps", 1)[1].split(
        "function toQuote",
        1,
    )[0]

    assert build_steps.index('["coverage_amount", draft.coverageAmount]') < build_steps.index(
        '["property_type", draft.propertyType]'
    )


def test_backend_quote_mapping_requires_authoritative_backend_response() -> None:
    source = read_frontend_source("src/services/backend/quoteService.ts")
    to_quote = source.split("function toQuote", 1)[1].split(
        "function normalizePreviewPricing",
        1,
    )[0]
    backend_risk = source.split("function normalizeBackendRisk", 1)[1].split(
        "function toMockDocument",
        1,
    )[0]

    assert "normalizeBackendRisk(optionalObjectValue(record.risk))" in to_quote
    assert "backendRisk ?? unavailableRisk(record)" in to_quote
    assert "backendPricing ?? unavailablePricing(record)" in to_quote
    assert "backendRisk ?? previewRisk" not in to_quote
    assert "backendPricing ?? previewPricing" not in to_quote
    assert "requiresManualReview: risk.requiresManualReview" in to_quote
    assert "value.requiresManualReview ?? value.requires_manual_review" in backend_risk


def test_backend_quote_payload_sends_frontend_estimates_as_non_binding_context() -> None:
    source = read_frontend_source("src/services/backend/quoteService.ts")
    payload_builder = source.split("function buildCreateQuotePayload", 1)[1].split(
        "function buildQuoteSteps",
        1,
    )[0]

    assert 'source: "frontend_preview_context"' in payload_builder
    assert "binding: false" in payload_builder
    assert "submitted_pricing_estimate: pricingPreview" in payload_builder
    assert "submitted_risk_estimate: riskPreview" in payload_builder
    assert "risk_assessment: riskPreview" not in payload_builder
    assert "pricing: pricingPreview" not in payload_builder


def test_new_quote_page_starts_with_compact_premium_summary() -> None:
    source = read_frontend_source("src/pages/ClientPages.tsx")
    new_quote_page = source.split("export function NewQuotePage()", 1)[1].split(
        "export function ClientQuotesPage()",
        1,
    )[0]

    assert "<PageHeader" not in new_quote_page
    assert "Get a Quote" not in new_quote_page
    assert "We calculate your estimated annual premium as you complete the quote." not in new_quote_page
    assert new_quote_page.index("<PremiumCounter") < new_quote_page.index("<WizardStepper")
    assert 'disabled={step === 0}' not in new_quote_page
    assert 'step === 0 ? navigate("/client") : setStep((current) => Math.max(current - 1, 0))' in new_quote_page


def test_accepted_quote_view_contract_opens_specific_generated_contract() -> None:
    source = read_frontend_source("src/pages/ClientPages.tsx")
    quote_detail = source.split("export function ClientQuoteDetailPage()", 1)[1].split(
        "function QuoteAnswerList",
        1,
    )[0]

    assert "resolveQuoteContract" in source
    assert "convertQuoteToContract" in source
    assert "resolveQuoteContract(quote.id, { clientScoped: true })" in quote_detail
    assert "const result = await convertQuoteToContract(quote.id, { clientScoped: true })" in quote_detail
    assert "if (!contractId) {\n        const result = await convertQuoteToContract" not in quote_detail
    assert "navigate(`/client/contracts/${contractId}`)" in quote_detail
    assert "loading={contractOpening}" in quote_detail
    assert 'to="/client/contracts">View Contract' not in quote_detail


def test_premium_counter_uses_side_by_side_receipt_layout() -> None:
    source = read_frontend_source("src/components/ui.tsx")
    premium_counter = source.split("export function PremiumCounter", 1)[1].split(
        "export function DocumentTextViewer",
        1,
    )[0]

    assert "lg:flex-row" in premium_counter
    assert "lg:w-[460px]" in premium_counter
    assert "tabular-nums" in premium_counter
    assert "Final price is confirmed after backend submission." not in premium_counter
    assert "Increased" not in premium_counter
    assert "Decreased" not in premium_counter
    assert "Annual Premium Estimate" in premium_counter
    assert "Property type adjustment" in premium_counter
    assert "Property age adjustment" in premium_counter
    assert "Property size adjustment" in premium_counter
    assert "Construction adjustment" in premium_counter
    assert "Claims history adjustment" in premium_counter
    assert "Claims surcharge" in premium_counter
    assert "Preview estimate" in premium_counter
