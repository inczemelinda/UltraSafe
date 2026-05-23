from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CustomerProfileStatus = Literal["pending_customer_link", "incomplete", "complete"]
CustomerType = Literal["individual", "company"]
CustomerProfileCompletionSource = Literal[
    "client_self_service",
    "employee_link",
    "admin_update",
    "seed",
]


class CustomerAddressProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str | None = None
    county: str | None = None
    city: str | None = None
    street: str | None = None
    number: str | None = None
    postal_code: str | None = None
    full_text: str | None = None


class CustomerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: CustomerType | None = None
    full_name: str | None = None
    national_id: str | None = None
    company_id: str | None = None
    email: str | None = None
    phone: str | None = None
    address: CustomerAddressProfile | None = None


class StoredCustomerProfile(BaseModel):
    customer_id: int
    type: CustomerType
    full_name: str
    national_id: str | None = None
    company_id: str | None = None
    email: str
    phone: str
    address: CustomerAddressProfile
    customer_profile_completed_at: datetime | None = None
    customer_profile_updated_at: datetime | None = None
    customer_profile_updated_by_auth_user_id: int | None = None
    customer_profile_completion_source: CustomerProfileCompletionSource | None = None
    profile_update_count: int = 0


class CustomerProfileReadModel(BaseModel):
    customer_id: int | None = None
    status: CustomerProfileStatus
    requires_customer_profile_completion: bool
    type: CustomerType | None = None
    full_name: str | None = None
    national_id: str | None = None
    company_id: str | None = None
    email: str | None = None
    phone: str | None = None
    address: CustomerAddressProfile | None = None
    missing_fields: list[str] = Field(default_factory=list)
    customer_profile_completed_at: datetime | None = None
    customer_profile_updated_at: datetime | None = None
    customer_profile_updated_by_auth_user_id: int | None = None
    customer_profile_completion_source: CustomerProfileCompletionSource | None = None
    profile_update_count: int = 0
    linked_auth_user_count: int | None = None


__all__ = [
    "CustomerAddressProfile",
    "CustomerProfileCompletionSource",
    "CustomerProfileReadModel",
    "CustomerProfileStatus",
    "CustomerProfileUpdate",
    "CustomerType",
    "StoredCustomerProfile",
]
