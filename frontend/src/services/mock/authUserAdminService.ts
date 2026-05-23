import { mockUsers } from "../../data/mockUsers";
import type { AppUser, AuthUserSearchParams, AuthUserSearchResult } from "../../types";
import { delay, readStored } from "../storage";

const usersKey = "ultrasafe_users_v4";

export async function searchAuthUsers(
  params: AuthUserSearchParams = {}
): Promise<AuthUserSearchResult[]> {
  const users = readStored(usersKey, mockUsers);
  const query = params.query?.trim().toLowerCase() ?? "";
  const role = params.role ?? "client";
  const unlinkedOnly = params.unlinkedOnly ?? true;
  const limit = params.limit ?? 20;

  return delay(
    users
      .filter((user) => !role || user.role === role)
      .filter((user) => !unlinkedOnly || !user.customerId)
      .filter((user) => {
        if (!query) return true;
        return (
          user.email.toLowerCase().includes(query) ||
          user.fullName.toLowerCase().includes(query)
        );
      })
      .slice(0, limit)
      .map(toSearchResult)
  );
}

function toSearchResult(user: AppUser): AuthUserSearchResult {
  return {
    id: authUserSearchId(user),
    email: user.email,
    role: user.role,
    full_name: user.fullName,
    client_id: user.customerId ? Number.parseInt(user.customerId, 10) || null : null,
    customer_full_name: user.customerId ? user.fullName : null,
    is_active: true,
    status: "active",
    created_at: new Date().toISOString()
  };
}

export function authUserSearchId(user: AppUser) {
  const parsedId = Number.parseInt(user.id, 10);
  return Number.isFinite(parsedId) ? parsedId : Math.abs(hashString(user.email));
}

function hashString(value: string) {
  return value.split("").reduce((hash, char) => {
    return (hash << 5) - hash + char.charCodeAt(0);
  }, 0);
}


