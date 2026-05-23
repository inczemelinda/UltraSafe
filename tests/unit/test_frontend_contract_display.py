from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_frontend_source(relative_path: str) -> str:
    return (ROOT / "frontend" / relative_path).read_text(encoding="utf-8")


def test_contract_display_helper_uses_display_id_then_human_format_then_uuid() -> None:
    source = read_frontend_source("src/utils/contractDisplay.ts")

    assert "contract?.display_id" in source
    assert "buildContractDisplayIdentifier" in source
    assert "isUuidIdentifier(cleaned)" in source
    assert "legalNameDisplayPart(legalName)" in source
    assert 'replace(/\\s+/g, "_")' in source
    assert "return `${template}-${name}-${differentiator}`;" in source
    assert "cleanIdentifier(contract?.id)" in source


def test_contract_status_helper_uses_customer_lifecycle_labels() -> None:
    source = read_frontend_source("src/utils/contractDisplay.ts")

    assert "export type ContractLifecycleDisplayStatus =" in source
    assert '| "awaiting_client_signing"' in source
    assert '| "issued"' in source
    assert '| "signed"' in source
    assert '| "declined"' in source
    assert 'if (status === "generated" || status === "awaiting_client_signing") return "awaiting_client_signing";' in source
    assert 'if (status === "declined") return "declined";' in source
    assert 'if (status === "issued" || status === "active") return "signed";' in source
    assert 'return "issued";' in source
    assert 'if (displayStatus === "awaiting_client_signing") return "Awaiting client signing";' in source
    assert 'if (displayStatus === "signed") return "Signed";' in source
    assert 'if (displayStatus === "declined") return "Declined";' in source
    assert 'return "Issued";' in source


def test_client_contract_screens_render_display_identifier_but_keep_uuid_loading() -> None:
    source = read_frontend_source("src/pages/ClientPages.tsx")
    contract_view = source.split("function ContractView", 1)[1].split(
        "function ClientContractSummaryDetails",
        1,
    )[0]
    contract_detail_page = source.split("export function ClientContractDetailPage()", 1)[
        1
    ].split("export function ClientClaimsPage()", 1)[0]
    claim_step = source.split("function ClaimStep", 1)[1]

    assert "getContractDisplayIdentifier(contract)" in contract_view
    assert "contract.contract_number || contract.id" not in contract_view
    assert "const { contractId } = useParams();" in contract_detail_page
    assert "const found = await getMyContract(contractId);" in contract_detail_page
    assert "getLatestMyContractDocument(found.id)" in contract_detail_page
    assert "canCreatePdf" in contract_view
    assert "clientScoped" in contract_view
    assert "ensureLatestPdf" in contract_view
    assert "getContractDisplayIdentifier(selectedContract)" in claim_step
    assert "options={claimableContracts.map((contract) => [contract.contract_id, claimableOptionLabel(contract)])}" in claim_step


def test_pdf_viewer_uses_client_scoped_pdf_creation_when_needed() -> None:
    pdf_viewer = read_frontend_source("src/components/GeneratedDocumentPdfViewer.tsx")
    backend_service = read_frontend_source("src/services/backend/contractService.ts")

    assert "createGeneratedDocumentPdf(document.id, { clientScoped })" in pdf_viewer
    assert 'const prefix = options.clientScoped ? "/me/generated-documents" : "/generated-documents";' in backend_service
    assert "`${prefix}/${documentId}/pdf`" in backend_service


def test_employee_contract_and_claim_screens_render_display_identifier() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")

    assert "render: (item) => getContractDisplayIdentifier(item)" in source
    assert "render: (item) => <StatusBadge status={getContractLifecycleStatusLabel(item.status)} />" in source
    assert 'const contractStatusOptions: ContractLifecycleDisplayStatus[] = ["awaiting_client_signing", "issued", "signed", "declined"];' in source
    assert "getContractDisplayIdentifier(contract)" in source
    assert "getContractLifecycleDisplayStatus(contract.status) !== filters.status" in source
    assert "title={`Contract ${getContractDisplayIdentifier(contract)}`}" in source
    assert '["Contract display ID", getContractDisplayIdentifier(contract)]' in source
    assert '["Status", <StatusBadge status={getContractLifecycleStatusLabel(contract.status)} />]' in source
    assert '["Contract", <ClaimContractDetailsLink claim={claim} />]' in source
    assert '["Property", claim.propertyAddress]' in source
    assert '["Contract UUID", contract.id]' in source


def test_employee_contract_detail_hides_internal_pdf_label() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    contract_detail_page = source.split("export function EmployeeContractDetailPage()", 1)[
        1
    ].split("export function EmployeeCustomersPage()", 1)[0]

    assert "<GeneratedDocumentPdfViewer" in contract_detail_page
    assert "showEyebrow={false}" in contract_detail_page
