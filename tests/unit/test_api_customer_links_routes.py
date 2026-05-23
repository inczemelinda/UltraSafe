from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from underwright.api.dependencies import (
    get_auth_user_customer_link_service,
    get_current_auth_user,
    get_current_employee_user,
)
from underwright.api.main import create_app
from underwright.application.services.auth_user_customer_link_service import (
    AuthUserAlreadyLinkedError,
    AuthUserCustomerLinkService,
    AuthUserNotFoundError,
    AuthUserNotLinkedError,
    CustomerNotFoundError,
    NonClientAuthUserLinkError,
    RelinkReasonRequiredError,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.auth_user_admin import (
    CustomerAuthUserLinkAuditRecord,
    CustomerAuthUserRelinkResult,
)


def test_relink_requires_authentication() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/customers/101/auth-users/1/relink",
        json={"reason": "Move duplicate client account to the active customer."},
    )

    assert response.status_code == 401


def test_client_cannot_relink_auth_users() -> None:
    app = create_app()
    app.dependency_overrides[get_current_auth_user] = lambda: _client_user(client_id=202)
    client = TestClient(app)

    response = client.post(
        "/customers/101/auth-users/1/relink",
        json={"reason": "Move duplicate client account to the active customer."},
    )

    assert response.status_code == 403


def test_employee_can_relink_client_auth_user() -> None:
    app = _app_with_employee()
    service = FakeRouteRelinkService()
    app.dependency_overrides[get_auth_user_customer_link_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/customers/101/auth-users/1/relink",
        json={"reason": "Move duplicate client account to the active customer."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_user_id"] == 1
    assert payload["old_customer_id"] == 202
    assert payload["new_customer_id"] == 101
    assert payload["reason"] == "Move duplicate client account to the active customer."
    assert service.calls[0]["changed_by_auth_user_id"] == 2


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (CustomerNotFoundError("Customer not found."), 404, "CUSTOMER_NOT_FOUND"),
        (AuthUserNotFoundError("Auth user not found."), 404, "AUTH_USER_NOT_FOUND"),
        (NonClientAuthUserLinkError("Only client users can be linked."), 400, "AUTH_USER_NOT_CLIENT"),
        (AuthUserNotLinkedError("Auth user is not linked."), 400, "AUTH_USER_NOT_LINKED"),
        (RelinkReasonRequiredError("Reason required."), 400, "RELINK_REASON_REQUIRED"),
    ],
)
def test_relink_maps_service_errors(error, status_code: int, code: str) -> None:
    app = _app_with_employee()
    service = FakeRouteRelinkService(error=error)
    app.dependency_overrides[get_auth_user_customer_link_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/customers/101/auth-users/1/relink",
        json={"reason": "Move duplicate client account to the active customer."},
    )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code


def test_normal_link_endpoint_still_conflicts_for_user_linked_elsewhere() -> None:
    app = _app_with_employee()
    service = FakeConflictLinkService()
    app.dependency_overrides[get_auth_user_customer_link_service] = lambda: service
    client = TestClient(app)

    response = client.post("/customers/101/auth-users/1/link")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AUTH_USER_ALREADY_LINKED"


def test_service_relink_unlinked_client_is_rejected() -> None:
    service = AuthUserCustomerLinkService(
        FakeAuthUserRepository(_client_user(client_id=None)),
        FakeCustomerProfileService(),
    )

    with pytest.raises(AuthUserNotLinkedError):
        service.relink_client_user(
            auth_user_id=1,
            customer_id=101,
            reason="Move duplicate client account to the active customer.",
            changed_by_auth_user_id=9,
        )


def test_service_relink_non_client_user_is_rejected() -> None:
    service = AuthUserCustomerLinkService(
        FakeAuthUserRepository(_employee_user()),
        FakeCustomerProfileService(),
    )

    with pytest.raises(NonClientAuthUserLinkError):
        service.relink_client_user(
            auth_user_id=2,
            customer_id=101,
            reason="Move duplicate client account to the active customer.",
            changed_by_auth_user_id=9,
        )


def test_service_relink_to_same_customer_is_idempotent() -> None:
    repository = FakeAuthUserRepository(_client_user(client_id=101))
    profile_service = FakeCustomerProfileService()
    service = AuthUserCustomerLinkService(repository, profile_service)

    result = service.relink_client_user(
        auth_user_id=1,
        customer_id=101,
        reason="",
        changed_by_auth_user_id=9,
    )

    assert result.old_customer_id == 101
    assert result.new_customer_id == 101
    assert repository.updated_client_id == "not-called"
    assert repository.audit_records == []
    assert profile_service.marked_customer_ids == []


def test_service_relink_requires_reason_when_moving_customer() -> None:
    repository = FakeAuthUserRepository(_client_user(client_id=202))
    service = AuthUserCustomerLinkService(repository, FakeCustomerProfileService())

    with pytest.raises(RelinkReasonRequiredError):
        service.relink_client_user(
            auth_user_id=1,
            customer_id=101,
            reason="too short",
            changed_by_auth_user_id=9,
        )

    assert repository.updated_client_id == "not-called"
    assert repository.audit_records == []


def test_service_relink_moves_user_and_writes_audit_record() -> None:
    repository = FakeAuthUserRepository(_client_user(client_id=202))
    profile_service = FakeCustomerProfileService()
    service = AuthUserCustomerLinkService(repository, profile_service)

    result = service.relink_client_user(
        auth_user_id=1,
        customer_id=101,
        reason="Move duplicate client account to the active customer.",
        changed_by_auth_user_id=9,
    )

    assert result.old_customer_id == 202
    assert result.old_customer_name == "Old Customer"
    assert result.new_customer_id == 101
    assert result.new_customer_name == "New Customer"
    assert result.changed_by_auth_user_id == 9
    assert repository.users[1].client_id == 101
    assert repository.list_users_by_client_id(202) == []
    assert [user.id for user in repository.list_users_by_client_id(101)] == [1]
    assert profile_service.marked_customer_ids == [202, 101]
    assert len(repository.audit_records) == 1
    audit = repository.audit_records[0]
    assert audit.action == "relink"
    assert audit.old_customer_id == 202
    assert audit.new_customer_id == 101
    assert audit.reason == "Move duplicate client account to the active customer."
    assert audit.changed_by_auth_user_id == 9


class FakeRouteRelinkService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    def relink_client_user(
        self,
        *,
        auth_user_id: int,
        customer_id: int,
        reason: str | None,
        changed_by_auth_user_id: int | None = None,
    ) -> CustomerAuthUserRelinkResult:
        self.calls.append(
            {
                "auth_user_id": auth_user_id,
                "customer_id": customer_id,
                "reason": reason,
                "changed_by_auth_user_id": changed_by_auth_user_id,
            }
        )
        if self.error is not None:
            raise self.error
        return CustomerAuthUserRelinkResult(
            auth_user_id=auth_user_id,
            auth_user_email="client@example.test",
            old_customer_id=202,
            old_customer_name="Old Customer",
            new_customer_id=customer_id,
            new_customer_name="New Customer",
            reason=reason or "",
            changed_by_auth_user_id=changed_by_auth_user_id,
            changed_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        )


class FakeConflictLinkService:
    def link_client_user(self, *, auth_user_id, customer_id, updated_by_auth_user_id=None):
        del auth_user_id, customer_id, updated_by_auth_user_id
        raise AuthUserAlreadyLinkedError(
            "Auth user is already linked to a different customer."
        )


class FakeAuthUserRepository:
    def __init__(self, user: AuthUser) -> None:
        if user.id is None:
            raise ValueError("Fake users need an id")
        self.users = {user.id: user}
        self.customer_ids = {101, 202}
        self.customer_names = {101: "New Customer", 202: "Old Customer"}
        self.updated_client_id = "not-called"
        self.audit_records: list[CustomerAuthUserLinkAuditRecord] = []

    def customer_exists(self, customer_id: int) -> bool:
        return customer_id in self.customer_ids

    def get_user_by_id(self, auth_user_id: int) -> AuthUser:
        try:
            return self.users[auth_user_id]
        except KeyError as exc:
            raise ValueError("AuthUser not found") from exc

    def list_users_by_client_id(self, client_id: int) -> list[AuthUser]:
        return [user for user in self.users.values() if user.client_id == client_id]

    def update_user_client_id(self, *, user_id: int, client_id: int | None) -> AuthUser:
        self.updated_client_id = client_id
        updated = self.users[user_id].model_copy(update={"client_id": client_id})
        self.users[user_id] = updated
        return updated

    def get_customer_display_name(self, customer_id: int) -> str | None:
        return self.customer_names.get(customer_id)

    def record_customer_auth_user_link_audit(
        self,
        *,
        action: str,
        auth_user_id: int,
        old_customer_id: int | None,
        new_customer_id: int | None,
        reason: str | None,
        changed_by_auth_user_id: int | None,
    ) -> CustomerAuthUserLinkAuditRecord:
        record = CustomerAuthUserLinkAuditRecord(
            id=len(self.audit_records) + 1,
            auth_user_id=auth_user_id,
            old_customer_id=old_customer_id,
            old_customer_name=self.get_customer_display_name(old_customer_id)
            if old_customer_id
            else None,
            new_customer_id=new_customer_id,
            new_customer_name=self.get_customer_display_name(new_customer_id)
            if new_customer_id
            else None,
            action=action,
            reason=reason,
            changed_by_auth_user_id=changed_by_auth_user_id,
            changed_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        )
        self.audit_records.append(record)
        return record


class FakeCustomerProfileService:
    def __init__(self) -> None:
        self.marked_customer_ids: list[int] = []

    def mark_employee_link(self, *, customer_id: int, updated_by_auth_user_id: int | None):
        del updated_by_auth_user_id
        self.marked_customer_ids.append(customer_id)
        return None


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
