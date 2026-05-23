from __future__ import annotations

from underwright.domain.auth_user import AuthUser
from underwright.domain.customer_profile import (
    CustomerAddressProfile,
    CustomerProfileCompletionSource,
    CustomerProfileReadModel,
    CustomerProfileStatus,
    CustomerProfileUpdate,
    StoredCustomerProfile,
)


class CustomerProfileError(ValueError):
    pass


class CustomerProfileIncompleteError(CustomerProfileError):
    def __init__(
        self,
        message: str = "Customer profile is incomplete.",
        *,
        missing_fields: list[str] | None = None,
        status: CustomerProfileStatus = "incomplete",
    ) -> None:
        super().__init__(message)
        self.missing_fields = missing_fields or []
        self.status = status


class CustomerProfileNotFoundError(CustomerProfileError):
    pass


class CustomerProfileService:
    """Owns profile completeness for the auth_user.client_id customer link."""

    def __init__(self, customer_profile_repository, auth_user_repository) -> None:
        self.customer_profile_repository = customer_profile_repository
        self.auth_user_repository = auth_user_repository

    def get_profile(self, user: AuthUser) -> CustomerProfileReadModel:
        if user.role != "client":
            raise CustomerProfileNotFoundError("Customer profile is client-only.")
        if user.client_id is None:
            return self._pending_profile(user)
        return self.get_customer_profile(user.client_id)

    def get_customer_profile(self, customer_id: int) -> CustomerProfileReadModel:
        try:
            stored = self.customer_profile_repository.get_customer_profile(customer_id)
        except ValueError as exc:
            raise CustomerProfileNotFoundError("Customer profile not found.") from exc
        linked_count = self._linked_auth_user_count(customer_id)
        return self._read_model(stored, linked_auth_user_count=linked_count)

    def list_customer_profiles(self) -> list[CustomerProfileReadModel]:
        profiles = self.customer_profile_repository.list_customer_profiles()
        return [
            self._read_model(
                profile,
                linked_auth_user_count=self._linked_auth_user_count(
                    profile.customer_id
                ),
            )
            for profile in profiles
        ]

    def update_profile(
        self,
        *,
        user: AuthUser,
        update: CustomerProfileUpdate,
        source: CustomerProfileCompletionSource = "client_self_service",
    ) -> CustomerProfileReadModel:
        existing = self._stored_profile_or_none(user)
        draft = self._merge_profile(user=user, existing=existing, update=update)
        missing_fields = self._missing_fields(draft)
        if missing_fields:
            raise CustomerProfileIncompleteError(
                missing_fields=missing_fields,
                status="pending_customer_link" if user.client_id is None else "incomplete",
            )

        complete_profile = StoredCustomerProfile.model_validate(draft)
        if user.client_id is None:
            stored = self.customer_profile_repository.create_customer_profile(
                complete_profile,
                updated_by_auth_user_id=user.id,
                source=source,
            )
            self.auth_user_repository.update_user_client_id(
                user_id=user.id,
                client_id=stored.customer_id,
            )
        else:
            stored = self.customer_profile_repository.update_customer_profile(
                customer_id=user.client_id,
                profile=complete_profile,
                status="complete",
                updated_by_auth_user_id=user.id,
                source=source,
            )
        return self._read_model(stored, linked_auth_user_count=1)

    def ensure_complete_profile(self, user: AuthUser) -> CustomerProfileReadModel:
        profile = self.get_profile(user)
        if profile.status != "complete":
            raise CustomerProfileIncompleteError(
                missing_fields=profile.missing_fields,
                status=profile.status,
            )
        return profile

    def profile_status_for_user(self, user: AuthUser) -> CustomerProfileStatus | None:
        if user.role != "client":
            return None
        return self.get_profile(user).status

    def mark_employee_link(
        self,
        *,
        customer_id: int,
        updated_by_auth_user_id: int | None,
    ) -> CustomerProfileReadModel:
        stored = self.customer_profile_repository.get_customer_profile(customer_id)
        status = "complete" if not self._missing_fields(stored.model_dump()) else "incomplete"
        updated = self.customer_profile_repository.touch_customer_profile(
            customer_id=customer_id,
            status=status,
            updated_by_auth_user_id=updated_by_auth_user_id,
            source="employee_link",
        )
        return self._read_model(updated)

    def _stored_profile_or_none(
        self,
        user: AuthUser,
    ) -> StoredCustomerProfile | None:
        if user.client_id is None:
            return None
        try:
            return self.customer_profile_repository.get_customer_profile(user.client_id)
        except ValueError as exc:
            raise CustomerProfileNotFoundError("Customer profile not found.") from exc

    def _pending_profile(self, user: AuthUser) -> CustomerProfileReadModel:
        draft = {
            "customer_id": None,
            "type": None,
            "full_name": user.full_name,
            "national_id": None,
            "company_id": None,
            "email": user.email,
            "phone": user.phone,
            "address": None,
        }
        return CustomerProfileReadModel(
            **draft,
            status="pending_customer_link",
            requires_customer_profile_completion=True,
            missing_fields=self._missing_fields(draft),
        )

    def _read_model(
        self,
        stored: StoredCustomerProfile,
        *,
        linked_auth_user_count: int | None = None,
    ) -> CustomerProfileReadModel:
        missing_fields = self._missing_fields(stored.model_dump())
        status: CustomerProfileStatus = "complete" if not missing_fields else "incomplete"
        return CustomerProfileReadModel(
            customer_id=stored.customer_id,
            status=status,
            requires_customer_profile_completion=status != "complete",
            type=stored.type,
            full_name=stored.full_name,
            national_id=stored.national_id,
            company_id=stored.company_id,
            email=stored.email,
            phone=stored.phone,
            address=stored.address,
            missing_fields=missing_fields,
            customer_profile_completed_at=stored.customer_profile_completed_at,
            customer_profile_updated_at=stored.customer_profile_updated_at,
            customer_profile_updated_by_auth_user_id=(
                stored.customer_profile_updated_by_auth_user_id
            ),
            customer_profile_completion_source=(
                stored.customer_profile_completion_source
            ),
            profile_update_count=stored.profile_update_count,
            linked_auth_user_count=linked_auth_user_count,
        )

    def _merge_profile(
        self,
        *,
        user: AuthUser,
        existing: StoredCustomerProfile | None,
        update: CustomerProfileUpdate,
    ) -> dict:
        base = (
            existing.model_dump()
            if existing is not None
            else {
                "customer_id": 0,
                "type": None,
                "full_name": user.full_name,
                "national_id": None,
                "company_id": None,
                "email": user.email,
                "phone": user.phone,
                "address": {},
            }
        )
        update_values = update.model_dump(exclude_unset=True)
        address_update = update_values.pop("address", None)
        for field_name, value in update_values.items():
            base[field_name] = self._clean(value)

        address = dict(base.get("address") or {})
        if isinstance(base.get("address"), CustomerAddressProfile):
            address = base["address"].model_dump()
        if address_update is not None:
            for field_name, value in address_update.items():
                address[field_name] = self._clean(value)
        base["address"] = self._address_with_full_text(address)
        return base

    def _address_with_full_text(self, address: dict) -> dict:
        full_text = self._clean(address.get("full_text"))
        if not full_text:
            parts = [
                address.get("street"),
                address.get("number"),
                address.get("city"),
                address.get("county"),
                address.get("country"),
                address.get("postal_code"),
            ]
            full_text = ", ".join(
                self._clean(part) for part in parts if self._clean(part)
            )
        address["full_text"] = full_text
        return address

    def _missing_fields(self, profile: dict) -> list[str]:
        missing: list[str] = []
        customer_type = profile.get("type")
        for field_name in ("type", "full_name", "email", "phone"):
            if not self._present(profile.get(field_name)):
                missing.append(field_name)

        if customer_type == "individual" and not self._present(
            profile.get("national_id")
        ):
            missing.append("national_id")
        if customer_type == "company" and not self._present(profile.get("company_id")):
            missing.append("company_id")

        address = profile.get("address")
        if isinstance(address, CustomerAddressProfile):
            address = address.model_dump()
        if not isinstance(address, dict):
            address = {}
        for field_name in (
            "country",
            "county",
            "city",
            "street",
            "number",
            "postal_code",
        ):
            if not self._present(address.get(field_name)):
                missing.append(f"address.{field_name}")
        return missing

    def _linked_auth_user_count(self, customer_id: int) -> int:
        if not hasattr(self.auth_user_repository, "list_users_by_client_id"):
            return 0
        return len(self.auth_user_repository.list_users_by_client_id(customer_id))

    def _present(self, value) -> bool:
        return bool(self._clean(value))

    def _clean(self, value) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            return str(value)
        stripped = value.strip()
        return stripped or None


__all__ = [
    "CustomerProfileError",
    "CustomerProfileIncompleteError",
    "CustomerProfileNotFoundError",
    "CustomerProfileService",
]
