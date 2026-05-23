import type { QuoteDraft, RiskAssessment } from "../types";

export function assessQuoteRiskPreview(draft: QuoteDraft): RiskAssessment {
  let score = 100;
  const reasons: string[] = [];
  const yearBuilt = Number(draft.yearBuilt);
  const previousClaims = Number(draft.previousClaimsCount || 0);

  if (yearBuilt && yearBuilt < 1975) {
    score -= 20;
    reasons.push("Property was built before 1975.");
  }
  if (previousClaims > 5) {
    score -= 30;
    reasons.push("More than 5 property claims in the last 5 years.");
  }
  if (draft.usageType === "Vacant") {
    score -= 15;
    reasons.push("Vacant property increases exposure.");
  }
  if (draft.constructionType === "Wood") {
    score -= 10;
    reasons.push("Wood construction adds fire and structural risk.");
  }

  const securityBonus = Math.min(draft.securityFeatures.length * 2, 10);
  if (securityBonus > 0) {
    score += securityBonus;
    reasons.push(`Security measures improve score by ${securityBonus} points.`);
  }

  score = Math.max(0, Math.min(100, score));
  const requiresManualReview = score <= 70;
  const riskLevel = score > 80 ? "Low" : score > 70 ? "Medium" : "High";

  return {
    riskScore: score,
    riskLevel,
    triggeredRules: reasons.length ? reasons : ["No major underwriting rules were triggered."],
    recommendation: requiresManualReview
      ? "Manual underwriting review recommended before approval."
      : "Quote can be accepted automatically.",
    requiresManualReview,
    source: "preview"
  };
}

