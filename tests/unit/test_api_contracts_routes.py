from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from fastapi.testclient import TestClient

from underwright.api.dependencies import (
    get_contract_document_generation_service,
    get_contract_decline_service,
    get_contract_query_service,
    get_current_auth_user,
    get_current_client_user,
    get_current_employee_user,
    get_generated_document_pdf_service,
    get_generated_document_query_service,
    get_quote_to_contract_conversion_service,
    get_quote_request_service,
)
from underwright.api.main import create_app
from underwright.domain.contract_lifecycle import (
    AddressSnapshot,
    ContractAssetSummary,
    ContractConversionIssue,
    ContractConversionValidation,
    ContractCustomerSummary,
    ContractPricingSummary,
    ContractReadModel,
    QuoteContractResolution,
    QuoteToContractConversionResult,
)
from underwright.domain.contract_decline import ContractDecline, ContractDeclineInput
from underwright.domain.auth_user import AuthUser
from underwright.domain.generated_document_lifecycle import (
    ContractDocumentGenerationResult,
    ContractGenerationIssue,
    ContractGenerationValidation,
    GeneratedDocumentReadModel,
    PdfArtifactReadModel,
    PdfExportIssue,
    PdfExportResult,
)
from underwright.domain.quote_document import QuoteDocument
from underwright.domain.quote_request import QuoteRequest

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000031")
MISSING_CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000099")
QUOTE_ID = UUID("90000000-0000-0000-0000-000000000031")


class FakeContractQueryService:
    def __init__(self, contracts: list[ContractReadModel] | None = None) -> None:
        self.contracts = contracts or [_contract()]
        self.contract = self.contracts[0]

    def list_contracts(self) -> list[ContractReadModel]:
        return self.contracts

    def get_contract(self, contract_id: UUID) -> ContractReadModel:
        for contract in self.contracts:
            if contract_id == contract.id:
                return contract
        raise ValueError("Contract not found")

    def list_contracts_for_client(
        self,
        client_id: int | str | UUID,
    ) -> list[ContractReadModel]:
        return [
            contract
            for contract in self.contracts
            if str(contract.customer.id if contract.customer else "") == str(client_id)
        ]

    def get_contract_for_client(
        self,
        contract_id: UUID,
        client_id: int | str | UUID,
    ) -> ContractReadModel:
        for contract in self.list_contracts_for_client(client_id):
            if contract.id == contract_id:
                return contract
        raise ValueError("Contract not found")

    def list_claimable_contracts_for_client(
        self,
        client_id: int | str | UUID,
    ) -> list[ContractReadModel]:
        return [
            contract
            for contract in self.contracts
            if _is_fake_claimable(contract, client_id)
        ]

    def get_claimable_contract_for_client(
        self,
        contract_id: UUID,
        client_id: int | str | UUID,
    ) -> ContractReadModel:
        for contract in self.list_claimable_contracts_for_client(client_id):
            if contract.id == contract_id:
                return contract
        raise ValueError("Claimable contract not found")


class FakeQuoteToContractConversionService:
    def __init__(self) -> None:
        self.created = False
        self.published = False
        self.existing = _contract()
        self.latest_document = _quote_document()

    def resolve_quote_contract(self, quote_id: UUID) -> QuoteContractResolution:
        return QuoteContractResolution(
            quote_id=quote_id,
            already_converted=True,
            conversion_status="converted",
            contract_id=self.existing.id,
            contract=self.existing,
            validation=ContractConversionValidation(can_convert=False),
        )

    def latest_successful_quote_document(
        self,
        quote_id: UUID,
    ) -> QuoteDocument | None:
        return self.latest_document

    def convert_quote(
        self,
        quote_id: UUID,
    ) -> QuoteToContractConversionResult:
        self.created = True
        return QuoteToContractConversionResult(
            quote_id=quote_id,
            result="already_exists",
            contract_id=self.existing.id,
            contract=self.existing,
            validation=ContractConversionValidation(can_convert=False),
        )

    def publish_approved_quote(
        self,
        quote_id: UUID,
        *,
        quote_document: QuoteDocument | None = None,
    ) -> QuoteToContractConversionResult:
        self.published = True
        return QuoteToContractConversionResult(
            quote_id=quote_id,
            result="already_exists",
            contract_id=self.existing.id,
            contract=self.existing,
            validation=ContractConversionValidation(can_convert=False),
        )


class FakeEligibleQuoteContractService(FakeQuoteToContractConversionService):
    def resolve_quote_contract(self, quote_id: UUID) -> QuoteContractResolution:
        return QuoteContractResolution(
            quote_id=quote_id,
            already_converted=False,
            conversion_status="eligible",
            validation=ContractConversionValidation(can_convert=True),
        )


class FakeBlockedQuoteContractService(FakeQuoteToContractConversionService):
    def convert_quote(
        self,
        quote_id: UUID,
    ) -> QuoteToContractConversionResult:
        return QuoteToContractConversionResult(
            quote_id=quote_id,
            result="blocked",
            validation=ContractConversionValidation(
                can_convert=False,
                blocking_errors=[
                    ContractConversionIssue(
                        code="QUOTE_NOT_ACCEPTED",
                        field="request_status",
                        message="Quote is not accepted.",
                    )
                ],
            ),
        )


class FakeQuoteRequestService:
    def __init__(self, *, client_id: int = 1001, missing: bool = False) -> None:
        self.client_id = client_id
        self.missing = missing

    def get_quote_request_detail(self, request_id: UUID) -> QuoteRequest:
        if self.missing:
            raise ValueError("Quote not found")
        return QuoteRequest(
            request_id=request_id,
            client_id=self.client_id,
            request_status="approved",
        )


class FakeContractDeclineService:
    def __init__(self) -> None:
        self.declined_contract_id: UUID | None = None
        self.decline_input: ContractDeclineInput | None = None
        self.user: AuthUser | None = None

    def decline_contract_for_client(
        self,
        *,
        contract_id: UUID,
        user: AuthUser,
        decline_input: ContractDeclineInput,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ContractDecline:
        self.declined_contract_id = contract_id
        self.decline_input = decline_input
        self.user = user
        return ContractDecline(
            id=1,
            contract_id=contract_id,
            source_quote_request_id=QUOTE_ID,
            declined_by_auth_user_id=user.id,
            declined_by_customer_id=int(user.client_id or 0),
            reason=decline_input.reason,
            declined_at=datetime(2026, 5, 17, 10, 0, tzinfo=timezone.utc),
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={},
        )


class FakeContractDocumentGenerationService:
    def __init__(self, *, fail: bool = False, missing: bool = False) -> None:
        self.fail = fail
        self.missing = missing
        self.generated: list[tuple[UUID, str]] = []
        self.next_id = 40

    def generate(
        self,
        contract_id: UUID,
        template_code: str,
    ) -> ContractDocumentGenerationResult:
        if self.missing:
            raise ValueError("Contract not found")
        self.generated.append((contract_id, template_code))
        if self.fail:
            return ContractDocumentGenerationResult(
                status="failed",
                validation=ContractGenerationValidation(
                    can_generate=False,
                    blocking_errors=[
                        ContractGenerationIssue(
                            code="CUSTOMER_LEGAL_ID_MISSING",
                            field="customer.national_id",
                            message="customer.national_id is required.",
                        )
                    ],
                ),
            )

        self.next_id += 1
        return ContractDocumentGenerationResult(
            status="success",
            document=_generated_document(self.next_id),
            validation=ContractGenerationValidation(can_generate=True),
        )


class FakeGeneratedDocumentQueryService:
    def __init__(self, *, missing: bool = False, no_document: bool = False) -> None:
        self.missing = missing
        self.no_document = no_document
        self.latest_calls: list[UUID] = []
        self.document_calls: list[int] = []

    def get_latest_for_contract(
        self,
        contract_id: UUID,
    ) -> GeneratedDocumentReadModel | None:
        self.latest_calls.append(contract_id)
        if self.missing:
            raise ValueError("Contract not found")
        if self.no_document:
            return None
        return _generated_document(42)

    def get_document(self, document_id: int) -> GeneratedDocumentReadModel:
        self.document_calls.append(document_id)
        if self.missing:
            raise ValueError("GeneratedDocument not found")
        return _generated_document(document_id)


class FakeGeneratedDocumentPdfService:
    def __init__(
        self,
        *,
        missing_document: bool = False,
        missing_content: bool = False,
        missing_pdf: bool = False,
    ) -> None:
        self.missing_document = missing_document
        self.missing_content = missing_content
        self.missing_pdf = missing_pdf
        self.created: list[int] = []
        self.reads: list[int] = []
        self._tmpdir = TemporaryDirectory()
        self.file_path = Path(self._tmpdir.name) / "contract.pdf"
        self.file_path.write_bytes(b"%PDF-1.4\nfake\n%%EOF\n")

    def create_pdf(self, document_id: int) -> PdfExportResult:
        if self.missing_document:
            raise ValueError("GeneratedDocument not found")
        self.created.append(document_id)
        if self.missing_content:
            return PdfExportResult(
                status="failed",
                blocking_errors=[
                    PdfExportIssue(
                        code="GENERATED_DOCUMENT_CONTENT_MISSING",
                        field="rendered_text",
                        message="Generated document has no rendered content.",
                    )
                ],
            )
        return PdfExportResult(
            status="ready",
            artifact=_pdf_artifact(document_id),
        )

    def get_existing_pdf(self, document_id: int):
        if self.missing_document:
            raise ValueError("GeneratedDocument not found")
        self.reads.append(document_id)
        if self.missing_pdf:
            return None
        return type(
            "PdfArtifactFile",
            (),
            {
                "artifact": _pdf_artifact(document_id),
                "file_path": self.file_path,
            },
        )()


def _employee_client(app):
    app.dependency_overrides[get_current_employee_user] = lambda: _employee_user()
    return TestClient(app)


def _client_role_client(app):
    app.dependency_overrides[get_current_auth_user] = lambda: _auth_user(1)
    return TestClient(app)


def test_global_contract_endpoints_require_employee_role() -> None:
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService()
    )
    unauthenticated = TestClient(app)
    assert unauthenticated.get("/contracts").status_code == 401

    client = _client_role_client(app)
    assert client.get("/contracts").status_code == 403

    employee = _employee_client(app)
    assert employee.get("/contracts").status_code == 200


def test_global_generated_document_endpoints_require_employee_role() -> None:
    def configured_app():
        app = create_app()
        app.dependency_overrides[get_generated_document_query_service] = (
            lambda: FakeGeneratedDocumentQueryService()
        )
        app.dependency_overrides[get_generated_document_pdf_service] = (
            lambda: FakeGeneratedDocumentPdfService()
        )
        return app

    assert TestClient(configured_app()).get("/generated-documents/77").status_code == 401
    assert _client_role_client(configured_app()).get("/generated-documents/77").status_code == 403
    assert _employee_client(configured_app()).get("/generated-documents/77").status_code == 200
    assert TestClient(configured_app()).get("/generated-documents/77/pdf").status_code == 401
    assert _client_role_client(configured_app()).get("/generated-documents/77/pdf").status_code == 403


def test_get_contracts_returns_contract_summaries() -> None:
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService()
    )
    client = _employee_client(app)

    response = client.get("/contracts")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == str(CONTRACT_ID)
    assert payload[0]["contract_number"] == "PAD-Q-2026-ABCDEF123456"
    assert payload[0]["display_id"] == "PAD-Q-Ion_Popescu-ABCDEF123456"
    assert payload[0]["source_quote_request_id"] == str(QUOTE_ID)
    assert payload[0]["customer"]["full_name"] == "Ion Popescu"


def test_get_my_claimable_contracts_returns_only_authenticated_client_contracts() -> None:
    owned_claimable = _contract(status="issued", customer_id=1001)
    other_client = _contract(
        contract_id=UUID("10000000-0000-0000-0000-000000000032"),
        status="issued",
        customer_id=2002,
    )
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService([owned_claimable, other_client])
    )
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    client = _employee_client(app)

    response = client.get("/me/claimable-contracts")

    assert response.status_code == 200
    payload = response.json()
    assert [item["contract_id"] for item in payload["items"]] == [
        str(owned_claimable.id)
    ]
    assert payload["items"][0]["display_id"] == "PAD-Q-Ion_Popescu-ABCDEF123456"
    assert payload["items"][0]["address"]["full_text"] == (
        "Str. Lalelelor 12, Bucuresti"
    )


def test_get_my_claimable_contracts_excludes_non_claimable_and_expired_contracts() -> None:
    issued = _contract(status="issued", customer_id=1001)
    draft = _contract(
        contract_id=UUID("10000000-0000-0000-0000-000000000033"),
        status="draft",
        customer_id=1001,
    )
    expired = _contract(
        contract_id=UUID("10000000-0000-0000-0000-000000000034"),
        status="issued",
        customer_id=1001,
        expiration_date=date(2026, 5, 12),
    )
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService([issued, draft, expired])
    )
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    client = _employee_client(app)

    response = client.get("/me/claimable-contracts")

    assert response.status_code == 200
    assert [item["contract_id"] for item in response.json()["items"]] == [
        str(issued.id)
    ]


def test_get_my_contracts_returns_only_authenticated_client_contracts() -> None:
    owned = _contract(customer_id=1001)
    other_client = _contract(
        contract_id=UUID("10000000-0000-0000-0000-000000000035"),
        customer_id=2002,
    )
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService([owned, other_client])
    )
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    client = _employee_client(app)

    response = client.get("/me/contracts")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(owned.id)]


def test_get_my_contract_returns_404_for_another_client_contract() -> None:
    other_client = _contract(customer_id=2002)
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService([other_client])
    )
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    client = _employee_client(app)

    response = client.get(f"/me/contracts/{other_client.id}")

    assert response.status_code == 404


def test_client_can_decline_own_generated_contract() -> None:
    app = create_app()
    service = FakeContractDeclineService()
    app.dependency_overrides[get_contract_decline_service] = lambda: service
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    client = TestClient(app)

    response = client.post(
        f"/me/contracts/{CONTRACT_ID}/decline",
        json={"reason": "Coverage no longer needed."},
    )

    assert response.status_code == 200
    assert response.json()["contract_id"] == str(CONTRACT_ID)
    assert response.json()["reason"] == "Coverage no longer needed."
    assert service.declined_contract_id == CONTRACT_ID
    assert service.decline_input is not None
    assert service.decline_input.reason == "Coverage no longer needed."


def test_get_contract_by_uuid_returns_real_backend_contract() -> None:
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService()
    )
    client = _employee_client(app)

    response = client.get(f"/contracts/{CONTRACT_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(CONTRACT_ID)


def test_get_contract_rejects_fake_c_quote_id() -> None:
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService()
    )
    client = _employee_client(app)

    response = client.get(f"/contracts/C-{QUOTE_ID}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONTRACT_NOT_FOUND"


def test_get_contract_returns_404_for_missing_contract() -> None:
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService()
    )
    client = _employee_client(app)

    response = client.get(f"/contracts/{MISSING_CONTRACT_ID}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONTRACT_NOT_FOUND"


def test_quote_contract_resolver_returns_existing_contract() -> None:
    app = create_app()
    service = FakeQuoteToContractConversionService()
    app.dependency_overrides[get_quote_to_contract_conversion_service] = (
        lambda: service
    )
    client = _employee_client(app)

    response = client.get(f"/quotes/{QUOTE_ID}/contract")

    assert response.status_code == 200
    payload = response.json()
    assert payload["already_converted"] is True
    assert payload["contract_id"] == str(CONTRACT_ID)


def test_quote_contract_resolver_does_not_create_contract() -> None:
    app = create_app()
    service = FakeQuoteToContractConversionService()
    app.dependency_overrides[get_quote_to_contract_conversion_service] = (
        lambda: service
    )
    client = _employee_client(app)

    response = client.get(f"/quotes/{QUOTE_ID}/contract")

    assert response.status_code == 200
    assert service.created is False


def test_quote_contract_resolver_returns_conversion_eligibility() -> None:
    app = create_app()
    app.dependency_overrides[get_quote_to_contract_conversion_service] = (
        lambda: FakeEligibleQuoteContractService()
    )
    client = _employee_client(app)

    response = client.get(f"/quotes/{QUOTE_ID}/contract")

    assert response.status_code == 200
    payload = response.json()
    assert payload["already_converted"] is False
    assert payload["conversion_status"] == "eligible"
    assert payload["validation"]["can_convert"] is True


def test_convert_quote_to_contract_returns_existing_contract_idempotently() -> None:
    app = create_app()
    service = FakeQuoteToContractConversionService()
    app.dependency_overrides[get_quote_to_contract_conversion_service] = (
        lambda: service
    )
    client = _employee_client(app)

    response = client.post(f"/quotes/{QUOTE_ID}/contract")

    assert response.status_code == 200
    assert response.json()["result"] == "already_exists"
    assert service.created is True


def test_convert_quote_to_contract_returns_400_when_blocked() -> None:
    app = create_app()
    app.dependency_overrides[get_quote_to_contract_conversion_service] = (
        lambda: FakeBlockedQuoteContractService()
    )
    client = _employee_client(app)

    response = client.post(f"/quotes/{QUOTE_ID}/contract")

    assert response.status_code == 400
    assert response.json()["result"] == "blocked"
    assert (
        response.json()["validation"]["blocking_errors"][0]["code"]
        == "QUOTE_NOT_ACCEPTED"
    )


def test_client_can_publish_own_approved_quote_to_contract_for_signing() -> None:
    app = create_app()
    service = FakeQuoteToContractConversionService()
    pdf_service = FakeGeneratedDocumentPdfService()
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    app.dependency_overrides[get_quote_request_service] = (
        lambda: FakeQuoteRequestService(client_id=1001)
    )
    app.dependency_overrides[get_quote_to_contract_conversion_service] = (
        lambda: service
    )
    app.dependency_overrides[get_generated_document_query_service] = (
        lambda: FakeGeneratedDocumentQueryService()
    )
    app.dependency_overrides[get_contract_document_generation_service] = (
        lambda: FakeContractDocumentGenerationService()
    )
    app.dependency_overrides[get_generated_document_pdf_service] = lambda: pdf_service
    client = TestClient(app)

    response = client.post(f"/me/quotes/{QUOTE_ID}/contract")

    assert response.status_code == 200
    assert response.json()["result"] == "already_exists"
    assert service.created is False
    assert service.published is True
    assert pdf_service.created == [42]


def test_client_quote_contract_publication_generates_missing_document() -> None:
    app = create_app()
    service = FakeQuoteToContractConversionService()
    query_service = FakeGeneratedDocumentQueryService(no_document=True)
    generation_service = FakeContractDocumentGenerationService()
    pdf_service = FakeGeneratedDocumentPdfService()
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    app.dependency_overrides[get_quote_request_service] = (
        lambda: FakeQuoteRequestService(client_id=1001)
    )
    app.dependency_overrides[get_quote_to_contract_conversion_service] = (
        lambda: service
    )
    app.dependency_overrides[get_generated_document_query_service] = (
        lambda: query_service
    )
    app.dependency_overrides[get_contract_document_generation_service] = (
        lambda: generation_service
    )
    app.dependency_overrides[get_generated_document_pdf_service] = lambda: pdf_service
    client = TestClient(app)

    response = client.post(f"/me/quotes/{QUOTE_ID}/contract")

    assert response.status_code == 200
    assert response.json()["contract_id"] == str(CONTRACT_ID)
    assert query_service.latest_calls == [CONTRACT_ID]
    assert generation_service.generated == [(CONTRACT_ID, "PAD_PROPERTY_RO")]
    assert pdf_service.created == [41]


def test_client_cannot_convert_another_clients_quote_to_contract() -> None:
    app = create_app()
    service = FakeQuoteToContractConversionService()
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    app.dependency_overrides[get_quote_request_service] = (
        lambda: FakeQuoteRequestService(client_id=2002)
    )
    app.dependency_overrides[get_quote_to_contract_conversion_service] = (
        lambda: service
    )
    client = TestClient(app)

    response = client.post(f"/me/quotes/{QUOTE_ID}/contract")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUOTE_REQUEST_NOT_FOUND"
    assert service.created is False


def test_generate_contract_document_returns_404_for_missing_contract() -> None:
    app = create_app()
    app.dependency_overrides[get_contract_document_generation_service] = (
        lambda: FakeContractDocumentGenerationService(missing=True)
    )
    client = _employee_client(app)

    response = client.post(f"/contracts/{CONTRACT_ID}/generated-documents")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONTRACT_NOT_FOUND"


def test_generate_contract_document_rejects_fake_c_quote_id() -> None:
    app = create_app()
    service = FakeContractDocumentGenerationService()
    app.dependency_overrides[get_contract_document_generation_service] = (
        lambda: service
    )
    client = _employee_client(app)

    response = client.post(f"/contracts/C-{QUOTE_ID}/generated-documents")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONTRACT_NOT_FOUND"
    assert service.generated == []


def test_generate_contract_document_returns_structured_failure() -> None:
    app = create_app()
    app.dependency_overrides[get_contract_document_generation_service] = (
        lambda: FakeContractDocumentGenerationService(fail=True)
    )
    client = _employee_client(app)

    response = client.post(f"/contracts/{CONTRACT_ID}/generated-documents")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "CONTRACT_DOCUMENT_GENERATION_FAILED"
    assert (
        payload["error"]["validation"]["blocking_errors"][0]["code"]
        == "CUSTOMER_LEGAL_ID_MISSING"
    )


def test_generate_contract_document_creates_persisted_document() -> None:
    app = create_app()
    service = FakeContractDocumentGenerationService()
    app.dependency_overrides[get_contract_document_generation_service] = (
        lambda: service
    )
    client = _employee_client(app)

    response = client.post(
        f"/contracts/{CONTRACT_ID}/generated-documents",
        json={"template_code": "PAD_STANDARD_RO"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 41
    assert payload["contract_id"] == str(CONTRACT_ID)
    assert payload["rendered_text"] == "Rendered contract 41"
    assert service.generated == [(CONTRACT_ID, "PAD_STANDARD_RO")]


def test_generate_contract_document_creates_new_document_on_repeat_post() -> None:
    app = create_app()
    service = FakeContractDocumentGenerationService()
    app.dependency_overrides[get_contract_document_generation_service] = (
        lambda: service
    )
    client = _employee_client(app)

    first = client.post(f"/contracts/{CONTRACT_ID}/generated-documents")
    second = client.post(f"/contracts/{CONTRACT_ID}/generated-documents")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == 41
    assert second.json()["id"] == 42


def test_get_latest_generated_document_returns_latest_document() -> None:
    app = create_app()
    service = FakeGeneratedDocumentQueryService()
    app.dependency_overrides[get_generated_document_query_service] = lambda: service
    client = _employee_client(app)

    response = client.get(f"/contracts/{CONTRACT_ID}/generated-documents/latest")

    assert response.status_code == 200
    assert response.json()["id"] == 42
    assert service.latest_calls == [CONTRACT_ID]


def test_get_latest_generated_document_does_not_generate_document() -> None:
    app = create_app()
    generation_service = FakeContractDocumentGenerationService()
    query_service = FakeGeneratedDocumentQueryService()
    app.dependency_overrides[get_contract_document_generation_service] = (
        lambda: generation_service
    )
    app.dependency_overrides[get_generated_document_query_service] = (
        lambda: query_service
    )
    client = _employee_client(app)

    response = client.get(f"/contracts/{CONTRACT_ID}/generated-documents/latest")

    assert response.status_code == 200
    assert generation_service.generated == []
    assert query_service.latest_calls == [CONTRACT_ID]


def test_get_latest_generated_document_returns_404_when_none_exists() -> None:
    app = create_app()
    app.dependency_overrides[get_generated_document_query_service] = (
        lambda: FakeGeneratedDocumentQueryService(no_document=True)
    )
    client = _employee_client(app)

    response = client.get(f"/contracts/{CONTRACT_ID}/generated-documents/latest")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GENERATED_DOCUMENT_NOT_FOUND"


def test_get_generated_document_returns_persisted_document() -> None:
    app = create_app()
    service = FakeGeneratedDocumentQueryService()
    app.dependency_overrides[get_generated_document_query_service] = lambda: service
    client = _employee_client(app)

    response = client.get("/generated-documents/77")

    assert response.status_code == 200
    assert response.json()["id"] == 77
    assert service.document_calls == [77]


def test_get_generated_document_does_not_regenerate_content() -> None:
    app = create_app()
    generation_service = FakeContractDocumentGenerationService()
    query_service = FakeGeneratedDocumentQueryService()
    app.dependency_overrides[get_contract_document_generation_service] = (
        lambda: generation_service
    )
    app.dependency_overrides[get_generated_document_query_service] = (
        lambda: query_service
    )
    client = _employee_client(app)

    response = client.get("/generated-documents/77")

    assert response.status_code == 200
    assert generation_service.generated == []
    assert query_service.document_calls == [77]


def test_create_generated_document_pdf_returns_404_for_missing_document() -> None:
    app = create_app()
    app.dependency_overrides[get_generated_document_pdf_service] = (
        lambda: FakeGeneratedDocumentPdfService(missing_document=True)
    )
    client = _employee_client(app)

    response = client.post("/generated-documents/77/pdf")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GENERATED_DOCUMENT_NOT_FOUND"


def test_create_generated_document_pdf_returns_structured_failure_for_empty_content() -> None:
    app = create_app()
    app.dependency_overrides[get_generated_document_pdf_service] = (
        lambda: FakeGeneratedDocumentPdfService(missing_content=True)
    )
    client = _employee_client(app)

    response = client.post("/generated-documents/77/pdf")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "GENERATED_DOCUMENT_PDF_EXPORT_FAILED"
    assert (
        payload["error"]["blocking_errors"][0]["code"]
        == "GENERATED_DOCUMENT_CONTENT_MISSING"
    )


def test_create_generated_document_pdf_returns_artifact_metadata() -> None:
    app = create_app()
    service = FakeGeneratedDocumentPdfService()
    app.dependency_overrides[get_generated_document_pdf_service] = lambda: service
    client = _employee_client(app)

    response = client.post("/generated-documents/77/pdf")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == 77
    assert payload["pdf_storage_key"] == "generated-document-77.pdf"
    assert payload["pdf_content_hash"] == "pdf-hash"
    assert payload["source_content_hash"] == "source-hash"
    assert service.created == [77]


def test_client_can_create_pdf_for_owned_generated_document() -> None:
    owned = _contract(customer_id=1001)
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService([owned])
    )
    app.dependency_overrides[get_generated_document_query_service] = (
        lambda: FakeGeneratedDocumentQueryService()
    )
    pdf_service = FakeGeneratedDocumentPdfService()
    app.dependency_overrides[get_generated_document_pdf_service] = lambda: pdf_service
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    client = _employee_client(app)

    response = client.post("/me/generated-documents/77/pdf")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == 77
    assert payload["pdf_storage_key"] == "generated-document-77.pdf"
    assert pdf_service.created == [77]


def test_client_cannot_create_pdf_for_other_client_generated_document() -> None:
    other_client = _contract(customer_id=2002)
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService([other_client])
    )
    app.dependency_overrides[get_generated_document_query_service] = (
        lambda: FakeGeneratedDocumentQueryService()
    )
    pdf_service = FakeGeneratedDocumentPdfService()
    app.dependency_overrides[get_generated_document_pdf_service] = lambda: pdf_service
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    client = _employee_client(app)

    response = client.post("/me/generated-documents/77/pdf")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GENERATED_DOCUMENT_NOT_FOUND"
    assert pdf_service.created == []


def test_client_pdf_creation_returns_structured_failure_for_empty_content() -> None:
    owned = _contract(customer_id=1001)
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService([owned])
    )
    app.dependency_overrides[get_generated_document_query_service] = (
        lambda: FakeGeneratedDocumentQueryService()
    )
    app.dependency_overrides[get_generated_document_pdf_service] = (
        lambda: FakeGeneratedDocumentPdfService(missing_content=True)
    )
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    client = _employee_client(app)

    response = client.post("/me/generated-documents/77/pdf")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "GENERATED_DOCUMENT_PDF_EXPORT_FAILED"
    assert (
        payload["error"]["blocking_errors"][0]["code"]
        == "GENERATED_DOCUMENT_CONTENT_MISSING"
    )


def test_get_generated_document_pdf_returns_404_when_pdf_missing() -> None:
    app = create_app()
    app.dependency_overrides[get_generated_document_pdf_service] = (
        lambda: FakeGeneratedDocumentPdfService(missing_pdf=True)
    )
    client = _employee_client(app)

    response = client.get("/generated-documents/77/pdf")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GENERATED_DOCUMENT_PDF_NOT_FOUND"


def test_get_generated_document_pdf_streams_application_pdf() -> None:
    app = create_app()
    service = FakeGeneratedDocumentPdfService()
    app.dependency_overrides[get_generated_document_pdf_service] = lambda: service
    client = _employee_client(app)

    response = client.get("/generated-documents/77/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert service.reads == [77]


def test_get_generated_document_pdf_does_not_create_pdf() -> None:
    app = create_app()
    service = FakeGeneratedDocumentPdfService()
    app.dependency_overrides[get_generated_document_pdf_service] = lambda: service
    client = _employee_client(app)

    response = client.get("/generated-documents/77/pdf")

    assert response.status_code == 200
    assert service.created == []
    assert service.reads == [77]


def test_get_my_generated_document_pdf_streams_only_owned_pdf() -> None:
    owned = _contract(customer_id=1001)
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService([owned])
    )
    app.dependency_overrides[get_generated_document_query_service] = (
        lambda: FakeGeneratedDocumentQueryService()
    )
    pdf_service = FakeGeneratedDocumentPdfService()
    app.dependency_overrides[get_generated_document_pdf_service] = (
        lambda: pdf_service
    )
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    client = _employee_client(app)

    response = client.get("/me/generated-documents/77/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_get_my_generated_document_pdf_returns_404_for_other_client() -> None:
    other_client = _contract(customer_id=2002)
    app = create_app()
    app.dependency_overrides[get_contract_query_service] = (
        lambda: FakeContractQueryService([other_client])
    )
    app.dependency_overrides[get_generated_document_query_service] = (
        lambda: FakeGeneratedDocumentQueryService()
    )
    app.dependency_overrides[get_generated_document_pdf_service] = (
        lambda: FakeGeneratedDocumentPdfService()
    )
    app.dependency_overrides[get_current_client_user] = lambda: _auth_user(1001)
    client = _employee_client(app)

    response = client.get("/me/generated-documents/77/pdf")

    assert response.status_code == 404


def _contract(
    *,
    contract_id: UUID = CONTRACT_ID,
    status: str = "draft",
    customer_id: int = 1,
    expiration_date: date = date(2027, 5, 12),
) -> ContractReadModel:
    now = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
    address = AddressSnapshot(
        country="Romania",
        county="Bucuresti",
        city="Bucuresti",
        street="Str. Lalelelor",
        number="12",
        postal_code="031234",
        full_text="Str. Lalelelor 12, Bucuresti",
    )
    return ContractReadModel(
        id=contract_id,
        contract_number="PAD-Q-2026-ABCDEF123456",
        document_type="insurance_contract",
        document_version="1.0",
        status=status,
        source_quote_request_id=QUOTE_ID,
        source_quote_id=QUOTE_ID,
        source_quote_document_id=77,
        issue_date=date(2026, 5, 13),
        effective_date=date(2026, 5, 13),
        expiration_date=expiration_date,
        jurisdiction="Romania",
        governing_law="Legea 260/2008",
        currency="RON",
        created_at=now,
        updated_at=now,
        customer=ContractCustomerSummary(
            id=customer_id,
            type="individual",
            full_name="Ion Popescu",
            national_id="1800101223344",
            email="ion@example.test",
            phone="+40700000000",
            address=address,
        ),
        asset=ContractAssetSummary(
            id=1,
            asset_type="Apartment",
            usage_type="Owner occupied",
            construction_type="Concrete",
            year_built=1998,
            floor=4,
            area_sqm=Decimal("70"),
            declared_value=Decimal("300000"),
            occupancy="Owner occupied",
            address=address,
        ),
        pricing=ContractPricingSummary(
            base_premium_ron=Decimal("600"),
            final_premium_ron=Decimal("513"),
            currency="RON",
            payment_plan_type="annual",
            installments=1,
        ),
    )


def _is_fake_claimable(
    contract: ContractReadModel,
    client_id: int | str | UUID,
) -> bool:
    return (
        str(contract.customer.id if contract.customer else "") == str(client_id)
        and contract.status == "issued"
        and contract.expiration_date >= date(2026, 5, 13)
    )


def _auth_user(client_id: int | None) -> AuthUser:
    return AuthUser(
        id=1,
        email="client@example.test",
        password_hash="hash",
        role="client",
        full_name="Ion Popescu",
        client_id=client_id,
    )


def _employee_user() -> AuthUser:
    return AuthUser(
        id=2,
        email="employee@example.test",
        password_hash="hash",
        role="underwriter",
        full_name="Under Writer",
    )


def _generated_document(document_id: int) -> GeneratedDocumentReadModel:
    now = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
    return GeneratedDocumentReadModel(
        id=document_id,
        contract_id=CONTRACT_ID,
        document_type="insurance_contract",
        template_id=22,
        template_code="PAD_PROPERTY_RO",
        template_version="1.0",
        template_version_hash="template-hash",
        rendered_text=f"Rendered contract {document_id}",
        payload_snapshot={"document_type": "insurance_contract"},
        generation_metadata={"generation_mode": "template"},
        content_hash=f"content-hash-{document_id}",
        created_at=now,
        updated_at=now,
        status="success",
    )


def _quote_document() -> QuoteDocument:
    return QuoteDocument(
        id=77,
        quote_request_id=QUOTE_ID,
        template_id=22,
        generation_status="success",
        rendered_text="Rendered quote document",
    )


def _pdf_artifact(document_id: int) -> PdfArtifactReadModel:
    return PdfArtifactReadModel(
        document_id=document_id,
        contract_id=CONTRACT_ID,
        pdf_storage_key=f"generated-document-{document_id}.pdf",
        pdf_content_hash="pdf-hash",
        source_content_hash="source-hash",
        pdf_generated_at=datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc),
        status="ready",
        filename=f"generated-document-{document_id}.pdf",
    )
