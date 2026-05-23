from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from underwright.api.dependencies import (
    get_current_auth_user,
    get_current_employee_user,
    get_wording_document_service,
)
from underwright.api.main import create_app
from underwright.application.services.wording_document_service import (
    WordingDocumentNotFoundError,
    WordingVersionNotFoundError,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.wording import WordingDocument, WordingDocumentVersion


def test_wording_documents_require_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/wording-documents")

    assert response.status_code == 401


def test_client_cannot_list_wording_documents() -> None:
    app = create_app()
    app.dependency_overrides[get_current_auth_user] = lambda: _user("client")
    app.dependency_overrides[get_wording_document_service] = lambda: FakeWordingService()
    client = TestClient(app)

    response = client.get("/wording-documents")

    assert response.status_code == 403


def test_employee_can_list_wording_documents() -> None:
    app = _app_with_employee()
    client = TestClient(app)

    response = client.get("/wording-documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["code"] == "DEMO_PAD_POLICY_WORDING_RO"
    assert payload[0]["product_line"] == "property"
    assert payload[0]["jurisdiction"] == "RO"
    assert payload[0]["language"] == "ro-RO"
    assert payload[0]["status"] == "published"


def test_admin_can_fetch_wording_document_detail() -> None:
    app = create_app()
    app.dependency_overrides[get_current_auth_user] = lambda: _user("admin")
    app.dependency_overrides[get_wording_document_service] = lambda: FakeWordingService()
    client = TestClient(app)

    response = client.get("/wording-documents/1")

    assert response.status_code == 200
    assert response.json()["title"] == "PAD Property Insurance Wording RO"


def test_employee_can_fetch_wording_versions() -> None:
    app = _app_with_employee()
    client = TestClient(app)

    response = client.get("/wording-documents/1/versions")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["version"] == "1.0"
    assert payload[0]["content_hash"] == "content-hash"
    assert payload[0]["published_at"] is not None


def test_employee_can_fetch_current_wording_version() -> None:
    app = _app_with_employee()
    client = TestClient(app)

    response = client.get("/wording-documents/1/versions/current")

    assert response.status_code == 200
    assert response.json()["status"] == "published"


def test_employee_can_fetch_wording_version_detail() -> None:
    app = _app_with_employee()
    client = TestClient(app)

    response = client.get("/wording-document-versions/10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["wording_document_id"] == 1
    assert payload["legal_references_json"] == ["ro:lege:260:2008"]


def test_missing_wording_document_returns_404() -> None:
    app = _app_with_employee()
    client = TestClient(app)

    response = client.get("/wording-documents/404")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORDING_DOCUMENT_NOT_FOUND"


def test_missing_wording_version_returns_404() -> None:
    app = _app_with_employee()
    client = TestClient(app)

    response = client.get("/wording-document-versions/404")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORDING_VERSION_NOT_FOUND"


class FakeWordingService:
    def list_wording_documents(self) -> list[WordingDocument]:
        return [_document()]

    def get_wording_document(self, wording_document_id: int) -> WordingDocument:
        if wording_document_id != 1:
            raise WordingDocumentNotFoundError("missing")
        return _document()

    def list_wording_versions(
        self,
        wording_document_id: int,
    ) -> list[WordingDocumentVersion]:
        if wording_document_id != 1:
            raise WordingDocumentNotFoundError("missing")
        return [_version()]

    def get_current_published_version(
        self,
        wording_document_id: int,
    ) -> WordingDocumentVersion:
        if wording_document_id != 1:
            raise WordingDocumentNotFoundError("missing")
        return _version()

    def get_wording_version(self, wording_version_id: int) -> WordingDocumentVersion:
        if wording_version_id != 10:
            raise WordingVersionNotFoundError("missing")
        return _version()


def _app_with_employee():
    app = create_app()
    user = _user("employee")
    app.dependency_overrides[get_current_auth_user] = lambda: user
    app.dependency_overrides[get_current_employee_user] = lambda: user
    app.dependency_overrides[get_wording_document_service] = lambda: FakeWordingService()
    return app


def _user(role: str) -> AuthUser:
    return AuthUser(
        id=1,
        email=f"{role}@example.test",
        password_hash="hash",
        role=role,
        full_name=f"{role.title()} User",
        is_active=True,
    )


def _document() -> WordingDocument:
    return WordingDocument(
        id=1,
        code="DEMO_PAD_POLICY_WORDING_RO",
        title="PAD Property Insurance Wording RO",
        product_line="property",
        jurisdiction="RO",
        language="ro-RO",
        status="published",
        metadata_json={"is_synthetic": True},
        created_at=_now(),
        updated_at=_now(),
    )


def _version() -> WordingDocumentVersion:
    return WordingDocumentVersion(
        id=10,
        wording_document_id=1,
        version="1.0",
        status="published",
        full_text="Legal wording",
        content_hash="content-hash",
        legal_references_json=["ro:lege:260:2008"],
        effective_from=date(2026, 5, 14),
        published_at=_now(),
        created_at=_now(),
        updated_at=_now(),
    )


def _now() -> datetime:
    return datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc)
