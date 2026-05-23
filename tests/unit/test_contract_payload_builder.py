from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import unittest
from uuid import UUID

from underwright.application.modules.contract_payload_builder import ContractPayloadBuilder
from underwright.application.services.case_context_service import CaseContextFactory
from underwright.domain.models import (
    Address,
    Contract,
    ContractContextSource,
    Customer,
    InsuredAsset,
    Insurer,
    Pricing,
    PricingAdjustment,
    RiskFactor,
    RiskProfile,
)

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000001")


def make_source() -> ContractContextSource:
    now = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)
    customer_address = Address(
        id=2,
        country="Romania",
        county="Bucuresti",
        city="Bucuresti",
        street="Str. Lalelelor",
        number="12",
        postal_code="031234",
        full_text="Str. Lalelelor 12, Sector 3, Bucuresti",
    )

    return ContractContextSource(
        contract=Contract(
            id=CONTRACT_ID,
            contract_number="PAD-RISK-2026-000145",
            document_type="insurance_contract",
            document_version="1.0",
            insurer_id=1,
            customer_id=1,
            insured_asset_id=1,
            issue_date=date(2026, 4, 20),
            effective_date=date(2026, 5, 1),
            expiration_date=date(2027, 4, 30),
            jurisdiction="Romania",
            governing_law="Legea 260/2008",
            currency="RON",
            status="draft",
            created_at=now,
            updated_at=now,
        ),
        customer=Customer(
            id=1,
            type="individual",
            full_name="Ion Popescu",
            national_id="1800101223344",
            company_id=None,
            email="ion.popescu@example.test",
            phone="+40712345678",
            address_id=2,
        ),
        customer_address=customer_address,
        insurer=Insurer(
            id=1,
            name="Asigurator Demo SA",
            company_id="RO12345678",
            representative_name="Maria Ionescu",
            representative_role="Director General",
            address_id=1,
        ),
        insurer_address=Address(
            id=1,
            country="Romania",
            county="Bucuresti",
            city="Bucuresti",
            street="Bd. Exemplu",
            number="100",
            postal_code="010101",
            full_text="Bd. Exemplu 100, Bucuresti",
        ),
        insured_asset=InsuredAsset(
            id=1,
            customer_id=1,
            asset_type="apartment",
            usage_type="residential",
            construction_type="concrete",
            year_built=1986,
            floor=4,
            area_sqm=Decimal("68.00"),
            declared_value=Decimal("350000.00"),
            occupancy="owner_occupied",
            previous_claims_count=2,
            address_id=2,
            created_at=now,
            updated_at=now,
        ),
        insured_asset_address=customer_address,
        risk_profile=RiskProfile(
            id=1,
            contract_id=CONTRACT_ID,
            overall_risk_level="medium_high",
            risk_score=72,
            assessment_date=date(2026, 4, 20),
            created_at=now,
        ),
        risk_factors=[
            RiskFactor(
                id=1,
                risk_profile_id=1,
                code="FLOOD_EXPOSURE",
                label="Expunere la inundatii",
                level="high",
                score=85,
                evidence_json=["zona cu istoric de inundatii"],
                clause_tags_json=["flood_specific"],
                premium_adjustment_percent=Decimal("12.00"),
                deductible_adjustment_ron=Decimal("500.00"),
                created_at=now,
            )
        ],
        pricing=Pricing(
            id=1,
            contract_id=CONTRACT_ID,
            base_premium_ron=Decimal("1200.00"),
            adjustments_json=[
                PricingAdjustment(
                    source="FLOOD_EXPOSURE",
                    type="percentage",
                    value=Decimal("12.00"),
                )
            ],
            final_premium_ron=Decimal("1490.00"),
            payment_plan_type="annual",
            installments=1,
        ),
    )


class ContractPayloadBuilderTestCase(unittest.TestCase):
    def test_builds_current_contract_generation_payload_shape(self) -> None:
        case_context = (
            CaseContextFactory().create_contract_case_context_from_contract_id(
                CONTRACT_ID
            )
        )
        case_context.reference_data.contract_source = make_source()

        result = ContractPayloadBuilder().build(case_context)

        self.assertEqual(
            case_context.domain_payload.contract_generation_payload,
            {
                "document_type": "insurance_contract",
                "document_version": "1.0",
                "language": "ro-RO",
                "generation_mode": "hybrid_template_plus_llm",
                "contract_meta": {
                    "contract_id": "PAD-RISK-Ion_Popescu-000145",
                    "issue_date": "2026-04-20",
                    "effective_date": "2026-05-01",
                    "expiration_date": "2027-04-30",
                    "jurisdiction": "Romania",
                    "governing_law": "Legea 260/2008",
                    "currency": "RON",
                },
                "parties": {
                    "insurer": {
                        "name": "Asigurator Demo SA",
                        "company_id": "RO12345678",
                        "address": "Bd. Exemplu 100, Bucuresti",
                        "representative": {
                            "name": "Maria Ionescu",
                            "role": "Director General",
                        },
                    },
                    "insured": {
                        "type": "individual",
                        "full_name": "Ion Popescu",
                        "national_id": "1800101223344",
                        "company_id": None,
                        "email": "ion.popescu@example.test",
                        "phone": "+40712345678",
                        "address": "Str. Lalelelor 12, Sector 3, Bucuresti",
                    },
                },
                "insured_asset": {
                    "asset_type": "apartment",
                    "usage_type": "residential",
                    "construction_type": "concrete",
                    "year_built": 1986,
                    "floor": 4,
                    "area_sqm": 68.0,
                    "declared_value": 350000.0,
                    "occupancy": "owner_occupied",
                    "previous_claims_count": 2,
                    "address": {
                        "country": "Romania",
                        "county": "Bucuresti",
                        "city": "Bucuresti",
                        "street": "Str. Lalelelor",
                        "number": "12",
                        "postal_code": "031234",
                    },
                },
                "coverage": {
                    "building_sum_insured": 350000.0,
                    "contents_sum_insured": 350000.0,
                    "total_sum_insured": 350000.0,
                },
                "risk_profile": {
                    "overall_risk_level": "medium_high",
                    "risk_score": 72,
                    "factors": [
                        {
                            "code": "FLOOD_EXPOSURE",
                            "label": "Expunere la inundatii",
                            "level": "high",
                            "score": 85,
                            "evidence": ["zona cu istoric de inundatii"],
                            "contract_impact": {
                                "clause_tags": ["flood_specific"],
                                "premium_adjustment_percent": 12.0,
                                "deductible_adjustment_ron": 500.0,
                            },
                        }
                    ],
                },
                "pricing": {
                    "base_premium_ron": 1200.0,
                    "adjustments": [
                        {
                            "source": "FLOOD_EXPOSURE",
                            "type": "percentage",
                            "value": 12.0,
                        }
                    ],
                    "final_premium_ron": 1490.0,
                    "payment_plan": {
                        "type": "annual",
                        "installments": 1,
                    },
                },
            },
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.module_name, "ContractPayloadBuilder")
        self.assertIn(
            "reference_data.contract_source.contract",
            result.source_fields_used,
        )

    def test_returns_failed_result_when_source_data_is_missing(self) -> None:
        case_context = (
            CaseContextFactory().create_contract_case_context_from_contract_id(
                CONTRACT_ID
            )
        )

        result = ContractPayloadBuilder().build(case_context)

        self.assertEqual(result.status, "failed")
        self.assertIn("contract_source", result.summary)
        self.assertEqual(
            case_context.domain_payload.contract_generation_payload,
            {},
        )
