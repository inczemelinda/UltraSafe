from __future__ import annotations

from typing import Any

from underwright.domain.contract_case_context import ContractCaseContext
from underwright.domain.module_result import ModuleResult
from underwright.domain.models import (
    ContractContextSource,
)
from underwright.domain.contract_lifecycle import build_contract_display_id


class ContractPayloadBuilder:
    """Builds and attaches the canonical contract_generation_payload."""

    def build(self, case_context: ContractCaseContext) -> ModuleResult:
        source_data = case_context.reference_data.contract_source
        if source_data is None:
            return ModuleResult(
                module_name="ContractPayloadBuilder",
                status="failed",
                summary=(
                    "reference_data.contract_source is required before building "
                    "contract_generation_payload."
                ),
            )

        payload = self._build_payload(source_data)
        case_context.domain_payload.contract_generation_payload = payload
        return ModuleResult(
            module_name="ContractPayloadBuilder",
            status="success",
            summary="Built contract_generation_payload.",
            source_fields_used=[
                "reference_data.contract_source.contract",
                "reference_data.contract_source.customer",
                "reference_data.contract_source.insurer",
                "reference_data.contract_source.insured_asset",
                "reference_data.contract_source.risk_profile",
                "reference_data.contract_source.risk_factors",
                "reference_data.contract_source.pricing",
            ],
        )

    def _build_payload(
        self,
        source_data: ContractContextSource,
    ) -> dict[str, Any]:
        declared_value = float(source_data.insured_asset.declared_value)

        return {
            "document_type": source_data.contract.document_type,
            "document_version": source_data.contract.document_version,
            "language": "ro-RO",
            "generation_mode": "hybrid_template_plus_llm",
            "contract_meta": {
                "contract_id": build_contract_display_id(
                    contract_number=source_data.contract.contract_number,
                    legal_name=source_data.customer.full_name,
                    fallback_id=source_data.contract.id,
                ),
                "issue_date": source_data.contract.issue_date.isoformat(),
                "effective_date": source_data.contract.effective_date.isoformat(),
                "expiration_date": source_data.contract.expiration_date.isoformat(),
                "jurisdiction": source_data.contract.jurisdiction,
                "governing_law": source_data.contract.governing_law,
                "currency": source_data.contract.currency,
            },
            "parties": {
                "insurer": {
                    "name": source_data.insurer.name,
                    "company_id": source_data.insurer.company_id,
                    "address": source_data.insurer_address.full_text,
                    "representative": {
                        "name": source_data.insurer.representative_name,
                        "role": source_data.insurer.representative_role,
                    },
                },
                "insured": {
                    "type": source_data.customer.type,
                    "full_name": source_data.customer.full_name,
                    "national_id": source_data.customer.national_id,
                    "company_id": source_data.customer.company_id,
                    "email": source_data.customer.email,
                    "phone": source_data.customer.phone,
                    "address": source_data.customer_address.full_text,
                },
            },
            "insured_asset": {
                "asset_type": source_data.insured_asset.asset_type,
                "usage_type": source_data.insured_asset.usage_type,
                "construction_type": source_data.insured_asset.construction_type,
                "year_built": source_data.insured_asset.year_built,
                "floor": source_data.insured_asset.floor,
                "area_sqm": float(source_data.insured_asset.area_sqm),
                "declared_value": declared_value,
                "occupancy": source_data.insured_asset.occupancy,
                "previous_claims_count": (
                    source_data.insured_asset.previous_claims_count
                ),
                "address": {
                    "country": source_data.insured_asset_address.country,
                    "county": source_data.insured_asset_address.county,
                    "city": source_data.insured_asset_address.city,
                    "street": source_data.insured_asset_address.street,
                    "number": source_data.insured_asset_address.number,
                    "postal_code": source_data.insured_asset_address.postal_code,
                },
            },
            "coverage": {
                "building_sum_insured": declared_value,
                "contents_sum_insured": declared_value,
                "total_sum_insured": declared_value,
            },
            "risk_profile": {
                "overall_risk_level": source_data.risk_profile.overall_risk_level,
                "risk_score": source_data.risk_profile.risk_score,
                "factors": [
                    {
                        "code": factor.code,
                        "label": factor.label,
                        "level": factor.level,
                        "score": factor.score,
                        "evidence": factor.evidence_json,
                        "contract_impact": {
                            "clause_tags": factor.clause_tags_json,
                            "premium_adjustment_percent": float(
                                factor.premium_adjustment_percent
                            ),
                            "deductible_adjustment_ron": float(
                                factor.deductible_adjustment_ron
                            ),
                        },
                    }
                    for factor in source_data.risk_factors
                ],
            },
            "pricing": {
                "base_premium_ron": float(source_data.pricing.base_premium_ron),
                "adjustments": [
                    {
                        "source": adjustment.source,
                        "type": adjustment.type,
                        "value": float(adjustment.value),
                    }
                    for adjustment in source_data.pricing.adjustments_json
                ],
                "final_premium_ron": float(source_data.pricing.final_premium_ron),
                "payment_plan": {
                    "type": source_data.pricing.payment_plan_type,
                    "installments": source_data.pricing.installments,
                },
            },
        }


__all__ = ["ContractPayloadBuilder"]
