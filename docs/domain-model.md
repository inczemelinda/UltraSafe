# Underwright Domain Model

This document describes the current Postgres schema defined across:

- `sql/001_init_schema.sql`
- `sql/004_quote_requests.sql`
- `sql/005_quote_documents.sql`

Keep this aligned with:
- the SQL DDL
- `src/underwright/domain/models.py`
- `src/underwright/domain/quote_request.py`
- `src/underwright/domain/quote_document.py`
- `docs/quote-context.md`
- `docs/contract-context.md`

## Tables

### Address

Reusable address record for customer, insurer, and insured asset.

Fields:
- `id`
- `country`
- `county`
- `city`
- `street`
- `number`
- `postal_code`
- `full_text`

### Customer

Stores the insured party.

Fields:
- `id`
- `type`
- `full_name`
- `national_id`
- `company_id`
- `email`
- `phone`
- `address_id`

Notes:
- `type` is constrained to `individual` or `company`
- `address_id` references `address.id`

### Insurer

Stores the issuing insurer.

Fields:
- `id`
- `name`
- `company_id`
- `representative_name`
- `representative_role`
- `address_id`

Notes:
- `address_id` references `address.id`

### InsuredAsset

Stores the apartment / house / building being insured.

Fields:
- `id`
- `customer_id`
- `asset_type`
- `usage_type`
- `construction_type`
- `year_built`
- `floor`
- `area_sqm`
- `declared_value`
- `occupancy`
- `previous_claims_count`
- `address_id`
- `created_at`
- `updated_at`

Notes:
- `customer_id` references `customer.id`
- `address_id` references `address.id`

### Contract

Legacy/post-signing contract record.
This is not the active client intake aggregate after the quote-first refactor.
A signed quote can become a contract later, but that conversion workflow is not implemented yet.

Fields:
- `id`
- `contract_number`
- `document_type`
- `document_version`
- `insurer_id`
- `customer_id`
- `insured_asset_id`
- `issue_date`
- `effective_date`
- `expiration_date`
- `jurisdiction`
- `governing_law`
- `currency`
- `status`
- `created_at`
- `updated_at`

Notes:
- `id` is a UUID
- `contract_number` is unique
- `status` is constrained to `draft`, `generated`, `issued`, `expired`
- foreign keys point to `insurer`, `customer`, and `insured_asset`

### RiskProfile

One risk assessment snapshot for a contract.

Fields:
- `id`
- `contract_id`
- `overall_risk_level`
- `risk_score`
- `assessment_date`
- `created_at`

Notes:
- `contract_id` is a UUID that references `contract.id`

### RiskFactor

Individual risk drivers under a risk profile.

Fields:
- `id`
- `risk_profile_id`
- `code`
- `label`
- `level`
- `score`
- `evidence_json`
- `clause_tags_json`
- `premium_adjustment_percent`
- `deductible_adjustment_ron`
- `created_at`

Notes:
- `risk_profile_id` references `risk_profile.id`
- JSONB fields store factor evidence and clause tags

### Pricing

Contract pricing snapshot.

Fields:
- `id`
- `contract_id`
- `base_premium_ron`
- `adjustments_json`
- `final_premium_ron`
- `payment_plan_type`
- `installments`

Notes:
- `contract_id` is a UUID that references `contract.id`
- `adjustments_json` stores the pricing adjustments array

### Template

Stores the template metadata and template body used during generation.

Fields:
- `id`
- `template_code`
- `name`
- `version`
- `document_type`
- `is_active`
- `content`
- `created_at`

Notes:
- `template_code` is unique

### GeneratedDocument

Stores legacy generated contract results.
New unsigned quote output should use `quote_document`.

Fields:
- `id`
- `contract_id`
- `template_id`
- `generation_status`
- `rendered_text`
- `rendered_json`
- `file_url`
- `created_at`
- `updated_at`

Notes:
- `contract_id` is a UUID that references `contract.id`
- `generation_status` is constrained to `pending`, `success`, `failed`
- `rendered_json` stores the context snapshot plus generation metadata

### QuoteRequest

Stores client quote intake before a contract exists.

Fields:
- `request_id`
- `client_id`
- `request_status`
- `client_data`
- `asset_data`
- `quote_steps`
- `mandatory_data_status`
- `attachments`
- `pricing_preview`
- `created_at`
- `updated_at`

Notes:
- `request_id` is a UUID and the primary key
- `request_status` is constrained to `draft`, `pricing_in_progress`, `quote_ready`, `auto_accepted`, `underwriter_review`, `approved`, `disapproved`, `field_review_required`, or `failed`
- JSONB fields store client-entered intake, step state, attachments, and pricing preview data
- this is the active pre-signature request aggregate

### QuoteDocument

Stores the generated unsigned quote document.

Fields:
- `id`
- `quote_request_id`
- `template_id`
- `generation_status`
- `rendered_text`
- `rendered_json`
- `file_url`
- `created_at`
- `updated_at`

Notes:
- `quote_request_id` references `quote_request.request_id`
- `template_id` references `template.id`
- `generation_status` is constrained to `pending`, `success`, `failed`
- `rendered_json` stores quote payload, approval decision, generation metadata, and audit trail
- a quote document is not a contract; it can become contract source data after signing

## Relationships

- one `customer` belongs to one `address`
- one `insurer` belongs to one `address`
- one `insured_asset` belongs to one `customer` and one `address`
- one `contract` belongs to one `customer`, one `insurer`, and one `insured_asset`
- one `risk_profile` belongs to one `contract`
- many `risk_factor` rows belong to one `risk_profile`
- one `pricing` row belongs to one `contract`
- many `generated_document` rows can belong to one `contract`
- many `generated_document` rows can reference one `template`
- many `quote_document` rows can belong to one `quote_request`
- many `quote_document` rows can reference one `template`

## Conventions

- prefer `pydantic` models over `dataclasses`
- keep validation light in the scaffold
- add stricter validation only where the MVP really needs it
- keep pre-signature records under quote models and tables
- keep contract records for post-signing or legacy contract artifacts

Reference diagram:
- https://www.drawdb.app/editor?shareId=03189c8ecb91e861e82d8aa540989aec
