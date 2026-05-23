from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from underwright.application.services.client_data_service import ClientDataService
from underwright.domain.contract_case_context import ContractCaseContext
from underwright.domain.models import (
    Address,
    Contract,
    ContractContextSource,
    Customer,
    InsuredAsset,
    Insurer,
    Pricing,
    RiskProfile,
)

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000001")


def test_client_data_service_populates_profiles_from_loaded_contract_source():
    now = datetime.now()

    customer_address = Address(
        id=1,
        country="Romania",
        county="Cluj",
        city="Cluj-Napoca",
        street="Memorandumului",
        number="10",
        postal_code="400000",
        full_text="Str. Memorandumului 10, Cluj-Napoca",
    )

    insured_asset_address = Address(
        id=2,
        country="Romania",
        county="Cluj",
        city="Cluj-Napoca",
        street="Observatorului",
        number="20",
        postal_code="400001",
        full_text="Str. Observatorului 20, Cluj-Napoca",
    )

    insurer_address = Address(
        id=3,
        country="Romania",
        county="Bucuresti",
        city="Bucuresti",
        street="Victoriei",
        number="1",
        postal_code="010000",
        full_text="Calea Victoriei 1, Bucuresti",
    )

    source = ContractContextSource(
        contract=Contract(
            id=CONTRACT_ID,
            contract_number="PAD-001",
            document_type="PAD",
            document_version="v1",
            insurer_id=1,
            customer_id=1,
            insured_asset_id=1,
            issue_date=date(2026, 1, 1),
            effective_date=date(2026, 1, 2),
            expiration_date=date(2027, 1, 1),
            jurisdiction="RO",
            governing_law="Romanian law",
            currency="RON",
            status="draft",
            created_at=now,
            updated_at=now,
        ),
        customer=Customer(
            id=1,
            type="individual",
            full_name="Vladut Rad",
            national_id="1234567890123",
            company_id=None,
            email="vladut@example.com",
            phone="0712345678",
            address_id=1,
        ),
        customer_address=customer_address,
        insurer=Insurer(
            id=1,
            name="Test Insurance",
            company_id="RO123456",
            representative_name="Maria Ionescu",
            representative_role="Underwriting Manager",
            address_id=3,
        ),
        insurer_address=insurer_address,
        insured_asset=InsuredAsset(
            id=1,
            customer_id=1,
            asset_type="apartment",
            usage_type="residential",
            construction_type="concrete",
            year_built=2000,
            floor=2,
            area_sqm=Decimal("70.50"),
            declared_value=Decimal("100000"),
            occupancy="owner_occupied",
            previous_claims_count=0,
            address_id=2,
            created_at=now,
            updated_at=now,
        ),
        insured_asset_address=insured_asset_address,
        risk_profile=RiskProfile(
            id=1,
            contract_id=CONTRACT_ID,
            overall_risk_level="medium",
            risk_score=55,
            assessment_date=date(2026, 1, 1),
            created_at=now,
        ),
        pricing=Pricing(
            id=1,
            contract_id=CONTRACT_ID,
            base_premium_ron=Decimal("100"),
            adjustments_json=[],
            final_premium_ron=Decimal("120"),
            payment_plan_type="single",
            installments=1,
        ),
    )

    context = ContractCaseContext()
    context.reference_data.contract_source = source

    service = ClientDataService()
    result = service.populate_profiles(context)

    assert result.reference_data.client_profile["customer_id"] == 1
    assert result.reference_data.client_profile["full_name"] == "Vladut Rad"
    assert result.reference_data.client_profile["email"] == "vladut@example.com"
    assert result.reference_data.client_profile["address"]["city"] == "Cluj-Napoca"

    assert result.reference_data.property_profile["asset_id"] == 1
    assert result.reference_data.property_profile["asset_type"] == "apartment"
    assert result.reference_data.property_profile["year_built"] == 2000
    assert result.reference_data.property_profile["address"]["full_text"] == (
        "Str. Observatorului 20, Cluj-Napoca"
    )
