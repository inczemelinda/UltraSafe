import type {
  ClaimableContract,
  ClaimableContractsResponse,
  Contract,
  ContractDecline,
  ContractConversionResult,
  ContractDetail,
  ContractSummary,
  GeneratedDocument,
  GeneratedDocumentPdfArtifact,
  QuoteContractResolution
} from "../../types";
import { ApiError, apiBlobRequest, apiRequest, resolveApiUrl } from "./http";

export async function getContracts(): Promise<ContractSummary[]> {
  return apiRequest<ContractSummary[]>("/contracts");
}

export async function getMyContracts(): Promise<ContractSummary[]> {
  return apiRequest<ContractSummary[]>("/me/contracts");
}

export async function getClaimableContracts(): Promise<ClaimableContract[]> {
  const response = await apiRequest<ClaimableContractsResponse>("/me/claimable-contracts");
  return response.items;
}

export async function getContract(contractId: string): Promise<ContractDetail> {
  return apiRequest<ContractDetail>(`/contracts/${encodeURIComponent(contractId)}`);
}

export async function getMyContract(contractId: string): Promise<ContractDetail> {
  return apiRequest<ContractDetail>(`/me/contracts/${encodeURIComponent(contractId)}`);
}

export async function declineMyContract(
  contractId: string,
  reason?: string
): Promise<ContractDecline> {
  return apiRequest<ContractDecline>(
    `/me/contracts/${encodeURIComponent(contractId)}/decline`,
    {
      method: "POST",
      body: reason?.trim() ? { reason: reason.trim() } : {}
    }
  );
}

type QuoteContractRequestOptions = {
  clientScoped?: boolean;
};

function quoteContractPath(quoteId: string, options: QuoteContractRequestOptions = {}) {
  const prefix = options.clientScoped ? "/me/quotes" : "/quotes";
  return `${prefix}/${encodeURIComponent(quoteId)}/contract`;
}

export async function resolveQuoteContract(
  quoteId: string,
  options: QuoteContractRequestOptions = {}
): Promise<QuoteContractResolution> {
  return apiRequest<QuoteContractResolution>(quoteContractPath(quoteId, options));
}

export async function convertQuoteToContract(
  quoteId: string,
  options: QuoteContractRequestOptions = {}
): Promise<ContractConversionResult> {
  return apiRequest<ContractConversionResult>(quoteContractPath(quoteId, options), {
    method: "POST"
  });
}

export async function generateContractDocument(contractId: string): Promise<GeneratedDocument> {
  return apiRequest<GeneratedDocument>(`/contracts/${encodeURIComponent(contractId)}/generated-documents`, {
    method: "POST"
  });
}

export async function getLatestContractDocument(contractId: string): Promise<GeneratedDocument | undefined> {
  try {
    return await apiRequest<GeneratedDocument>(`/contracts/${encodeURIComponent(contractId)}/generated-documents/latest`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return undefined;
    throw error;
  }
}

export async function getLatestMyContractDocument(contractId: string): Promise<GeneratedDocument | undefined> {
  try {
    return await apiRequest<GeneratedDocument>(`/me/contracts/${encodeURIComponent(contractId)}/generated-documents/latest`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return undefined;
    throw error;
  }
}

export async function getGeneratedDocument(documentId: number): Promise<GeneratedDocument> {
  return apiRequest<GeneratedDocument>(`/generated-documents/${documentId}`);
}

export async function createGeneratedDocumentPdf(
  documentId: number,
  options: { clientScoped?: boolean } = {}
): Promise<GeneratedDocumentPdfArtifact> {
  const prefix = options.clientScoped ? "/me/generated-documents" : "/generated-documents";
  return apiRequest<GeneratedDocumentPdfArtifact>(`${prefix}/${documentId}/pdf`, {
    method: "POST"
  });
}

export function getGeneratedDocumentPdfUrl(documentId: number): string {
  return resolveApiUrl(`/generated-documents/${documentId}/pdf`) ?? "";
}

export async function downloadGeneratedDocumentPdf(
  documentId: number,
  options: { clientScoped?: boolean } = {}
): Promise<{ blob: Blob; filename?: string }> {
  const prefix = options.clientScoped ? "/me/generated-documents" : "/generated-documents";
  return apiBlobRequest(`${prefix}/${documentId}/pdf`);
}

export async function getAllContracts(): Promise<Contract[]> {
  const contracts = await getContracts();
  return contracts.map(toLegacyContract);
}

export async function getClientContracts(clientId: string): Promise<Contract[]> {
  const contracts = await getContracts();
  return contracts
    .filter((contract) => String(contract.customer?.id ?? "") === clientId)
    .map(toLegacyContract);
}

export async function getContractById(contractId: string): Promise<Contract | undefined> {
  try {
    return toLegacyContract(await getContract(contractId));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return undefined;
    throw error;
  }
}

function toLegacyContract(contract: ContractSummary): Contract {
  const pricing = contract.pricing;
  const asset = contract.asset;
  const customer = contract.customer;
  const coverageAmount = numberValue(asset?.declared_value);
  const premium = numberValue(pricing?.final_premium_ron);
  return {
    id: contract.id,
    quoteId: contract.source_quote_request_id ?? "",
    clientId: String(customer?.id ?? contract.source_quote_request_id ?? contract.id),
    clientName: customer?.full_name ?? "Unknown client",
    propertyAddress: asset?.address?.full_text ?? "Unknown property",
    coverageAmount,
    premium,
    status: normalizeContractStatus(contract.status),
    generatedAt: contract.created_at,
    policyPeriodStart: contract.effective_date,
    policyPeriodEnd: contract.expiration_date,
    limits: [],
    documentText: ""
  };
}

function normalizeContractStatus(status: string): Contract["status"] {
  if (status === "draft" || status === "generated" || status === "issued" || status === "active" || status === "expired" || status === "declined") {
    return status;
  }
  return "draft";
}

function numberValue(value: number | string | null | undefined) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

