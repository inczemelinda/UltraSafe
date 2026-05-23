from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

_UUID_TEXT_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class AddressSnapshot(BaseModel):
    country: str
    county: str
    city: str
    street: str
    number: str
    postal_code: str
    full_text: str


class ContractCustomerSummary(BaseModel):
    id: int | None = None
    type: str
    full_name: str
    national_id: str | None = None
    company_id: str | None = None
    email: str
    phone: str
    address: AddressSnapshot | None = None


class ContractAssetSummary(BaseModel):
    id: int | None = None
    asset_type: str
    usage_type: str
    construction_type: str
    year_built: int
    floor: int | None = None
    area_sqm: Decimal
    declared_value: Decimal
    occupancy: str
    previous_claims_count: int = 0
    address: AddressSnapshot | None = None


class ContractPricingSummary(BaseModel):
    base_premium_ron: Decimal
    final_premium_ron: Decimal
    currency: str
    payment_plan_type: str
    installments: int


class ContractReadModel(BaseModel):
    id: UUID
    contract_number: str
    display_id: str | None = None
    document_type: str
    document_version: str
    status: str
    source_quote_request_id: UUID | None = None
    source_quote_id: UUID | None = None
    source_quote_document_id: int | None = None
    source_quote_acceptance_id: int | None = None
    issue_date: date
    effective_date: date
    expiration_date: date
    jurisdiction: str
    governing_law: str
    currency: str
    created_at: datetime
    updated_at: datetime
    customer: ContractCustomerSummary | None = None
    asset: ContractAssetSummary | None = None
    pricing: ContractPricingSummary | None = None

    @model_validator(mode="after")
    def populate_display_id(self) -> "ContractReadModel":
        if not self.display_id:
            self.display_id = build_contract_display_id(
                contract_number=self.contract_number,
                legal_name=self.customer.full_name if self.customer else None,
                fallback_id=self.id,
            )
        return self


def build_contract_display_id(
    *,
    contract_number: str | None,
    legal_name: str | None,
    fallback_id: UUID | str | None = None,
) -> str:
    template = _contract_template(contract_number, legal_name)
    differentiator = _contract_differentiator(contract_number, fallback_id)
    legal = _legal_name_display_part(legal_name)
    if template and legal and differentiator:
        return f"{template}-{legal}-{differentiator}"
    return _clean_display_part(contract_number) or _clean_display_part(fallback_id)


def _contract_template(contract_number: str | None, legal_name: str | None) -> str:
    parts = _contract_number_parts(contract_number)
    if not parts:
        return ""
    template_parts = parts[:-1]
    if template_parts and re.fullmatch(r"\d{4}", template_parts[-1]):
        template_parts = template_parts[:-1]

    template_parts = _without_legal_name_suffix(template_parts, legal_name)
    return "-".join(template_parts)


def _contract_differentiator(
    contract_number: str | None,
    fallback_id: UUID | str | None,
) -> str:
    parts = _contract_number_parts(contract_number)
    if parts:
        return parts[-1]
    fallback = _clean_display_part(fallback_id)
    return fallback.split("-")[-1] if fallback else ""


def _contract_number_parts(contract_number: str | None) -> list[str]:
    cleaned = _clean_display_part(contract_number)
    if _UUID_TEXT_PATTERN.fullmatch(cleaned):
        return []
    return [
        part.strip()
        for part in cleaned.split("-")
        if part.strip()
    ]


def _without_legal_name_suffix(
    template_parts: list[str],
    legal_name: str | None,
) -> list[str]:
    legal = _clean_display_part(legal_name)
    if len(template_parts) <= 1 or not legal:
        return template_parts

    normalized_legal = _normalized_token(legal)
    first_legal_token = _normalized_token(legal.split(" ")[0])
    for suffix_length in range(len(template_parts) - 1, 0, -1):
        suffix = " ".join(template_parts[-suffix_length:])
        if _normalized_token(suffix) == normalized_legal:
            return template_parts[:-suffix_length]

    if _normalized_token(template_parts[-1]) == first_legal_token:
        return template_parts[:-1]
    return template_parts


def _normalized_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _clean_display_part(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _legal_name_display_part(value: Any) -> str:
    return re.sub(r"\s+", "_", _clean_display_part(value))


class ContractConversionIssue(BaseModel):
    code: str
    message: str
    field: str | None = None


class ContractConversionValidation(BaseModel):
    can_convert: bool
    blocking_errors: list[ContractConversionIssue] = Field(default_factory=list)
    warnings: list[ContractConversionIssue] = Field(default_factory=list)
    model_gaps: list[str] = Field(default_factory=list)


class QuoteContractResolution(BaseModel):
    quote_id: UUID
    already_converted: bool
    conversion_status: Literal["converted", "eligible", "blocked"]
    contract_id: UUID | None = None
    contract: ContractReadModel | None = None
    validation: ContractConversionValidation


class QuoteToContractConversionResult(BaseModel):
    quote_id: UUID
    result: Literal["created", "already_exists", "blocked"]
    contract_id: UUID | None = None
    contract: ContractReadModel | None = None
    validation: ContractConversionValidation


class ContractCreationData(BaseModel):
    id: UUID
    contract_number: str
    source_quote_request_id: UUID
    source_quote_document_id: int
    source_quote_acceptance_id: int | None = None
    document_type: str = "insurance_contract"
    document_version: str = "1.0"
    customer_type: Literal["individual", "company"] = "individual"
    customer_full_name: str
    customer_national_id: str | None = None
    customer_company_id: str | None = None
    customer_email: str
    customer_phone: str
    customer_address: AddressSnapshot
    asset_type: str
    usage_type: str
    construction_type: str
    year_built: int
    floor: int | None = None
    area_sqm: Decimal
    declared_value: Decimal
    occupancy: str
    previous_claims_count: int = 0
    asset_address: AddressSnapshot
    issue_date: date
    effective_date: date
    expiration_date: date
    jurisdiction: str = "Romania"
    governing_law: str = "Legea 260/2008"
    currency: str = "RON"
    status: Literal["draft", "generated", "issued", "expired", "declined"] = "draft"
    overall_risk_level: str = "standard"
    risk_score: int = 0
    base_premium_ron: Decimal
    pricing_adjustments: list[dict[str, Any]] = Field(default_factory=list)
    final_premium_ron: Decimal
    payment_plan_type: str = "annual"
    installments: int = 1
    created_at: datetime
    updated_at: datetime


__all__ = [
    "AddressSnapshot",
    "ContractAssetSummary",
    "ContractConversionIssue",
    "ContractConversionValidation",
    "ContractCreationData",
    "ContractCustomerSummary",
    "ContractPricingSummary",
    "ContractReadModel",
    "build_contract_display_id",
    "QuoteContractResolution",
    "QuoteToContractConversionResult",
]
