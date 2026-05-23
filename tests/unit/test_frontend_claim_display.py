from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_frontend_source(relative_path: str) -> str:
    return (ROOT / "frontend" / relative_path).read_text(encoding="utf-8")


def read_styles_source() -> str:
    return (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")


def test_claim_display_helper_prefers_backend_display_fields_then_internal_id() -> None:
    source = read_frontend_source("src/utils/claimDisplay.ts")

    assert "claim?.displayClaimId" in source
    assert "claim?.claimNumber" in source
    assert "claim?.claimReference" in source
    assert "claim?.publicId" in source
    assert "claim?.externalId" in source
    assert "cleanDisplayIdentifier(claim?.id)" in source
    assert "isUuidIdentifier(cleaned)" in source
    assert '"Claim reference pending"' in source


def test_backend_claim_mapper_keeps_request_id_internal_and_maps_claim_data_display_id() -> None:
    source = read_frontend_source("src/services/backend/claimService.ts")

    assert "id: record.request_id" in source
    assert "claimData.claim_id" in source
    assert "displayClaimId: displayClaimId || undefined" in source


def test_backend_claim_mapper_matches_extracted_documents_by_attachment_identity() -> None:
    source = read_frontend_source("src/services/backend/claimService.ts")

    assert "extractedDocumentsByAttachmentIdentity(reviewView)" in source
    assert "extractedDocumentForAttachment(" in source
    assert 'identityKey("attachment_id", metadata.attachment_id)' in source
    assert 'identityKey("storage_key", metadata.storage_key)' in source
    assert 'identityKey("file_url", attachment.file_url || fileUrl)' in source
    assert "byUniqueFilename" in source
    assert "extracted_text: extractedText" in source
    assert "extractedDocumentsByFilename" not in source


def test_claim_document_type_preserves_png_incident_photos() -> None:
    backend_source = read_frontend_source("src/services/backend/claimService.ts")
    mock_source = read_frontend_source("src/services/mock/claimService.ts")

    assert "documentType(fileName, label, attachment.content_type)" in backend_source
    assert 'if (extension === "JPEG") return "JPG";' in backend_source
    assert '["PDF", "DOCX", "JPG", "PNG", "ZIP"]' in backend_source
    assert 'normalizedContentType.includes("png")' in backend_source
    assert "documentType(attachment.file_name, String(attachment.metadata?.label || \"\"), attachment.content_type)" in mock_source
    assert "type: documentType(fileName, label)" in mock_source
    assert 'normalizedContentType.includes("png")' in mock_source


def test_employee_claim_header_and_details_use_same_claim_display_identifier() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")

    assert '<ClaimMetadataPill label="Claim ID" value={getClaimDisplayIdentifier(claim)} />' in source
    assert '["Claim ID", getClaimDisplayIdentifier(claim)]' in source
    assert "to={`/employee/claims/${claimId}/${step.id}`}" in source
    assert "getLatestClaimReview(claimId)" in source


def test_employee_claim_details_link_to_contract_detail() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    details_source = source[
        source.index("function ClaimDetailsTab"):
        source.index("function isVisibleClientLegalDocument")
    ]

    assert '["Contract", <ClaimContractDetailsLink claim={claim} />]' in details_source
    assert "function ClaimContractDetailsLink" in details_source
    assert "getClaimContractDisplayIdentifier(claim)" in details_source
    assert "to={`/contracts/${encodeURIComponent(claim.contractId)}`}" in details_source


def test_employee_claims_queue_does_not_render_score_column() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    queue_source = source[
        source.index("export function EmployeeClaimsPage()"):
        source.index("interface ClaimQueueFiltersState")
    ]

    assert '{ header: "Score"' not in queue_source
    assert "ScoreBadge" not in queue_source


def test_employee_claim_detail_starts_review_for_submitted_claim_on_open() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    detail_source = source[
        source.index("export function EmployeeClaimDetailPage()"):
        source.index("if (claimLoading)")
    ]

    assert "startClaimReview" in detail_source
    assert 'loadedClaim.status === "submitted"' in detail_source
    assert detail_source.index("await startClaimReview(claimId)") < detail_source.index("setClaim(loadedClaim)")


def test_employee_claim_detail_header_keeps_back_button_without_status_badges() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    detail_header_source = source[
        source.index("export function EmployeeClaimDetailPage()"):
        source.index("<ClaimWorkspaceTabs")
    ]

    assert "Back to claims" in detail_header_source
    assert "reviewStatus" not in detail_header_source
    assert "<Badge" not in detail_header_source
    assert "claimReviewStatus" not in source


def test_employee_claim_review_tabs_match_legal_review_tab_styling() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    tabs_source = source[
        source.index("function ClaimWorkspaceTabs"):
        source.index("function claimReviewTabId")
    ]

    assert 'aria-label="Claim review tabs"' in tabs_source
    assert "flex h-12 shrink-0 items-end overflow-y-hidden border-b border-slate-200 bg-slate-50/80 px-5 pt-2 sm:px-6" in tabs_source
    assert "min-w-0 max-w-full overflow-x-auto overflow-y-hidden pb-px scrollbar-none" in tabs_source
    assert "inline-flex min-w-max items-end gap-1" in tabs_source
    assert "relative -mb-px inline-flex h-10 items-center justify-center rounded-t-lg border px-4" in tabs_source
    assert "focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-blue-100" in tabs_source
    assert "border-slate-200 border-b-white bg-white font-bold text-blue-800 shadow-sm" in tabs_source
    assert "after:inset-x-4 after:top-0 after:h-0.5 after:rounded-full after:bg-blue-600" in tabs_source
    assert "border-transparent bg-slate-100/70 font-semibold text-slate-600 hover:bg-slate-200/70 hover:text-slate-950" in tabs_source
    assert 'aria-selected={selected ? "true" : undefined}' in tabs_source


def test_employee_claim_details_include_submitted_optional_legal_documents() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    details_source = source[
        source.index("function ClaimDetailsTab"):
        source.index("function isClaimEvidencePhotoLikeClientDocument")
    ]
    evidence_filter_source = source[
        source.index("function isClientLegalProfileDocumentText"):
        source.index("function documentMatchesEvidenceRequirement")
    ]

    assert "buildSubmittedClaimLegalDocuments(claim)" in details_source
    assert "mergeClientLegalDocuments" in details_source
    assert "clientLegalDocumentFromClaimEvidence" in details_source
    assert "`/claims/${claimId}/profile-documents/${profileDocumentId}`" in details_source
    assert "bank_document" in details_source
    assert "land_registry" in details_source
    assert "existing_policy" in details_source
    assert "property ownership" in evidence_filter_source
    assert "bank document" in evidence_filter_source
    assert "land registry" in evidence_filter_source


def test_employee_claim_evidence_hides_extraction_summary_previews() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    extraction_source = source[
        source.index("function claimEvidenceExtractionInfo"):
        source.index("function extractionReviewStatus")
    ]
    row_source = source[
        source.index("function ClaimEvidenceItemRow"):
        source.index("function evidenceUploadTone")
    ]

    assert "metadata.extracted_text" not in extraction_source
    assert "extractedFieldsSummary" not in source
    assert "extractedPreview" not in row_source
    assert "item.extractedText" not in row_source
    assert "function visibleClaimEvidenceFindings" in source
    assert 'normalizeEvidenceText(finding.findingType) !== "document summary"' not in source
    assert '"document summary": "AI analysis"' in source
    assert '"summary / interpretation": "AI analysis"' in source


def test_employee_claim_details_do_not_synthesize_profile_document_rows() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    build_source = source[
        source.index("function buildClientLegalDocuments"):
        source.index("function slugFileName")
    ]

    assert "profile.legal_documents ?? []" in build_source
    assert "filter(hasClientDocumentFile)" in build_source
    assert "national_id" not in build_source
    assert "customer_profile_completion_source" not in build_source
    assert "terms-consent" not in build_source
    assert "id-document" not in build_source


def test_employee_client_document_preview_loads_real_images() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    modal_source = source[
        source.index("function ClientDocumentPreviewModal"):
        source.index("function ClientDocumentPreviewFact")
    ]

    assert "apiBlobRequest(item.file_url)" in modal_source
    assert "previewBlobUrl && imagePreview" in modal_source
    assert "<img alt={item.file_name}" in modal_source
    assert "preview placeholder" not in modal_source


def test_employee_claim_review_tab_header_scrolls_only_horizontally() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    styles = read_styles_source()
    tabs_source = source[
        source.index("function ClaimWorkspaceTabs"):
        source.index("function claimReviewTabId")
    ]

    assert "overflow-x-auto" in tabs_source
    assert "overflow-y-hidden" in tabs_source
    assert "overflow-x-hidden" not in tabs_source
    assert ".scrollbar-none" in styles
    assert "scrollbar-width: none;" in styles
    assert ".scrollbar-none::-webkit-scrollbar" in styles
    assert "display: none;" in styles


def test_employee_layout_keeps_content_scroll_owned_by_page_body() -> None:
    source = read_frontend_source("src/layouts/AppLayouts.tsx")
    employee_layout = source[
        source.index("export function EmployeeLayout()"):
        source.index("function MockDataIndicator")
    ]

    assert "hideEmployeeScrollbar" not in employee_layout
    assert 'className="min-w-0 flex-1 overflow-y-auto"' in employee_layout


def test_client_claim_views_render_display_identifier_but_keep_internal_routes() -> None:
    source = read_frontend_source("src/pages/ClientPages.tsx")

    assert '{ header: "Claim ID", render: (item) => getClaimDisplayIdentifier(item) }' in source
    assert "title={`Claim ${getClaimDisplayIdentifier(claim)}`}" in source
    assert 'getRowHref={(item) => `/client/claims/${item.id}`}' in source
