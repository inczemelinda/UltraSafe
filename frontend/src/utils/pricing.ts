import type { PricingBreakdown, QuoteDraft } from "../types";

const BASE_RATE = 0.002;
const MAX_SECURITY_DISCOUNT = 0.1;

const propertyTypeMultiplier: Record<string, number> = {
  Apartment: 1,
  House: 1.08,
  Commercial: 1.25
};

const propertyUseMultiplier: Record<string, number> = {
  "Owner occupied": 1,
  Rented: 1.1,
  "Holiday home": 1.1,
  Vacant: 1.3,
  "Commercial use": 1.25
};

const constructionMultiplier: Record<string, number> = {
  Concrete: 0.95,
  Brick: 0.95,
  Steel: 1,
  Wood: 1.2
};

const securityDiscounts: Record<string, number> = {
  Alarm: 0.05,
  "Smoke detector": 0.03,
  Sprinklers: 0.05,
  "Security cameras": 0.05,
  "Security door": 0.03,
  "Security guard": 0.05
};

export function getPremiumPreviewBreakdown(draft: QuoteDraft): PricingBreakdown {
  const coverageAmount = positiveNumber(draft.coverageAmount);
  const areaSqm = positiveNumber(draft.areaSqm);
  const yearBuilt = positiveNumber(draft.yearBuilt);
  const previousClaims =
    draft.hadClaims === "Yes" ? positiveNumber(draft.previousClaimsCount) : 0;
  const basePremium = Math.round(coverageAmount * BASE_RATE);
  const typeMultiplier = propertyTypeMultiplier[draft.propertyType] ?? 1;
  const useMultiplier = propertyUseMultiplier[draft.usageType] ?? 1;
  const areaMultiplier = getSizeMultiplier(areaSqm);
  const buildMultiplier = constructionMultiplier[draft.constructionType] ?? 1;
  const ageMultiplier = getAgeMultiplier(yearBuilt);
  const claimsMultiplier = previousClaims === 0 ? 1 : previousClaims <= 5 ? 1.25 : 1.25;
  const rawDiscount = draft.securityFeatures.reduce(
    (total, feature) => total + (securityDiscounts[feature] ?? 0),
    0
  );
  const securityDiscountPercent = Math.min(rawDiscount, MAX_SECURITY_DISCOUNT);
  const manualReviewSurcharge = previousClaims > 5 ? 100 : 0;
  let runningPremium = basePremium;
  const adjustments: PricingBreakdown["adjustments"] = [];

  runningPremium = applyMultiplier(adjustments, runningPremium, "property_type", "Property type", typeMultiplier);
  runningPremium = applyMultiplier(adjustments, runningPremium, "property_age", "Property age", ageMultiplier);
  runningPremium = applyMultiplier(adjustments, runningPremium, "property_size", "Property size", areaMultiplier);
  runningPremium = applyMultiplier(adjustments, runningPremium, "construction", "Construction", buildMultiplier);
  runningPremium = applyMultiplier(adjustments, runningPremium, "property_use", "Use", useMultiplier);
  runningPremium = applyMultiplier(adjustments, runningPremium, "claims_history", "Claims history", claimsMultiplier);

  if (securityDiscountPercent > 0) {
    const beforeDiscount = runningPremium;
    runningPremium = runningPremium * (1 - securityDiscountPercent);
    adjustments.push({
      code: "security",
      label: "Security",
      value: `-${Math.round(securityDiscountPercent * 100)}%`,
      amountDelta: Math.round(runningPremium - beforeDiscount)
    });
  }

  if (manualReviewSurcharge > 0) {
    runningPremium += manualReviewSurcharge;
    adjustments.push({
      code: "claims_surcharge",
      label: "Claims surcharge",
      value: `+${manualReviewSurcharge} RON`,
      amountDelta: manualReviewSurcharge
    });
  }

  const estimatedPremium = Math.round(runningPremium);

  return {
    basePremium,
    coverageAmount,
    coverageRate: BASE_RATE,
    propertyTypeMultiplier: typeMultiplier,
    propertyUseMultiplier: useMultiplier,
    sizeMultiplier: areaMultiplier,
    constructionMultiplier: buildMultiplier,
    ageMultiplier,
    claimsMultiplier,
    securityDiscountPercent,
    manualReviewSurcharge,
    finalPremium: estimatedPremium,
    estimatedPremium,
    adjustments,
    source: "preview",
    explanation: [
      "Base premium equals selected coverage amount x 0.2%.",
      `Property type multiplier: ${typeMultiplier.toFixed(2)}.`,
      `Property size multiplier: ${areaMultiplier.toFixed(2)}.`,
      `Property use multiplier: ${useMultiplier.toFixed(2)}.`,
      `Construction multiplier: ${buildMultiplier.toFixed(2)}.`,
      `Age multiplier: ${ageMultiplier.toFixed(2)}.`,
      `Claims multiplier: ${claimsMultiplier.toFixed(2)}.`,
      `Security discount: ${Math.round(securityDiscountPercent * 100)}%.`
    ]
  };
}

export function calculatePremiumPreview(draft: QuoteDraft): PricingBreakdown {
  return getPremiumPreviewBreakdown(draft);
}

function applyMultiplier(
  adjustments: NonNullable<PricingBreakdown["adjustments"]>,
  currentPremium: number,
  code: string,
  label: string,
  multiplier: number
) {
  const nextPremium = currentPremium * multiplier;
  if (multiplier !== 1) {
    adjustments.push({
      code,
      label,
      value: `x ${multiplier.toFixed(2)}`,
      amountDelta: Math.round(nextPremium - currentPremium)
    });
  }
  return nextPremium;
}

function getAgeMultiplier(yearBuilt: number) {
  if (!yearBuilt) return 1;
  const age = new Date().getFullYear() - yearBuilt;
  if (age < 20) return 0.95;
  if (age <= 50) return 1;
  return 1.15;
}

function getSizeMultiplier(areaSqm: number) {
  if (!areaSqm || areaSqm <= 80) return 1;
  if (areaSqm <= 150) return 1.08;
  if (areaSqm <= 250) return 1.16;
  return 1.25;
}

function positiveNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

