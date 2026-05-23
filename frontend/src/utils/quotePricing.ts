import type { Quote } from "../types";

export function getQuotePremium(quote: Quote) {
  if (isQuotePricingUnavailable(quote)) return 0;
  return quote.premium || quote.pricing.finalPremium || 0;
}

export function isQuotePricingBackendDriven(quote: Quote) {
  return (quote.pricingSource ?? quote.pricing.source) === "backend";
}

export function isQuotePricingUnavailable(quote: Quote) {
  return (quote.pricingSource ?? quote.pricing.source) === "unavailable";
}

export function isQuoteRiskBackendDriven(quote: Quote) {
  return quote.riskSource === "backend";
}

export function isQuoteRiskUnavailable(quote: Quote) {
  return quote.riskSource === "unavailable";
}

export function getQuotePricingSourceLabel(quote: Quote) {
  if (isQuotePricingBackendDriven(quote)) {
    return quote.pricingRuleVersion
      ? `Backend pricing ${quote.pricingRuleVersion}`
      : "Backend pricing";
  }
  if (isQuotePricingUnavailable(quote)) {
    return "Backend pricing unavailable";
  }
  return "Preview estimate";
}

export function getQuoteRiskSourceLabel(quote: Quote) {
  if (isQuoteRiskBackendDriven(quote)) {
    return quote.riskRuleVersion ? `Backend risk ${quote.riskRuleVersion}` : "Backend risk";
  }
  if (isQuoteRiskUnavailable(quote)) {
    return "Backend risk unavailable";
  }
  return "Preview risk estimate";
}

export function getQuoteRiskRecommendation(quote: Quote) {
  if (isQuoteRiskUnavailable(quote)) {
    return "Backend risk assessment unavailable";
  }
  if (!isQuoteRiskBackendDriven(quote)) {
    return "Preview only - backend decision is authoritative";
  }
  return quote.riskLevel ? `${quote.riskLevel} risk` : "Backend risk result";
}

