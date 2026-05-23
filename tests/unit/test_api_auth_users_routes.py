from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from underwright.api.dependencies import (
    get_auth_user_customer_link_service,
    get_auth_user_search_service,
    get_current_auth_user,
    get_current_employee_user,
    get_customer_profile_service,
)
from underwright.api.main import create_app
from underwright.application.services.auth_user_customer_link_service import (
    AuthUserAlreadyLinkedError,
    AuthUserCustomerLinkService,
    NonClientAuthUserLinkError,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.auth_user_admin import AuthUserSearchResult


class FakeAuthUserSearchService:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.users = [
            AuthUserSearchResult(
                id=1,
                email="unlinked@example.test",
                role="client",
                full_name="Unlinked Client",
                client_id=None,
                status="active",
                created_at=datetime(2026, 5, 13, tzinfo=timezone.utc),
            ),
            AuthUserSearchResult(
                id=2,
                email="linked@example.test",
                role="client",
                full_name="Linked Client",
                client_id=101,
                customer_full_name="Existing Customer",
                status="active",
                created_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
            ),
            AuthUserSearchResult(
                id=3,
                email="underwriter@example.test",
                role="underwriter",
                full_name="Underwriter",
                client_id=None,
                status="active",
                created_at=datetime(2026, 5, 11, tzinfo=timezone.utc),
            ),
        ]

    def search_auth_users(
        self,
        *,
        query: str = "",
        role: str | None = "client",
        unlinked_only: bool = True,
        limit: int = 20,
    ) -> list[AuthUserSearchResult]:
        self.calls.append(
            {
                "query": query,
                "role": role,
                "unlinked_only": unlinked_only,
                "limit": limit,
            }
        )
        results = self.users
        if query:
            normalized = query.lower()
            results = [
                user
                for user in results
                if normalized in user.email.lower()
                or normalized in user.full_name.lower()
            ]
        if role:
            results = [user for user in results if user.role == role]
        if unlinked_only:
            results = [user for user in results if user.client_id is None]
        return results[:limit]


class FakeAuthUserRepository:
    def __init__(self, user: AuthUser) -> None:
        self.user = user
        self.updated_client_id = "not-called"
        self.customer_ids = {101, 202}

    def customer_exists(self, customer_id: int) -> bool:
        return customer_id in self.customer_ids

    def get_user_by_id(self, auth_user_id: int) -> AuthUser:
        if auth_user_id != self.user.id:
            raise ValueError("AuthUser not found")
        return self.user

    def update_user_client_id(self, *, user_id: int, client_id: int | None) -> AuthUser:
        self.updated_client_id = client_id
        return self.user.model_copy(update={"client_id": client_id})


class FakeCustomerProfileService:
    def __init__(self) -> None:
        self.marked_customer_id = None

    def mark_employee_link(self, *, customer_id: int, updated_by_auth_user_id: int | None):
        self.marked_customer_id = customer_id
        return None


class FakeConflictLinkService:
    def link_client_user(self, *, auth_user_id, customer_id, updated_by_auth_user_id=None):
        del auth_user_id, customer_id, updated_by_auth_user_id
        raise AuthUserAlreadyLinkedError(
            "Auth user is already linked to a different customer."
        )


def test_auth_user_search_requires_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/auth-users")

    assert response.status_code == 401


def test_client_cannot_search_auth_users() -> None:
    app = create_app()
    user = _client_user()
    app.dependency_overrides[get_current_auth_user] = lambda: user
    client = TestClient(app)

    response = client.get("/auth-users")

    assert response.status_code == 403


def test_employee_can_search_client_auth_users_by_email() -> None:
    app = _app_with_employee()
    service = FakeAuthUserSearchService()
    app.dependency_overrides[get_auth_user_search_service] = lambda: service
    client = TestClient(app)

    response = client.get(
        "/auth-users",
        params={"q": "unlinked", "role": "client", "unlinked_only": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["email"] == "unlinked@example.test"
    assert "password_hash" not in payload[0]
    assert service.calls[0]["query"] == "unlinked"


def test_role_client_excludes_employee_users() -> None:
    app = _app_with_employee()
    app.dependency_overrides[get_auth_user_search_service] = (
        lambda: FakeAuthUserSearchService()
    )
    client = TestClient(app)

    response = client.get("/auth-users", params={"role": "client", "unlinked_only": "false"})

    assert response.status_code == 200
    assert {item["role"] for item in response.json()} == {"client"}


def test_unlinked_only_excludes_already_linked_clients() -> None:
    app = _app_with_employee()
    app.dependency_overrides[get_auth_user_search_service] = (
        lambda: FakeAuthUserSearchService()
    )
    client = TestClient(app)

    response = client.get("/auth-users", params={"role": "client", "unlinked_only": "true"})

    assert response.status_code == 200
    assert [item["email"] for item in response.json()] == ["unlinked@example.test"]


def test_auth_user_search_limit_is_forwarded() -> None:
    app = _app_with_employee()
    service = FakeAuthUserSearchService()
    app.dependency_overrides[get_auth_user_search_service] = lambda: service
    client = TestClient(app)

    response = client.get("/auth-users", params={"limit": "1", "unlinked_only": "false"})

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert service.calls[0]["limit"] == 1


def test_link_endpoint_returns_conflict_for_user_linked_elsewhere() -> None:
    app = _app_with_employee()
    app.dependency_overrides[get_auth_user_customer_link_service] = (
        lambda: FakeConflictLinkService()
    )
    app.dependency_overrides[get_customer_profile_service] = (
        lambda: FakeCustomerProfileService()
    )
    client = TestClient(app)

    response = client.post("/customers/101/auth-users/1/link")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AUTH_USER_ALREADY_LINKED"


def test_linking_unlinked_client_succeeds() -> None:
    repository = FakeAuthUserRepository(_client_user(client_id=None))
    profile_service = FakeCustomerProfileService()
    service = AuthUserCustomerLinkService(repository, profile_service)

    user = service.link_client_user(
        auth_user_id=1,
        customer_id=101,
        updated_by_auth_user_id=9,
    )

    assert user.client_id == 101
    assert repository.updated_client_id == 101
    assert profile_service.marked_customer_id == 101


def test_linking_non_client_user_is_rejected() -> None:
    repository = FakeAuthUserRepository(_employee_user())
    service = AuthUserCustomerLinkService(repository, FakeCustomerProfileService())

    with pytest.raises(NonClientAuthUserLinkError):
        service.link_client_user(auth_user_id=2, customer_id=101)


def test_linking_user_already_linked_to_other_customer_is_conflict() -> None:
    repository = FakeAuthUserRepository(_client_user(client_id=202))
    service = AuthUserCustomerLinkService(repository, FakeCustomerProfileService())

    with pytest.raises(AuthUserAlreadyLinkedError):
        service.link_client_user(auth_user_id=1, customer_id=101)


def test_linking_user_already_linked_to_same_customer_is_idempotent() -> None:
    repository = FakeAuthUserRepository(_client_user(client_id=101))
    profile_service = FakeCustomerProfileService()
    service = AuthUserCustomerLinkService(repository, profile_service)

    user = service.link_client_user(auth_user_id=1, customer_id=101)

    assert user.client_id == 101
    assert repository.updated_client_id == "not-called"
    assert profile_service.marked_customer_id == 101


def _app_with_employee():
    app = create_app()
    user = _employee_user()
    app.dependency_overrides[get_current_auth_user] = lambda: user
    app.dependency_overrides[get_current_employee_user] = lambda: user
    return app


def _client_user(client_id: int | None = None) -> AuthUser:
    return AuthUser(
        id=1,
        email="client@example.test",
        password_hash="hash",
        role="client",
        full_name="Client User",
        client_id=client_id,
        is_active=True,
    )


def _employee_user() -> AuthUser:
    return AuthUser(
        id=2,
        email="employee@example.test",
        password_hash="hash",
        role="underwriter",
        full_name="Employee User",
        is_active=True,
    )
