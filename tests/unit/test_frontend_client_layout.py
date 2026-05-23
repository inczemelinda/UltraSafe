from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_client_pages_source() -> str:
    return (ROOT / "frontend/src/pages/ClientPages.tsx").read_text(
        encoding="utf-8"
    )


def read_ui_source() -> str:
    return (ROOT / "frontend/src/components/ui.tsx").read_text(
        encoding="utf-8"
    )


def read_pdf_viewer_source() -> str:
    return (ROOT / "frontend/src/components/GeneratedDocumentPdfViewer.tsx").read_text(
        encoding="utf-8"
    )


def read_animated_content_source() -> str:
    return (ROOT / "frontend/src/components/react-bits/AnimatedContent.tsx").read_text(
        encoding="utf-8"
    )


def read_animated_reveal_source() -> str:
    return (ROOT / "frontend/src/components/animations/AnimatedCardReveal.tsx").read_text(
        encoding="utf-8"
    )


def component_source(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_client_page_content_matches_account_width_container() -> None:
    source = read_client_pages_source()
    wrapper = component_source(
        source,
        "function ClientPageContent",
        "function ClientLoadingWait",
    )

    assert "mx-auto w-full max-w-5xl" in wrapper


def test_quotes_claims_and_contract_pages_use_centered_content() -> None:
    source = read_client_pages_source()

    quotes = component_source(
        source,
        "export function ClientQuotesPage()",
        "export function ClientQuoteDetailPage()",
    )
    contracts = component_source(
        source,
        "export function ClientContractsPage()",
        "function ContractView",
    )
    claims = component_source(
        source,
        "export function ClientClaimsPage()",
        "export function NewClaimPage()",
    )

    assert "<ClientPageContent className=\"flex min-h-0 flex-1 flex-col\">" in quotes
    assert "<ClientPageContent className=\"flex min-h-0 flex-1 flex-col\">" in contracts
    assert '>Contracts</h1>' in contracts
    assert "<DataTable" in contracts
    assert "<ClientPageContent className=\"flex min-h-0 flex-1 flex-col\">" in claims


def test_client_list_back_actions_live_in_top_cards() -> None:
    source = read_client_pages_source()
    quotes = component_source(
        source,
        "export function ClientQuotesPage()",
        "export function ClientQuoteDetailPage()",
    )
    contracts = component_source(
        source,
        "export function ClientContractsPage()",
        "function ContractView",
    )
    claims = component_source(
        source,
        "export function ClientClaimsPage()",
        "export function NewClaimPage()",
    )

    assert quotes.index('onClick={() => navigate("/client")}') < quotes.index("<DataTable")
    assert contracts.index('onClick={() => navigate("/client")}') < contracts.index("<DataTable")
    assert claims.index('onClick={() => navigate("/client")}') < claims.index("<DataTable")
    assert 'className="mt-6 flex justify-end"' not in quotes
    assert 'className="mt-6 flex justify-end"' not in contracts
    assert 'className="mt-6 flex justify-end"' not in claims


def test_client_list_headers_reveal_before_tables() -> None:
    source = read_client_pages_source()
    pages = [
        component_source(
            source,
            "export function ClientQuotesPage()",
            "export function ClientQuoteDetailPage()",
        ),
        component_source(
            source,
            "export function ClientContractsPage()",
            "function ContractView",
        ),
        component_source(
            source,
            "export function ClientClaimsPage()",
            "export function NewClaimPage()",
        ),
    ]

    assert "const listHeaderRevealDelay = 0;" in source
    assert "const listTableRevealDelay = 0.16;" in source
    for page in pages:
        assert "revealDelay={listHeaderRevealDelay}" in page
        assert "revealDelay={listTableRevealDelay}" in page
        assert page.index("revealDelay={listHeaderRevealDelay}") < page.index("revealDelay={listTableRevealDelay}")


def test_get_a_quote_wizard_uses_centered_client_content() -> None:
    source = read_client_pages_source()
    quote_wizard = component_source(
        source,
        "export function NewQuotePage()",
        "export function ClientQuotesPage()",
    )

    assert "<ClientPageContent>" in quote_wizard
    assert "<PremiumCounter animated breakdown={pricing} value={premium} />" in quote_wizard
    assert '<Panel animated className="mt-4" revealDelay={0.08}>' in quote_wizard
    assert "className=\"mb-5\"" in quote_wizard
    assert quote_wizard.index('<Panel animated className="mt-4" revealDelay={0.08}>') < quote_wizard.index("<WizardStepper")
    assert quote_wizard.index("<WizardStepper") < quote_wizard.index("<QuoteStep")


def test_quote_contact_information_prefills_from_backend_customer_profile() -> None:
    source = read_client_pages_source()
    new_quote_page = component_source(
        source,
        "export function NewQuotePage()",
        "export function ClientQuotesPage()",
    )
    profile_merge = component_source(
        source,
        "function quoteDraftWithCustomerProfile",
        "function claimDraftWithCustomerProfile",
    )

    assert "const { user, setUser } = useAuth();" in new_quote_page
    assert "getMyCustomerProfile()" in new_quote_page
    assert "customerProfileFormFromProfile(profile, user)" in new_quote_page
    assert "appUserWithCustomerProfile(user, profile, profileForm)" in new_quote_page
    assert "setUser(profileUser)" in new_quote_page
    assert "setDraft((current) => quoteDraftWithCustomerProfile(current, profileForm, profileUser, user))" in new_quote_page
    assert 'fullName: profileForm.fullName || profileUser.fullName || ""' in profile_merge
    assert 'phone: profileForm.phone || profileUser.phone || ""' in profile_merge
    assert 'email: profileForm.email || profileUser.email || ""' in profile_merge
    assert 'nationalId: profileForm.nationalId || profileUser.nationalId || ""' in profile_merge
    assert "quoteAddressWithCustomerProfile(draft.address, profileForm, previousUser)" in profile_merge
    assert "fieldFromCustomerProfile(draft.fullName" not in profile_merge


def test_client_cards_use_react_bits_animated_content_reveal() -> None:
    source = read_client_pages_source()
    animated_content = read_animated_content_source()
    animated_reveal = read_animated_reveal_source()

    assert "interface AnimatedContentProps extends React.HTMLAttributes<HTMLDivElement>" in animated_content
    assert "gsap.registerPlugin(ScrollTrigger);" in animated_content
    assert "document.getElementById('snap-main-container')" in animated_content
    assert "const axis = direction === 'horizontal' ? 'x' : 'y';" in animated_content
    assert "once: true" in animated_content
    assert "st.kill();" in animated_content
    assert "tl.kill();" in animated_content
    assert '<div ref={ref} className={className} {...props}>' in animated_content
    assert "prefers-reduced-motion: reduce" in animated_reveal
    assert "disappearAfter=" not in animated_reveal
    assert "duration={1.5}" in animated_reveal
    assert "threshold={0.1}" in animated_reveal
    assert 'ease="power2.out"' in animated_reveal
    assert "staggerCardDelay(index)" in source
    assert "<DataTable\n        animated" in source
    assert "<UploadCard\n                  animated" in source


def test_claim_required_document_upload_cards_are_not_animated() -> None:
    source = read_client_pages_source()
    required_documents = source.split("Claim documents", 1)[1].split(
        "function QuoteStep",
        1,
    )[0]

    assert "requiredClaimDocumentLabels.map((label) =>" in required_documents
    assert "accountDocumentLabels.map((label) =>" in required_documents
    assert "mt-3 space-y-4" in required_documents
    assert "grid gap-2 sm:grid-cols-2 lg:grid-cols-3" in required_documents
    assert 'size="compact"' in required_documents
    assert "<UploadCard" in required_documents
    assert "animated" not in required_documents
    assert "revealDelay" not in required_documents


def test_upload_card_supports_compact_layout() -> None:
    source = read_ui_source()
    upload_card = component_source(
        source,
        "export function UploadCard",
        "function fileToUploadCardFile",
    )

    assert 'size = "default"' in upload_card
    assert 'size?: "default" | "compact"' in upload_card
    assert 'const compact = size === "compact";' in upload_card
    assert 'compact ? "min-h-20" : "min-h-32"' in upload_card
    assert 'compact ? "h-4 w-4" : "h-5 w-5"' in upload_card


def test_claim_required_documents_accept_profile_prefill() -> None:
    source = read_client_pages_source()
    new_claim_page = component_source(
        source,
        "export function NewClaimPage()",
        "export function ClientClaimDetailPage()",
    )
    display_helper = component_source(
        source,
        "function displayFilesForLabel",
        "function flattenSelectedEvidenceFiles",
    )

    assert "listMyProfileDocuments()" in new_claim_page
    assert "evidenceFilesFromProfileDocuments(documents)" in new_claim_page
    assert "metadataFromProfileDocuments(documents)" in new_claim_page
    assert "clearLegacyAccountDocuments(user.id);" in new_claim_page
    assert "profileDocumentAttachmentsForClaim(" in new_claim_page
    assert "loadAccountDocuments" not in source
    assert "saveAccountDocuments" not in source
    assert "hasEvidenceForLabel(evidenceFiles, label)" in new_claim_page
    assert "needs_reselect" not in display_helper


def test_claim_contact_information_prefills_from_backend_customer_profile() -> None:
    source = read_client_pages_source()
    new_claim_page = component_source(
        source,
        "export function NewClaimPage()",
        "export function ClientClaimDetailPage()",
    )
    profile_merge = component_source(
        source,
        "function claimDraftWithCustomerProfile",
        "function clampDraftStep",
    )

    assert "const { user, setUser } = useAuth();" in new_claim_page
    assert "getMyCustomerProfile()" in new_claim_page
    assert "customerProfileFormFromProfile(profile, user)" in new_claim_page
    assert "appUserWithCustomerProfile(user, profile, profileForm)" in new_claim_page
    assert "setUser(profileUser)" in new_claim_page
    assert "setDraft((current) => claimDraftWithCustomerProfile(current, profileUser, user))" in new_claim_page
    assert "fieldFromCustomerProfile(draft.fullName, previousUser?.fullName, profileUser.fullName)" in profile_merge
    assert "fieldFromCustomerProfile(draft.phone, previousUser?.phone, profileUser.phone)" in profile_merge
    assert "fieldFromCustomerProfile(draft.email, previousUser?.email, profileUser.email)" in profile_merge


def test_account_documents_use_backend_profile_document_storage() -> None:
    source = read_client_pages_source()
    account_page = component_source(
        source,
        "export function ClientAccountPage()",
        "function ClaimStep",
    )

    assert "listMyProfileDocuments()" in account_page
    assert "uploadMyProfileDocument({" in account_page
    assert "deleteMyProfileDocument(existing.id)" in account_page
    assert "clearLegacyAccountDocuments(user?.id);" in account_page
    assert "loadAccountDocuments" not in source
    assert "saveAccountDocuments" not in source
    assert "window.localStorage.getItem(legacyAccountDocsKey" not in source
    assert "window.localStorage.setItem(legacyAccountDocsKey" not in source


def test_claim_submission_only_requires_incident_photos() -> None:
    source = read_client_pages_source()
    labels = component_source(
        source,
        "const accountDocumentLabels",
        "function ClientPageContent",
    )
    new_claim_page = component_source(
        source,
        "export function NewClaimPage()",
        "export function ClientClaimDetailPage()",
    )
    required_documents = source.split("Claim documents", 1)[1].split(
        "function QuoteStep",
        1,
    )[0]

    assert 'const requiredClaimDocumentLabels = ["Photos from incident"];' in labels
    assert "const claimDocumentLabels = [...requiredClaimDocumentLabels, ...accountDocumentLabels];" in labels
    assert "requiredClaimDocumentLabels.find((label) => !hasEvidenceForLabel(evidenceFiles, label))" in new_claim_page
    assert "claimDocumentLabels.find((label) => !hasEvidenceForLabel(evidenceFiles, label))" not in new_claim_page
    assert "Incident photos are required. Profile documents are optional and prefilled when available." not in required_documents
    assert "border-l-4 border-blue-500 pl-3" in required_documents
    assert "border-l border-slate-200 pl-3" in required_documents
    assert ">Required</p>" in required_documents
    assert ">Optional</p>" in required_documents
    assert "optional={!isRequiredClaimDocument(label)}" not in required_documents
    assert "isRequiredClaimDocument" not in source
    assert "optional" in required_documents


def test_client_home_curved_loop_sits_on_transparent_hero_background() -> None:
    source = read_client_pages_source()
    home = component_source(
        source,
        "export function ClientHomePage()",
        "export function NewQuotePage()",
    )

    assert "CurvedLoop" in home
    assert 'marqueeText={"\\u00A0\\u00A0\\u00A0\\u00A0\\u00A0you crash it, we cash it!\\u00A0\\u00A0\\u00A0\\u00A0\\u00A0you crash it, we cash it!\\u00A0\\u00A0\\u00A0\\u00A0\\u00A0"}' in home
    assert "clientFirstName(user)" in home
    assert 'const greeting = firstName ? `Welcome back, ${firstName}` : "Welcome back";' in home
    assert "<TextPressure" in home
    assert 'splitBy="words"' in home
    assert 'fontFamily="ClientHeroInter"' in home
    assert 'fontFamily="Inter"' not in home
    assert 'fontSize="clamp(3rem, 8vw, 6rem)"' in home
    assert "lineHeight={0.98}" in home
    assert "singleLine" in home
    assert "singleLineMinFontSize={16}" in home
    assert "w-full whitespace-nowrap" in home
    assert "[text-wrap:balance]" not in home
    assert "Get a quote, report a claim, or find your policy documents" in home
    assert "all from one simple dashboard" not in home
    assert "Start a quote" in home
    assert "Report a claim" in home
    assert "Hello," not in home
    assert "Get a Quote" not in home
    assert "File a Claim" not in home
    assert "generated contract" not in home
    assert "relative min-h-[calc(100vh-5rem)] overflow-hidden" in home
    assert "absolute bottom-0 left-1/2 w-[100vw] max-w-none -translate-x-1/2 overflow-visible" in home
    assert "bg-transparent" in home
    assert "curveAmount={-55}" in home
    assert "[&_svg]:!text-[1.75rem]" in home
    assert "lg:[&_svg]:!text-[3rem]" in home
    assert "interactive={false}" in home
    assert "rounded-lg border border-blue-100 bg-gradient-to-r" not in home
    assert "shadow-inner" not in home


def test_text_pressure_can_preserve_word_spacing() -> None:
    source = (ROOT / "frontend/src/components/react-bits/TextPressure.tsx").read_text(
        encoding="utf-8"
    )

    assert "splitBy?: 'characters' | 'words'" in source
    assert "singleLine?: boolean" in source
    assert "singleLineMinFontSize?: number" in source
    assert "text.trim().split(/\\s+/).filter(Boolean)" in source
    assert "whiteSpace: singleLine ? 'nowrap' : undefined" in source
    assert "className=\"inline-block whitespace-nowrap\"" in source
    assert "i < segments.length - 1 ? ' ' : null" in source
    assert "char === ' ' ? '\\u00A0' : char" in source


def test_client_page_header_uses_account_card_pattern() -> None:
    source = read_ui_source()
    header = component_source(
        source,
        "export function PageHeader",
        "export function Modal",
    )

    assert "rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm" in header
    assert "mb-4" in header
    assert "sm:items-center sm:justify-between" in header
    assert "shrink-0 flex-wrap gap-2 sm:justify-end" in header
    assert "animated?: boolean" in header
    assert "revealDelay?: number" in header
    assert "<AnimatedCardReveal className={headerClassName} delay={revealDelay}>" in header


def test_client_claims_page_animates_page_header() -> None:
    source = read_client_pages_source()
    claims = component_source(
        source,
        "export function ClientClaimsPage()",
        "export function NewClaimPage()",
    )

    assert "<PageHeader" in claims
    assert "animated" in claims
    assert "revealDelay={listHeaderRevealDelay}" in claims
    assert "title=\"Claims\"" in claims


def test_client_nav_uses_plural_contracts_label() -> None:
    source = read_ui_source()
    nav = component_source(
        source,
        "export function ClientNavbar",
        "export function EmployeeNavbar",
    )

    assert '{ label: "Contracts", to: "/client/contracts" }' in nav
    assert '{ label: "Contract", to: "/client/contracts" }' not in nav


def test_account_page_uses_shared_page_header() -> None:
    source = read_client_pages_source()
    account = component_source(
        source,
        "export function ClientAccountPage()",
        "function ClaimStep",
    )

    assert "<PageHeader" in account
    assert 'title="Account"' in account
    assert "Sign Out" in account
    assert 'onClick={() => navigate("/client")}' in account
    assert account.index("Sign Out") < account.index("grid gap-4")
    assert account.index('onClick={() => navigate("/client")}') < account.index("grid gap-4")
    assert 'className="mt-6 flex flex-wrap justify-end gap-3"' not in account
    assert '<Panel className="mb-4 py-3">' not in account


def test_client_contract_detail_centers_whole_contract_layout() -> None:
    source = read_client_pages_source()
    contract_detail = component_source(
        source,
        "export function ClientContractDetailPage()",
        "export function ClientClaimsPage()",
    )

    assert "<ClientPageContent>" in contract_detail
    assert "<ContractView contract={contract} document={document} quote={quote} />" in contract_detail


def test_client_claim_detail_is_centered_and_document_rows_truncate() -> None:
    source = read_client_pages_source()
    claim_detail = component_source(
        source,
        "export function ClientClaimDetailPage()",
        "function ClientClaimDetailGrid",
    )
    document_row = component_source(
        source,
        "function ClientClaimDocumentRow",
        "function formatDocumentMeta",
    )

    assert "<ClientPageContent>" in claim_detail
    assert "lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" in claim_detail
    assert "ClientClaimDocumentRow" in claim_detail
    assert "No uploaded documents." in claim_detail
    assert "min-w-0 flex-1" in document_row
    assert "truncate font-bold" in document_row
    assert "View document" in document_row
    assert 'className="shrink-0' in document_row


def test_client_contracts_page_uses_clickable_list() -> None:
    source = read_client_pages_source()
    contracts_page = component_source(
        source,
        "export function ClientContractsPage()",
        "function ContractView",
    )
    summary = component_source(
        source,
        "function SelectedContractSummary",
        "function ClientContractSummaryDetails",
    )

    assert "getMyContracts()" in contracts_page
    assert "<DataTable" in contracts_page
    assert 'getRowHref={(item) => `/client/contracts/${item.id}`}' in contracts_page
    assert '{ header: "Contract ID", render: (item) => getContractDisplayIdentifier(item) }' in contracts_page
    assert '{ header: "Property Address", render: (item) => contractPropertyAddress(item) }' in contracts_page
    assert '{ header: "Premium", render: (item) => formatCurrency(contractPremium(item)) }' in contracts_page
    assert '{ header: "Status", render: (item) => <ClientContractStatusBadge status={item.status} /> }' in contracts_page
    assert 'onClick={() => navigate("/client")}' in contracts_page
    assert "ContractsWorkspace" not in source
    assert "Contract summary" in summary
    assert "Download selected PDF" not in summary
    assert "Linked quote ID" in summary
    assert "Linked quote status" not in summary
    assert "ClientContractStatusBadge" in summary
    assert "Other contracts" not in source


def test_client_contract_detail_keeps_summary_card() -> None:
    source = read_client_pages_source()
    summary = component_source(
        source,
        "function SelectedContractSummary",
        "function ClientContractSummaryDetails",
    )
    contract_detail = component_source(
        source,
        "export function ClientContractDetailPage()",
        "export function ClientClaimsPage()",
    )

    assert "Contract summary" in summary
    assert "Download selected PDF" not in summary
    assert "Linked quote ID" in summary
    assert "<ContractView contract={contract} document={document} quote={quote} />" in contract_detail
    assert 'className="mt-4 border-emerald-200 bg-emerald-50 text-sm font-semibold text-emerald-700"' not in contract_detail
    assert "acceptance.signer_name" not in contract_detail
    assert '<PrimaryLink to="/client/contracts">Back to Contracts</PrimaryLink>' in contract_detail
    assert "function ClientContractBackAction" not in source


def test_client_contract_viewer_hides_internal_pdf_labels() -> None:
    source = read_client_pages_source()
    pdf_viewer = read_pdf_viewer_source()
    panel = component_source(
        source,
        "function ContractPdfPanel",
        "function SelectedContractSummary",
    )

    assert "showEyebrow?: boolean" in pdf_viewer
    assert "displayFilename?: string" in pdf_viewer
    assert "emptyDescription?: string" in pdf_viewer
    assert "showEyebrow={false}" in panel
    assert "The policy PDF will appear here when it is available." in panel
    assert "contractPdfFilenameLabel" in panel


def test_client_contract_status_uses_customer_facing_label() -> None:
    source = read_client_pages_source()
    status_helper = component_source(
        source,
        "function ClientContractStatusBadge",
        "function contractPremium",
    )

    assert "getContractLifecycleStatusLabel(status)" in status_helper
    assert 'displayStatus === "awaiting_client_signing"' in status_helper
    assert 'displayStatus === "issued"' in status_helper


def test_client_contract_index_no_longer_renders_inline_workspace() -> None:
    source = read_client_pages_source()
    contracts = component_source(
        source,
        "export function ClientContractsPage()",
        "function ContractView",
    )

    assert "ContractPdfPanel" not in contracts
    assert "SelectedContractSummary" not in contracts
    assert "getRowHref" in contracts
