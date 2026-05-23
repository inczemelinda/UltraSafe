from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from underwright.application.services.contract_query_service import ContractQueryService
from underwright.domain.contract_lifecycle import (
    AddressSnapshot,
    ContractAssetSummary,
    ContractCustomerSummary,
    ContractPricingSummary,
    ContractReadModel,
)

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000011")
QUOTE_ID = UUID("90000000-0000-0000-0000-000000000011")


class FakeContractRepository:
    def __init__(self) -> None:
        self.contract = _contract()

    def list_contracts(self) -> list[ContractReadModel]:
        return [self.contract]

    def get_contract_by_id(self, contract_id: UUID) -> ContractReadModel:
        if contract_id != CONTRACT_ID:
            raise ValueError("Contract not found")
        return self.contract

    def get_contract_by_source_quote_request_id(
        self,
        quote_request_id: UUID,
    ) -> ContractReadModel | None:
        if quote_request_id == QUOTE_ID:
            return self.contract
        return None


def test_contract_query_service_lists_contracts() -> None:
    service = ContractQueryService(FakeContractRepository())

    contracts = service.list_contracts()

    assert len(contracts) == 1
    assert contracts[0].id == CONTRACT_ID


def test_contract_query_service_gets_contract_by_uuid() -> None:
    service = ContractQueryService(FakeContractRepository())

    contract = service.get_contract(CONTRACT_ID)

    assert contract.contract_number == "PAD-Q-2026-ABCDEF123456"


def test_contract_query_service_finds_by_source_quote() -> None:
    service = ContractQueryService(FakeContractRepository())

    contract = service.find_by_source_quote_request_id(QUOTE_ID)

    assert contract is not None
    assert contract.source_quote_request_id == QUOTE_ID


def _contract() -> ContractReadModel:
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
        id=CONTRACT_ID,
        contract_number="PAD-Q-2026-ABCDEF123456",
        document_type="insurance_contract",
        document_version="1.0",
        status="draft",
        source_quote_request_id=QUOTE_ID,
        source_quote_id=QUOTE_ID,
        source_quote_document_id=77,
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
