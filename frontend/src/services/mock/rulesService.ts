import { buildMockUnderwritingRulesDocument } from "../../data/mockUnderwritingRules";
import type { UnderwritingRulesDocument } from "../../types";
import { delay, readStored, writeStored } from "../storage";

const underwritingRulesKey = "ultrasafe_mock_underwriting_rules_v1";

export async function getUnderwritingRules(): Promise<UnderwritingRulesDocument> {
  return delay(readStored(underwritingRulesKey, buildMockUnderwritingRulesDocument()));
}

export async function updateUnderwritingRules(
  document: UnderwritingRulesDocument,
  updatedBy?: string
): Promise<UnderwritingRulesDocument> {
  const saved: UnderwritingRulesDocument = {
    ...structuredClone(document),
    key: "employee_underwriting_rules",
    updated_at: new Date().toISOString(),
    updated_by: updatedBy || "frontend-mock"
  };
  writeStored(underwritingRulesKey, saved);
  return delay(saved);
}


