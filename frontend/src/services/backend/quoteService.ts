import type {
  AddressData,
  ConstructionType,
  CustomerData,
  InsuredAssetData,
  MockDocument,
  PricingBreakdown,
  PropertyType,
  Quote,
  QuoteAcceptance,
  QuoteAcceptanceInput,
  QuoteDecisionAuditRecord,
  QuoteDraft,
  QuoteStatus,
  RequestDetails,
  SecurityFeature,
  UsageType
} from "../../types";
import { calculatePremiumPreview } from "../../utils/pricing";
import { assessQuoteRiskPreview } from "../../utils/riskRules";
import { ApiError, apiRequest } from "./http";

interface BackendAttachment {
  file_name: string;
  content_type: string;
  size_bytes: number;
  file_url?: string | null;
  metadata?: Record<string, unknown>;
}

interface BackendQuoteRequest {
  id?: string;
  request_id?: string;
  client_id?: string | number;
  request_status?: string;
  status?: string;
  client_data?: Record<string, unknown>;
  asset_data?: Record<string, unknown>;
  quote_steps?: Array<Record<string, unknown>>;
  mandatory_data_status?: Record<string, unknown>;
  attachments?: BackendAttachment[];
  pricing_preview?: Record<string, unknown>;
  pricing?: Record<string, unknown> | null;
  risk?: Record<string, unknown> | null;
  allowed_actions?: unknown;
  created_at?: string;
  updated_at?: string;
}

const underwriterStatuses = [
  "underwriter_review",
  "approved",
  "disapproved",
  "field_review_required",
  "quote_ready",
  "pricing_in_progress",
  "auto_accepted",
  "failed",
  "draft"
];

export async function getClientQuotes(): Promise<Quote[]> {
  const records = await apiRequest<BackendQuoteRequest[]>("/me/quotes");
  return records.map(toQuote);
}

export async function getAllQuotes(): Promise<Quote[]> {
  const batches = await Promise.all(
    underwriterStatuses.map((status) =>
      apiRequest<BackendQuoteRequest[]>(
        `/underwriter/quotes?status=${encodeURIComponent(status)}`
      )
    )
  );
  return uniqueById(batches.flat().map(toQuote));
}

export async function getQuoteById(quoteId: string): Promise<Quote | undefined> {
  try {
    return toQuote(await getRawQuote(quoteId));
  } catch (error) {
    if (isNotFoundApiError(error)) return undefined;
    throw error;
  }
}

function isNotFoundApiError(error: unknown) {
  return error instanceof ApiError && error.status === 404;
}

export async function getMyQuoteById(quoteId: string): Promise<Quote | undefined> {
  try {
    return toQuote(await apiRequest<BackendQuoteRequest>(`/me/quotes/${encodeURIComponent(quoteId)}`));
  } catch (error) {
    if (isNotFoundApiError(error)) return undefined;
    throw error;
  }
}

export async function createQuote(draft: QuoteDraft): Promise<Quote> {
  const created = await apiRequest<BackendQuoteRequest>("/me/quotes", {
    method: "POST",
    body: buildCreateQuotePayload(draft)
  });
  return toQuote(created);
}

export async function getMyQuoteAcceptance(quoteId: string): Promise<QuoteAcceptance | undefined> {
  try {
    return await apiRequest<QuoteAcceptance>(
      `/me/quotes/${encodeURIComponent(quoteId)}/acceptance`
    );
  } catch (error) {
    if (isNotFoundApiError(error)) return undefined;
    throw error;
  }
}

export async function getQuoteAcceptance(quoteId: string): Promise<QuoteAcceptance | undefined> {
  try {
    return await apiRequest<QuoteAcceptance>(
      `/quotes/${encodeURIComponent(quoteId)}/acceptance`
    );
  } catch (error) {
    if (isNotFoundApiError(error)) return undefined;
    throw error;
  }
}

export async function getQuoteDecisionAudit(quoteId: string): Promise<QuoteDecisionAuditRecord[]> {
  return apiRequest<QuoteDecisionAuditRecord[]>(
    `/underwriter/quotes/${encodeURIComponent(quoteId)}/decision-audit`
  );
}

export async function acceptQuote(
  quoteId: string,
  acceptance: QuoteAcceptanceInput
): Promise<Quote> {
  await apiRequest<QuoteAcceptance>(
    `/me/quotes/${encodeURIComponent(quoteId)}/acceptance`,
    {
      method: "POST",
      body: {
        signer_name: acceptance.signer_name,
        signer_email: acceptance.signer_email,
        signer_role: acceptance.signer_role,
        acceptance_statement: acceptance.acceptance_statement
      }
    }
  );
  const refreshed = await apiRequest<BackendQuoteRequest>(
    `/me/quotes/${encodeURIComponent(quoteId)}`
  );
  return toQuote(refreshed);
}

export async function declineQuote(quoteId: string): Promise<Quote> {
  const updated = toQuote(await updateMyRawQuote(quoteId, { request_status: "disapproved" }));
  return { ...updated, status: "declined_by_client" };
}

export async function employeeApproveQuote(quoteId: string, reason?: string): Promise<Quote> {
  const updated = await apiRequest<BackendQuoteRequest>(
    `/underwriter/quotes/${encodeURIComponent(quoteId)}/decision`,
    {
      method: "PATCH",
      body: { status: "approved", reason: reason?.trim() || undefined }
    }
  );
  return toQuote(updated);
}

export async function employeeRejectQuote(quoteId: string, reason: string): Promise<Quote> {
  const updated = await apiRequest<BackendQuoteRequest>(
    `/underwriter/quotes/${encodeURIComponent(quoteId)}/decision`,
    {
      method: "PATCH",
      body: { status: "disapproved", reason: reason.trim() }
    }
  );
  return { ...toQuote(updated), rejectionReason: reason };
}

export async function updateQuoteStatus(
  quoteId: string,
  status: QuoteStatus,
  rejectionReason?: string
): Promise<Quote> {
  const updated = toQuote(
    await updateRawQuote(quoteId, { request_status: toBackendStatus(status) })
  );
  return { ...updated, rejectionReason: rejectionReason ?? updated.rejectionReason };
}

async function getRawQuote(quoteId: string) {
  return apiRequest<BackendQuoteRequest>(`/quotes/${encodeURIComponent(quoteId)}`);
}

async function updateRawQuote(quoteId: string, body: Record<string, unknown>) {
  return apiRequest<BackendQuoteRequest>(`/quotes/${encodeURIComponent(quoteId)}`, {
    method: "PATCH",
    body
  });
}

async function updateMyRawQuote(quoteId: string, body: Record<string, unknown>) {
  return apiRequest<BackendQuoteRequest>(`/me/quotes/${encodeURIComponent(quoteId)}`, {
    method: "PATCH",
    body
  });
}

function buildCreateQuotePayload(draft: QuoteDraft) {
  const pricingPreview = calculatePremiumPreview(draft);
  const riskPreview = assessQuoteRiskPreview(draft);
  const fullAddress = formatAddress(draft.address);
  const previousClaimsCount =
    draft.hadClaims === "Yes" ? numberValue(draft.previousClaimsCount) : 0;
  const clientData: CustomerData = {
    type: "individual",
    full_name: draft.fullName,
    national_id: draft.nationalId,
    email: draft.email,
    phone: draft.phone,
    address: fullAddress
  };
  const assetData: InsuredAssetData = {
    asset_type: draft.propertyType || "Apartment",
    usage_type: draft.usageType || "Owner occupied",
    construction_type: draft.constructionType || "Concrete",
    year_built: numberValue(draft.yearBuilt),
    area_sqm: numberValue(draft.areaSqm),
    declared_value: numberValue(draft.coverageAmount),
    occupancy: draft.usageType || "Owner occupied",
    previous_claims_count: previousClaimsCount,
    address: {
      ...draft.address,
      full_text: fullAddress
    }
  };
  const requestDetails: RequestDetails = {
    coverage_amount: numberValue(draft.coverageAmount),
    security_features: draft.securityFeatures,
    systems_updated: draft.systemsUpdated,
    location_risks: draft.locationRisks,
    high_value_items: draft.highValueItems,
    renovations: draft.renovations,
    long_vacancy: draft.longVacancy
  };

  return {
    request_status: "underwriter_review",
    client_data: clientData,
    asset_data: assetData,
    quote_steps: buildQuoteSteps(draft),
    mandatory_data_status: { is_complete: true },
    attachments: [],
    pricing_preview: {
      source: "frontend_preview_context",
      binding: false,
      request_details: requestDetails,
      ui_context: {
        submitted_pricing_estimate: pricingPreview,
        submitted_risk_estimate: riskPreview
      }
    }
  };
}

function buildQuoteSteps(draft: QuoteDraft) {
  return [
    ["coverage_amount", draft.coverageAmount],
    ["property_type", draft.propertyType],
    ["address", formatAddress(draft.address)],
    ["year_built", draft.yearBuilt],
    ["area_sqm", draft.areaSqm],
    ["construction_type", draft.constructionType],
    ["usage_type", draft.usageType],
    ["previous_claims_count", draft.previousClaimsCount],
    ["security_features", draft.securityFeatures.join(", ")]
  ].map(([step, value]) => ({ step, value }));
}

function toQuote(record: BackendQuoteRequest): Quote {
  const quoteId = backendQuoteId(record);
  const clientData = record.client_data || {};
  const assetData = record.asset_data || {};
  const preview = record.pricing_preview || {};
  const requestDetails = objectValue(preview.request_details);
  const backendPricing = normalizeBackendPricing(optionalObjectValue(record.pricing));
  const pricing = backendPricing ?? unavailablePricing(record);
  const backendRisk = normalizeBackendRisk(optionalObjectValue(record.risk));
  const risk = backendRisk ?? unavailableRisk(record);
  const address = objectValue(assetData.address);
  const propertyAddress = stringValue(address.full_text) || formatAddress(address);
  const securityFeatures = arrayValue(requestDetails.security_features).filter(
    isSecurityFeature
  );
  const attachments = (record.attachments || []).map(toMockDocument);

  return {
    id: quoteId,
    requestId: quoteId,
    clientId: String(record.client_id ?? ""),
    clientName: stringValue(clientData.full_name) || "Unknown client",
    propertyType: propertyTypeValue(assetData.asset_type),
    propertyAddress: propertyAddress || "Property address unavailable",
    yearBuilt: numberValue(assetData.year_built),
    areaSqm: numberValue(assetData.area_sqm),
    constructionType: constructionTypeValue(assetData.construction_type),
    usageType: usageTypeValue(assetData.usage_type || assetData.occupancy),
    coverageAmount: numberValue(
      requestDetails.coverage_amount || assetData.declared_value
    ),
    previousClaimsCount: numberValue(assetData.previous_claims_count),
    securityFeatures,
    premium: pricing.finalPremium,
    riskScore: risk.riskScore,
    riskReasons: risk.triggeredRules,
    pricing,
    pricingSource: pricing.source,
    riskSource: risk.source,
    pricingRuleVersion: pricing.ruleVersion,
    riskRuleVersion: risk.ruleVersion,
    riskLevel: risk.riskLevel,
    requiresManualReview: risk.requiresManualReview,
    allowedActions: arrayValue(record.allowed_actions).map(String),
    status: toFrontendStatus(backendQuoteStatus(record)),
    createdAt: dateValue(record.created_at),
    updatedAt: dateValue(record.updated_at),
    rejectionReason: getRejectionReason(record),
    clientData: {
      type: clientData.type === "company" ? "company" : "individual",
      full_name: stringValue(clientData.full_name),
      national_id: stringValue(clientData.national_id),
      company_id: stringValue(clientData.company_id) || undefined,
      email: stringValue(clientData.email),
      phone: stringValue(clientData.phone),
      address: stringValue(clientData.address) || propertyAddress
    },
    insuredData: {
      asset_type: propertyTypeValue(assetData.asset_type),
      usage_type: usageTypeValue(assetData.usage_type),
      construction_type: constructionTypeValue(assetData.construction_type),
      year_built: numberValue(assetData.year_built),
      area_sqm: numberValue(assetData.area_sqm),
      declared_value: numberValue(assetData.declared_value),
      occupancy: usageTypeValue(assetData.occupancy || assetData.usage_type),
      previous_claims_count: numberValue(assetData.previous_claims_count),
      address: normalizeAddress(address)
    },
    requestDetails: {
      coverage_amount: numberValue(
        requestDetails.coverage_amount || assetData.declared_value
      ),
      security_features: securityFeatures,
      systems_updated: stringValue(requestDetails.systems_updated),
      location_risks: stringValue(requestDetails.location_risks),
      high_value_items: stringValue(requestDetails.high_value_items),
      renovations: stringValue(requestDetails.renovations),
      long_vacancy: stringValue(requestDetails.long_vacancy)
    },
    attachments
  };
}

function normalizePreviewPricing(value: Record<string, unknown>): PricingBreakdown {
  const finalPremium = numberValue(value.finalPremium ?? value.final_premium ?? value.estimatedPremium ?? value.estimated_premium);
  return {
    basePremium: numberValue(value.basePremium ?? value.base_premium),
    coverageAmount: optionalNumber(value.coverageAmount ?? value.coverage_amount),
    coverageRate: optionalNumber(value.coverageRate ?? value.coverage_rate),
    propertyTypeMultiplier: optionalNumber(value.propertyTypeMultiplier ?? value.property_type_multiplier) ?? 1,
    propertyUseMultiplier: numberValue(value.propertyUseMultiplier ?? value.property_use_multiplier, 1),
    sizeMultiplier: optionalNumber(value.sizeMultiplier ?? value.size_multiplier) ?? 1,
    constructionMultiplier: numberValue(value.constructionMultiplier ?? value.construction_multiplier, 1),
    ageMultiplier: numberValue(value.ageMultiplier ?? value.age_multiplier, 1),
    claimsMultiplier: numberValue(value.claimsMultiplier ?? value.claims_multiplier, 1),
    securityDiscountPercent: numberValue(value.securityDiscountPercent ?? value.security_discount_percent),
    manualReviewSurcharge: numberValue(value.manualReviewSurcharge ?? value.manual_review_surcharge),
    finalPremium,
    estimatedPremium: numberValue(value.estimatedPremium ?? value.estimated_premium, finalPremium),
    adjustments: normalizePricingAdjustments(value.adjustments ?? value.pricing_adjustments),
    explanation: arrayValue(value.explanation).map(String),
    currency: stringValue(value.currency) || "RON",
    ruleVersion: stringValue(value.ruleVersion ?? value.rule_version) || undefined,
    source: "preview"
  };
}

function normalizeBackendPricing(value?: Record<string, unknown>): PricingBreakdown | undefined {
  if (!value) return undefined;
  const premium = optionalNumber(
    value.premium ?? value.finalPremium ?? value.final_premium ?? value.final_premium_ron
  );
  if (premium == null) return undefined;
  return {
    basePremium: optionalNumber(value.basePremium ?? value.base_premium ?? value.base_premium_ron) ?? 0,
    coverageAmount: optionalNumber(value.coverageAmount ?? value.coverage_amount),
    coverageRate: optionalNumber(value.coverageRate ?? value.coverage_rate),
    propertyTypeMultiplier: optionalNumber(value.propertyTypeMultiplier ?? value.property_type_multiplier) ?? 1,
    propertyUseMultiplier: optionalNumber(value.propertyUseMultiplier ?? value.property_use_multiplier) ?? 1,
    sizeMultiplier: optionalNumber(value.sizeMultiplier ?? value.size_multiplier) ?? 1,
    constructionMultiplier: optionalNumber(value.constructionMultiplier ?? value.construction_multiplier) ?? 1,
    ageMultiplier: optionalNumber(value.ageMultiplier ?? value.age_multiplier) ?? 1,
    claimsMultiplier: optionalNumber(value.claimsMultiplier ?? value.claims_multiplier) ?? 1,
    securityDiscountPercent: optionalNumber(value.securityDiscountPercent ?? value.security_discount_percent) ?? 0,
    manualReviewSurcharge: optionalNumber(value.manualReviewSurcharge ?? value.manual_review_surcharge) ?? 0,
    finalPremium: premium,
    estimatedPremium: premium,
    adjustments: normalizePricingAdjustments(value.adjustments ?? value.pricing_adjustments),
    explanation: arrayValue(value.rationale ?? value.explanation ?? value.reasons).map(String),
    currency: stringValue(value.currency) || undefined,
    ruleVersion: stringValue(value.ruleVersion ?? value.rule_version) || undefined,
    source: "backend"
  };
}

function unavailablePricing(record: BackendQuoteRequest): PricingBreakdown {
  const preview = record.pricing_preview || {};
  const message =
    stringValue(preview.pricing_error) || "Backend pricing is unavailable for this quote.";
  return {
    basePremium: 0,
    propertyTypeMultiplier: 1,
    propertyUseMultiplier: 1,
    sizeMultiplier: 1,
    constructionMultiplier: 1,
    ageMultiplier: 1,
    claimsMultiplier: 1,
    securityDiscountPercent: 0,
    manualReviewSurcharge: 0,
    finalPremium: 0,
    estimatedPremium: 0,
    adjustments: [],
    explanation: [message],
    currency: stringValue(preview.currency) || "RON",
    source: "unavailable"
  };
}

function normalizePricingAdjustments(value: unknown) {
  return arrayValue(value).map((item) => {
    const record = objectValue(item);
    const amount = numberValue(record.amountDelta ?? record.amount_delta ?? record.amount);
    const type = stringValue(record.adjustment_type);
    return {
      code: stringValue(record.code) || undefined,
      label: stringValue(record.label) || "Adjustment",
      value: stringValue(record.value) || "",
      amountDelta: type === "discount" && amount > 0 ? -amount : amount
    };
  });
}

function normalizePreviewRisk(value?: Record<string, unknown>) {
  const riskScore = numberValue(value?.riskScore ?? value?.risk_score, 75);
  const riskLevel = normalizeRiskLevel(value?.riskLevel ?? value?.risk_level, riskScore);
  return {
    riskScore,
    riskLevel,
    triggeredRules: arrayValue(value?.triggeredRules ?? value?.triggered_rules).map(String),
    recommendation: stringValue(value?.recommendation),
    requiresManualReview: Boolean(value?.requiresManualReview || value?.requires_manual_review),
    ruleVersion: stringValue(value?.ruleVersion ?? value?.rule_version) || undefined,
    source: "preview" as const
  };
}

function normalizeBackendRisk(value?: Record<string, unknown>) {
  if (!value) return undefined;
  const score = optionalNumber(value.score ?? value.riskScore ?? value.risk_score);
  if (score == null) return undefined;
  const riskLevel = normalizeRiskLevel(
    value.level ?? value.riskLevel ?? value.risk_level,
    score
  );
  const requiresManualReview = booleanValue(
    value.requiresManualReview ?? value.requires_manual_review,
    score <= 70
  );
  return {
    riskScore: score,
    riskLevel,
    triggeredRules: arrayValue(
      value.reasons ?? value.triggeredRules ?? value.triggered_rules
    ).map(String),
    recommendation: stringValue(value.recommendation),
    requiresManualReview,
    ruleVersion: stringValue(value.ruleVersion ?? value.rule_version) || undefined,
    source: "backend" as const
  };
}

function unavailableRisk(record: BackendQuoteRequest) {
  const preview = record.pricing_preview || {};
  const message =
    stringValue(preview.risk_error) || "Backend risk assessment is unavailable for this quote.";
  return {
    riskScore: 0,
    riskLevel: "High" as const,
    triggeredRules: [message],
    recommendation: message,
    requiresManualReview: true,
    ruleVersion: undefined,
    source: "unavailable" as const
  };
}

function toMockDocument(attachment: BackendAttachment, index: number): MockDocument {
  const fileName = attachment.file_name || `attachment-${index + 1}`;
  const extension = fileName.split(".").pop()?.toUpperCase();
  const type = ["PDF", "DOCX", "JPG", "PNG", "ZIP"].includes(extension || "")
    ? (extension as MockDocument["type"])
    : "PDF";

  return {
    id: attachment.file_url || fileName,
    label: String(attachment.metadata?.label || fileName),
    fileName,
    type
  };
}

function toFrontendStatus(status: string): QuoteStatus {
  if (status === "approved") return "approved";
  if (status === "auto_accepted") return "accepted_by_client";
  if (status === "disapproved" || status === "failed") return "rejected";
  if (status === "draft") return "draft";
  return "in_review";
}

function toBackendStatus(status: QuoteStatus) {
  if (status === "approved") return "approved";
  if (status === "rejected" || status === "declined_by_client") return "disapproved";
  if (status === "accepted_by_client" || status === "contract_generated") {
    return "auto_accepted";
  }
  if (status === "draft") return "draft";
  return "underwriter_review";
}

function getRejectionReason(record: BackendQuoteRequest) {
  const step = (record.quote_steps || []).find((item) => "rejection_reason" in item);
  return stringValue(step?.rejection_reason);
}

function uniqueById(quotes: Quote[]) {
  return Array.from(new Map(quotes.map((quote) => [quote.id, quote])).values()).sort(
    (first, second) => second.createdAt.localeCompare(first.createdAt)
  );
}

function backendQuoteId(record: Pick<BackendQuoteRequest, "id" | "request_id">) {
  return stringValue(record.request_id ?? record.id);
}

function backendQuoteStatus(record: Pick<BackendQuoteRequest, "request_status" | "status">) {
  return stringValue(record.request_status ?? record.status);
}

function propertyTypeValue(value: unknown): PropertyType {
  return value === "House" || value === "Commercial" ? value : "Apartment";
}

function constructionTypeValue(value: unknown): ConstructionType {
  return value === "Brick" || value === "Wood" || value === "Steel" ? value : "Concrete";
}

function usageTypeValue(value: unknown): UsageType {
  if (
    value === "Rented" ||
    value === "Vacant" ||
    value === "Holiday home" ||
    value === "Commercial use"
  ) {
    return value;
  }
  return "Owner occupied";
}

function isSecurityFeature(value: unknown): value is SecurityFeature {
  return (
    value === "Alarm" ||
    value === "Smoke detector" ||
    value === "Sprinklers" ||
    value === "Security cameras" ||
    value === "Security door" ||
    value === "Security guard"
  );
}

function normalizeAddress(value: Record<string, unknown>): AddressData {
  return {
    country: stringValue(value.country),
    county: stringValue(value.county),
    city: stringValue(value.city),
    street: stringValue(value.street),
    number: stringValue(value.number),
    postal_code: stringValue(value.postal_code),
    full_text: stringValue(value.full_text) || formatAddress(value)
  };
}

function formatAddress(address: Partial<AddressData> | Record<string, unknown>) {
  return [
    stringValue(address.street),
    stringValue(address.number),
    stringValue(address.city),
    stringValue(address.county),
    stringValue(address.country)
  ]
    .filter(Boolean)
    .join(", ");
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function optionalObjectValue(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function numberValue(value: unknown, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function optionalNumber(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number : undefined;
}

function booleanValue(value: unknown, fallback = false) {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.toLowerCase();
    if (normalized === "true") return true;
    if (normalized === "false") return false;
  }
  return fallback;
}

function normalizeRiskLevel(value: unknown, score: number): "Low" | "Medium" | "High" {
  const label = stringValue(value).toLowerCase();
  if (label === "low") return "Low";
  if (label === "medium") return "Medium";
  if (label === "high") return "High";
  return score > 80 ? "Low" : score > 70 ? "Medium" : "High";
}

function dateValue(value: unknown) {
  const date = new Date(stringValue(value));
  return Number.isFinite(date.getTime()) ? date.toISOString().slice(0, 10) : "";
}

