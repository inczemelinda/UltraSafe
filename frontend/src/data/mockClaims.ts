import type { Claim } from "../types";

export const mockClaims: Claim[] = [
  {
    id: "CL-2026-001",
    contractId: "C-2026-001",
    clientId: "client-001",
    clientName: "Ana Popescu",
    policyNumber: "C-2026-001",
    propertyAddress: "Str. Aviatorilor 12, București",
    claimType: "Water damage",
    incidentDate: "2026-04-24",
    incidentTime: "09:30",
    estimatedDamage: 3200,
    score: 88,
    scoreReasons: ["Photos uploaded", "Documents uploaded", "Damage amount is within coverage"],
    status: "submitted",
    description: "Water damage in the kitchen caused by a broken pipe.",
    emergencyServices: true,
    hasPhotos: true,
    hasDocuments: true,
    contactPhone: "+40 721 000 111",
    contactEmail: "ana.popescu@client.com",
    createdAt: "2026-04-24",
    evidence: [
      { id: "ev-photo-1", label: "Photos", fileName: "kitchen-damage.jpg", type: "JPG" },
      { id: "ev-doc-1", label: "Documents", fileName: "repair-estimate.pdf", type: "PDF" }
    ]
  },
  {
    id: "CL-2026-002",
    contractId: "C-2026-001",
    clientId: "client-001",
    clientName: "Ana Popescu",
    policyNumber: "C-2026-001",
    propertyAddress: "Str. Aviatorilor 12, București",
    claimType: "Other",
    incidentDate: "2026-04-10",
    incidentTime: "18:10",
    estimatedDamage: 80000,
    score: 45,
    scoreReasons: ["Missing photos", "Damage is over 50% of the coverage limit", "Description is too short"],
    status: "in_review",
    description: "Damage happened.",
    emergencyServices: false,
    hasPhotos: false,
    hasDocuments: true,
    contactPhone: "+40 721 000 111",
    contactEmail: "ana.popescu@client.com",
    createdAt: "2026-04-10",
    suggestedNextAction: "request_evidence",
    requiredEvidence: [
      {
        requirementType: "additional_incident_details",
        reason: "The incident description is too short for underwriter review.",
        acceptableDocuments: ["claimant_statement", "written_incident_description"],
        severity: "medium",
        status: "missing",
        suggestedNextAction: "request_evidence"
      }
    ],
    evidence: [{ id: "ev-doc-2", label: "Documents", fileName: "incident-note.docx", type: "DOCX" }]
  }
];



