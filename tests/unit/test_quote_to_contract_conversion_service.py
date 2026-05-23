from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from underwright.application.ports import ContractSourceQuoteConflictError
from underwright.application.services.quote_to_contract_conversion_service import (
    QuoteToContractConversionService,
    _contract_number,
)
from underwright.domain.contract_lifecycle import (
    AddressSnapshot,
    ContractAssetSummary,
    ContractCreationData,
    ContractCustomerSummary,
    ContractPricingSummary,
    ContractReadModel,
)
from underwright.domain.quote_acceptance import QuoteAcceptance
from underwright.domain.quote_document import QuoteDocument
from underwright.domain.quote_request import QuoteRequest

QUOTE_ID = UUID("90000000-0000-0000-0000-000000000021")
CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000021")
_DEFAULT_QUOTE = object()
_DEFAULT_QUOTE_DOCUMENT = object()
_DEFAULT_QUOTE_ACCEPTANCE = object()


class FakeContractRepository:
    def __init__(
        self,
        existing_contract: ContractReadModel | None = None,
        *,
        has_default_insurer: bool = True,
        conflict_on_create: bool = False,
    ) -> None:
        self.existing_contract = existing_contract
        self.has_default_insurer_value = has_default_insurer
        self.conflict_on_create = conflict_on_create
        self.created_contracts: list[ContractCreationData] = []

    def list_contracts(self) -> list[ContractReadModel]:
        return [self.existing_contract] if self.existing_contract else []

    def get_contract_by_id(self, contract_id: UUID) -> ContractReadModel:
        if self.existing_contract and self.existing_contract.id == contract_id:
            return self.existing_contract
        raise ValueError("Contract not found")

    def get_contract_by_source_quote_request_id(
        self,
        quote_request_id: UUID,
    ) -> ContractReadModel | None:
        if (
            self.existing_contract is not None
            and self.existing_contract.source_quote_request_id == quote_request_id
        ):
            return self.existing_contract
        return None

    def mark_contract_issued_for_quote_acceptance(
        self,
        quote_request_id: UUID,
        quote_acceptance_id: int,
    ) -> ContractReadModel | None:
        if (
            self.existing_contract is None
            or self.existing_contract.source_quote_request_id != quote_request_id
        ):
            return None
        self.existing_contract = self.existing_contract.model_copy(
            update={
                "status": "issued",
                "source_quote_acceptance_id": quote_acceptance_id,
            }
        )
        return self.existing_contract

    def create_contract_from_quote_data(
        self,
        creation_data: ContractCreationData,
    ) -> ContractReadModel:
        if self.conflict_on_create:
            self.existing_contract = _contract(
                contract_id=CONTRACT_ID,
                quote_id=creation_data.source_quote_request_id,
                quote_document_id=creation_data.source_quote_document_id,
                quote_acceptance_id=creation_data.source_quote_acceptance_id,
                status=creation_data.status,
            )
            raise ContractSourceQuoteConflictError(
                creation_data.source_quote_request_id
            )
        self.created_contracts.append(creation_data)
        contract = _contract(
            contract_id=creation_data.id,
            quote_id=creation_data.source_quote_request_id,
            quote_document_id=creation_data.source_quote_document_id,
            quote_acceptance_id=creation_data.source_quote_acceptance_id,
            status=creation_data.status,
        )
        self.existing_contract = contract
        return contract

    def has_default_insurer(self) -> bool:
        return self.has_default_insurer_value


class FakeQuoteRequestService:
    def __init__(self, quote: QuoteRequest | None) -> None:
        self.quote = quote

    def get_quote_request_detail(self, request_id: UUID) -> QuoteRequest:
        if self.quote is None:
            raise ValueError("QuoteRequest not found")
        return self.quote


class FakeQuoteDocumentRepository:
    def __init__(self, document: QuoteDocument | None) -> None:
        self.document = document

    def get_by_id(self, document_id: int) -> QuoteDocument:
        if self.document is None or self.document.id != document_id:
            raise ValueError("QuoteDocument not found")
        return self.document

    def get_latest_successful_by_quote_request_id(
        self,
        quote_request_id: UUID,
    ) -> QuoteDocument | None:
        return self.document


class FakeQuoteAcceptanceRepository:
    def __init__(self, acceptance: QuoteAcceptance | None) -> None:
        self.acceptance = acceptance

    def get_by_quote_request_id(
        self,
        quote_request_id: UUID,
    ) -> QuoteAcceptance | None:
        if (
            self.acceptance is not None
            and self.acceptance.quote_request_id == quote_request_id
        ):
            return self.acceptance
        return None


def test_resolve_returns_existing_contract_when_quote_already_converted() -> None:
    existing = _contract()
    repo = FakeContractRepository(existing)
    service = _service(contract_repository=repo)

    result = service.resolve_quote_contract(QUOTE_ID)

    assert result.already_converted is True
    assert result.conversion_status == "converted"
    assert result.contract_id == existing.id
    assert repo.created_contracts == []


def test_resolve_does_not_create_contract_for_eligible_quote() -> None:
    repo = FakeContractRepository()
    service = _service(contract_repository=repo)

    result = service.resolve_quote_contract(QUOTE_ID)

    assert result.already_converted is False
    assert result.conversion_status == "eligible"
    assert result.validation.can_convert is True
    assert repo.created_contracts == []


def test_resolve_returns_blocking_errors_when_quote_is_not_convertible() -> None:
    quote = _quote(request_status="draft")
    repo = FakeContractRepository()
    service = _service(contract_repository=repo, quote=quote)

    result = service.resolve_quote_contract(QUOTE_ID)

    assert result.conversion_status == "blocked"
    assert result.validation.can_convert is False
    assert "QUOTE_NOT_ACCEPTED" in {
        error.code for error in result.validation.blocking_errors
    }


def test_convert_blocks_invalid_quote_state_without_creating_contract() -> None:
    quote = _quote(request_status="underwriter_review")
    repo = FakeContractRepository()
    service = _service(contract_repository=repo, quote=quote)

    result = service.convert_quote(QUOTE_ID)

    assert result.result == "blocked"
    assert repo.created_contracts == []
    assert any(
        error.field == "request_status"
        for error in result.validation.blocking_errors
    )


def test_convert_blocks_when_required_data_is_missing() -> None:
    quote = _quote()
    quote.client_data.pop("national_id")
    repo = FakeContractRepository()
    service = _service(contract_repository=repo, quote=quote)

    result = service.convert_quote(QUOTE_ID)

    assert result.result == "blocked"
    assert repo.created_contracts == []
    assert any(
        error.field == "client_data.national_id"
        for error in result.validation.blocking_errors
    )


def test_convert_blocks_when_successful_quote_document_is_missing() -> None:
    repo = FakeContractRepository()
    service = _service(contract_repository=repo, quote_document=None)

    result = service.convert_quote(QUOTE_ID)

    assert result.result == "blocked"
    assert repo.created_contracts == []
    assert any(
        error.code == "QUOTE_DOCUMENT_MISSING"
        for error in result.validation.blocking_errors
    )


def test_convert_blocks_without_quote_acceptance() -> None:
    repo = FakeContractRepository()
    service = _service(contract_repository=repo, quote_acceptance=None)

    result = service.convert_quote(QUOTE_ID)

    assert result.result == "blocked"
    assert repo.created_contracts == []
    assert any(
        error.code == "QUOTE_ACCEPTANCE_REQUIRED"
        for error in result.validation.blocking_errors
    )


def test_convert_blocks_when_quote_document_belongs_to_another_quote() -> None:
    other_quote_id = UUID("90000000-0000-0000-0000-000000000099")
    quote_document = _quote_document(quote_request_id=other_quote_id)
    repo = FakeContractRepository()
    service = _service(contract_repository=repo, quote_document=quote_document)

    result = service.convert_quote(QUOTE_ID)

    assert result.result == "blocked"
    assert repo.created_contracts == []
    assert any(
        error.code == "SOURCE_QUOTE_DOCUMENT_MISMATCH"
        for error in result.validation.blocking_errors
    )


def test_convert_blocks_when_default_insurer_is_missing() -> None:
    repo = FakeContractRepository(has_default_insurer=False)
    service = _service(contract_repository=repo)

    result = service.convert_quote(QUOTE_ID)

    assert result.result == "blocked"
    assert repo.created_contracts == []
    assert any(
        error.code == "DEFAULT_INSURER_MISSING"
        for error in result.validation.blocking_errors
    )


def test_convert_creates_contract_for_valid_accepted_quote() -> None:
    repo = FakeContractRepository()
    service = _service(contract_repository=repo)

    result = service.convert_quote(QUOTE_ID)

    assert result.result == "created"
    assert result.contract is not None
    assert result.contract.source_quote_request_id == QUOTE_ID
    assert len(repo.created_contracts) == 1
    assert repo.created_contracts[0].final_premium_ron == Decimal("513")
    assert repo.created_contracts[0].source_quote_acceptance_id == 88
    assert repo.created_contracts[0].status == "issued"
    assert result.contract.source_quote_acceptance_id == 88


def test_publish_approved_quote_creates_generated_contract_before_acceptance() -> None:
    repo = FakeContractRepository()
    service = _service(contract_repository=repo, quote_acceptance=None)

    result = service.publish_approved_quote(QUOTE_ID)

    assert result.result == "created"
    assert result.contract is not None
    assert result.contract.source_quote_request_id == QUOTE_ID
    assert len(repo.created_contracts) == 1
    assert repo.created_contracts[0].source_quote_document_id == 77
    assert repo.created_contracts[0].source_quote_acceptance_id is None
    assert repo.created_contracts[0].status == "generated"


def test_publish_approved_quote_normalizes_quote_pricing_adjustments() -> None:
    quote = _quote()
    quote.pricing_preview["pricing_result"] = {
        "pricing_adjustments": [
            {
                "code": "property_type_multiplier",
                "label": "Property type",
                "adjustment_type": "multiplier",
                "value": 1.08,
                "amount": 48,
                "explanation": "Property type multiplier: 1.08.",
            }
        ]
    }
    repo = FakeContractRepository()
    service = _service(
        contract_repository=repo,
        quote=quote,
        quote_acceptance=None,
    )

    result = service.publish_approved_quote(QUOTE_ID)

    assert result.result == "created"
    adjustment = repo.created_contracts[0].pricing_adjustments[0]
    assert adjustment["source"] == "property_type_multiplier"
    assert adjustment["type"] == "multiplier"
    assert adjustment["code"] == "property_type_multiplier"


def test_publish_approved_quote_is_idempotent_when_contract_already_exists() -> None:
    existing = _contract(quote_acceptance_id=None, status="generated")
    repo = FakeContractRepository(existing)
    service = _service(contract_repository=repo, quote_acceptance=None)

    result = service.publish_approved_quote(QUOTE_ID)

    assert result.result == "already_exists"
    assert result.contract_id == existing.id
    assert repo.created_contracts == []


def test_convert_is_idempotent_when_contract_already_exists() -> None:
    existing = _contract()
    repo = FakeContractRepository(existing)
    service = _service(contract_repository=repo)

    result = service.convert_quote(QUOTE_ID)

    assert result.result == "already_exists"
    assert result.contract_id == existing.id
    assert repo.created_contracts == []


def test_convert_is_idempotent_when_unique_conflict_races() -> None:
    repo = FakeContractRepository(conflict_on_create=True)
    service = _service(contract_repository=repo)

    result = service.convert_quote(QUOTE_ID)

    assert result.result == "already_exists"
    assert result.contract_id == CONTRACT_ID
    assert repo.created_contracts == []


def test_contract_number_uses_unique_uuid_tail_for_demo_quote_ids() -> None:
    issue_date = date(2026, 5, 17)
    first_quote_id = UUID("11111111-1111-4111-8111-000000000002")
    second_quote_id = UUID("11111111-1111-4111-8111-000000000007")

    assert _contract_number(first_quote_id, issue_date) == "PAD-Q-2026-1111111100000002"
    assert _contract_number(second_quote_id, issue_date) == "PAD-Q-2026-1111111100000007"


def test_missing_quote_raises_value_error() -> None:
    service = _service(quote=None)

    with pytest.raises(ValueError, match="QuoteRequest not found"):
        service.resolve_quote_contract(QUOTE_ID)


def test_contract_creation_data_requires_source_quote_request_id() -> None:
    kwargs = _creation_data_kwargs()
    kwargs["source_quote_request_id"] = None
    with pytest.raises(ValidationError):
        ContractCreationData(**kwargs)


def _service(
    *,
    contract_repository: FakeContractRepository | None = None,
    quote: QuoteRequest | None | object = _DEFAULT_QUOTE,
    quote_document: QuoteDocument | None | object = _DEFAULT_QUOTE_DOCUMENT,
    quote_acceptance: QuoteAcceptance | None | object = _DEFAULT_QUOTE_ACCEPTANCE,
) -> QuoteToContractConversionService:
    resolved_quote = _quote() if quote is _DEFAULT_QUOTE else quote
    resolved_quote_document = (
        _quote_document()
        if quote_document is _DEFAULT_QUOTE_DOCUMENT
        else quote_document
    )
    resolved_quote_acceptance = (
        _quote_acceptance()
        if quote_acceptance is _DEFAULT_QUOTE_ACCEPTANCE
        else quote_acceptance
    )
    return QuoteToContractConversionService(
        contract_repository=contract_repository or FakeContractRepository(),
        quote_request_service=FakeQuoteRequestService(resolved_quote),
        quote_document_repository=FakeQuoteDocumentRepository(
            resolved_quote_document
        ),
        quote_acceptance_repository=FakeQuoteAcceptanceRepository(
            resolved_quote_acceptance
        ),
    )


def _quote(request_status: str = "approved") -> QuoteRequest:
    return QuoteRequest(
        request_id=QUOTE_ID,
        client_id=1001,
        request_status=request_status,
        client_data={
            "type": "individual",
            "full_name": "Ion Popescu",
            "national_id": "1800101223344",
            "email": "ion@example.test",
            "phone": "+40700000000",
            "address": {
                "country": "Romania",
                "county": "Bucuresti",
                "city": "Bucuresti",
                "street": "Str. Lalelelor",
                "number": "12",
                "postal_code": "031234",
                "full_text": "Str. Lalelelor 12, Bucuresti",
            },
        },
        asset_data={
            "asset_type": "Apartment",
            "usage_type": "Owner occupied",
            "construction_type": "Concrete",
            "year_built": 1998,
            "floor": 4,
            "area_sqm": 70,
            "declared_value": 300000,
            "occupancy": "Owner occupied",
            "previous_claims_count": 0,
            "address": {
                "country": "Romania",
                "county": "Bucuresti",
                "city": "Bucuresti",
                "street": "Str. Lalelelor",
                "number": "12",
                "postal_code": "031234",
                "full_text": "Str. Lalelelor 12, Bucuresti",
            },
        },
        pricing_preview={
            "currency": "RON",
            "estimated_premium": 513,
            "pricing": {
                "basePremium": 600,
                "finalPremium": 513,
            },
        },
    )


def _quote_document(quote_request_id: UUID = QUOTE_ID) -> QuoteDocument:
    return QuoteDocument(
        id=77,
        quote_request_id=quote_request_id,
        template_id=1,
        generation_status="success",
        rendered_text="Unsigned quote",
    )


def _quote_acceptance(
    *,
    quote_request_id: UUID = QUOTE_ID,
    quote_document_id: int = 77,
    accepted_by_customer_id: int = 1001,
) -> QuoteAcceptance:
    now = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
    return QuoteAcceptance(
        id=88,
        quote_request_id=quote_request_id,
        quote_document_id=quote_document_id,
        accepted_by_customer_id=accepted_by_customer_id,
        signer_name="Ion Popescu",
        signer_email="ion@example.test",
        accepted_at=now,
        acceptance_method="client_portal",
        acceptance_statement="I accept this quote.",
        quote_content_hash="quote-hash",
        created_at=now,
    )


def _creation_data_kwargs() -> dict:
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
    return {
        "id": CONTRACT_ID,
        "contract_number": "PAD-Q-2026-ABCDEF123456",
        "source_quote_request_id": QUOTE_ID,
        "source_quote_document_id": 77,
        "source_quote_acceptance_id": 88,
        "customer_full_name": "Ion Popescu",
        "customer_national_id": "1800101223344",
        "customer_email": "ion@example.test",
        "customer_phone": "+40700000000",
        "customer_address": address,
        "asset_type": "Apartment",
        "usage_type": "Owner occupied",
        "construction_type": "Concrete",
        "year_built": 1998,
        "area_sqm": Decimal("70"),
        "declared_value": Decimal("300000"),
        "occupancy": "Owner occupied",
        "asset_address": address,
        "issue_date": date(2026, 5, 13),
        "effective_date": date(2026, 5, 13),
        "expiration_date": date(2027, 5, 12),
        "base_premium_ron": Decimal("600"),
        "final_premium_ron": Decimal("513"),
        "created_at": now,
        "updated_at": now,
    }


def _contract(
    *,
    contract_id: UUID = CONTRACT_ID,
    quote_id: UUID = QUOTE_ID,
    quote_document_id: int = 77,
    quote_acceptance_id: int | None = 88,
    status: str = "draft",
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
        source_quote_request_id=quote_id,
        source_quote_id=quote_id,
        source_quote_document_id=quote_document_id,
        source_quote_acceptance_id=quote_acceptance_id,
        issue_date=date(2026, 5, 13),
        effective_date=date(2026, 5, 13),
        expiration_date=date(2027, 5, 12),
        jurisdiction="Romania",
        governing_law="Legea 260/2008",
        currency="RON",
        created_at=now,
        updated_at=now,
        customer=ContractCustomerSummary(
            id=1,
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
