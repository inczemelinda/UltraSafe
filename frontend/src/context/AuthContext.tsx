import {
  createContext,
  type ReactNode,
  useContext,
  useMemo,
  useState
} from "react";
import { useLocation } from "react-router-dom";
import type { AppUser, UserRole } from "../types";
import {
  authRoleForPathname,
  clearAuthSession,
  getAuthSessions,
  setAuthSession
} from "../services/authSession";

interface AuthContextValue {
  user: AppUser | null;
  getUser: (role: UserRole) => AppUser | null;
  setUser: (user: AppUser | null) => void;
  logout: (role?: UserRole) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const activeRole = authRoleForPathname(location.pathname);
  const [sessions, setSessions] = useState<Record<UserRole, AppUser | null>>(() =>
    getAuthSessions()
  );

  const user = activeRole ? sessions[activeRole] : (sessions.employee ?? sessions.client);

  function setUser(nextUser: AppUser | null) {
    if (nextUser) {
      setAuthSession(nextUser);
      setSessions((current) => ({ ...current, [nextUser.role]: nextUser }));
    } else {
      const role = activeRole ?? user?.role;
      if (!role) return;
      clearAuthSession(role);
      setSessions((current) => ({ ...current, [role]: null }));
    }
  }

  function logout(role = activeRole ?? user?.role) {
    if (!role) return;
    clearAuthSession(role);
    setSessions((current) => ({ ...current, [role]: null }));
  }

  const value = useMemo(
    () => ({
      user,
      getUser: (role: UserRole) => sessions[role],
      setUser,
      logout
    }),
    [activeRole, sessions, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

