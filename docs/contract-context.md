# Underwright Contract Generation Payload

This file describes the legacy/post-signing contract generation payload.
It is not the active client quote request flow.

For the active pre-signature payload, see `docs/quote-context.md`.

## Boundary

The current product lifecycle is:

`QuoteRequest -> QuoteDocument -> signed quote -> Contract`

The old `ContractWorkflow` and `contract_generation_payload` remain useful as legacy demo code and future post-signing groundwork.
Do not use this payload for new pre-signature quote behavior.

Owner:

- `ContractPayloadBuilder` in `src/underwright/application/modules/contract_payload_builder.py`

Rules:

- repositories return normalized contract source models
- services attach source models to `ContractCaseContext.reference_data`
- `ContractPayloadBuilder` shapes those models into `contract_generation_payload`
- legacy PAD contract templates use this snake_case payload dialect
- the payload lives under `contract_case_context.domain_payload.contract_generation_payload`

Do not use the older template dialect with placeholders such as `Insurer.name`, `Customer.full_name`, or `RiskProfile.summary` in active templates/tests.

## Payload Shape

```json
{
  "document_type": "insurance_contract",
  "document_version": "1.0",
  "language": "ro-RO",
  "generation_mode": "hybrid_template_plus_llm",
  "contract_meta": {},
  "parties": {},
  "insured_asset": {},
  "risk_profile": {},
  "pricing": {}
}
```

## Field Mapping

| JSON field | DB source | Notes |
| --- | --- | --- |
| `document_type` | `contract.document_type` | direct mapping |
| `document_version` | `contract.document_version` | direct mapping |
| `language` | constant | always `ro-RO` for MVP |
| `generation_mode` | constant | always `hybrid_template_plus_llm` for legacy flow |
| `contract_meta.contract_id` | `contract.contract_number` | rendered contract number |
| `contract_meta.issue_date` | `contract.issue_date` | serialized as ISO date |
| `contract_meta.effective_date` | `contract.effective_date` | serialized as ISO date |
| `contract_meta.expiration_date` | `contract.expiration_date` | serialized as ISO date |
| `contract_meta.jurisdiction` | `contract.jurisdiction` | direct mapping |
| `contract_meta.governing_law` | `contract.governing_law` | direct mapping |
| `contract_meta.currency` | `contract.currency` | direct mapping |
| `parties.insurer.name` | `insurer.name` | direct mapping |
| `parties.insurer.company_id` | `insurer.company_id` | direct mapping |
| `parties.insurer.address` | `insurer_address.full_text` | flattened display address |
| `parties.insurer.representative.name` | `insurer.representative_name` | direct mapping |
| `parties.insurer.representative.role` | `insurer.representative_role` | direct mapping |
| `parties.insured.type` | `customer.type` | `individual` or `company` |
| `parties.insured.full_name` | `customer.full_name` | person or company display name |
| `parties.insured.national_id` | `customer.national_id` | `null` when `customer.type = company` |
| `parties.insured.company_id` | `customer.company_id` | `null` when `customer.type = individual` |
| `parties.insured.email` | `customer.email` | direct mapping |
| `parties.insured.phone` | `customer.phone` | direct mapping |
| `parties.insured.address` | `customer_address.full_text` | flattened display address |
| `insured_asset.asset_type` | `insured_asset.asset_type` | direct mapping |
| `insured_asset.usage_type` | `insured_asset.usage_type` | direct mapping |
| `insured_asset.construction_type` | `insured_asset.construction_type` | direct mapping |
| `insured_asset.year_built` | `insured_asset.year_built` | direct mapping |
| `insured_asset.floor` | `insured_asset.floor` | `null` when not applicable |
| `insured_asset.area_sqm` | `insured_asset.area_sqm` | serialized as JSON number |
| `insured_asset.declared_value` | `insured_asset.declared_value` | serialized as JSON number |
| `insured_asset.occupancy` | `insured_asset.occupancy` | direct mapping |
| `insured_asset.previous_claims_count` | `insured_asset.previous_claims_count` | direct mapping |
| `insured_asset.address.country` | `insured_asset_address.country` | direct mapping |
| `insured_asset.address.county` | `insured_asset_address.county` | direct mapping |
| `insured_asset.address.city` | `insured_asset_address.city` | direct mapping |
| `insured_asset.address.street` | `insured_asset_address.street` | direct mapping |
| `insured_asset.address.number` | `insured_asset_address.number` | direct mapping |
| `insured_asset.address.postal_code` | `insured_asset_address.postal_code` | direct mapping |
| `risk_profile.overall_risk_level` | `risk_profile.overall_risk_level` | direct mapping |
| `risk_profile.risk_score` | `risk_profile.risk_score` | direct mapping |
| `risk_profile.factors[].code` | `risk_factor.code` | one item per `risk_factor` row |
| `risk_profile.factors[].label` | `risk_factor.label` | direct mapping |
| `risk_profile.factors[].level` | `risk_factor.level` | direct mapping |
| `risk_profile.factors[].score` | `risk_factor.score` | direct mapping |
| `risk_profile.factors[].evidence` | `risk_factor.evidence_json` | JSON array passthrough |
| `risk_profile.factors[].contract_impact.clause_tags` | `risk_factor.clause_tags_json` | JSON array passthrough |
| `risk_profile.factors[].contract_impact.premium_adjustment_percent` | `risk_factor.premium_adjustment_percent` | serialized as JSON number |
| `risk_profile.factors[].contract_impact.deductible_adjustment_ron` | `risk_factor.deductible_adjustment_ron` | serialized as JSON number |
| `pricing.base_premium_ron` | `pricing.base_premium_ron` | serialized as JSON number |
| `pricing.adjustments[].source` | `pricing.adjustments_json[].source` | passthrough from JSONB |
| `pricing.adjustments[].type` | `pricing.adjustments_json[].type` | passthrough from JSONB |
| `pricing.adjustments[].value` | `pricing.adjustments_json[].value` | serialized as JSON number |
| `pricing.final_premium_ron` | `pricing.final_premium_ron` | serialized as JSON number |
| `pricing.payment_plan.type` | `pricing.payment_plan_type` | direct mapping |
| `pricing.payment_plan.installments` | `pricing.installments` | direct mapping |

## Null Rules

- `parties.insured.national_id` is `null` for company customers.
- `parties.insured.company_id` is `null` for individual customers.
- `insured_asset.floor` is `null` when the asset does not have a floor value.

## Excluded From Generation Payload

- `contract.status`
- `risk_profile.assessment_date`
- `address.full_text` for the insured asset nested address

These stay available in the normalized source models but are not part of the legacy PAD contract generation payload.
