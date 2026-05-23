import type { ClaimDraft } from "../types";

export function scoreClaim(
  draft: ClaimDraft,
  coverageAmount: number
): { score: number; reasons: string[] } {
  let score = 100;
  const reasons: string[] = [];
  const estimatedDamage = Number(draft.estimatedDamage || 0);

  if (!draft.photosFileName) {
    score -= 25;
    reasons.push("Missing photos.");
  }
  if (!draft.documentsFileName) {
    score -= 25;
    reasons.push("Missing documents.");
  }
  if (coverageAmount > 0 && estimatedDamage > coverageAmount * 0.5) {
    score -= 15;
    reasons.push("Estimated damage is over 50% of the coverage limit.");
  }
  if (draft.description.trim().length < 30) {
    score -= 15;
    reasons.push("Description is too short.");
  }
  if (draft.claimType === "Other") {
    score -= 10;
    reasons.push("Incident type Other needs additional verification.");
  }
  if (
    ["Fire", "Water damage", "Storm"].includes(draft.claimType) &&
    draft.emergencyServices === "No"
  ) {
    score -= 10;
    reasons.push("No emergency services for a severe incident type.");
  }

  return {
    score: Math.max(0, Math.min(100, score)),
    reasons: reasons.length ? reasons : ["Claim evidence looks complete."]
  };
}

