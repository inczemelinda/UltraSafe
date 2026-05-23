import { mockContracts } from "../../data/mockContracts";
import { mockQuotes } from "../../data/mockQuotes";
import type {
  ClaimableContract,
  Contract,
  ContractDecline,
  ContractConversionResult,
  ContractDetail,
  ContractSummary,
  GeneratedDocument,
  GeneratedDocumentPdfArtifact,
  Quote,
  QuoteContractResolution
} from "../../types";
import { getQuotePremium } from "../../utils/quotePricing";
import { readStoredAuthUser } from "../authSession";
import { delay, readStored, today, writeStored } from "../storage";

const contractsKey = "ultrasafe_contracts_v3";
const quotesKey = "ultrasafe_quotes_v3";
const MOCK_CLAIMABLE_CONTRACT_STATUSES = new Set(["issued", "generated", "active"]);

function buildMockContractFromQuote(quote: Quote): Contract {
  return {
    id: `C-${new Date().getFullYear()}-${String(Date.now()).slice(-3)}`,
    quoteId: quote.id,
    clientId: quote.clientId,
    clientName: quote.clientName,
    propertyAddress: quote.propertyAddress,
    coverageAmount: quote.coverageAmount,
    premium: getQuotePremium(quote),
    status: "generated",
    generatedAt: today(),
    policyPeriodStart: today(),
    policyPeriodEnd: `${new Date().getFullYear() + 1}-${today().slice(5)}`,
    limits: [],
    documentText: "Generated document text is loaded from the generated document service."
  };
}

async function createMockContractFromQuote(quote: Quote): Promise<Contract> {
  if (!isContractCandidate(quote)) {
    throw new Error("Only accepted quotes can generate contracts.");
  }
  const contracts = readStored(contractsKey, mockContracts);
  const existing = contracts.find((contract) => contract.quoteId === quote.id);
  if (existing) return delay(existing);

  const contract = buildMockContractFromQuote(quote);
  writeStored(contractsKey, [contract, ...contracts]);
  return delay(contract);
}

export async function publishMockApprovedQuoteContract(quote: Quote): Promise<Contract> {
  return createMockContractFromQuote(quote);
}

export function markMockContractIssuedForQuote(quoteId: string) {
  const contracts = readStored(contractsKey, mockContracts);
  writeStored(
    contractsKey,
    contracts.map((contract) =>
      contract.quoteId === quoteId ? { ...contract, status: "issued" } : contract
    )
  );
}

export async function getClientContracts(clientId: string): Promise<Contract[]> {
  return delay(readStored(contractsKey, mockContracts).filter((contract) => contract.clientId === clientId));
}

export async function getAllContracts(): Promise<Contract[]> {
  return delay(readStored(contractsKey, mockContracts));
}

export async function getContractById(contractId: string): Promise<Contract | undefined> {
  return delay(
    readStored(contractsKey, mockContracts).find(
      (contract) => contract.id === contractId || canonicalMockContractId(contract) === contractId
    )
  );
}

export async function getContracts(): Promise<ContractSummary[]> {
  return delay(readStored(contractsKey, mockContracts).map(toContractDetail));
}

export async function getMyContracts(): Promise<ContractSummary[]> {
  const user = readStoredAuthUser();
  const clientId = user?.id ?? "client-001";
  return delay(
    readStored(contractsKey, mockContracts)
      .filter((contract) => contract.clientId === clientId)
      .map(toContractDetail)
  );
}

export async function getClaimableContracts(): Promise<ClaimableContract[]> {
  const user = readStoredAuthUser();
  const clientId = user?.id ?? "client-001";
  return delay(
    readStored(contractsKey, mockContracts)
      .filter((contract) => contract.clientId === clientId)
      .filter((contract) => MOCK_CLAIMABLE_CONTRACT_STATUSES.has(contract.status))
      .filter((contract) => !contract.policyPeriodEnd || contract.policyPeriodEnd >= today())
      .map(toClaimableContract)
  );
}

export async function getContract(contractId: string): Promise<ContractDetail> {
  const contract = readStored(contractsKey, mockContracts).find(
    (item) => item.id === contractId || canonicalMockContractId(item) === contractId
  );
  if (!contract) throw new Error("Contract not found.");
  return delay(toContractDetail(contract));
}

export async function getMyContract(contractId: string): Promise<ContractDetail> {
  const contracts = await getMyContracts();
  const contract = contracts.find((item) => item.id === contractId || item.contract_number === contractId);
  if (!contract) throw new Error("Contract not found.");
  return delay(contract);
}

export async function declineMyContract(
  contractId: string,
  reason?: string
): Promise<ContractDecline> {
  const contracts = readStored(contractsKey, mockContracts);
  const updatedContracts = contracts.map((contract) =>
    contract.id === contractId || canonicalMockContractId(contract) === contractId
      ? { ...contract, status: "declined" as const }
      : contract
  );
  writeStored(contractsKey, updatedContracts);
  const declinedContract = updatedContracts.find(
    (contract) => contract.id === contractId || canonicalMockContractId(contract) === contractId
  );
  if (!declinedContract) throw new Error("Contract not found.");
  return delay({
    id: Date.now(),
    contract_id: canonicalMockContractId(declinedContract),
    source_quote_request_id: declinedContract.quoteId,
    declined_by_auth_user_id: null,
    declined_by_customer_id: 1,
    reason: reason?.trim() || null,
    declined_at: new Date().toISOString(),
    metadata: {}
  });
}

type QuoteContractRequestOptions = {
  clientScoped?: boolean;
};

export async function resolveQuoteContract(
  quoteId: string,
  _options: QuoteContractRequestOptions = {}
): Promise<QuoteContractResolution> {
  const contract = readStored(contractsKey, mockContracts).find((item) => item.quoteId === quoteId || item.id === `C-${quoteId}`);
  if (contract) {
    const detail = toContractDetail(contract);
    return delay({
      quote_id: quoteId,
      already_converted: true,
      conversion_status: "converted",
      contract_id: detail.id,
      contract: detail,
      validation: { can_convert: false, blocking_errors: [], warnings: [] }
    });
  }
  const quote = readStored(quotesKey, mockQuotes).find((item) => item.id === quoteId);
  const canConvert = Boolean(quote && isContractCandidate(quote));
  return delay({
    quote_id: quoteId,
    already_converted: false,
    conversion_status: canConvert ? "eligible" : "blocked",
    validation: {
      can_convert: canConvert,
      blocking_errors: canConvert
        ? []
        : [{ code: "MOCK_CONTRACT_NOT_READY", message: "No converted contract is available for this quote yet." }],
      warnings: []
    }
  });
}

export async function convertQuoteToContract(
  quoteId: string,
  options: QuoteContractRequestOptions = {}
): Promise<ContractConversionResult> {
  const resolution = await resolveQuoteContract(quoteId, options);
  if (resolution.contract) {
    return {
      quote_id: quoteId,
      result: "already_exists",
      contract_id: resolution.contract_id,
      contract: resolution.contract,
      validation: resolution.validation
    };
  }
  const quote = readStored(quotesKey, mockQuotes).find((item) => item.id === quoteId);
  if (quote && resolution.validation.can_convert) {
    const contract = await createMockContractFromQuote(quote);
    const detail = toContractDetail(contract);
    return {
      quote_id: quoteId,
      result: "created",
      contract_id: detail.id,
      contract: detail,
      validation: { can_convert: true, blocking_errors: [], warnings: [] }
    };
  }
  return {
    quote_id: quoteId,
    result: "blocked",
    contract_id: resolution.contract_id,
    contract: resolution.contract,
    validation: resolution.validation
  };
}

export async function generateContractDocument(contractId: string): Promise<GeneratedDocument> {
  const contract = await getContract(contractId);
  return delay(toGeneratedDocument(contract));
}

export async function getLatestContractDocument(contractId: string): Promise<GeneratedDocument | undefined> {
  const contract = await getContract(contractId);
  return delay(toGeneratedDocument(contract));
}

export async function getLatestMyContractDocument(contractId: string): Promise<GeneratedDocument | undefined> {
  const contract = await getMyContract(contractId);
  return delay(toGeneratedDocument(contract));
}

export async function getGeneratedDocument(documentId: number): Promise<GeneratedDocument> {
  const contracts = await getContracts();
  const contract = contracts[0];
  if (!contract) throw new Error("Generated document not found.");
  return delay(toGeneratedDocument(contract, documentId));
}

export async function createGeneratedDocumentPdf(
  documentId: number,
  _options: { clientScoped?: boolean } = {}
): Promise<GeneratedDocumentPdfArtifact> {
  const contractId = mockContracts[0] ? canonicalMockContractId(mockContracts[0]) : "00000000-0000-4000-8000-000000000000";
  return delay({
    document_id: documentId,
    contract_id: contractId,
    pdf_storage_key: `mock-contract-${contractId}.pdf`,
    pdf_content_hash: "mock-pdf-hash",
    source_content_hash: "mock-source-hash",
    pdf_generated_at: new Date().toISOString(),
    status: "ready",
    filename: `mock-contract-${contractId}.pdf`
  });
}

export function getGeneratedDocumentPdfUrl(documentId: number): string {
  return `#mock-contract-${documentId}.pdf`;
}

export async function downloadGeneratedDocumentPdf(
  documentId: number,
  _options: { clientScoped?: boolean } = {}
): Promise<{ blob: Blob; filename?: string }> {
  const contractId = mockContracts[0] ? canonicalMockContractId(mockContracts[0]) : "00000000-0000-4000-8000-000000000000";
  return delay({
    blob: new Blob([`Mock PDF ${documentId}`], { type: "application/pdf" }),
    filename: `mock-contract-${contractId}.pdf`
  });
}

function isContractCandidate(quote: Quote) {
  return (
    quote.status === "approved" ||
    quote.status === "accepted_by_client" ||
    quote.status === "contract_generated"
  );
}

function toContractDetail(contract: Contract): ContractDetail {
  const displayId = mockContractDisplayId(contract);
  return {
    id: canonicalMockContractId(contract),
    contract_number: contract.id,
    display_id: displayId,
    document_type: "insurance_contract",
    document_version: "mock",
    status: contract.status,
    source_quote_request_id: contract.quoteId,
    source_quote_id: contract.quoteId,
    source_quote_document_id: null,
    issue_date: contract.generatedAt,
    effective_date: contract.policyPeriodStart,
    expiration_date: contract.policyPeriodEnd,
    jurisdiction: "Romania",
    governing_law: "Mock",
    currency: "RON",
    created_at: contract.generatedAt,
    updated_at: contract.generatedAt,
    customer: {
      id: 1,
      type: "individual",
      full_name: contract.clientName,
      email: "mock@example.test",
      phone: "+40000000000",
      address: null
    },
    asset: {
      id: 1,
      asset_type: "Property",
      usage_type: "Mock",
      construction_type: "Mock",
      year_built: 2000,
      area_sqm: 0,
      declared_value: contract.coverageAmount,
      occupancy: "Mock",
      previous_claims_count: 0,
      address: {
        country: "Romania",
        county: "Mock",
        city: "Mock",
        street: contract.propertyAddress,
        number: "N/A",
        postal_code: "N/A",
        full_text: contract.propertyAddress
      }
    },
    pricing: {
      base_premium_ron: contract.premium,
      final_premium_ron: contract.premium,
      currency: "RON",
      payment_plan_type: "annual",
      installments: 1
    }
  };
}

function toClaimableContract(contract: Contract): ClaimableContract {
  const displayId = mockContractDisplayId(contract);
  return {
    contract_id: contract.id,
    contract_number: contract.id,
    display_id: displayId,
    policy_number: contract.id,
    status: contract.status,
    effective_date: contract.policyPeriodStart,
    expiration_date: contract.policyPeriodEnd,
    insured_asset_id: contract.id,
    address: {
      country: "Romania",
      county: "Mock",
      city: "Mock",
      street: contract.propertyAddress,
      number: "N/A",
      postal_code: "N/A",
      full_text: contract.propertyAddress
    },
    coverage_amount: contract.coverageAmount
  };
}

function mockContractDisplayId(contract: Contract) {
  return `MOCK-${contract.clientName.trim().replace(/\s+/g, "_")}-${contract.id}`;
}

function canonicalMockContractId(contract: Contract) {
  const source = `${contract.id}:${contract.quoteId}`;
  let hash = 0;
  for (let index = 0; index < source.length; index += 1) {
    hash = (hash * 31 + source.charCodeAt(index)) >>> 0;
  }
  const prefix = hash.toString(16).padStart(8, "0");
  return `${prefix}-0000-4000-8000-${prefix.padEnd(12, "0")}`;
}

function toGeneratedDocument(contract: ContractDetail, id = 1): GeneratedDocument {
  return {
    id,
    contract_id: contract.id,
    document_type: contract.document_type,
    template_id: 1,
    template_code: "MOCK",
    template_version: "mock",
    template_version_hash: "mock-template-hash",
    rendered_text: `Contract PDF\n\nClient: ${contract.customer?.full_name ?? "Unknown client"}\n\nDocument content is generated by the backend in local mode.`,
    payload_snapshot: {},
    generation_metadata: {},
    content_hash: "mock-content-hash",
    created_at: contract.created_at,
    updated_at: contract.updated_at,
    status: "success"
  };
}


