# Underwright Quote Generation Payload

This file describes the active quote generation payload.
It is the source of truth for the pre-signature `QuoteRequest -> JSON -> template/LLM -> QuoteDocument` projection.

Owner:

- `QuotePayloadBuilder` in `src/underwright/application/modules/quote_payload_builder.py`

Rules:

- client intake starts on `QuoteRequest`
- services attach source data to `QuoteCaseContext.reference_data`
- `QuotePayloadBuilder` shapes that data into `quote_generation_payload`
- quote templates should use this snake_case payload dialect
- the payload lives under `quote_case_context.domain_payload.quote_generation_payload`

Do not add new active pre-signature fields to `contract_generation_payload`.

## Payload Shape

```json
{
  "document_type": "insurance_quote",
  "document_version": "1.0",
  "language": "ro-RO",
  "generation_mode": "template_plus_ai_additions",
  "quote_meta": {},
  "contract_meta": {},
  "parties": {},
  "insured_asset": {},
  "risk_profile": {},
  "pricing": {},
  "approval": {}
}
```

## Field Mapping

| JSON field | Source | Notes |
| --- | --- | --- |
| `document_type` | constant | `insurance_quote` |
| `document_version` | constant | `1.0` |
| `language` | `QuoteCaseContext.source_inputs.language` | defaults to `ro-RO` |
| `generation_mode` | constant | `template_plus_ai_additions` |
| `quote_meta.quote_id` | `QuoteRequest.request_id` | request UUID |
| `quote_meta.request_id` | `QuoteRequest.request_id` | same source, explicit naming for templates |
| `quote_meta.status` | `QuoteRequest.request_status` | current lifecycle status |
| `contract_meta.contract_id` | compatibility value | temporary key for older PAD templates |
| `parties.insured` | `QuoteRequest.client_data` | client-entered insured party data |
| `insured_asset` | `QuoteRequest.asset_data` | client-entered asset data |
| `risk_profile.overall_risk_level` | constant | `pending_rules` until real rules exist |
| `risk_profile.factors` | constant | empty until risk rules exist |
| `pricing` | `QuoteRequest.pricing_preview` | pricing preview data |
| `approval` | `QuoteCaseContext.domain_payload.approval_decision` | approval/preapproval decision |

## Required Intake Fields

`QuoteDataCompletionModule` currently requires:

- `client_data.full_name`
- `client_data.email`
- `client_data.phone`
- `asset_data.asset_type`
- `asset_data.usage_type`
- `asset_data.construction_type`
- `asset_data.year_built`
- `asset_data.area_sqm`
- `asset_data.declared_value`
- `asset_data.occupancy`

Incomplete data is saved back to `QuoteRequest.mandatory_data_status`.
No `QuoteDocument` is generated until the mandatory data check passes.

## Approval Payload

The current approval payload is stubbed:

```json
{
  "status": "underwriter_review",
  "decision_source": "stub",
  "reasons": ["approval_rules_not_configured"]
}
```

Future rules should keep this decision under `quote_case_context.domain_payload.approval_decision`.
The request status should remain the queue/source-of-truth status for API list views.
