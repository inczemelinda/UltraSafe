import type {
  LegalChangeReviewStatus,
  LegalChangeItem,
  TemplateChangeSuggestion,
  TemplateChangeSuggestionDetail,
  TemplateChangeSuggestionHunkStatus,
  TemplateDraftRevision
} from "../../types";
import { getAuthSession } from "../authSession";
import { ApiError, apiRequest, type ApiRequestOptions } from "./http";

export type LegalChangeReviewFilter = LegalChangeReviewStatus | "processed";

export async function getLegalChanges(
  status: LegalChangeReviewFilter = "needs_review"
): Promise<LegalChangeItem[]> {
  if (status === "processed") {
    const batches = await Promise.all([
      getLegalChangesByStatus("accepted"),
      getLegalChangesByStatus("dismissed")
    ]);
    return mergeLegalChangeItems(batches.flat());
  }
  return getLegalChangesByStatus(status);
}

async function getLegalChangesByStatus(
  status: LegalChangeReviewStatus
): Promise<LegalChangeItem[]> {
  const query = new URLSearchParams({ status, limit: "50" });
  return apiRequest<LegalChangeItem[]>(
    `/intelligence/legal-template-review-candidates?${query.toString()}`
  );
}

export async function createTemplateChangeSuggestion(
  candidateId: string
): Promise<TemplateChangeSuggestion> {
  return underwriterMutation<TemplateChangeSuggestion>(
    `/intelligence/legal-template-review-candidates/${encodeURIComponent(candidateId)}/suggestions`,
    { method: "POST" }
  );
}

export async function getTemplateChangeSuggestion(
  suggestionId: string
): Promise<TemplateChangeSuggestionDetail> {
  return apiRequest<TemplateChangeSuggestionDetail>(
    `/intelligence/template-change-suggestions/${encodeURIComponent(suggestionId)}`
  );
}

export async function updateTemplateChangeSuggestionHunk(
  suggestionId: string,
  hunkId: string,
  patch: {
    new_text?: string;
    status?: TemplateChangeSuggestionHunkStatus;
    reviewer_notes?: string;
  }
): Promise<TemplateChangeSuggestion> {
  return underwriterMutation<TemplateChangeSuggestion>(
    `/intelligence/template-change-suggestions/${encodeURIComponent(suggestionId)}/hunks/${encodeURIComponent(hunkId)}`,
    { body: patch, method: "PATCH" }
  );
}

export async function acceptTemplateChangeSuggestionHunk(
  suggestionId: string,
  hunkId: string
): Promise<TemplateChangeSuggestion> {
  return underwriterMutation<TemplateChangeSuggestion>(
    `/intelligence/template-change-suggestions/${encodeURIComponent(suggestionId)}/hunks/${encodeURIComponent(hunkId)}/accept`,
    { method: "POST" }
  );
}

export async function rejectTemplateChangeSuggestionHunk(
  suggestionId: string,
  hunkId: string
): Promise<TemplateChangeSuggestion> {
  return underwriterMutation<TemplateChangeSuggestion>(
    `/intelligence/template-change-suggestions/${encodeURIComponent(suggestionId)}/hunks/${encodeURIComponent(hunkId)}/reject`,
    { method: "POST" }
  );
}

export async function createDraftRevisionFromSuggestion(
  suggestionId: string
): Promise<TemplateDraftRevision> {
  return underwriterMutation<TemplateDraftRevision>(
    `/intelligence/template-change-suggestions/${encodeURIComponent(suggestionId)}/create-draft-revision`,
    { method: "POST" }
  );
}

export async function submitDraftRevisionForApproval(
  draftRevisionId: string
): Promise<TemplateDraftRevision> {
  return underwriterMutation<TemplateDraftRevision>(
    `/intelligence/template-draft-revisions/${encodeURIComponent(draftRevisionId)}/submit-for-approval`,
    { method: "POST" }
  );
}

async function underwriterMutation<T>(
  path: string,
  options: ApiRequestOptions
): Promise<T> {
  try {
    return await apiRequest<T>(path, {
      ...options,
      headers: employeeMutationHeaders(options.headers)
    });
  } catch (error) {
    if (!canRetryWithDemoUnderwriterHeader(error)) throw error;
    return apiRequest<T>(path, {
      ...options,
      headers: { "X-UltraSafe-Role": "underwriter" },
      skipAuth: true
    });
  }
}

function employeeMutationHeaders(existing?: HeadersInit): HeadersInit {
  const headers = new Headers(existing);
  const user = getAuthSession("employee");
  if (user?.accessToken) {
    headers.set("Authorization", `Bearer ${user.accessToken}`);
  } else if (user?.role === "employee") {
    headers.set("X-UltraSafe-Role", "underwriter");
  }
  return headers;
}

function canRetryWithDemoUnderwriterHeader(error: unknown) {
  const user = getAuthSession("employee");
  return (
    user?.role === "employee" &&
    error instanceof ApiError &&
    error.status === 401 &&
    error.message.toLowerCase().includes("invalid access token")
  );
}

function mergeLegalChangeItems(items: LegalChangeItem[]): LegalChangeItem[] {
  const byDocumentId = new Map<string, LegalChangeItem>();
  for (const item of items) {
    const existing = byDocumentId.get(item.legal_document.id);
    if (!existing) {
      byDocumentId.set(item.legal_document.id, item);
      continue;
    }
    const candidates = uniqueLegalReviewCandidates([
      ...existing.candidates,
      ...item.candidates
    ]);
    byDocumentId.set(item.legal_document.id, {
      ...existing,
      candidates,
      affected_template_count: new Set(
        candidates.map((candidate) => candidate.template_id)
      ).size,
      highest_confidence: Math.max(existing.highest_confidence, item.highest_confidence)
    });
  }
  return Array.from(byDocumentId.values());
}

function uniqueLegalReviewCandidates(candidates: LegalChangeItem["candidates"]) {
  return Array.from(
    new Map(candidates.map((candidate) => [candidate.candidate_id, candidate])).values()
  );
}


