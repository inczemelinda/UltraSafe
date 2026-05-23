import type { UnderwritingRulesDocument } from "../types";

const premiumFactorRows = [
  ["Property use", "Owner occupied", "1.00"],
  ["Property use", "Rented", "1.10"],
  ["Property use", "Holiday home", "1.10"],
  ["Property use", "Vacant", "1.30"],
  ["Property use", "Commercial use", "1.25"],
  ["Construction", "Concrete", "0.95"],
  ["Construction", "Brick", "0.95"],
  ["Construction", "Steel", "1.00"],
  ["Construction", "Wood", "1.20"],
  ["Property age", "< 20 years", "0.95"],
  ["Property age", "20-50 years", "1.00"],
  ["Property age", "50+ years", "1.15"],
  ["Claims history", "None", "1.00"],
  ["Claims history", "1-5 claims", "1.25"],
  ["Claims history", "> 5 claims", "Manual review"]
];

const securityDiscountRows = [
  ["Alarm system", "-5%"],
  ["Smoke detector", "-3%"],
  ["Sprinklers", "-5%"],
  ["Security cameras", "-5%"],
  ["Security door", "-3%"],
  ["Security guard", "-5%"],
  ["Multiple measures", "Maximum -10% total"]
];

const manualReviewRows = [
  ["Property built before 1975", "Risk score -20"],
  ["More than 5 claims in last 5 years", "Risk score -30"],
  ["Vacant property", "Risk score -15"],
  ["Wood construction", "Risk score -10"],
  ["Security measures present", "Can improve score up to +10"],
  ["Final score <= 70", "Send quote to underwriting review"]
];

const underwritingQuestionRows = [
  ["Property use", "Yes", "Yes"],
  ["Rebuild/coverage value", "Yes", "Yes"],
  ["Construction type", "Yes", "Yes"],
  ["Year built", "Yes", "Yes"],
  ["Claims history", "Yes", "Yes"],
  ["Security measures", "Yes, as discount", "Yes"],
  ["Location risk", "Optional/AI-derived", "Yes"],
  ["High-value items", "Only if coverage extension exists", "Yes"],
  ["Renovations/structural changes", "Usually no", "Yes"],
  ["Occupancy/vacancy", "Yes", "Yes"],
  ["Key systems update history", "Usually no", "Yes"]
];

const claimRuleRows = [
  ["Missing photos", "-25"],
  ["Missing documents", "-25"],
  ["Damage over 50% of coverage", "-15"],
  ["Description too short", "-15"],
  ["Incident type Other", "-10"],
  ["No emergency services for severe events", "-10"]
];

export function buildMockUnderwritingRulesDocument(): UnderwritingRulesDocument {
  return {
    key: "employee_underwriting_rules",
    updated_by: "frontend-mock",
    sections: [
      {
        id: "quote_review_principles",
        title: "Quote Review Principles",
        blocks: [
          {
            id: "principles",
            kind: "list",
            items: [
              "A Quote is the client's insurance request.",
              "A Contract is generated only after a Quote is approved.",
              "A Claim is separate and linked to an existing contract.",
              "Clients cannot see the internal risk score.",
              "Employees can see the risk score, triggered rules, and suggested next action.",
              "Some questions are used for premium calculation; others support underwriting decisions."
            ]
          }
        ]
      },
      {
        id: "premium_calculation_model",
        title: "Premium Calculation Model",
        blocks: [
          {
            id: "premium_formula",
            kind: "notice",
            text: "Annual Premium = (Coverage Amount x Base Rate) x Risk Multipliers - Security Discounts"
          },
          {
            id: "premium_factors",
            kind: "table",
            headers: ["Factor", "Option", "Multiplier"],
            rows: premiumFactorRows
          },
          {
            id: "security_discounts",
            kind: "table",
            headers: ["Security Feature", "Discount"],
            rows: securityDiscountRows
          }
        ]
      },
      {
        id: "manual_review_rules",
        title: "Manual Review Rules",
        blocks: [
          {
            id: "manual_review_table",
            kind: "table",
            headers: ["Rule", "Impact"],
            rows: manualReviewRows
          }
        ]
      },
      {
        id: "underwriting_questions",
        title: "Questions Used for Underwriting",
        blocks: [
          {
            id: "underwriting_questions_table",
            kind: "table",
            headers: ["Question", "Used for Premium?", "Used for Underwriting?"],
            rows: underwritingQuestionRows
          }
        ]
      },
      {
        id: "coverage_and_limits",
        title: "Coverage and Limits",
        blocks: [
          {
            id: "coverage_limits",
            kind: "list",
            items: [
              "Overall policy limit equals declared rebuild/replacement value.",
              "Fire and explosion: 100% of sum insured.",
              "Storm/hail: 100%.",
              "Water damage: 20-30%.",
              "Theft structural damage: 10-20%.",
              "Flood: 15-25%.",
              "Earthquake: 20-30%."
            ]
          }
        ]
      },
      {
        id: "claim_review_rules",
        title: "Claim Review Rules",
        blocks: [
          {
            id: "claim_review_table",
            kind: "table",
            headers: ["Claim Rule", "Score Impact"],
            rows: claimRuleRows
          }
        ]
      }
    ]
  };
}

