from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from underwright.application.services.contract_decline_service import (
    ContractDeclineInvalidStatusError,
    ContractDeclineOwnershipError,
    ContractDeclineService,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.contract_decline import (
    ContractDecline,
    ContractDeclineCreate,
    ContractDeclineInput,
)
from underwright.domain.contract_lifecycle import (
    AddressSnapshot,
    ContractAssetSummary,
    ContractCustomerSummary,
    ContractPricingSummary,
    ContractReadModel,
)


CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000041")
QUOTE_ID = UUID("90000000-0000-0000-0000-000000000041")


class FakeContractRepository:
    def __init__(self, contract: ContractReadModel | None = None) -> None:
        self.contract = contract or _contract()
        self.declined_contract_id: UUID | None = None

    def get_contract_by_id_for_client(
        self,
        contract_id: UUID,
        client_id: int | str | UUID,
    ) -> ContractReadModel:
        if (
            self.contract.id == contract_id
            and self.contract.customer
            and str(self.contract.customer.id) == str(client_id)
        ):
            return self.contract
        raise ValueError("Contract not found")

    def mark_contract_declined(
        self,
        contract_id: UUID,
    ) -> ContractReadModel | None:
        self.declined_contract_id = contract_id
        if self.contract.id != contract_id:
            return None
        if self.contract.status == "generated":
            self.contract = self.contract.model_copy(update={"status": "declined"})
        return self.contract


class FakeContractDeclineRepository:
    def __init__(self, decline: ContractDecline | None = None) -> None:
        self.decline = decline
        self.created: list[ContractDeclineCreate] = []

    def create(self, decline: ContractDeclineCreate) -> ContractDecline:
        self.created.append(decline)
        self.decline = ContractDecline(
            id=1,
            declined_at=datetime(2026, 5, 17, 10, 0, tzinfo=timezone.utc),
            **decline.model_dump(),
        )
        return self.decline

    def get_by_contract_id(self, contract_id: UUID) -> ContractDecline | None:
        if self.decline and self.decline.contract_id == contract_id:
            return self.decline
        return None


def test_client_declines_generated_contract_and_marks_contract_declined() -> None:
    contract_repository = FakeContractRepository()
    decline_repository = FakeContractDeclineRepository()
    service = _service(contract_repository, decline_repository)

    decline = service.decline_contract_for_client(
        contract_id=CONTRACT_ID,
        user=_client_user(),
        decline_input=ContractDeclineInput(reason=" Not needed "),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert decline.contract_id == CONTRACT_ID
    assert decline.source_quote_request_id == QUOTE_ID
    assert decline.reason == "Not needed"
    assert decline.declined_by_auth_user_id == 10
    assert decline.declined_by_customer_id == 1001
    assert decline_repository.created[0].metadata["contract_status_before_decline"] == "generated"
    assert contract_repository.declined_contract_id == CONTRACT_ID
    assert contract_repository.contract.status == "declined"


def test_duplicate_decline_returns_existing_record_without_mutation() -> None:
    existing = _decline()
    contract_repository = FakeContractRepository(_contract(status="declined"))
    decline_repository = FakeContractDeclineRepository(existing)
    service = _service(contract_repository, decline_repository)

    decline = service.decline_contract_for_client(
        contract_id=CONTRACT_ID,
        user=_client_user(),
        decline_input=ContractDeclineInput(reason="Another reason"),
    )

    assert decline == existing
    assert decline_repository.created == []


def test_client_cannot_decline_another_clients_contract() -> None:
    service = _service(
        FakeContractRepository(_contract(customer_id=2002)),
        FakeContractDeclineRepository(),
    )

    with pytest.raises(ContractDeclineOwnershipError):
        service.decline_contract_for_client(
            contract_id=CONTRACT_ID,
            user=_client_user(),
            decline_input=ContractDeclineInput(),
        )


def test_signed_contract_cannot_be_declined() -> None:
    service = _service(
        FakeContractRepository(_contract(status="issued")),
        FakeContractDeclineRepository(),
    )

    with pytest.raises(ContractDeclineInvalidStatusError):
        service.decline_contract_for_client(
            contract_id=CONTRACT_ID,
            user=_client_user(),
            decline_input=ContractDeclineInput(),
        )


def _service(
    contract_repository: FakeContractRepository,
    decline_repository: FakeContractDeclineRepository,
) -> ContractDeclineService:
    return ContractDeclineService(
        contract_repository=contract_repository,
        contract_decline_repository=decline_repository,
    )


def _client_user(client_id: int | None = 1001) -> AuthUser:
    return AuthUser(
        id=10,
        email="client@example.test",
        password_hash="hash",
        role="client",
        full_name="Ion Popescu",
        client_id=client_id,
    )


def _decline() -> ContractDecline:
    return ContractDecline(
        id=1,
        contract_id=CONTRACT_ID,
        source_quote_request_id=QUOTE_ID,
        declined_by_auth_user_id=10,
        declined_by_customer_id=1001,
        reason="Not needed",
        declined_at=datetime(2026, 5, 17, 10, 0, tzinfo=timezone.utc),
        metadata={},
    )


def _contract(
    *,
    status: str = "generated",
    customer_id: int = 1001,
) -> ContractReadModel:
    now = datetime(2026, 5, 17, 10, 0, tzinfo=timezone.utc)
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
        id=CONTRACT_ID,
        contract_number="PAD-Q-2026-ABCDEF123456",
        document_type="insurance_contract",
        document_version="1.0",
        status=status,
        source_quote_request_id=QUOTE_ID,
        source_quote_id=QUOTE_ID,
        source_quote_document_id=77,
        issue_date=date(2026, 5, 17),
        effective_date=date(2026, 5, 17),
        expiration_date=date(2027, 5, 16),
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
            previous_claims_count=0,
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
