from __future__ import annotations

from typing import Any

from underwright.domain.contract_case_context import ContractCaseContext
from underwright.domain.models import ContractContextSource


class ClientDataService:
    """Derives stable profile sections from an already loaded contract source."""

    def populate_profiles(self, case_context: ContractCaseContext) -> ContractCaseContext:
        contract_source = case_context.reference_data.contract_source

        if contract_source is None:
            raise ValueError("reference_data.contract_source is required")

        if isinstance(contract_source, dict):
            contract_source = ContractContextSource.model_validate(contract_source)

        case_context.reference_data.client_profile = self._build_client_profile(
            contract_source
        )
        case_context.reference_data.property_profile = self._build_property_profile(
            contract_source
        )

        return case_context

    def _build_client_profile(
        self,
        source: ContractContextSource,
    ) -> dict[str, Any]:
        customer = source.customer
        address = source.customer_address

        return {
            "customer_id": customer.id,
            "customer_type": customer.type,
            "full_name": customer.full_name,
            "national_id": customer.national_id,
            "company_id": customer.company_id,
            "email": customer.email,
            "phone": customer.phone,
            "address": {
                "id": address.id,
                "country": address.country,
                "county": address.county,
                "city": address.city,
                "street": address.street,
                "number": address.number,
                "postal_code": address.postal_code,
                "full_text": address.full_text,
            },
        }

    def _build_property_profile(
        self,
        source: ContractContextSource,
    ) -> dict[str, Any]:
        asset = source.insured_asset
        address = source.insured_asset_address

        return {
            "asset_id": asset.id,
            "customer_id": asset.customer_id,
            "asset_type": asset.asset_type,
            "usage_type": asset.usage_type,
            "construction_type": asset.construction_type,
            "year_built": asset.year_built,
            "floor": asset.floor,
            "area_sqm": asset.area_sqm,
            "declared_value": asset.declared_value,
            "occupancy": asset.occupancy,
            "previous_claims_count": asset.previous_claims_count,
            "address": {
                "id": address.id,
                "country": address.country,
                "county": address.county,
                "city": address.city,
                "street": address.street,
                "number": address.number,
                "postal_code": address.postal_code,
                "full_text": address.full_text,
            },
        }
