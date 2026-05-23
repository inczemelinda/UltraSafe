import type { Quote } from "../types";

export const mockQuotes: Quote[] = [
  {
    id: "Q-2026-001",
    requestId: "Q-2026-001",
    clientId: "client-001",
    clientName: "Ana Popescu",
    propertyType: "Apartment",
    propertyAddress: "Str. Aviatorilor 12, București",
    yearBuilt: 2012,
    areaSqm: 78,
    constructionType: "Concrete",
    usageType: "Owner occupied",
    coverageAmount: 135000,
    previousClaimsCount: 0,
    securityFeatures: ["Alarm", "Smoke detector"],
    premium: 250,
    riskScore: 92,
    riskReasons: ["Modern property", "Low claims history", "Security features present"],
    pricing: {
      basePremium: 270,
      propertyUseMultiplier: 1,
      constructionMultiplier: 0.95,
      ageMultiplier: 0.95,
      claimsMultiplier: 1,
      securityDiscountPercent: 0.08,
      manualReviewSurcharge: 0,
      finalPremium: 250,
      explanation: [
        "Base premium is coverage amount x 0.2%.",
        "Concrete construction and newer age reduce the premium.",
        "Security features apply an 8% discount."
      ]
    },
    status: "approved",
    createdAt: "2026-04-20",
    updatedAt: "2026-04-22",
    clientData: {
      type: "individual",
      full_name: "Ana Popescu",
      national_id: "1900101123456",
      email: "ana.popescu@client.com",
      phone: "+40 721 000 111",
      address: "Str. Aviatorilor 12, București"
    },
    insuredData: {
      asset_type: "Apartment",
      usage_type: "Owner occupied",
      construction_type: "Concrete",
      year_built: 2012,
      floor: "4",
      area_sqm: 78,
      declared_value: 135000,
      occupancy: "Owner occupied",
      previous_claims_count: 0,
      address: {
        country: "Romania",
        county: "București",
        city: "București",
        street: "Str. Aviatorilor",
        number: "12",
        postal_code: "010862",
        full_text: "Str. Aviatorilor 12, București"
      }
    },
    requestDetails: {
      coverage_amount: 135000,
      security_features: ["Alarm", "Smoke detector"]
    },
    attachments: [
      { id: "doc-id-1", label: "ID document", fileName: "ana-id.pdf", type: "PDF" },
      { id: "doc-property-1", label: "Property ownership", fileName: "ownership.pdf", type: "PDF" }
    ]
  },
  {
    id: "Q-2026-002",
    requestId: "Q-2026-002",
    clientId: "client-001",
    clientName: "Ana Popescu",
    propertyType: "House",
    propertyAddress: "Str. Lalelelor 8, Cluj-Napoca",
    yearBuilt: 1968,
    areaSqm: 145,
    constructionType: "Wood",
    usageType: "Vacant",
    coverageAmount: 210000,
    previousClaimsCount: 6,
    securityFeatures: [],
    premium: 780,
    riskScore: 35,
    riskReasons: [
      "Property was built before 1975",
      "More than 5 claims in the last 5 years",
      "Vacant property",
      "Wood construction"
    ],
    pricing: {
      basePremium: 420,
      propertyUseMultiplier: 1.3,
      constructionMultiplier: 1.2,
      ageMultiplier: 1.15,
      claimsMultiplier: 1.25,
      securityDiscountPercent: 0,
      manualReviewSurcharge: 100,
      finalPremium: 780,
      explanation: [
        "Vacant use, wood construction, older age, and claims history increase the premium.",
        "Manual review surcharge is added because risk rules were triggered."
      ]
    },
    status: "in_review",
    createdAt: "2026-04-21",
    updatedAt: "2026-04-21",
    clientData: {
      type: "individual",
      full_name: "Ana Popescu",
      national_id: "1900101123456",
      email: "ana.popescu@client.com",
      phone: "+40 721 000 111",
      address: "Str. Aviatorilor 12, București"
    },
    insuredData: {
      asset_type: "House",
      usage_type: "Vacant",
      construction_type: "Wood",
      year_built: 1968,
      floor: "Ground + 1",
      area_sqm: 145,
      declared_value: 210000,
      occupancy: "Vacant",
      previous_claims_count: 6,
      address: {
        country: "Romania",
        county: "Cluj",
        city: "Cluj-Napoca",
        street: "Str. Lalelelor",
        number: "8",
        postal_code: "400000",
        full_text: "Str. Lalelelor 8, Cluj-Napoca"
      }
    },
    requestDetails: {
      coverage_amount: 210000,
      security_features: []
    },
    attachments: [{ id: "doc-property-2", label: "Property photos", fileName: "house-photos.zip", type: "ZIP" }]
  }
];



