from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_frontend_source(relative_path: str) -> str:
    return (ROOT / "frontend" / relative_path).read_text(encoding="utf-8")


def test_auth_session_uses_role_namespaced_storage_keys() -> None:
    source = read_frontend_source("src/services/authSession.ts")

    assert 'employee: "underwright_employee_user_v1"' in source
    assert 'client: "underwright_client_user_v1"' in source
    assert "setAuthSession(user: AppUser)" in source
    assert "authStorageKeys[user.role]" in source
    assert "clearAuthSession(role: UserRole)" in source
    assert "authStorageKeys[role]" in source


def test_auth_context_tracks_sessions_by_role() -> None:
    source = read_frontend_source("src/context/AuthContext.tsx")

    assert "getAuthSessions()" in source
    assert "setAuthSession(nextUser)" in source
    assert "[nextUser.role]: nextUser" in source
    assert "clearAuthSession(role)" in source
    assert "getUser: (role: UserRole) => sessions[role]" in source


def test_route_guards_read_required_role_session() -> None:
    source = read_frontend_source("src/routes/AppRoutes.tsx")

    assert "const { getUser } = useAuth();" in source
    assert "const user = getUser(role);" in source
    assert '<RequireRole role="client">' in source
    assert '<RequireRole role="employee">' in source
    assert 'path="/legal-review"' in source
    assert 'path="/contracts/:contractId" element={<EmployeeContractDetailPage />}' in source


def test_backend_http_uses_role_aware_token_selection() -> None:
    source = read_frontend_source("src/services/backend/http.ts")

    assert "authRole?: UserRole | \"none\"" in source
    assert "authRoleForApiPath(path)" in source
    assert "const url = resolveApiUrl(path)" in source
    assert 'inferredRole === "none"' in source
    assert "currentRouteAuthRole()" in source
    assert "getAccessToken(role)" in source
    assert "readAccessToken" not in source


def test_legal_change_service_uses_shared_employee_auth_helper() -> None:
    source = read_frontend_source("src/services/backend/legalChangeService.ts")

    assert 'getAuthSession("employee")' in source
    assert "underwright_current_user_v4" not in source


def test_auth_role_inference_covers_client_employee_and_legal_review_paths() -> None:
    source = read_frontend_source("src/services/authSession.ts")

    assert 'pathname === "/client"' in source
    assert 'pathname.startsWith("/client/")' in source
    assert 'pathname === "/employee"' in source
    assert 'pathname.startsWith("/employee/")' in source
    assert 'pathname === "/legal-review"' in source
    assert 'pathname.startsWith("/legal-review/")' in source
    assert 'pathname === "/me"' in source
    assert 'pathname.startsWith("/me/")' in source
    assert 'pathname.startsWith("/auth/")' in source
    assert 'pathname.startsWith("/underwriter/")' in source
