from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from underwright.api.dependencies import (
    get_claim_attachment_storage_service,
    get_current_auth_user,
    get_current_client_user,
    get_current_employee_user,
    get_customer_profile_document_service,
    get_customer_profile_service,
)
from underwright.api.main import create_app
from underwright.application.services.claim_attachment_storage_service import (
    StoredClaimAttachment,
)
from underwright.application.services.customer_profile_document_service import (
    CustomerProfileDocumentNotFoundError,
    CustomerProfileDocumentOwnershipError,
)
from underwright.application.services.customer_profile_service import (
    CustomerProfileIncompleteError,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.claim_request import ClaimAttachmentMetadata
from underwright.domain.customer_profile import (
    CustomerAddressProfile,
    CustomerProfileReadModel,
)
from underwright.domain.customer_profile_document import CustomerProfileDocument


class FakeCustomerProfileService:
    def __init__(self, *, complete_update: bool = True) -> None:
        self.complete_update = complete_update

    def get_profile(self, user: AuthUser) -> CustomerProfileReadModel:
        if user.client_id is None:
            return CustomerProfileReadModel(
                status="pending_customer_link",
                requires_customer_profile_completion=True,
                full_name=user.full_name,
                email=user.email,
                phone=user.phone,
                missing_fields=["type", "address.country"],
            )
        return _profile(customer_id=user.client_id)

    def update_profile(self, *, user: AuthUser, update):
        del user, update
        if not self.complete_update:
            raise CustomerProfileIncompleteError(
                missing_fields=["national_id"],
                status="pending_customer_link",
            )
        return _profile(customer_id=303)

    def list_customer_profiles(self):
        return [_profile(customer_id=101)]

    def get_customer_profile(self, customer_id: int):
        return _profile(customer_id=customer_id)


class FakeCustomerProfileDocumentService:
    def __init__(
        self,
        documents: list[CustomerProfileDocument] | None = None,
    ) -> None:
        self.documents = documents or []
        self.deleted_ids: list[UUID] = []

    def list_for_user(self, user: AuthUser) -> list[CustomerProfileDocument]:
        self._assert_linked_client(user)
        return self.documents

    def create_for_user(
        self,
        *,
        user: AuthUser,
        label: str,
        document_type: str | None,
        stored_attachment: ClaimAttachmentMetadata,
    ) -> CustomerProfileDocument:
        self._assert_linked_client(user)
        document = _profile_document(
            customer_id=user.client_id or 0,
            label=label,
            document_type=document_type or label,
            file_name=stored_attachment.file_name,
            content_type=stored_attachment.content_type,
            size_bytes=stored_attachment.size_bytes,
            storage_key=str(stored_attachment.metadata["storage_key"]),
        )
        self.documents = [
            document,
            *[item for item in self.documents if item.label != label],
        ]
        return document

    def get_for_user(
        self,
        *,
        user: AuthUser,
        document_id: UUID,
    ) -> CustomerProfileDocument:
        self._assert_linked_client(user)
        for document in self.documents:
            if document.id == document_id:
                return document
        raise CustomerProfileDocumentNotFoundError("missing")

    def delete_for_user(self, *, user: AuthUser, document_id: UUID) -> None:
        self._assert_linked_client(user)
        if not any(document.id == document_id for document in self.documents):
            raise CustomerProfileDocumentNotFoundError("missing")
        self.deleted_ids.append(document_id)
        self.documents = [
            document for document in self.documents if document.id != document_id
        ]

    def _assert_linked_client(self, user: AuthUser) -> None:
        if user.client_id is None:
            raise CustomerProfileDocumentOwnershipError("linked client required")


class FakeProfileDocumentStorage:
    def __init__(self, directory: Path) -> None:
        self.path = directory / "profile-document.pdf"
        self.path.write_bytes(b"%PDF profile document")

    def save_attachment(
        self,
        *,
        file_name: str,
        content_type: str | None,
        content,
    ) -> ClaimAttachmentMetadata:
        data = content.read()
        return ClaimAttachmentMetadata(
            file_name=file_name,
            content_type=content_type or "application/octet-stream",
            size_bytes=len(data),
            file_url="/me/customer-profile/documents/document-id/download",
            metadata={"storage_key": "profile-documents/test-profile-document.pdf"},
        )

    def get_attachment(self, storage_key: str) -> StoredClaimAttachment:
        assert storage_key == "profile-documents/test-profile-document.pdf"
        return StoredClaimAttachment(
            path=self.path,
            file_name="profile-document.pdf",
            content_type="application/pdf",
            size_bytes=self.path.stat().st_size,
        )


def test_get_customer_profile_requires_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/me/customer-profile")

    assert response.status_code == 401


def test_non_client_cannot_get_customer_profile() -> None:
    app = create_app()
    app.dependency_overrides[get_current_auth_user] = lambda: AuthUser(
        id=2,
        email="uw@example.test",
        password_hash="hash",
        role="underwriter",
        full_name="Underwriter",
        is_active=True,
    )
    client = TestClient(app)

    response = client.get("/me/customer-profile")

    assert response.status_code == 403


def test_unlinked_client_gets_pending_profile_status() -> None:
    app = _app_with_client(client_id=None)
    app.dependency_overrides[get_customer_profile_service] = (
        lambda: FakeCustomerProfileService()
    )
    client = TestClient(app)

    response = client.get("/me/customer-profile")

    assert response.status_code == 200
    assert response.json()["status"] == "pending_customer_link"
    assert response.json()["requires_customer_profile_completion"] is True


def test_put_customer_profile_returns_audit_metadata() -> None:
    app = _app_with_client(client_id=None)
    app.dependency_overrides[get_customer_profile_service] = (
        lambda: FakeCustomerProfileService()
    )
    client = TestClient(app)

    response = client.put("/me/customer-profile", json=_valid_profile_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["customer_id"] == 303
    assert payload["status"] == "complete"
    assert payload["customer_profile_completed_at"] is not None
    assert payload["customer_profile_completion_source"] == "client_self_service"


def test_put_customer_profile_rejects_customer_id_from_client() -> None:
    app = _app_with_client(client_id=None)
    app.dependency_overrides[get_customer_profile_service] = (
        lambda: FakeCustomerProfileService()
    )
    client = TestClient(app)
    payload = _valid_profile_payload()
    payload["customer_id"] = 999

    response = client.put("/me/customer-profile", json=payload)

    assert response.status_code == 422


def test_employee_can_list_customer_profile_statuses() -> None:
    app = _app_with_employee()
    app.dependency_overrides[get_customer_profile_service] = (
        lambda: FakeCustomerProfileService()
    )
    client = TestClient(app)

    response = client.get("/customers")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["status"] == "complete"
    assert payload[0]["customer_profile_updated_at"] is not None


def test_client_can_list_customer_profile_documents() -> None:
    app = _app_with_client(client_id=101)
    service = FakeCustomerProfileDocumentService(
        [_profile_document(customer_id=101, label="Identity document")]
    )
    app.dependency_overrides[get_customer_profile_document_service] = lambda: service
    client = TestClient(app)

    response = client.get("/me/customer-profile/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["customer_id"] == 101
    assert payload[0]["label"] == "Identity document"
    assert payload[0]["file_url"] == "/me/customer-profile/documents/document-id/download"


def test_client_can_upload_customer_profile_document(tmp_path: Path) -> None:
    app = _app_with_client(client_id=101)
    service = FakeCustomerProfileDocumentService()
    app.dependency_overrides[get_customer_profile_document_service] = lambda: service
    app.dependency_overrides[get_claim_attachment_storage_service] = (
        lambda: FakeProfileDocumentStorage(tmp_path)
    )
    client = TestClient(app)

    response = client.post(
        "/me/customer-profile/documents",
        data={"label": "Identity document", "document_type": "identity"},
        files={"file": ("identity.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["customer_id"] == 101
    assert payload["label"] == "Identity document"
    assert payload["document_type"] == "identity"
    assert payload["storage_key"] == "profile-documents/test-profile-document.pdf"
    assert service.documents[0].file_name == "identity.pdf"


def test_client_can_download_owned_customer_profile_document(tmp_path: Path) -> None:
    app = _app_with_client(client_id=101)
    document = _profile_document(customer_id=101, label="Identity document")
    app.dependency_overrides[get_customer_profile_document_service] = (
        lambda: FakeCustomerProfileDocumentService([document])
    )
    app.dependency_overrides[get_claim_attachment_storage_service] = (
        lambda: FakeProfileDocumentStorage(tmp_path)
    )
    client = TestClient(app)

    response = client.get(f"/me/customer-profile/documents/{document.id}/download")

    assert response.status_code == 200
    assert response.content == b"%PDF profile document"
    assert response.headers["content-type"] == "application/pdf"


def test_client_can_delete_customer_profile_document() -> None:
    app = _app_with_client(client_id=101)
    document = _profile_document(customer_id=101, label="Identity document")
    service = FakeCustomerProfileDocumentService([document])
    app.dependency_overrides[get_customer_profile_document_service] = lambda: service
    client = TestClient(app)

    response = client.delete(f"/me/customer-profile/documents/{document.id}")

    assert response.status_code == 204
    assert service.deleted_ids == [document.id]


def test_unlinked_client_cannot_access_customer_profile_documents() -> None:
    app = _app_with_client(client_id=None)
    app.dependency_overrides[get_customer_profile_document_service] = (
        lambda: FakeCustomerProfileDocumentService()
    )
    client = TestClient(app)

    response = client.get("/me/customer-profile/documents")

    assert response.status_code == 400
    assert response.json()["detail"] == "linked client required"


def test_client_cannot_list_customer_profile_statuses() -> None:
    app = _app_with_client(client_id=101)
    app.dependency_overrides[get_customer_profile_service] = (
        lambda: FakeCustomerProfileService()
    )
    client = TestClient(app)

    response = client.get("/customers")

    assert response.status_code == 403


def _app_with_client(client_id: int | None):
    app = create_app()
    user = AuthUser(
        id=1,
        email="client@example.test",
        password_hash="hash",
        role="client",
        full_name="Client User",
        phone="+40700000000",
        client_id=client_id,
        is_active=True,
    )
    app.dependency_overrides[get_current_client_user] = lambda: user
    app.dependency_overrides[get_current_auth_user] = lambda: user
    return app


def _app_with_employee():
    app = create_app()
    user = AuthUser(
        id=2,
        email="uw@example.test",
        password_hash="hash",
        role="underwriter",
        full_name="Underwriter",
        is_active=True,
    )
    app.dependency_overrides[get_current_auth_user] = lambda: user
    app.dependency_overrides[get_current_employee_user] = lambda: user
    return app


def _profile(customer_id: int) -> CustomerProfileReadModel:
    now = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
    return CustomerProfileReadModel(
        customer_id=customer_id,
        status="complete",
        requires_customer_profile_completion=False,
        type="individual",
        full_name="Client User",
        national_id="1800101223344",
        email="client@example.test",
        phone="+40700000000",
        address=CustomerAddressProfile(
            country="Romania",
            county="Bucuresti",
            city="Bucuresti",
            street="Str. Lalelelor",
            number="12",
            postal_code="031234",
            full_text="Str. Lalelelor 12, Bucuresti",
        ),
        missing_fields=[],
        customer_profile_completed_at=now,
        customer_profile_updated_at=now,
        customer_profile_updated_by_auth_user_id=1,
        customer_profile_completion_source="client_self_service",
        profile_update_count=1,
        linked_auth_user_count=1,
    )


def _profile_document(
    *,
    customer_id: int,
    label: str,
    document_type: str | None = None,
    file_name: str = "profile-document.pdf",
    content_type: str = "application/pdf",
    size_bytes: int = 120,
    storage_key: str = "profile-documents/test-profile-document.pdf",
) -> CustomerProfileDocument:
    now = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
    return CustomerProfileDocument(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        customer_id=customer_id,
        label=label,
        document_type=document_type or label,
        file_name=file_name,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_key=storage_key,
        file_url="/me/customer-profile/documents/document-id/download",
        metadata={"label": label, "source": "client_profile"},
        created_at=now,
        updated_at=now,
    )


def _valid_profile_payload() -> dict:
    return {
        "type": "individual",
        "full_name": "Client User",
        "national_id": "1800101223344",
        "email": "client@example.test",
        "phone": "+40700000000",
        "address": {
            "country": "Romania",
            "county": "Bucuresti",
            "city": "Bucuresti",
            "street": "Str. Lalelelor",
            "number": "12",
            "postal_code": "031234",
        },
    }
