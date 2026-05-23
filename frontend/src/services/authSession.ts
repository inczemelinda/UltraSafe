import type { AppUser, UserRole } from "../types";

export const authStorageKeys: Record<UserRole, string> = {
  employee: "ultrasafe_employee_user_v1",
  client: "ultrasafe_client_user_v1"
};

const legacyAuthStorageKey = "ultrasafe_current_user_v4";

export function getAuthSession(role: UserRole): AppUser | null {
  migrateLegacyAuthSession();
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(authStorageKeys[role]);
    return stored ? (JSON.parse(stored) as AppUser) : null;
  } catch {
    return null;
  }
}

export function getAuthSessions(): Record<UserRole, AppUser | null> {
  return {
    employee: getAuthSession("employee"),
    client: getAuthSession("client")
  };
}

export function setAuthSession(user: AppUser) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(authStorageKeys[user.role], JSON.stringify(user));
  window.localStorage.removeItem(legacyAuthStorageKey);
}

export function clearAuthSession(role: UserRole) {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(authStorageKeys[role]);
}

export function getAccessToken(role: UserRole): string | undefined {
  return getAuthSession(role)?.accessToken;
}

export function readStoredAuthUser(role?: UserRole): AppUser | null {
  if (role) return getAuthSession(role);

  const routeRole = currentRouteAuthRole();
  if (routeRole) return getAuthSession(routeRole);

  return getAuthSession("employee") ?? getAuthSession("client");
}

export function authRoleForPathname(pathname: string): UserRole | null {
  if (pathname === "/client" || pathname.startsWith("/client/")) return "client";
  if (
    pathname === "/employee" ||
    pathname.startsWith("/employee/") ||
    pathname === "/legal-review" ||
    pathname.startsWith("/legal-review/")
  ) {
    return "employee";
  }
  return null;
}

export type AuthRoleResolution = UserRole | "none" | null;

export function authRoleForApiPath(path: string): AuthRoleResolution {
  const pathname = apiPathname(path);
  if (!pathname || pathname === "/auth" || pathname.startsWith("/auth/")) return "none";
  if (pathname === "/me" || pathname.startsWith("/me/")) return "client";
  if (
    pathname === "/underwriter" ||
    pathname.startsWith("/underwriter/") ||
    pathname === "/customers" ||
    pathname.startsWith("/customers/") ||
    pathname === "/auth-users" ||
    pathname.startsWith("/auth-users/") ||
    pathname === "/intelligence" ||
    pathname.startsWith("/intelligence/") ||
    pathname === "/contracts" ||
    pathname.startsWith("/contracts/") ||
    pathname === "/generated-documents" ||
    pathname.startsWith("/generated-documents/") ||
    pathname === "/emails" ||
    pathname.startsWith("/emails/") ||
    pathname === "/quotes" ||
    pathname.startsWith("/quotes/") ||
    pathname === "/raw-ingestion" ||
    pathname.startsWith("/raw-ingestion/") ||
    pathname === "/wording-documents" ||
    pathname.startsWith("/wording-documents/")
  ) {
    return "employee";
  }
  return null;
}

export function currentRouteAuthRole(): UserRole | null {
  if (typeof window === "undefined") return null;
  return authRoleForPathname(window.location.pathname);
}

function migrateLegacyAuthSession() {
  if (typeof window === "undefined") return;
  const legacy = readUserFromKey(legacyAuthStorageKey);
  if (!legacy || !isUserRole(legacy.role)) {
    window.localStorage.removeItem(legacyAuthStorageKey);
    return;
  }

  const targetKey = authStorageKeys[legacy.role];
  if (!window.localStorage.getItem(targetKey)) {
    window.localStorage.setItem(targetKey, JSON.stringify(legacy));
  }
  window.localStorage.removeItem(legacyAuthStorageKey);
}

function readUserFromKey(key: string): AppUser | null {
  try {
    const stored = window.localStorage.getItem(key);
    return stored ? (JSON.parse(stored) as AppUser) : null;
  } catch {
    return null;
  }
}

function isUserRole(value: unknown): value is UserRole {
  return value === "employee" || value === "client";
}

function apiPathname(path: string): string {
  try {
    return new URL(path, "http://ultrasafe.local").pathname;
  } catch {
    return path.startsWith("/") ? path.split("?")[0] : `/${path.split("?")[0]}`;
  }
}


