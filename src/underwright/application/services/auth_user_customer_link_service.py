from __future__ import annotations

from datetime import datetime, timezone

from underwright.domain.auth_user import AuthUser
from underwright.domain.auth_user_admin import CustomerAuthUserRelinkResult


class AuthUserCustomerLinkError(ValueError):
    pass


class AuthUserNotFoundError(AuthUserCustomerLinkError):
    pass


class CustomerNotFoundError(AuthUserCustomerLinkError):
    pass


class NonClientAuthUserLinkError(AuthUserCustomerLinkError):
    pass


class AuthUserAlreadyLinkedError(AuthUserCustomerLinkError):
    pass


class AuthUserNotLinkedError(AuthUserCustomerLinkError):
    pass


class RelinkReasonRequiredError(AuthUserCustomerLinkError):
    pass


class AuthUserCustomerLinkService:
    def __init__(self, auth_user_repository, customer_profile_service) -> None:
        self.auth_user_repository = auth_user_repository
        self.customer_profile_service = customer_profile_service

    def list_customer_auth_users(self, customer_id: int) -> list[AuthUser]:
        self._require_customer(customer_id)
        return self.auth_user_repository.list_users_by_client_id(customer_id)

    def link_client_user(
        self,
        *,
        auth_user_id: int,
        customer_id: int,
        updated_by_auth_user_id: int | None = None,
    ) -> AuthUser:
        self._require_customer(customer_id)
        user = self._get_user(auth_user_id)
        self._require_client_user(user)
        if user.client_id is not None and user.client_id != customer_id:
            raise AuthUserAlreadyLinkedError(
                "Auth user is already linked to a different customer."
            )
        if user.client_id is None:
            old_customer_id = user.client_id
            user = self.auth_user_repository.update_user_client_id(
                user_id=auth_user_id,
                client_id=customer_id,
            )
            self._record_link_audit(
                action="link",
                auth_user_id=auth_user_id,
                old_customer_id=old_customer_id,
                new_customer_id=customer_id,
                reason=None,
                changed_by_auth_user_id=updated_by_auth_user_id,
            )
        self.customer_profile_service.mark_employee_link(
            customer_id=customer_id,
            updated_by_auth_user_id=updated_by_auth_user_id,
        )
        return user

    def unlink_client_user(
        self,
        *,
        auth_user_id: int,
        customer_id: int,
        updated_by_auth_user_id: int | None = None,
    ) -> AuthUser:
        self._require_customer(customer_id)
        user = self._get_user(auth_user_id)
        self._require_client_user(user)
        if user.client_id is None:
            return user
        if user.client_id != customer_id:
            raise CustomerNotFoundError("Auth user is not linked to this customer.")
        updated = self.auth_user_repository.update_user_client_id(
            user_id=auth_user_id,
            client_id=None,
        )
        self._record_link_audit(
            action="unlink",
            auth_user_id=auth_user_id,
            old_customer_id=customer_id,
            new_customer_id=None,
            reason=None,
            changed_by_auth_user_id=updated_by_auth_user_id,
        )
        self.customer_profile_service.mark_employee_link(
            customer_id=customer_id,
            updated_by_auth_user_id=updated_by_auth_user_id,
        )
        return updated

    def relink_client_user(
        self,
        *,
        auth_user_id: int,
        customer_id: int,
        reason: str | None,
        changed_by_auth_user_id: int | None = None,
    ) -> CustomerAuthUserRelinkResult:
        self._require_customer(customer_id)
        user = self._get_user(auth_user_id)
        self._require_client_user(user)
        old_customer_id = user.client_id

        if old_customer_id is None:
            raise AuthUserNotLinkedError("Auth user is not linked to a customer.")

        clean_reason = self._clean_reason(reason)
        if old_customer_id != customer_id and not self._valid_relink_reason(clean_reason):
            raise RelinkReasonRequiredError(
                "A relink reason of at least 10 characters is required."
            )

        changed_at = datetime.now(timezone.utc)
        if old_customer_id != customer_id:
            self.auth_user_repository.update_user_client_id(
                user_id=auth_user_id,
                client_id=customer_id,
            )
            self.customer_profile_service.mark_employee_link(
                customer_id=old_customer_id,
                updated_by_auth_user_id=changed_by_auth_user_id,
            )
            self.customer_profile_service.mark_employee_link(
                customer_id=customer_id,
                updated_by_auth_user_id=changed_by_auth_user_id,
            )
            audit_record = self._record_link_audit(
                action="relink",
                auth_user_id=auth_user_id,
                old_customer_id=old_customer_id,
                new_customer_id=customer_id,
                reason=clean_reason,
                changed_by_auth_user_id=changed_by_auth_user_id,
            )
            if audit_record is not None:
                changed_at = audit_record.changed_at

        return CustomerAuthUserRelinkResult(
            auth_user_id=auth_user_id,
            auth_user_email=user.email,
            old_customer_id=old_customer_id,
            old_customer_name=self._customer_name(old_customer_id),
            new_customer_id=customer_id,
            new_customer_name=self._customer_name(customer_id),
            reason=clean_reason
            or "Auth user is already linked to the target customer.",
            changed_by_auth_user_id=changed_by_auth_user_id,
            changed_at=changed_at,
        )

    def _require_customer(self, customer_id: int) -> None:
        if not self.auth_user_repository.customer_exists(customer_id):
            raise CustomerNotFoundError("Customer not found.")

    def _get_user(self, auth_user_id: int) -> AuthUser:
        try:
            return self.auth_user_repository.get_user_by_id(auth_user_id)
        except ValueError as exc:
            raise AuthUserNotFoundError("Auth user not found.") from exc

    def _require_client_user(self, user: AuthUser) -> None:
        if user.role != "client":
            raise NonClientAuthUserLinkError("Only client users can be linked.")

    def _record_link_audit(
        self,
        *,
        action: str,
        auth_user_id: int,
        old_customer_id: int | None,
        new_customer_id: int | None,
        reason: str | None,
        changed_by_auth_user_id: int | None,
    ):
        if not hasattr(self.auth_user_repository, "record_customer_auth_user_link_audit"):
            return None
        return self.auth_user_repository.record_customer_auth_user_link_audit(
            action=action,
            auth_user_id=auth_user_id,
            old_customer_id=old_customer_id,
            new_customer_id=new_customer_id,
            reason=reason,
            changed_by_auth_user_id=changed_by_auth_user_id,
        )

    def _customer_name(self, customer_id: int | None) -> str | None:
        if customer_id is None or not hasattr(
            self.auth_user_repository,
            "get_customer_display_name",
        ):
            return None
        return self.auth_user_repository.get_customer_display_name(customer_id)

    def _clean_reason(self, reason: str | None) -> str:
        return (reason or "").strip()

    def _valid_relink_reason(self, reason: str) -> bool:
        return len(reason) >= 10


__all__ = [
    "AuthUserAlreadyLinkedError",
    "AuthUserCustomerLinkError",
    "AuthUserCustomerLinkService",
    "AuthUserNotLinkedError",
    "AuthUserNotFoundError",
    "CustomerNotFoundError",
    "NonClientAuthUserLinkError",
    "RelinkReasonRequiredError",
]
