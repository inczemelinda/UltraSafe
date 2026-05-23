import type { AuthUserSearchParams, AuthUserSearchResult } from "../../types";
import { apiRequest } from "./http";

export async function searchAuthUsers(
  params: AuthUserSearchParams = {}
): Promise<AuthUserSearchResult[]> {
  const query = new URLSearchParams();
  if (params.query) query.set("q", params.query);
  if (params.role) query.set("role", params.role);
  if (params.unlinkedOnly !== undefined) {
    query.set("unlinked_only", String(params.unlinkedOnly));
  }
  if (params.limit !== undefined) query.set("limit", String(params.limit));

  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest<AuthUserSearchResult[]>(`/auth-users${suffix}`);
}

