import type {
  AiFollowUpSuggestion,
  AiReviewFinding,
  AiReviewLifecycleStatus,
  Claim,
  ClaimAttachmentMetadata,
  ClaimCoverageAssessment,
  ClaimDraft,
  ClaimDocumentConsistency,
  ClaimDocumentFinding,
  ClaimCommunicationSuggestionState,
  ClaimEvidenceRequirement,
  ClaimStatus,
  ClaimType,
  DemoInboundEmailResponse,
  EvidenceRequestDraft,
  EvidenceRequestDraftResponse,
  EvidenceRequestDraftUpdate,
  MockDocument,
  SentEmailMessage
} from "../../types";
import { ApiError, apiRequest, resolveApiUrl } from "./http";

type BackendAttachment = ClaimAttachmentMetadata;

interface BackendClaimRequest {
  request_id: string;
  client_id: string | number;
  request_status: string;
  client_data: Record<string, unknown>;
  claim_data: Record<string, unknown>;
  attachments: BackendAttachment[];
  created_at: string;
  updated_at: string;
}

interface ClaimAnalysisResponse {
  case_id: string;
  status: string;
  claim_request: BackendClaimRequest;
  review_view?: Record<string, unknown> | null;
}

interface ClaimReviewResponse {
  case_id?: string | null;
  status: string;
  review_state: string;
  claim_request: BackendClaimRequest;
  review_view?: Record<string, unknown> | null;
  evidence_request_draft?: BackendEvidenceRequestDraft | null;
}

interface BackendEvidenceRequestDraft {
  draft_id?: string;
  claim_request_id: string;
  subject: string;
  body: string;
  recipients?: string[];
  required_documents?: string[];
  status: string;
  source_suggestion_id?: string | null;
  requested_document_type?: string | null;
  due_date?: string | null;
  send_status?: string;
  sent_at?: string | null;
  sent_to?: string[];
  provider_message_id?: string | null;
  email_message_id?: string | null;
  reply_token?: string | null;
  send_error_message?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface BackendEvidenceRequestDraftResponse {
  needed: boolean;
  message: string;
  draft?: BackendEvidenceRequestDraft | null;
}

interface BackendEvidenceRequestDraftMutationResponse {
  message: string;
  draft: BackendEvidenceRequestDraft;
}

interface BackendCommunicationSuggestionState {
  suggestion_id: string;
  status: string;
  source?: string;
  draft_id?: string | null;
  dismissed_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

const underwriterStatuses = [
  "submitted",
  "screening",
  "needs_underwriter_review",
  "coverage_review_required",
  "in_review",
  "failed",
  "completed"
];

export async function getClientClaims(): Promise<Claim[]> {
  const records = await apiRequest<BackendClaimRequest[]>("/me/claims");
  return records.map((record) => toClaim(record));
}

export async function getAllClaims(): Promise<Claim[]> {
  const batches = await Promise.all(
    underwriterStatuses.map((status) =>
      apiRequest<BackendClaimRequest[]>(
        `/underwriter/claims?status=${encodeURIComponent(status)}`
      )
    )
  );
  return uniqueById(batches.flat().map((record) => toClaim(record)));
}

export async function getClaimById(claimId: string): Promise<Claim | undefined> {
  try {
    return await getLatestClaimReview(claimId);
  } catch (error) {
    if (!isNotFoundApiError(error)) throw error;
    try {
      return toClaim(await apiRequest<BackendClaimRequest>(`/underwriter/claims/${encodeURIComponent(claimId)}`));
    } catch (fallbackError) {
      if (isNotFoundApiError(fallbackError)) return undefined;
      throw fallbackError;
    }
  }
}

export async function getMyClaimById(claimId: string): Promise<Claim | undefined> {
  try {
    return toClaim(await apiRequest<BackendClaimRequest>(`/me/claims/${encodeURIComponent(claimId)}`));
  } catch (error) {
    if (isNotFoundApiError(error)) return undefined;
    throw error;
  }
}

export async function getLatestClaimReview(claimId: string): Promise<Claim> {
  const response = await apiRequest<ClaimReviewResponse>(
    `/underwriter/claims/${encodeURIComponent(claimId)}/review`
  );
  return toClaim(
    response.claim_request,
    response.review_view,
    response.case_id ?? undefined,
    response.review_state,
    response.evidence_request_draft ?? undefined
  );
}

export async function startClaimReview(claimId: string): Promise<Claim> {
  const response = await apiRequest<BackendClaimRequest>(
    `/underwriter/claims/${encodeURIComponent(claimId)}/start-review`,
    { method: "POST" }
  );
  return toClaim(response);
}

export async function getClaimRequestById(claimId: string): Promise<Claim | undefined> {
  try {
    return toClaim(await apiRequest<BackendClaimRequest>(`/underwriter/claims/${encodeURIComponent(claimId)}`));
  } catch (error) {
    if (isNotFoundApiError(error)) return undefined;
    throw error;
  }
}

function isNotFoundApiError(error: unknown) {
  return error instanceof ApiError && error.status === 404;
}

export async function createClaim(draft: ClaimDraft): Promise<Claim> {
  const created = await apiRequest<BackendClaimRequest>("/me/claims", {
    method: "POST",
    body: {
      request_status: "submitted",
      client_data: {
        full_name: draft.fullName,
        email: draft.email,
        phone: draft.phone
      },
      claim_data: {
        claim_id: draft.claimId,
        contract_id: draft.contractId,
        claim_type: draft.claimType || "Other",
        incident_date: draft.incidentDate,
        incident_time: draft.incidentTime,
        estimated_damage: numberValue(draft.estimatedDamage),
        emergency_services: draft.emergencyServices === "Yes",
        description: draft.description,
        contact_phone: draft.phone,
        contact_email: draft.email
      },
      attachments: draft.attachments ?? []
    }
  });
  return toClaim(created);
}

export async function uploadClaimAttachments(
  claimId: string,
  uploads: Array<{ file: File; documentRole?: string }>
): Promise<ClaimAttachmentMetadata[]> {
  if (!uploads.length) return [];

  const formData = new FormData();
  uploads.forEach(({ file, documentRole }) => {
    formData.append("files", file);
    formData.append("document_roles", String(documentRole || ""));
  });

  return apiRequest<ClaimAttachmentMetadata[]>(`/claims/${encodeURIComponent(claimId)}/attachments`, {
    method: "POST",
    body: formData
  });
}

export async function startClaimAnalysis(claimId: string): Promise<Claim> {
  const response = await apiRequest<ClaimAnalysisResponse>(
    `/underwriter/claims/${encodeURIComponent(claimId)}/start-analysis`,
    { method: "POST" }
  );
  return toClaim(response.claim_request, response.review_view, response.case_id);
}

export async function refreshClaimAttachmentAnalysis(claimId: string): Promise<Claim> {
  const response = await apiRequest<ClaimReviewResponse>(
    `/underwriter/claims/${encodeURIComponent(claimId)}/attachments/refresh-analysis`,
    { method: "POST" }
  );
  return toClaim(
    response.claim_request,
    response.review_view,
    response.case_id ?? undefined,
    response.review_state,
    response.evidence_request_draft ?? undefined
  );
}

export async function generateEvidenceRequestDraft(
  claimId: string
): Promise<EvidenceRequestDraftResponse> {
  let response: BackendEvidenceRequestDraftResponse;
  try {
    response = await apiRequest<BackendEvidenceRequestDraftResponse>(
      `/underwriter/claims/${encodeURIComponent(claimId)}/evidence-request/draft`,
      { method: "POST" }
    );
  } catch (error) {
    if (isMissingClaimReviewFindingsError(error)) {
      return {
        needed: false,
        message: "Run claim analysis before creating an evidence request draft.",
        draft: null
      };
    }
    throw error;
  }
  return {
    needed: Boolean(response.needed),
    message: stringValue(response.message),
    draft: response.draft ? toEvidenceRequestDraft(response.draft) : null
  };
}

export async function updateEvidenceRequestDraft(
  claimId: string,
  draft: EvidenceRequestDraftUpdate
): Promise<EvidenceRequestDraft> {
  const response = await apiRequest<BackendEvidenceRequestDraftMutationResponse>(
    `/underwriter/claims/${encodeURIComponent(claimId)}/evidence-request/draft`,
    {
      method: "PATCH",
      body: {
        body: draft.body,
        due_date: draft.dueDate,
        recipients: draft.recipients ?? [],
        requested_document_type: draft.requestedDocumentType,
        required_documents: draft.requiredDocuments ?? [],
        source_suggestion_id: draft.sourceSuggestionId,
        subject: draft.subject
      }
    }
  );
  return toEvidenceRequestDraft(response.draft);
}

export async function sendEvidenceRequestDraft(
  claimId: string
): Promise<EvidenceRequestDraft> {
  const response = await apiRequest<BackendEvidenceRequestDraftMutationResponse>(
    `/underwriter/claims/${encodeURIComponent(claimId)}/evidence-request/draft/send`,
    { method: "POST" }
  );
  return toEvidenceRequestDraft(response.draft);
}

export async function sendDemoInboundClaimEmail(
  claimId: string
): Promise<DemoInboundEmailResponse> {
  return apiRequest<DemoInboundEmailResponse>(
    `/underwriter/claims/${encodeURIComponent(claimId)}/communication/demo-inbound-email`,
    { method: "POST" }
  );
}

export async function dismissClaimAiSuggestion(
  claimId: string,
  suggestionId: string
): Promise<void> {
  await apiRequest(
    `/underwriter/claims/${encodeURIComponent(claimId)}/communication-suggestions/${encodeURIComponent(suggestionId)}/dismiss`,
    { method: "POST" }
  );
}

export async function sendClaimDecisionEmail(
  claimId: string
): Promise<SentEmailMessage> {
  return apiRequest<SentEmailMessage>(
    `/underwriter/claims/${encodeURIComponent(claimId)}/decision-email`,
    { method: "POST" }
  );
}

export async function rewordClaimDecisionJustification({
  decision,
  justification
}: {
  decision?: Claim["decision"];
  justification: string;
}): Promise<string> {
  const response = await apiRequest<{ suggestion: string }>(
    "/claims/decision-justification/reword",
    {
      authRole: "employee",
      method: "POST",
      body: {
        decision,
        justification
      }
    }
  );
  return stringValue(response.suggestion);
}

async function submitClaimDecision(
  claimId: string,
  decision: "approved" | "denied" | "inspection_requested",
  justification: string
): Promise<Claim> {
  const response = await apiRequest<BackendClaimRequest>(
    `/underwriter/claims/${encodeURIComponent(claimId)}/decision`,
    {
      method: "POST",
      body: {
        decision,
        justification
      }
    }
  );
  return toClaim(response);
}

export async function approveClaim(claimId: string, justification?: string): Promise<Claim> {
  return submitClaimDecision(claimId, "approved", justification ?? "");
}

export async function rejectClaim(claimId: string, reason: string): Promise<Claim> {
  return submitClaimDecision(claimId, "denied", reason);
}

export async function requestOnPremisesInspection(claimId: string, justification?: string): Promise<Claim> {
  return submitClaimDecision(claimId, "inspection_requested", justification ?? "");
}

function toClaim(
  record: BackendClaimRequest,
  reviewView?: Record<string, unknown> | null,
  caseId?: string,
  reviewState?: string,
  evidenceRequestDraft?: BackendEvidenceRequestDraft | null
): Claim {
  const claimData = record.claim_data || {};
  const clientData = record.client_data || {};
  const confidence = objectValue(reviewView?.confidence_panel);
  const summary = objectValue(reviewView?.summary_panel);
  const classification = objectValue(reviewView?.classification_panel);
  const scoreReasons = arrayValue(confidence.rationale).map(String);
  const requiredEvidence = evidenceRequirementsFromReviewView(reviewView);
  const evidenceDraft =
    evidenceRequestDraft ?? draftFromReviewView(reviewView);
  const claimType = claimTypeValue(claimData.claim_type);
  const displayClaimId = stringValue(
    claimData.display_claim_id ||
      claimData.displayClaimId ||
      claimData.claim_id ||
      claimData.claimNumber ||
      claimData.claim_reference ||
      claimData.claimReference ||
      claimData.public_id ||
      claimData.publicId ||
      claimData.external_id ||
      claimData.externalId
  );
  const decision = claimDecisionValue(claimData.decision);
  const decisionStatus = stringValue(claimData.decision_status || claimData.decisionStatus) || undefined;
  const decisionJustification =
    stringValue(claimData.decision_justification || claimData.decisionJustification) || undefined;
  const decidedAt = stringValue(claimData.decided_at || claimData.decidedAt) || undefined;
  const decidedBy = stringValue(claimData.decided_by || claimData.decidedBy) || undefined;
  const decidedByEmail = stringValue(claimData.decided_by_email || claimData.decidedByEmail) || undefined;
  const decisionEmailSentAt =
    stringValue(claimData.decision_email_sent_at || claimData.decisionEmailSentAt) || undefined;
  const decisionEmailMessageId =
    stringValue(claimData.decision_email_message_id || claimData.decisionEmailMessageId) || undefined;
  const extractedDocuments = extractedDocumentsByAttachmentIdentity(reviewView);

  return {
    id: record.request_id,
    displayClaimId: displayClaimId || undefined,
    contractId: stringValue(claimData.contract_id),
    contractDisplayId: stringValue(claimData.contract_display_id || claimData.contractDisplayId) || undefined,
    clientId: String(record.client_id),
    clientName: stringValue(clientData.full_name) || "Unknown client",
    policyNumber: stringValue(claimData.policy_number),
    propertyAddress: stringValue(claimData.property_address),
    claimType,
    incidentDate: stringValue(claimData.incident_date),
    incidentTime: stringValue(claimData.incident_time),
    estimatedDamage: numberValue(claimData.estimated_damage),
    score: numberValue(confidence.score),
    scoreReasons: scoreReasons.length ? scoreReasons : ["Analysis has not been started."],
    status: statusFromDecision(decision) ?? toFrontendStatus(record.request_status),
    description: stringValue(claimData.description),
    emergencyServices: Boolean(claimData.emergency_services),
    hasPhotos: record.attachments.some((attachment) => isPhotoAttachment(attachment)),
    hasDocuments: record.attachments.some((attachment) => isDocumentAttachment(attachment)),
    contactPhone: stringValue(claimData.contact_phone || clientData.phone),
    contactEmail: stringValue(claimData.contact_email || clientData.email),
    evidence: record.attachments.map((attachment, index) =>
      toMockDocument(attachment, index, extractedDocuments)
    ),
    createdAt: dateValue(record.created_at),
    decision,
    decisionStatus,
    decisionJustification,
    decidedAt,
    decidedBy,
    decidedByEmail,
    decisionEmailSentAt,
    decisionEmailMessageId,
    rejectionReason: decision === "denied" ? decisionJustification : undefined,
    internalNote:
      decisionJustification ||
      stringValue(reviewView?.human_readable_summary) ||
      stringValue(summary.summary) ||
      stringValue(classification.rationale) ||
      undefined,
    reviewCaseId: caseId,
    reviewState,
    coverageAssessment: coverageAssessmentFromReviewView(reviewView),
    coveragePrecheck: coveragePrecheckFromReviewView(reviewView),
    documentConsistency: documentConsistencyFromReviewView(reviewView),
    supportingFacts: findingListFromReviewView(reviewView, "supporting_facts"),
    discrepancies: findingListFromReviewView(reviewView, "discrepancies"),
    suggestedNextAction: stringValue(reviewView?.suggested_next_action) || undefined,
    requiredEvidence: requiredEvidence.length ? requiredEvidence : undefined,
    aiReviewStatus: aiReviewStatusFromReviewView(reviewView, reviewState),
    aiReviewFindings: aiReviewFindingsFromReviewView(reviewView),
    aiFollowUpSuggestions: aiFollowUpSuggestionsFromReviewView(reviewView),
    communicationSuggestionStates: communicationSuggestionStatesFromReviewView(reviewView),
    humanReadableSummary: stringValue(reviewView?.human_readable_summary) || undefined,
    evidenceRequestDraft: evidenceDraft ? toEvidenceRequestDraft(evidenceDraft) : null,
    availableActions: arrayValue(reviewView?.available_actions).map(stringValue).filter(Boolean)
  };
}

function isMissingClaimReviewFindingsError(error: unknown) {
  return (
    error instanceof ApiError &&
    error.status === 404 &&
    error.message.toLowerCase().includes("latest claim review findings")
  );
}

function aiReviewStatusFromReviewView(
  reviewView?: Record<string, unknown> | null,
  reviewState?: string
): AiReviewLifecycleStatus {
  const explicitStatus = stringValue(
    reviewView?.ai_review_status ||
      reviewView?.aiReviewStatus ||
      objectValue(reviewView?.ai_validation_panel).status
  );
  if (explicitStatus) return explicitStatus;

  const workflowStatus = stringValue(objectValue(reviewView?.header).workflow_status);
  if (workflowStatus) return workflowStatus;
  if (!reviewView || reviewState === "not_started") return "not_started";
  if (reviewState?.includes("processing")) return "processing";
  if (reviewState === "failed") return "failed";
  return reviewState && reviewState !== "not_started" ? "completed" : "not_started";
}

function aiReviewFindingsFromReviewView(
  reviewView?: Record<string, unknown> | null
): AiReviewFinding[] | undefined {
  const findings = [
    ...arrayValue(reviewView?.ai_review_findings),
    ...arrayValue(reviewView?.aiReviewFindings),
    ...arrayValue(reviewView?.document_analysis_findings),
    ...arrayValue(reviewView?.documentAnalysisFindings)
  ]
    .map(toAiReviewFinding)
    .filter((item): item is AiReviewFinding => Boolean(item));
  return findings.length ? findings : undefined;
}

function toAiReviewFinding(value: unknown): AiReviewFinding | null {
  const finding = objectValue(value);
  const findingType = stringValue(finding.finding_type || finding.findingType || finding.type);
  const description = stringValue(finding.description || finding.message || finding.reason);
  if (!findingType && !description) return null;
  const relatedDocument = stringValue(
    finding.related_document || finding.relatedDocument || finding.source_document || finding.sourceDocument
  );
  const relatedRequirement = stringValue(
    finding.related_requirement || finding.relatedRequirement || finding.requirement_type || finding.requirementType
  );
  return {
    id:
      stringValue(finding.id || finding.finding_id || finding.findingId) ||
      slugIdentifier(`${findingType}-${relatedDocument}-${relatedRequirement}-${description}`),
    claimId: stringValue(finding.claim_id || finding.claimId) || undefined,
    findingType: findingType || "AI review finding",
    severity: stringValue(finding.severity || finding.priority) || "medium",
    description: description || "AI review finding details are not available yet.",
    relatedDocument: relatedDocument || undefined,
    relatedRequirement: relatedRequirement || undefined,
    recommendation: stringValue(finding.recommendation || finding.suggested_next_action || finding.suggestedNextAction) || undefined,
    suggestedFollowUpAction: stringValue(
      finding.suggested_follow_up_action || finding.suggestedFollowUpAction || finding.follow_up_action || finding.followUpAction
    ) || undefined,
    confidence: stringValue(finding.confidence || finding.confidence_score || finding.confidenceScore) || undefined,
    reviewStatus: stringValue(finding.review_status || finding.reviewStatus || finding.status) || undefined,
    createdAt: stringValue(finding.created_at || finding.createdAt) || undefined,
    source: stringValue(finding.source) || undefined
  };
}

function aiFollowUpSuggestionsFromReviewView(
  reviewView?: Record<string, unknown> | null
): AiFollowUpSuggestion[] | undefined {
  const suggestions = [
    ...arrayValue(reviewView?.ai_follow_up_suggestions),
    ...arrayValue(reviewView?.aiFollowUpSuggestions),
    ...arrayValue(reviewView?.follow_up_suggestions),
    ...arrayValue(reviewView?.followUpSuggestions),
    ...arrayValue(reviewView?.communication_suggestions),
    ...arrayValue(reviewView?.communicationSuggestions)
  ]
    .map(toAiFollowUpSuggestion)
    .filter((item): item is AiFollowUpSuggestion => Boolean(item));
  return suggestions.length ? suggestions : undefined;
}

function toAiFollowUpSuggestion(value: unknown): AiFollowUpSuggestion | null {
  const suggestion = objectValue(value);
  const draft = objectValue(suggestion.suggested_email_draft || suggestion.suggestedEmailDraft || suggestion.email_draft || suggestion.emailDraft);
  const subject = stringValue(
    suggestion.suggested_email_subject || suggestion.suggestedEmailSubject || draft.subject
  );
  const body = stringValue(
    suggestion.suggested_email_body || suggestion.suggestedEmailBody || draft.body
  );
  const title = stringValue(suggestion.title || suggestion.suggestion_title || suggestion.suggestionTitle);
  const reason = stringValue(suggestion.reason || suggestion.finding || suggestion.description);
  const recommendedRequest = stringValue(
    suggestion.recommended_request || suggestion.recommendedRequest || suggestion.suggested_request || suggestion.suggestedRequest
  );
  if (!title && !reason && !recommendedRequest && !subject && !body) return null;

  return {
    id:
      stringValue(suggestion.id || suggestion.suggestion_id || suggestion.suggestionId) ||
      slugIdentifier(`${title}-${reason}-${recommendedRequest}`),
    claimId: stringValue(suggestion.claim_id || suggestion.claimId) || undefined,
    title: title || "Review AI follow-up suggestion",
    reason: reason || "AI review finding details are not available yet.",
    recommendedRequest: recommendedRequest || "Review the suggested follow-up request before contacting the client.",
    priority: stringValue(suggestion.priority) || "Medium",
    confidence: stringValue(suggestion.confidence || suggestion.confidence_score || suggestion.confidenceScore) || "Medium",
    relatedRequirementId: stringValue(suggestion.related_requirement_id || suggestion.relatedRequirementId) || undefined,
    relatedDocumentId: stringValue(suggestion.related_document_id || suggestion.relatedDocumentId) || undefined,
    relatedRequirement: stringValue(suggestion.related_requirement || suggestion.relatedRequirement) || undefined,
    relatedEvidenceIssue: stringValue(suggestion.related_evidence_issue || suggestion.relatedEvidenceIssue) || undefined,
    suggestedEmailSubject: subject || "Additional document required for your claim",
    suggestedEmailBody: body || "Please provide the requested document so we can continue reviewing your claim.",
    suggestedEmailDraft: {
      subject: subject || "Additional document required for your claim",
      body: body || "Please provide the requested document so we can continue reviewing your claim.",
      requestedDocumentType: stringValue(draft.requested_document_type || draft.requestedDocumentType) || undefined,
      dueDate: stringValue(draft.due_date || draft.dueDate) || undefined
    },
    status: stringValue(suggestion.status) || "New",
    createdAt: stringValue(suggestion.created_at || suggestion.createdAt) || undefined,
    warnings: arrayValue(suggestion.warnings).map(stringValue).filter(Boolean),
    fullReasoning: stringValue(suggestion.full_reasoning || suggestion.fullReasoning || suggestion.reasoning) || undefined
  };
}

function communicationSuggestionStatesFromReviewView(
  reviewView?: Record<string, unknown> | null
): Record<string, ClaimCommunicationSuggestionState> | undefined {
  const rawStates = objectValue(
    reviewView?.communication_suggestion_states ||
      reviewView?.communicationSuggestionStates
  );
  const entries = Object.entries(rawStates)
    .map(([id, value]) => toCommunicationSuggestionState(id, value))
    .filter((item): item is ClaimCommunicationSuggestionState => Boolean(item));
  return entries.length
    ? Object.fromEntries(entries.map((state) => [state.suggestionId, state]))
    : undefined;
}

function toCommunicationSuggestionState(
  fallbackId: string,
  value: unknown
): ClaimCommunicationSuggestionState | null {
  const state = objectValue(value);
  const suggestionId = stringValue(
    state.suggestion_id || state.suggestionId || fallbackId
  );
  if (!suggestionId) return null;
  return {
    suggestionId,
    status: stringValue(state.status) || "new",
    source: stringValue(state.source) || undefined,
    draftId: stringValue(state.draft_id || state.draftId) || undefined,
    dismissedAt: stringValue(state.dismissed_at || state.dismissedAt) || undefined,
    createdAt: stringValue(state.created_at || state.createdAt) || undefined,
    updatedAt: stringValue(state.updated_at || state.updatedAt) || undefined
  };
}

function coverageAssessmentFromReviewView(
  reviewView?: Record<string, unknown> | null
): ClaimCoverageAssessment | undefined {
  const value = objectValue(reviewView?.coverage_assessment);
  return toCoverageAssessment(value);
}

function coveragePrecheckFromReviewView(
  reviewView?: Record<string, unknown> | null
): ClaimCoverageAssessment | undefined {
  const value = objectValue(reviewView?.coverage_precheck);
  return toCoverageAssessment(value);
}

function toCoverageAssessment(value: Record<string, unknown>): ClaimCoverageAssessment | undefined {
  const coverageStatus = stringValue(value.coverage_status);
  if (!coverageStatus) return undefined;
  return {
    coverageStatus,
    matchedWordingSections: arrayValue(value.matched_wording_sections).map(stringValue).filter(Boolean),
    wordingSectionIds: arrayValue(value.wording_section_ids).map(stringValue).filter(Boolean),
    possibleExclusions: arrayValue(value.possible_exclusions).map(stringValue).filter(Boolean),
    rationale: stringValue(value.rationale),
    confidence: stringValue(value.confidence),
    assessedAt: stringValue(value.assessed_at) || undefined
  };
}

function documentConsistencyFromReviewView(
  reviewView?: Record<string, unknown> | null
): ClaimDocumentConsistency | undefined {
  const value = objectValue(reviewView?.document_consistency);
  const status = stringValue(value.status);
  if (!status) return undefined;
  return {
    status,
    message: stringValue(value.message) || undefined,
    supportingFactCount: numberValue(value.supporting_fact_count),
    discrepancyCount: numberValue(value.discrepancy_count)
  };
}

function findingListFromReviewView(
  reviewView: Record<string, unknown> | null | undefined,
  key: "supporting_facts" | "discrepancies"
): ClaimDocumentFinding[] {
  return arrayValue(reviewView?.[key])
    .map(toDocumentFinding)
    .filter((item): item is ClaimDocumentFinding => Boolean(item));
}

function toDocumentFinding(value: unknown): ClaimDocumentFinding | null {
  const finding = objectValue(value);
  const message = stringValue(finding.message);
  const field = stringValue(finding.field);
  if (!message && !field) return null;
  return {
    field,
    claimValue: finding.claim_value,
    documentValue: finding.document_value,
    sourceDocument: stringValue(finding.source_document) || undefined,
    severity: stringValue(finding.severity) || undefined,
    message
  };
}

function draftFromReviewView(
  reviewView?: Record<string, unknown> | null
): BackendEvidenceRequestDraft | null {
  const draft = objectValue(reviewView?.evidence_request_draft);
  if (!draft.subject && !draft.body) return null;
  return draft as unknown as BackendEvidenceRequestDraft;
}

function evidenceRequirementsFromReviewView(
  reviewView?: Record<string, unknown> | null
): ClaimEvidenceRequirement[] {
  const requirements = arrayValue(reviewView?.required_evidence);
  const fallbackRequirements = requirements.length
    ? requirements
    : arrayValue(reviewView?.missing_evidence);
  return fallbackRequirements
    .map(toEvidenceRequirement)
    .filter((item): item is ClaimEvidenceRequirement => Boolean(item));
}

function toEvidenceRequirement(value: unknown): ClaimEvidenceRequirement | null {
  const requirement = objectValue(value);
  const requirementType = stringValue(requirement.requirement_type || requirement.requirementType);
  const reason = stringValue(requirement.reason);
  const acceptableDocuments = arrayValue(requirement.acceptable_documents || requirement.acceptableDocuments)
    .map(stringValue)
    .filter(Boolean);

  if (!requirementType && !reason && !acceptableDocuments.length) return null;
  return {
    requirementType,
    reason,
    acceptableDocuments,
    severity: stringValue(requirement.severity) || undefined,
    status: stringValue(requirement.status) || undefined,
    suggestedNextAction: stringValue(requirement.suggested_next_action) || undefined
  };
}

function toEvidenceRequestDraft(
  draft: BackendEvidenceRequestDraft
): EvidenceRequestDraft {
  return {
    draftId: stringValue(draft.draft_id) || undefined,
    claimRequestId: stringValue(draft.claim_request_id),
    subject: stringValue(draft.subject),
    body: stringValue(draft.body),
    recipients: arrayValue(draft.recipients).map(stringValue).filter(Boolean),
    requiredDocuments: arrayValue(draft.required_documents).map(stringValue).filter(Boolean),
    status: stringValue(draft.status) || "draft",
    sourceSuggestionId: stringValue(draft.source_suggestion_id) || undefined,
    requestedDocumentType: stringValue(draft.requested_document_type) || undefined,
    dueDate: stringValue(draft.due_date) || undefined,
    sendStatus: stringValue(draft.send_status) || undefined,
    sentAt: stringValue(draft.sent_at) || undefined,
    sentTo: arrayValue(draft.sent_to).map(stringValue).filter(Boolean),
    providerMessageId: stringValue(draft.provider_message_id) || undefined,
    emailMessageId: stringValue(draft.email_message_id) || undefined,
    replyToken: stringValue(draft.reply_token) || undefined,
    sendErrorMessage: stringValue(draft.send_error_message) || undefined,
    createdAt: stringValue(draft.created_at) || undefined,
    updatedAt: stringValue(draft.updated_at) || undefined
  };
}

function claimDecisionValue(value: unknown): Claim["decision"] | undefined {
  const decision = stringValue(value).toLowerCase();
  if (
    decision === "approved" ||
    decision === "denied" ||
    decision === "inspection_requested"
  ) {
    return decision;
  }
  return undefined;
}

function statusFromDecision(decision: Claim["decision"] | undefined): ClaimStatus | undefined {
  if (decision === "approved") return "accepted";
  if (decision === "denied") return "rejected";
  if (decision === "inspection_requested") return "inspection_requested";
  return undefined;
}

function toFrontendStatus(status: string): ClaimStatus {
  if (status === "rejected" || status === "precheck_rejected") {
    return "rejected";
  }
  if (
    status === "in_review" ||
    status === "screening" ||
    status === "needs_underwriter_review" ||
    status === "coverage_review_required" ||
    status === "failed" ||
    status === "completed"
  ) {
    return "in_review";
  }
  return "submitted";
}

function toMockDocument(
  attachment: BackendAttachment,
  index: number,
  extractedDocuments: ExtractedDocumentLookup = emptyExtractedDocumentLookup()
): MockDocument {
  const fileName = attachment.file_name || `attachment-${index + 1}`;
  const label = String(attachment.metadata?.label || fileName);
  const fileUrl = stringValue(attachment.file_url) || undefined;
  const extractedDocument = extractedDocumentForAttachment(
    attachment,
    fileName,
    fileUrl,
    extractedDocuments
  );
  return {
    id: attachment.file_url || fileName,
    label,
    fileName,
    type: documentType(fileName, label, attachment.content_type),
    url: resolveApiUrl(fileUrl),
    fileUrl,
    contentType: attachment.content_type,
    sizeBytes: attachment.size_bytes,
    storageKey: stringValue(attachment.metadata?.storage_key) || undefined,
    metadata: mergeAttachmentExtractionMetadata(attachment.metadata, extractedDocument)
  };
}

function mergeAttachmentExtractionMetadata(
  metadata: BackendAttachment["metadata"] | undefined,
  extractedDocument?: Record<string, unknown>
) {
  const base = metadata ? { ...metadata } : {};
  if (!extractedDocument) return Object.keys(base).length ? base : undefined;
  const extractedFields = objectValue(extractedDocument.extracted_fields);
  const extractionMetadata = objectValue(extractedDocument.extraction_metadata);
  const extractedText = stringValue(extractedFields.extracted_text);
  return {
    ...base,
    extracted_fields: extractedFields,
    extracted_text: extractedText,
    extraction_confidence: extractedDocument.extraction_confidence,
    extraction_document_type: extractedDocument.document_type,
    extraction_message: extractedDocument.extraction_message,
    extraction_provenance: extractedDocument.extraction_provenance,
    extraction_source: extractedDocument.source,
    extraction_status: extractedDocument.extraction_status,
    extraction_metadata: extractionMetadata
  };
}

interface ExtractedDocumentLookup {
  byIdentity: Map<string, Record<string, unknown>>;
  byUniqueFilename: Map<string, Record<string, unknown>>;
}

function emptyExtractedDocumentLookup(): ExtractedDocumentLookup {
  return {
    byIdentity: new Map(),
    byUniqueFilename: new Map()
  };
}

function extractedDocumentForAttachment(
  attachment: BackendAttachment,
  fileName: string,
  fileUrl: string | undefined,
  lookup: ExtractedDocumentLookup
) {
  const metadata = objectValue(attachment.metadata);
  const identityKeys = [
    identityKey("attachment_id", metadata.attachment_id),
    identityKey("storage_key", metadata.storage_key),
    identityKey("file_url", attachment.file_url || fileUrl)
  ].filter(Boolean);

  for (const key of identityKeys) {
    const document = lookup.byIdentity.get(key);
    if (document) return document;
  }

  return lookup.byUniqueFilename.get(filenameKey(fileName));
}

function extractedDocumentsByAttachmentIdentity(
  reviewView?: Record<string, unknown> | null
) {
  const bundle = objectValue(reviewView?.extracted_documents || reviewView?.extractedDocuments);
  const documents = arrayValue(bundle.documents).map((document) => objectValue(document));
  const lookup = emptyExtractedDocumentLookup();
  const documentsByFilename = new Map<string, Record<string, unknown>>();
  const filenameCounts = new Map<string, number>();

  documents.forEach((document) => {
    const extractionMetadata = objectValue(document.extraction_metadata);
    addIdentityDocument(lookup.byIdentity, "attachment_id", extractionMetadata.attachment_id, document);
    addIdentityDocument(lookup.byIdentity, "storage_key", extractionMetadata.storage_key, document);
    addIdentityDocument(lookup.byIdentity, "file_url", extractionMetadata.file_url, document);

    const filename = filenameKey(stringValue(document.filename));
    if (!filename) return;
    filenameCounts.set(filename, (filenameCounts.get(filename) || 0) + 1);
    documentsByFilename.set(filename, document);
  });

  documentsByFilename.forEach((document, filename) => {
    if (filenameCounts.get(filename) === 1) {
      lookup.byUniqueFilename.set(filename, document);
    }
  });

  return lookup;
}

function addIdentityDocument(
  map: Map<string, Record<string, unknown>>,
  kind: string,
  value: unknown,
  document: Record<string, unknown>
) {
  const key = identityKey(kind, value);
  if (key) map.set(key, document);
}

function identityKey(kind: string, value: unknown) {
  const text = stringValue(value).trim();
  return text ? `${kind}:${text}` : "";
}

function filenameKey(value: string) {
  return value.trim().toLowerCase();
}

function documentType(fileName: string, label: string, contentType?: string): MockDocument["type"] {
  const extension = fileName.split(".").pop()?.toUpperCase();
  if (extension === "JPEG") return "JPG";
  if (["PDF", "DOCX", "JPG", "PNG", "ZIP"].includes(extension || "")) {
    return extension as MockDocument["type"];
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

function isPhotoAttachment(attachment: BackendAttachment) {
  const label = String(attachment.metadata?.label || "");
  return isImageName(attachment.file_name) || label.toLowerCase().includes("photo");
}

function isDocumentAttachment(attachment: BackendAttachment) {
  const label = String(attachment.metadata?.label || "");
  const haystack = `${attachment.file_name} ${attachment.content_type} ${label}`.toLowerCase();
  return ["document", "pdf", "invoice", "report", "doc"].some((token) =>
    haystack.includes(token)
  );
}

function isImageName(fileName: string) {
  return /\.(jpg|jpeg|png)$/i.test(fileName);
}

function claimTypeValue(value: unknown): ClaimType {
  const text = String(value || "Other");
  if (["Fire", "Water damage", "Theft", "Storm", "Other"].includes(text)) {
    return text as ClaimType;
  }
  return "Other";
}

function uniqueById(claims: Claim[]) {
  return Array.from(new Map(claims.map((claim) => [claim.id, claim])).values()).sort(
    (first, second) => second.createdAt.localeCompare(first.createdAt)
  );
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function numberValue(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function dateValue(value: unknown) {
  return stringValue(value).slice(0, 10) || new Date().toISOString().slice(0, 10);
}

function slugIdentifier(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80) || "ai-review-item";
}

