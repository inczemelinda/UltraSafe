from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from underwright.application.services.customer_profile_service import (
    CustomerProfileIncompleteError,
)
from underwright.application.services.quote_acceptance_service import (
    QuoteAcceptanceDocumentMissingError,
    QuoteAcceptanceInvalidStatusError,
    QuoteAcceptanceNotFoundError,
    QuoteAcceptanceOwnershipError,
    QuoteAcceptanceService,
    QuoteAcceptanceValidationError,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.quote_acceptance import (
    QuoteAcceptance,
    QuoteAcceptanceCreate,
    QuoteAcceptanceInput,
)
from underwright.domain.quote_document import QuoteDocument
from underwright.domain.quote_request import QuoteRequest


QUOTE_ID = UUID("11111111-1111-4111-8111-000000000015")
DEFAULT_DOCUMENT = object()


def test_valid_client_acceptance_creates_immutable_record_and_marks_quote() -> None:
    quote_service = FakeQuoteRequestService(_quote())
    acceptance_repository = FakeQuoteAcceptanceRepository()
    service = _service(
        quote_service=quote_service,
        acceptance_repository=acceptance_repository,
    )

    acceptance = service.accept_quote_for_client(
        quote_id=QUOTE_ID,
        user=_client_user(),
        signer_input=_signer_input(),
        ip_address="127.0.0.1",
        user_agent="test-client",
    )

    assert acceptance.id == 1
    assert acceptance.quote_request_id == QUOTE_ID
    assert acceptance.quote_document_id == 77
    assert acceptance.accepted_by_auth_user_id == 10
    assert acceptance.accepted_by_customer_id == 1001
    assert acceptance.signer_name == "Ion Popescu"
    assert acceptance.signer_email == "ion@example.test"
    assert acceptance.acceptance_method == "client_portal"
    assert len(acceptance.quote_content_hash) == 64
    assert quote_service.updated_status == (QUOTE_ID, "auto_accepted")


def test_acceptance_marks_existing_generated_contract_issued() -> None:
    contract_repository = FakeContractRepository()
    service = _service(contract_repository=contract_repository)

    acceptance = service.accept_quote_for_client(
        quote_id=QUOTE_ID,
        user=_client_user(),
        signer_input=_signer_input(),
    )

    assert contract_repository.issued_contract == (QUOTE_ID, acceptance.id)


def test_duplicate_acceptance_returns_existing_record_without_mutation() -> None:
    existing = _acceptance()
    quote_service = FakeQuoteRequestService(_quote())
    acceptance_repository = FakeQuoteAcceptanceRepository(existing)
    service = _service(
        quote_service=quote_service,
        acceptance_repository=acceptance_repository,
    )

    acceptance = service.accept_quote_for_client(
        quote_id=QUOTE_ID,
        user=_client_user(),
        signer_input=_signer_input(signer_name="Different Signer"),
    )

    assert acceptance == existing
    assert acceptance_repository.created_records == []
    assert quote_service.updated_status is None


def test_client_cannot_accept_another_clients_quote() -> None:
    service = _service()

    with pytest.raises(QuoteAcceptanceOwnershipError):
        service.accept_quote_for_client(
            quote_id=QUOTE_ID,
            user=_client_user(client_id=2002),
            signer_input=_signer_input(),
        )


def test_incomplete_profile_blocks_acceptance() -> None:
    service = _service(profile_service=FakeIncompleteProfileService())

    with pytest.raises(CustomerProfileIncompleteError):
        service.accept_quote_for_client(
            quote_id=QUOTE_ID,
            user=_client_user(),
            signer_input=_signer_input(),
        )


def test_invalid_quote_status_blocks_acceptance() -> None:
    service = _service(quote=_quote(request_status="draft"))

    with pytest.raises(QuoteAcceptanceInvalidStatusError):
        service.accept_quote_for_client(
            quote_id=QUOTE_ID,
            user=_client_user(),
            signer_input=_signer_input(),
        )


def test_declined_contract_blocks_acceptance() -> None:
    service = _service(contract_repository=FakeContractRepository(status="declined"))

    with pytest.raises(QuoteAcceptanceInvalidStatusError, match="Declined"):
        service.accept_quote_for_client(
            quote_id=QUOTE_ID,
            user=_client_user(),
            signer_input=_signer_input(),
        )


def test_missing_quote_document_blocks_acceptance() -> None:
    service = _service(document=None)

    with pytest.raises(QuoteAcceptanceDocumentMissingError):
        service.accept_quote_for_client(
            quote_id=QUOTE_ID,
            user=_client_user(),
            signer_input=_signer_input(),
        )


def test_missing_signer_fields_block_acceptance() -> None:
    service = _service()

    with pytest.raises(QuoteAcceptanceValidationError) as exc:
        service.accept_quote_for_client(
            quote_id=QUOTE_ID,
            user=_client_user(),
            signer_input=_signer_input(signer_name="", signer_email=""),
        )

    assert exc.value.missing_fields == ["signer_name", "signer_email"]


def test_get_client_acceptance_returns_only_owned_record() -> None:
    service = _service(acceptance_repository=FakeQuoteAcceptanceRepository(_acceptance()))

    acceptance = service.get_acceptance_for_client(
        quote_id=QUOTE_ID,
        user=_client_user(),
    )

    assert acceptance.id == 1

    with pytest.raises(QuoteAcceptanceOwnershipError):
        service.get_acceptance_for_client(
            quote_id=QUOTE_ID,
            user=_client_user(client_id=2002),
        )


def test_missing_acceptance_raises_not_found() -> None:
    service = _service()

    with pytest.raises(QuoteAcceptanceNotFoundError):
        service.get_acceptance(QUOTE_ID)


class FakeQuoteRequestService:
    def __init__(self, quote: QuoteRequest) -> None:
        self.quote = quote
        self.updated_status: tuple[UUID, str] | None = None

    def get_quote_request_detail(self, request_id: UUID) -> QuoteRequest:
        if request_id != self.quote.request_id:
            raise ValueError("QuoteRequest not found")
        return self.quote

    def update_request_status(self, request_id: UUID, request_status: str) -> QuoteRequest:
        self.updated_status = (request_id, request_status)
        self.quote = self.quote.model_copy(update={"request_status": request_status})
        return self.quote


class FakeQuoteDocumentRepository:
    def __init__(self, document: QuoteDocument | None) -> None:
        self.document = document

    def get_latest_successful_by_quote_request_id(
        self,
        quote_request_id: UUID,
    ) -> QuoteDocument | None:
        if self.document and self.document.quote_request_id == quote_request_id:
            return self.document
        return None

    def get_by_id(self, document_id: int) -> QuoteDocument:
        if self.document and self.document.id == document_id:
            return self.document
        raise ValueError("QuoteDocument not found")


class FakeQuoteAcceptanceRepository:
    def __init__(self, acceptance: QuoteAcceptance | None = None) -> None:
        self.acceptance = acceptance
        self.created_records: list[QuoteAcceptanceCreate] = []

    def create(self, acceptance: QuoteAcceptanceCreate) -> QuoteAcceptance:
        self.created_records.append(acceptance)
        self.acceptance = QuoteAcceptance(
            id=1,
            accepted_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
            created_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
            **acceptance.model_dump(),
        )
        return self.acceptance

    def get_by_quote_request_id(self, quote_request_id: UUID) -> QuoteAcceptance | None:
        if self.acceptance and self.acceptance.quote_request_id == quote_request_id:
            return self.acceptance
        return None


class FakeCompleteProfileService:
    def ensure_complete_profile(self, user: AuthUser):
        return None


class FakeIncompleteProfileService:
    def ensure_complete_profile(self, user: AuthUser):
        raise CustomerProfileIncompleteError(
            missing_fields=["national_id"],
            status="incomplete",
        )


class FakeContractRepository:
    def __init__(self, status: str | None = None) -> None:
        self.issued_contract: tuple[UUID, int] | None = None
        self.status = status

    def mark_contract_issued_for_quote_acceptance(
        self,
        quote_request_id: UUID,
        quote_acceptance_id: int,
    ):
        self.issued_contract = (quote_request_id, quote_acceptance_id)
        return None

    def get_contract_by_source_quote_request_id(self, quote_request_id: UUID):
        if self.status is None or quote_request_id != QUOTE_ID:
            return None
        return SimpleNamespace(status=self.status)


def _service(
    *,
    quote: QuoteRequest | None = None,
    document: QuoteDocument | None | object = DEFAULT_DOCUMENT,
    quote_service: FakeQuoteRequestService | None = None,
    acceptance_repository: FakeQuoteAcceptanceRepository | None = None,
    profile_service=None,
    contract_repository=None,
) -> QuoteAcceptanceService:
    quote_document = _quote_document() if document is DEFAULT_DOCUMENT else document
    return QuoteAcceptanceService(
        quote_request_service=quote_service or FakeQuoteRequestService(quote or _quote()),
        quote_document_repository=FakeQuoteDocumentRepository(quote_document),
        quote_acceptance_repository=acceptance_repository
        or FakeQuoteAcceptanceRepository(),
        customer_profile_service=profile_service or FakeCompleteProfileService(),
        contract_repository=contract_repository,
    )


def _quote(request_status: str = "approved") -> QuoteRequest:
    return QuoteRequest(
        request_id=QUOTE_ID,
        client_id=1001,
        request_status=request_status,
    )


def _quote_document() -> QuoteDocument:
    return QuoteDocument(
        id=77,
        quote_request_id=QUOTE_ID,
        template_id=1,
        generation_status="success",
        rendered_text="Generated quote text",
    )


def _acceptance() -> QuoteAcceptance:
    return QuoteAcceptance(
        id=1,
        quote_request_id=QUOTE_ID,
        quote_document_id=77,
        accepted_by_auth_user_id=10,
        accepted_by_customer_id=1001,
        signer_name="Ion Popescu",
        signer_email="ion@example.test",
        signer_role="policyholder",
        accepted_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        acceptance_method="client_portal",
        acceptance_statement="I accept this quote.",
        quote_content_hash="hash",
        created_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
    )


def _signer_input(
    *,
    signer_name: str = "Ion Popescu",
    signer_email: str = "ion@example.test",
) -> QuoteAcceptanceInput:
    return QuoteAcceptanceInput(
        signer_name=signer_name,
        signer_email=signer_email,
        signer_role="policyholder",
        acceptance_statement="I accept this quote and confirm the details are accurate.",
    )


def _client_user(client_id: int | None = 1001) -> AuthUser:
    return AuthUser(
        id=10,
        email="ion@example.test",
        password_hash="hash",
        role="client",
        full_name="Ion Popescu",
        client_id=client_id,
    )
