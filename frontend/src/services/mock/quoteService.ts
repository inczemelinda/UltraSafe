import { mockQuotes } from "../../data/mockQuotes";
import type {
  Quote,
  QuoteAcceptance,
  QuoteAcceptanceInput,
  QuoteDecisionAuditRecord,
  QuoteDraft,
  QuoteStatus
} from "../../types";
import { calculatePremiumPreview } from "../../utils/pricing";
import { assessQuoteRiskPreview } from "../../utils/riskRules";
import { readStoredAuthUser } from "../authSession";
import { delay, readStored, today, writeStored } from "../storage";
import {
  markMockContractIssuedForQuote,
  publishMockApprovedQuoteContract
} from "./contractService";

const quotesKey = "ultrasafe_quotes_v3";
const quoteAcceptancesKey = "ultrasafe_quote_acceptances_v1";
const quoteDecisionAuditKey = "ultrasafe_quote_decision_audit_v1";

export async function getClientQuotes(): Promise<Quote[]> {
  const clientId = currentMockClientId();
  return delay(readStored(quotesKey, mockQuotes).filter((quote) => quote.clientId === clientId));
}

export async function getAllQuotes(): Promise<Quote[]> {
  return delay(readStored(quotesKey, mockQuotes));
}

export async function getQuoteById(quoteId: string): Promise<Quote | undefined> {
  return delay(readStored(quotesKey, mockQuotes).find((quote) => quote.id === quoteId));
}

export async function getMyQuoteById(quoteId: string): Promise<Quote | undefined> {
  const clientId = currentMockClientId();
  return delay(
    readStored(quotesKey, mockQuotes).find(
      (quote) => quote.id === quoteId && quote.clientId === clientId
    )
  );
}

export async function createQuote(draft: QuoteDraft): Promise<Quote> {
  const clientId = currentMockClientId();
  if (clientId === "__incomplete_customer_profile__") {
    throw new Error("CUSTOMER_PROFILE_INCOMPLETE");
  }
  const quotes = readStored(quotesKey, mockQuotes);
  const pricing = calculatePremiumPreview(draft);
  const risk = assessQuoteRiskPreview(draft);
  const id = `Q-${new Date().getFullYear()}-${String(quotes.length + 1).padStart(3, "0")}`;
  const fullAddress = [
    draft.address.street,
    draft.address.number,
    draft.address.city,
    draft.address.county
  ]
    .filter(Boolean)
    .join(", ");

  const quote: Quote = {
    id,
    requestId: id,
    clientId,
    clientName: draft.fullName,
    propertyType: draft.propertyType || "Apartment",
    propertyAddress: fullAddress,
    yearBuilt: Number(draft.yearBuilt),
    areaSqm: Number(draft.areaSqm),
    constructionType: draft.constructionType || "Concrete",
    usageType: draft.usageType || "Owner occupied",
    coverageAmount: Number(draft.coverageAmount),
    previousClaimsCount: draft.hadClaims === "Yes" ? Number(draft.previousClaimsCount || 0) : 0,
    securityFeatures: draft.securityFeatures,
    premium: pricing.finalPremium,
    riskScore: risk.riskScore,
    riskReasons: risk.triggeredRules,
    pricing,
    pricingSource: "preview",
    riskSource: "preview",
    riskLevel: risk.riskLevel,
    requiresManualReview: risk.requiresManualReview,
    status: "in_review",
    createdAt: today(),
    updatedAt: today(),
    clientData: {
      type: "individual",
      full_name: draft.fullName,
      national_id: draft.nationalId,
      email: draft.email,
      phone: draft.phone,
      address: fullAddress
    },
    insuredData: {
      asset_type: draft.propertyType || "Apartment",
      usage_type: draft.usageType || "Owner occupied",
      construction_type: draft.constructionType || "Concrete",
      year_built: Number(draft.yearBuilt),
      area_sqm: Number(draft.areaSqm),
      declared_value: Number(draft.coverageAmount),
      occupancy: draft.usageType || "Owner occupied",
      previous_claims_count: draft.hadClaims === "Yes" ? Number(draft.previousClaimsCount || 0) : 0,
      address: {
        ...draft.address,
        full_text: fullAddress
      }
    },
    requestDetails: {
      coverage_amount: Number(draft.coverageAmount),
      security_features: draft.securityFeatures,
      systems_updated: draft.systemsUpdated,
      location_risks: draft.locationRisks,
      high_value_items: draft.highValueItems,
      renovations: draft.renovations,
      long_vacancy: draft.longVacancy
    },
    attachments: []
  };

  writeStored(quotesKey, [quote, ...quotes]);
  return delay(quote);
}

export async function getMyQuoteAcceptance(quoteId: string): Promise<QuoteAcceptance | undefined> {
  const quote = await getMyQuoteById(quoteId);
  if (!quote) return delay(undefined);
  return delay(getStoredQuoteAcceptance(quoteId));
}

export async function getQuoteAcceptance(quoteId: string): Promise<QuoteAcceptance | undefined> {
  return delay(getStoredQuoteAcceptance(quoteId));
}

export async function getQuoteDecisionAudit(quoteId: string): Promise<QuoteDecisionAuditRecord[]> {
  return delay(
    readStored<QuoteDecisionAuditRecord[]>(quoteDecisionAuditKey, []).filter(
      (record) => record.quote_request_id === quoteId
    )
  );
}

export async function acceptQuote(
  quoteId: string,
  acceptanceInput: QuoteAcceptanceInput
): Promise<Quote> {
  const current = getStoredQuote(quoteId);
  if (current.status !== "approved" && current.status !== "accepted_by_client") {
    return delay(current);
  }
  const existing = getStoredQuoteAcceptance(quoteId);
  if (!existing) {
    const acceptances = readStored<QuoteAcceptance[]>(quoteAcceptancesKey, []);
    writeStored(quoteAcceptancesKey, [
      buildQuoteAcceptance(current, acceptanceInput),
      ...acceptances
    ]);
  }
  markMockContractIssuedForQuote(quoteId);
  return updateQuoteStatus(quoteId, "accepted_by_client");
}

export async function declineQuote(quoteId: string): Promise<Quote> {
  const current = getStoredQuote(quoteId);
  if (current.status !== "approved") return delay(current);
  return updateQuoteStatus(quoteId, "declined_by_client");
}

export async function employeeApproveQuote(quoteId: string, reason?: string): Promise<Quote> {
  const current = getStoredQuote(quoteId);
  if (!isEmployeeReviewOpen(current.status)) return delay(current);
  recordMockQuoteDecision(current, "approved", reason);
  const updated = await updateQuoteStatus(quoteId, "approved");
  await publishMockApprovedQuoteContract(updated);
  return updated;
}

export async function employeeRejectQuote(quoteId: string, reason: string): Promise<Quote> {
  const current = getStoredQuote(quoteId);
  if (!isEmployeeReviewOpen(current.status)) return delay(current);
  recordMockQuoteDecision(current, "disapproved", reason);
  return updateQuoteStatus(quoteId, "rejected", reason);
}

export async function updateQuoteStatus(
  quoteId: string,
  status: QuoteStatus,
  rejectionReason?: string
): Promise<Quote> {
  const quotes = readStored(quotesKey, mockQuotes);
  const quote = quotes.find((item) => item.id === quoteId);
  if (!quote) throw new Error("Quote not found");

  const updated: Quote = {
    ...quote,
    status,
    rejectionReason: rejectionReason ?? quote.rejectionReason,
    updatedAt: today()
  };
  writeStored(
    quotesKey,
    quotes.map((item) => (item.id === quoteId ? updated : item))
  );
  return delay(updated);
}

function getStoredQuote(quoteId: string) {
  const quote = readStored(quotesKey, mockQuotes).find((item) => item.id === quoteId);
  if (!quote) throw new Error("Quote not found");
  return quote;
}

export function hasMockQuoteAcceptance(quoteId: string) {
  return Boolean(getStoredQuoteAcceptance(quoteId));
}

function getStoredQuoteAcceptance(quoteId: string) {
  return readStored<QuoteAcceptance[]>(quoteAcceptancesKey, []).find(
    (acceptance) => acceptance.quote_request_id === quoteId
  );
}

function buildQuoteAcceptance(
  quote: Quote,
  acceptanceInput: QuoteAcceptanceInput
): QuoteAcceptance {
  const acceptedAt = new Date().toISOString();
  return {
    id: Date.now(),
    quote_request_id: quote.id,
    quote_document_id: Date.now(),
    accepted_by_auth_user_id: Number(readStoredAuthUser()?.id) || null,
    accepted_by_customer_id: Number(quote.clientId) || 1,
    signer_name: acceptanceInput.signer_name,
    signer_email: acceptanceInput.signer_email,
    signer_role: acceptanceInput.signer_role,
    accepted_at: acceptedAt,
    acceptance_method: "client_portal",
    acceptance_statement: acceptanceInput.acceptance_statement,
    quote_content_hash: `mock-${quote.id}`,
    metadata: { source: "mock" },
    created_at: acceptedAt
  };
}

function recordMockQuoteDecision(
  quote: Quote,
  decisionStatus: "approved" | "disapproved" | "field_review_required",
  reason?: string
) {
  const currentUser = readStoredAuthUser();
  const records = readStored<QuoteDecisionAuditRecord[]>(quoteDecisionAuditKey, []);
  const decidedAt = new Date().toISOString();
  const record: QuoteDecisionAuditRecord = {
    id: Date.now(),
    quote_request_id: quote.id,
    previous_status: quote.status,
    decision_status: decisionStatus,
    reason: reason?.trim() || null,
    decided_by_auth_user_id: Number(currentUser?.id) || null,
    decided_by_name: currentUser?.fullName ?? null,
    decided_by_email: currentUser?.email ?? null,
    decided_at: decidedAt,
    metadata: { source: "mock" }
  };
  writeStored(quoteDecisionAuditKey, [record, ...records]);
}

function isEmployeeReviewOpen(status: QuoteStatus) {
  return status === "submitted" || status === "in_review";
}

function currentMockClientId() {
  const user = readStoredAuthUser();
  if (!user) return "client-001";
  if (!user.customerId || user.requiresCustomerProfileCompletion) {
    return "__incomplete_customer_profile__";
  }
  return user.customerId;
}


