from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class Address(BaseModel):
    id: int | None = None
    country: str
    county: str
    city: str
    street: str
    number: str
    postal_code: str
    full_text: str


class Customer(BaseModel):
    id: int | None = None
    type: Literal["individual", "company"]
    full_name: str
    national_id: str | None = None  # CNP
    company_id: str | None = None
    email: str
    phone: str
    address_id: int


class Insurer(BaseModel):
    id: int | None = None
    name: str
    company_id: str
    representative_name: str
    representative_role: str
    address_id: int


class InsuredAsset(BaseModel):
    id: int | None = None
    customer_id: int
    asset_type: str
    usage_type: str
    construction_type: str
    year_built: int
    floor: int | None = None
    area_sqm: Decimal
    declared_value: Decimal
    occupancy: str
    previous_claims_count: int = 0
    address_id: int
    created_at: datetime
    updated_at: datetime


class Contract(BaseModel):
    # Contract ids are stable outside the database.
    id: UUID | None = None
    contract_number: str
    document_type: str
    document_version: str
    insurer_id: int
    customer_id: int
    insured_asset_id: int
    issue_date: date
    effective_date: date
    expiration_date: date
    jurisdiction: str
    governing_law: str
    currency: str
    status: Literal["draft", "generated", "issued", "expired", "declined"]
    created_at: datetime
    updated_at: datetime


class RiskProfile(BaseModel):
    id: int | None = None
    # Foreign key to contract.id.
    contract_id: UUID
    overall_risk_level: str
    risk_score: int
    assessment_date: date
    created_at: datetime


class RiskFactor(BaseModel):
    id: int | None = None
    risk_profile_id: int
    code: str
    label: str
    level: str
    score: int
    evidence_json: list[str] = Field(default_factory=list)
    clause_tags_json: list[str] = Field(default_factory=list)
    premium_adjustment_percent: Decimal = Decimal("0")
    deductible_adjustment_ron: Decimal = Decimal("0")
    created_at: datetime


class PricingAdjustment(BaseModel):
    source: str
    type: str
    value: Decimal

    @model_validator(mode="before")
    @classmethod
    def accept_quote_pricing_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        source = normalized.get("source") or normalized.get("code")
        adjustment_type = normalized.get("type") or normalized.get("adjustment_type")
        if source is not None:
            normalized["source"] = str(source)
        if adjustment_type is not None:
            normalized["type"] = str(adjustment_type)
        return normalized


class Pricing(BaseModel):
    id: int | None = None
    # Foreign key to contract.id.
    contract_id: UUID
    base_premium_ron: Decimal
    adjustments_json: list[PricingAdjustment] = Field(default_factory=list)
    final_premium_ron: Decimal
    payment_plan_type: str
    installments: int


class Template(BaseModel):
    id: int | None = None
    template_code: str
    name: str
    version: str
    document_type: str
    is_active: bool = True
    content: str
    jurisdiction: str | None = None
    product_line: str | None = None
    legal_references_json: list[str] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class GeneratedDocument(BaseModel):
    id: int | None = None
    # Foreign key to contract.id.
    contract_id: UUID
    template_id: int
    generation_status: Literal["pending", "success", "failed"]
    rendered_text: str
    rendered_json: dict[str, Any]
    template_code: str | None = None
    template_version: str | None = None
    template_version_hash: str | None = None
    payload_snapshot: dict[str, Any] = Field(default_factory=dict)
    generation_metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str | None = None
    file_url: str | None = None
    created_at: datetime
    updated_at: datetime


# what gets loaded from the DB
class ContractContextSource(BaseModel):
    contract: Contract
    customer: Customer
    customer_address: Address
    insurer: Insurer
    insurer_address: Address
    insured_asset: InsuredAsset
    insured_asset_address: Address
    risk_profile: RiskProfile
    risk_factors: list[RiskFactor] = Field(default_factory=list)
    pricing: Pricing


class InsurerContextSource(BaseModel):
    insurer: Insurer
    insurer_address: Address


# JSON from of ContractContextSource
class ContractGenerationContext(BaseModel):
    payload: dict[str, Any]
