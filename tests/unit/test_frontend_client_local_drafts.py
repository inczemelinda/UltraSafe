from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_client_pages_source() -> str:
    return (ROOT / "frontend/src/pages/ClientPages.tsx").read_text(
        encoding="utf-8"
    )


def component_source(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_client_quote_and_claim_lists_use_backend_records_only() -> None:
    source = read_client_pages_source()
    quotes_page = component_source(
        source,
        "export function ClientQuotesPage()",
        "export function ClientQuoteDetailPage()",
    )
    claims_page = component_source(
        source,
        "export function ClientClaimsPage()",
        "export function NewClaimPage()",
    )

    assert "mergeSavedQuoteDraft" not in source
    assert "mergeSavedClaimDraft" not in source
    assert "buildDraftQuote" not in source
    assert "buildDraftClaim" not in source
    assert "setQuotes(items);" in quotes_page
    assert "setClaims(items);" in claims_page
    assert 'data={quotes}' in quotes_page
    assert 'data={claims}' in claims_page
    assert 'getRowHref={(item) => `/client/quotes/${item.id}`}' in quotes_page
    assert 'getRowHref={(item) => `/client/claims/${item.id}`}' in claims_page


def test_local_drafts_are_displayed_in_a_separate_unsent_section() -> None:
    source = read_client_pages_source()
    draft_section = component_source(
        source,
        "function LocalDraftsSection",
        "function numberValue",
    )

    assert "LocalDraftsSection" in source
    assert "Saved on this device" in draft_section
    assert "Local draft" in draft_section
    assert "Not submitted" in source
    assert 'ariaLabel="Local quote drafts"' in source
    assert 'ariaLabel="Local claim drafts"' in source
    assert 'href: "/client/quote/new"' in source
    assert 'href: "/client/claims/new"' in source


def test_local_draft_summaries_do_not_display_fake_backend_ids() -> None:
    source = read_client_pages_source()
    quote_summary = component_source(
        source,
        "function buildLocalQuoteDraftSummary",
        "function buildLocalClaimDraftSummary",
    )
    claim_summary = component_source(
        source,
        "function buildLocalClaimDraftSummary",
        "function loadVisibleQuoteDraftSummary",
    )

    assert 'id: "local-quote-draft"' in quote_summary
    assert 'id: "local-claim-draft"' in claim_summary
    assert "title: saved.id" not in quote_summary
    assert "description: saved.id" not in quote_summary
    assert "title: saved.id" not in claim_summary
    assert "description: saved.id" not in claim_summary


def test_saved_quote_drafts_do_not_restore_legacy_contact_identity() -> None:
    source = read_client_pages_source()
    hydrate_quote = component_source(
        source,
        "function hydrateQuoteDraft",
        "function hydrateClaimDraft",
    )

    assert "fullName: defaults.fullName" in hydrate_quote
    assert "email: defaults.email" in hydrate_quote
    assert "phone: defaults.phone" in hydrate_quote
    assert "nationalId: defaults.nationalId" in hydrate_quote
    assert hydrate_quote.index("...savedDraft") < hydrate_quote.index(
        "fullName: defaults.fullName"
    )


def test_successful_backend_submission_clears_local_drafts_after_create() -> None:
    source = read_client_pages_source()
    quote_page = component_source(
        source,
        "export function NewQuotePage()",
        "export function ClientQuotesPage()",
    )
    claim_page = component_source(
        source,
        "export function NewClaimPage()",
        "export function ClientClaimDetailPage()",
    )
    quote_submit = component_source(
        quote_page,
        "async function submit()",
        "if (requiresProfileCompletion(user))",
    )
    claim_submit = component_source(
        claim_page,
        "async function submitClaim()",
        "return (",
    )

    assert quote_submit.index("const quote = await createQuote(draft);") < quote_submit.index(
        "clearQuoteFormDraft(user?.id);"
    )
    assert "showToast(errorMessage(error, \"Quote submission failed. Please try again.\"), \"error\");" in quote_submit
    assert claim_submit.index("const createdClaim = await createClaim({") < claim_submit.index(
        "clearClaimFormDraft(user?.id);"
    )
    assert claim_submit.index("clearClaimFormDraft(user?.id);") < claim_submit.index(
        "await uploadClaimAttachments("
    )
