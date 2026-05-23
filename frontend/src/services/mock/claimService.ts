import { mockClaims } from "../../data/mockClaims";
import type {
  AiReviewFinding,
  Claim,
  ClaimAttachmentMetadata,
  ClaimDraft,
  ClaimEvidenceRequirement,
  ClaimStatus,
  DemoInboundEmailResponse,
  EvidenceRequestDraftResponse,
  EvidenceRequestDraft,
  EvidenceRequestDraftUpdate,
  SentEmailMessage
} from "../../types";
import { scoreClaim } from "../../utils/claimScoring";
import { getContractById } from "./contractService";
import { readStoredAuthUser } from "../authSession";
import { delay, readStored, today, writeStored } from "../storage";

const claimsKey = "ultrasafe_claims_v3";

export async function getClientClaims(): Promise<Claim[]> {
  const clientId = currentMockClientId();
  return delay(readStored(claimsKey, mockClaims).filter((claim) => claim.clientId === clientId));
}

export async function getAllClaims(): Promise<Claim[]> {
  return delay(readStored(claimsKey, mockClaims));
}

export async function getClaimById(claimId: string): Promise<Claim | undefined> {
  return delay(readStored(claimsKey, mockClaims).find((claim) => claim.id === claimId));
}

export async function getMyClaimById(claimId: string): Promise<Claim | undefined> {
  return getClaimById(claimId);
}

export async function getLatestClaimReview(claimId: string): Promise<Claim> {
  const claim = getStoredClaim(claimId);
  return delay({
    ...claim,
    reviewState: claim.suggestedNextAction ? "full_review" : "not_started",
    aiReviewStatus: claim.suggestedNextAction ? "completed" : "not_started",
    documentConsistency: claim.suggestedNextAction
      ? {
          status: "no_discrepancies",
          supportingFactCount: 0,
          discrepancyCount: 0
        }
      : {
          status: "not_started",
          message: "Claim review analysis has not started.",
          supportingFactCount: 0,
          discrepancyCount: 0
        },
    supportingFacts: claim.supportingFacts ?? [],
    discrepancies: claim.discrepancies ?? [],
    availableActions: ["start_analysis"]
  });
}

export async function startClaimReview(claimId: string): Promise<Claim> {
  const claim = getStoredClaim(claimId);
  if (claim.status === "submitted") {
    await updateStoredClaim(claimId, { status: "in_review" });
  }
  return getLatestClaimReview(claimId);
}

export async function createClaim(draft: ClaimDraft): Promise<Claim> {
  const clientId = currentMockClientId();
  if (clientId === "__incomplete_customer_profile__") {
    throw new Error("CUSTOMER_PROFILE_INCOMPLETE");
  }
  const claims = readStored(claimsKey, mockClaims);
  const contract = await getContractById(draft.contractId);
  if (!contract) throw new Error("Contract not found");
  const scoring = scoreClaim(draft, contract.coverageAmount);
  const propertyAddress = draft.propertyAddress || contract.propertyAddress;
  const policyNumber = draft.policyNumber || contract.id;
  const evidenceFiles = draft.evidenceFiles ?? {
    Photos: draft.photosFileName,
    Documents: draft.documentsFileName
  };
  const uploadedAttachments = draft.attachments ?? [];
  const claim: Claim = {
    id: draft.claimId || `CL-${new Date().getFullYear()}-${String(claims.length + 1).padStart(3, "0")}`,
    contractId: draft.contractId,
    clientId,
    clientName: draft.fullName,
    policyNumber,
    propertyAddress,
    claimType: draft.claimType || "Other",
    incidentDate: draft.incidentDate,
    incidentTime: draft.incidentTime,
    estimatedDamage: Number(draft.estimatedDamage),
    score: scoring.score,
    scoreReasons: scoring.reasons,
    status: "submitted",
    description: draft.description,
    emergencyServices: draft.emergencyServices === "Yes",
    hasPhotos: Boolean(draft.photosFileName) || uploadedAttachments.some(isPhotoAttachment),
    hasDocuments: Boolean(draft.documentsFileName) || uploadedAttachments.some(isDocumentAttachment),
    contactPhone: draft.phone,
    contactEmail: draft.email,
    createdAt: today(),
    evidence: uploadedAttachments.length
      ? uploadedAttachments.map((attachment, index) => ({
          id: attachment.file_url || `evidence-${index + 1}`,
          label: String(attachment.metadata?.label || attachment.file_name),
          fileName: attachment.file_name,
          type: documentType(attachment.file_name, String(attachment.metadata?.label || ""), attachment.content_type),
          fileUrl: attachment.file_url ?? undefined,
          contentType: attachment.content_type,
          sizeBytes: attachment.size_bytes,
          storageKey: String(attachment.metadata?.storage_key || "") || undefined,
          metadata: attachment.metadata ? { ...attachment.metadata } : undefined
        }))
      : Object.entries(evidenceFiles)
          .filter(([, fileName]) => Boolean(fileName))
          .map(([label, fileName], index) => ({
            id: `evidence-${index + 1}`,
            label,
            fileName,
            type: documentType(fileName, label)
          }))
  };
  writeStored(claimsKey, [claim, ...claims]);
  return delay(claim);
}

export async function uploadClaimAttachments(
  claimId: string,
  uploads: Array<{ file: File; documentRole?: string }>
): Promise<ClaimAttachmentMetadata[]> {
  if (!uploads.length) return delay([]);

  return delay(
    uploads.map(({ file, documentRole }, index) => {
      const storageKey = makeMockStorageKey(file, index);
      return {
        file_name: file.name,
        content_type: file.type || contentTypeForFile(file.name),
        size_bytes: file.size,
        file_url: `/claims/${claimId}/attachments/${storageKey}`,
        metadata: {
          attachment_id: storageKey,
          claim_id: claimId,
          storage_key: storageKey,
          mock_storage: true,
          document_role: documentRole || ""
        }
      };
    })
  );
}

export async function startClaimAnalysis(claimId: string): Promise<Claim> {
  const current = getStoredClaim(claimId);
  if (current.status !== "submitted" && current.status !== "in_review") {
    return delay(current);
  }
  const requiredEvidence = buildMockEvidenceRequirements(current);
  return updateClaimStatus(claimId, "in_review", "Deterministic claim review completed.", {
    requiredEvidence,
    suggestedNextAction: requiredEvidence.length ? "request_evidence" : "underwriter_review"
  });
}

export async function refreshClaimAttachmentAnalysis(claimId: string): Promise<Claim> {
  const claim = getStoredClaim(claimId);
  const lowerClaimType = claim.claimType.toLowerCase();
  const evidenceText = (claim.evidence ?? [])
    .map((document) => `${document.label} ${document.fileName} ${document.type}`)
    .join(" ")
    .toLowerCase();
  const mismatch =
    lowerClaimType.includes("fire") &&
    (evidenceText.includes("water") || evidenceText.includes("flood"));
  const finding: AiReviewFinding = {
    id: `mock-ai-analysis-${claimId}`,
    claimId,
    findingType: "document_summary",
    severity: mismatch ? "warning" : "info",
    description: mismatch
      ? "Out of place / needs review:\n- Claim context is fire, but the uploaded evidence appears to reference water or flood damage.\n\nEvidence signals:\n- Review the uploaded photos/documents against the reported incident type before deciding coverage."
      : "Evidence signals:\n- Uploaded attachments were reviewed against the claim context.\n- No obvious incident-type mismatch was detected in the mock analysis.",
    relatedDocument: "all_attachments",
    reviewStatus: "completed",
    source: "mock_attachment_analysis",
    createdAt: new Date().toISOString()
  };
  return updateStoredClaim(claimId, {
    aiReviewFindings: [finding],
    aiReviewStatus: "completed"
  });
}

export async function generateEvidenceRequestDraft(
  claimId: string
): Promise<EvidenceRequestDraftResponse> {
  const claim = getStoredClaim(claimId);
  const requiredEvidence = claim.requiredEvidence ?? [];
  if (!requiredEvidence.length) {
    return delay({
      needed: false,
      message: "No evidence request is needed for this claim review.",
      draft: null
    });
  }

  const fireRequired = requiredEvidence.some((item) =>
    item.requirementType.includes("fire")
  );
  const requiredDocuments = fireRequired
    ? fireRequiredDocuments
    : uniqueDocuments(
        requiredEvidence.flatMap((item) =>
          item.requirementType === "additional_incident_details"
            ? ["additional incident details"]
            : item.acceptableDocuments.map(formatDocumentLabel)
          )
      );
  const draft: EvidenceRequestDraft = {
    claimRequestId: claim.id,
    subject: fireRequired
      ? "Additional evidence required for your fire claim"
      : "Additional evidence required for your claim",
    body: buildDraftBody(claim, requiredEvidence, requiredDocuments),
    recipients: claim.contactEmail ? [claim.contactEmail] : [],
    requiredDocuments,
    status: "draft",
    sendStatus: "not_sent",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
  await updateStoredClaim(claimId, { evidenceRequestDraft: draft });

  return delay({
    needed: true,
    message: "Evidence request draft is ready for underwriter review.",
    draft
  });
}

export async function updateEvidenceRequestDraft(
  claimId: string,
  draftUpdate: EvidenceRequestDraftUpdate
): Promise<EvidenceRequestDraft> {
  const claim = getStoredClaim(claimId);
  const incomingDocuments = uniqueDocuments([
    ...(draftUpdate.requiredDocuments ?? []),
    ...(draftUpdate.requestedDocumentType ? [draftUpdate.requestedDocumentType] : [])
  ]);
  let existing = claim.evidenceRequestDraft;
  if (existing && evidenceRequestDraftIsSent(existing)) {
    if (sameEvidenceRequestScope(existing, draftUpdate.sourceSuggestionId, incomingDocuments)) {
      throw new Error("Sent evidence request drafts cannot be edited.");
    }
    existing = undefined;
  }
  const now = new Date().toISOString();
  const draft: EvidenceRequestDraft = {
    claimRequestId: claim.id,
    createdAt: existing?.createdAt || now,
    ...existing,
    body: draftUpdate.body,
    dueDate: draftUpdate.dueDate ?? existing?.dueDate,
    recipients: draftUpdate.recipients?.length ? draftUpdate.recipients : existing?.recipients ?? (claim.contactEmail ? [claim.contactEmail] : []),
    requiredDocuments: incomingDocuments.length ? incomingDocuments : existing?.requiredDocuments ?? [],
    requestedDocumentType: draftUpdate.requestedDocumentType ?? existing?.requestedDocumentType,
    sendStatus: "not_sent",
    sourceSuggestionId: draftUpdate.sourceSuggestionId ?? existing?.sourceSuggestionId,
    status: "draft",
    subject: draftUpdate.subject,
    updatedAt: now
  };
  const communicationSuggestionStates = {
    ...(claim.communicationSuggestionStates ?? {})
  };
  if (draft.sourceSuggestionId) {
    communicationSuggestionStates[draft.sourceSuggestionId] = {
      suggestionId: draft.sourceSuggestionId,
      status: "draft_created",
      draftId: draft.draftId,
      source: "mock",
      updatedAt: now
    };
  }
  await updateStoredClaim(claimId, { communicationSuggestionStates, evidenceRequestDraft: draft });
  return delay(draft);
}

export async function sendEvidenceRequestDraft(
  claimId: string
): Promise<EvidenceRequestDraft> {
  const claim = getStoredClaim(claimId);
  const draft = claim.evidenceRequestDraft;
  if (!draft) throw new Error("Evidence request draft was not found.");
  if (evidenceRequestDraftIsSent(draft)) {
    throw new Error("Evidence request draft has already been sent.");
  }
  const now = new Date().toISOString();
  const sentDraft: EvidenceRequestDraft = {
    ...draft,
    emailMessageId: `mock-email-message-${claimId}`,
    providerMessageId: `mock-evidence-request-${claimId}`,
    recipients: draft.recipients?.length ? draft.recipients : claim.contactEmail ? [claim.contactEmail] : [],
    sendStatus: "sent",
    sentAt: now,
    sentTo: draft.recipients?.length ? draft.recipients : claim.contactEmail ? [claim.contactEmail] : [],
    status: "sent",
    updatedAt: now
  };
  const communicationSuggestionStates = {
    ...(claim.communicationSuggestionStates ?? {})
  };
  if (sentDraft.sourceSuggestionId) {
    communicationSuggestionStates[sentDraft.sourceSuggestionId] = {
      ...(communicationSuggestionStates[sentDraft.sourceSuggestionId] ?? {
        suggestionId: sentDraft.sourceSuggestionId
      }),
      draftId: sentDraft.draftId,
      source: "mock",
      status: "sent",
      updatedAt: now
    };
  }
  await updateStoredClaim(claimId, { communicationSuggestionStates, evidenceRequestDraft: sentDraft });
  return delay(sentDraft);
}

export async function sendDemoInboundClaimEmail(
  claimId: string
): Promise<DemoInboundEmailResponse> {
  const claim = getStoredClaim(claimId);
  const draft = claim.evidenceRequestDraft;
  if (!draft || !evidenceRequestDraftIsSent(draft)) {
    throw new Error("Send an evidence request before triggering a demo inbound email.");
  }
  return delay({
    message: "Demo inbound email sent through Postmark.",
    to_email: `mock-inbound+${draft.replyToken || "reply-token"}@inbound.postmarkapp.com`,
    subject: `[UW-CLAIM:${draft.replyToken || "reply-token"}] Re: ${draft.subject}`,
    provider_message_id: `mock-demo-inbound-${claimId}`,
    reply_token: draft.replyToken || "reply-token",
    attachment_file_name: "demo-inbound-evidence.pdf"
  });
}

export async function dismissClaimAiSuggestion(
  claimId: string,
  suggestionId: string
): Promise<void> {
  const claim = getStoredClaim(claimId);
  const now = new Date().toISOString();
  await updateStoredClaim(claimId, {
    communicationSuggestionStates: {
      ...(claim.communicationSuggestionStates ?? {}),
      [suggestionId]: {
        suggestionId,
        status: "dismissed",
        source: "mock",
        dismissedAt: now,
        updatedAt: now
      }
    }
  });
  return delay(undefined);
}

export async function sendClaimDecisionEmail(
  claimId: string
): Promise<SentEmailMessage> {
  const claim = getStoredClaim(claimId);
  if (!claim.decision || claim.decisionStatus === "pending" || !claim.decisionJustification) {
    throw new Error("Claim decision must be submitted before sending a decision email.");
  }
  if (claim.decisionEmailSentAt) {
    throw new Error("Claim decision email has already been sent.");
  }
  const decisionLabel =
    claim.decision === "approved"
      ? "Approved"
      : claim.decision === "denied"
        ? "Denied"
        : "On-site inspection requested";
  const sentAt = new Date().toISOString();
  await updateStoredClaim(claimId, {
    decisionEmailMessageId: `mock-email-${claimId}`,
    decisionEmailSentAt: sentAt
  });
  return delay({
    id: `mock-email-${claimId}`,
    case_id: claimId,
    direction: "OUTBOUND",
    from_email: "maria.tiuca@zerorisk.com",
    to_email: "alex.vulcu@zerorisk.com",
    subject: "Your UltraSafe claim decision",
    body: [
      "Hello Alex,",
      "",
      `We have completed the review of your claim ${claim.id}.`,
      "",
      `Decision: ${decisionLabel}`,
      "",
      "Decision justification:",
      claim.decisionJustification,
      "",
      "This is a demo claim decision email sent from UltraSafe through Postmark.",
      "",
      "Regards,",
      "UltraSafe Claims Team"
    ].join("\n"),
    status: "SENT",
    provider_message_id: "mock-postmark-message-id",
    created_at: sentAt,
    sent_at: sentAt
  });
}

export async function rewordClaimDecisionJustification({
  decision,
  justification
}: {
  decision?: Claim["decision"];
  justification: string;
}): Promise<string> {
  if (!justification.trim()) {
    throw new Error("Decision justification is required.");
  }
  return delay(mockDecisionRewordingFallback(decision));
}

function mockDecisionRewordingFallback(decision?: Claim["decision"]) {
  if (decision === "approved") {
    return "Based on the claim review, the submitted information supports approval under the applicable policy terms. The claim has therefore been approved, and the claims team will continue with the next steps.";
  }
  if (decision === "inspection_requested") {
    return "Based on the claim review, additional on-site assessment is required before a final decision can be completed. An inspection has therefore been requested so the claims team can verify the damage and supporting details.";
  }
  if (decision === "denied") {
    return "Based on the claim review, the submitted information does not provide sufficient support for approval under the applicable policy terms. The claim has therefore been denied. Please contact the claims team if you would like additional clarification or wish to provide further documentation.";
  }
  return "Based on the claim review, the submitted information has been assessed under the applicable policy terms. The decision explanation should reflect the evidence available, any remaining documentation gaps, and the policy reasoning used by the claims team.";
}

export async function approveClaim(claimId: string, justification?: string): Promise<Claim> {
  const current = getStoredClaim(claimId);
  if (isClaimTerminal(current.status)) return delay(current);
  return updateClaimStatus(claimId, "accepted", justification || "Claim approved.");
}

export async function rejectClaim(claimId: string, reason: string): Promise<Claim> {
  const current = getStoredClaim(claimId);
  if (isClaimTerminal(current.status)) return delay(current);
  return updateClaimStatus(claimId, "rejected", reason);
}

export async function requestOnPremisesInspection(claimId: string, justification?: string): Promise<Claim> {
  const current = getStoredClaim(claimId);
  if (current.status !== "submitted" && current.status !== "in_review") return delay(current);
  return updateClaimStatus(
    claimId,
    "inspection_requested",
    justification || "On-premises inspection requested."
  );
}

export async function updateClaimStatus(
  claimId: string,
  status: ClaimStatus,
  note?: string,
  reviewUpdate: Partial<Pick<Claim, "requiredEvidence" | "suggestedNextAction">> = {}
): Promise<Claim> {
  const claims = readStored(claimsKey, mockClaims);
  const claim = claims.find((item) => item.id === claimId);
  if (!claim) throw new Error("Claim not found");

  const decision =
    status === "accepted"
      ? "approved"
      : status === "rejected"
        ? "denied"
        : status === "inspection_requested"
          ? "inspection_requested"
          : undefined;
  const decidedAt = decision ? new Date().toISOString() : claim.decidedAt;
  const updated: Claim = {
    ...claim,
    status,
    decision,
    decisionStatus: decision ? "submitted" : claim.decisionStatus,
    decisionJustification: decision ? note : claim.decisionJustification,
    decidedBy: decision ? "mock-underwriter" : claim.decidedBy,
    decidedByEmail: decision ? "underwriter@example.test" : claim.decidedByEmail,
    decidedAt,
    rejectionReason: status === "rejected" ? note : claim.rejectionReason,
    internalNote: note ?? claim.internalNote,
    ...reviewUpdate
  };
  writeStored(
    claimsKey,
    claims.map((item) => (item.id === claimId ? updated : item))
  );
  return delay(updated);
}

async function updateStoredClaim(claimId: string, update: Partial<Claim>): Promise<Claim> {
  const claims = readStored(claimsKey, mockClaims);
  const claim = claims.find((item) => item.id === claimId);
  if (!claim) throw new Error("Claim not found");
  const updated = { ...claim, ...update };
  writeStored(
    claimsKey,
    claims.map((item) => (item.id === claimId ? updated : item))
  );
  return updated;
}

function getStoredClaim(claimId: string) {
  const claim = readStored(claimsKey, mockClaims).find((item) => item.id === claimId);
  if (!claim) throw new Error("Claim not found");
  return claim;
}

function isClaimTerminal(status: ClaimStatus) {
  return status === "accepted" || status === "rejected" || status === "paid";
}

function evidenceRequestDraftIsSent(draft: EvidenceRequestDraft) {
  return draft.status === "sent" || draft.sendStatus === "mock_sent" || draft.sendStatus === "sent";
}

function sameEvidenceRequestScope(
  draft: EvidenceRequestDraft,
  sourceSuggestionId: string | undefined,
  documents: string[]
) {
  if (sourceSuggestionId && draft.sourceSuggestionId && sourceSuggestionId === draft.sourceSuggestionId) {
    return true;
  }
  const existingDocuments = uniqueDocuments([
    ...draft.requiredDocuments,
    ...(draft.requestedDocumentType ? [draft.requestedDocumentType] : [])
  ]).map(normalizeDocumentScope);
  const incomingDocuments = uniqueDocuments(documents).map(normalizeDocumentScope);
  return (
    existingDocuments.length > 0 &&
    incomingDocuments.length > 0 &&
    existingDocuments.length === incomingDocuments.length &&
    existingDocuments.every((document) => incomingDocuments.includes(document))
  );
}

function normalizeDocumentScope(value: string) {
  return value.trim().toLowerCase().replace(/[-_]+/g, " ").replace(/\s+/g, " ");
}

function makeMockStorageKey(file: File, index: number) {
  const seed = `${Date.now()}-${index}-${file.name || "claim-attachment"}`;
  return `mock-${seed.replace(/[^A-Za-z0-9._-]+/g, "-")}`;
}

function contentTypeForFile(fileName: string) {
  if (/\.(jpg|jpeg)$/i.test(fileName)) return "image/jpeg";
  if (/\.png$/i.test(fileName)) return "image/png";
  if (/\.docx$/i.test(fileName)) {
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  }
  return "application/pdf";
}

function documentType(fileName: string, label: string, contentType?: string): Claim["evidence"][number]["type"] {
  const extension = fileName.split(".").pop()?.toUpperCase();
  if (extension === "JPEG") return "JPG";
  if (["PDF", "DOCX", "JPG", "PNG", "ZIP"].includes(extension || "")) {
    return extension as Claim["evidence"][number]["type"];
  }
  const normalizedContentType = (contentType || "").toLowerCase();
  if (normalizedContentType.includes("png")) return "PNG";
  if (normalizedContentType.includes("jpeg") || normalizedContentType.includes("jpg")) return "JPG";
  if (normalizedContentType.includes("pdf")) return "PDF";
  if (normalizedContentType.includes("wordprocessingml")) return "DOCX";
  if (normalizedContentType.includes("zip")) return "ZIP";
  if (label.toLowerCase().includes("photo")) return "JPG";
  return "PDF";
}

function isPhotoAttachment(attachment: ClaimAttachmentMetadata) {
  const label = String(attachment.metadata?.label || "");
  return /\.(jpg|jpeg|png)$/i.test(attachment.file_name) || label.toLowerCase().includes("photo");
}

function isDocumentAttachment(attachment: ClaimAttachmentMetadata) {
  const label = String(attachment.metadata?.label || "");
  const haystack = `${attachment.file_name} ${attachment.content_type} ${label}`.toLowerCase();
  return ["document", "pdf", "invoice", "report", "doc"].some((token) =>
    haystack.includes(token)
  );
}

const fireRequiredDocuments = [
  "fire service report",
  "emergency intervention report",
  "police report",
  "authority-issued incident confirmation",
  "incident reference number"
];

function buildMockEvidenceRequirements(claim: Claim): ClaimEvidenceRequirement[] {
  const requirements: ClaimEvidenceRequirement[] = [];
  if (claim.claimType === "Fire" && !claim.emergencyServices) {
    requirements.push({
      requirementType: "official_fire_incident_confirmation",
      reason: "Fire claims without emergency-services confirmation need official incident proof.",
      acceptableDocuments: [
        "fire_service_report",
        "emergency_report",
        "official_incident_confirmation"
      ],
      severity: "high",
      status: "missing",
      suggestedNextAction: "request_evidence"
    });
  }
  if (claim.description.trim().split(/\s+/).filter(Boolean).length < 5) {
    requirements.push({
      requirementType: "additional_incident_details",
      reason: "The incident description is too short for underwriter review.",
      acceptableDocuments: ["claimant_statement", "written_incident_description"],
      severity: "medium",
      status: "missing",
      suggestedNextAction: "request_evidence"
    });
  }
  return requirements;
}

function buildDraftBody(
  claim: Claim,
  requiredEvidence: ClaimEvidenceRequirement[],
  requiredDocuments: string[]
) {
  const lines = [
    `Dear ${claim.clientName || "client"},`,
    "",
    "We need a little more information before the underwriter can continue reviewing your claim."
  ];

  if (requiredEvidence.some((item) => item.requirementType.includes("fire"))) {
    lines.push(
      "",
      "Please provide one of the following for the reported fire incident:",
      ...fireRequiredDocuments.map((item) => `- ${item}`)
    );
  }

  if (requiredEvidence.some((item) => item.requirementType === "additional_incident_details")) {
    lines.push(
      "",
      "Please also provide a fuller incident description, including what happened, when it happened, where it happened, and what damage occurred."
    );
  }

  const genericDocuments = requiredDocuments.filter(
    (item) => !fireRequiredDocuments.includes(item) && item !== "additional incident details"
  );
  if (genericDocuments.length) {
    lines.push(
      "",
      "Please provide the following supporting documents:",
      ...genericDocuments.map((item) => `- ${item}`)
    );
  }

  lines.push("", "Thank you,", "UltraSafe Claims Team");
  return lines.join("\n");
}

function formatDocumentLabel(value: string) {
  return value.replace(/[_-]+/g, " ").trim();
}

function uniqueDocuments(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function currentMockClientId() {
  const user = readStoredAuthUser();
  if (!user) return "client-001";
  if (!user.customerId || user.requiresCustomerProfileCompletion) {
    return "__incomplete_customer_profile__";
  }
  return user.customerId;
}


