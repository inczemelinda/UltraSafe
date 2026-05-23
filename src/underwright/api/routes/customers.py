from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from underwright.api.dependencies import (
    get_auth_user_customer_link_service,
    get_current_employee_user,
    get_customer_profile_service,
)
from underwright.application.services.auth_user_customer_link_service import (
    AuthUserAlreadyLinkedError,
    AuthUserCustomerLinkService,
    AuthUserNotLinkedError,
    AuthUserNotFoundError,
    CustomerNotFoundError,
    NonClientAuthUserLinkError,
    RelinkReasonRequiredError,
)
from underwright.application.services.customer_profile_service import (
    CustomerProfileNotFoundError,
    CustomerProfileService,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.auth_user_admin import CustomerAuthUserRelinkResult
from underwright.domain.customer_profile import CustomerProfileReadModel

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    dependencies=[Depends(get_current_employee_user)],
)


class CustomerAuthUserResponse(BaseModel):
    user_id: int | None
    email: str
    role: str
    full_name: str
    client_id: int | None
    customer_profile_status: str | None = None
    requires_customer_profile_completion: bool = False


class CustomerAuthUserRelinkRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


@router.get("", response_model=list[CustomerProfileReadModel])
def list_customer_profiles(
    service: CustomerProfileService = Depends(get_customer_profile_service),
) -> list[CustomerProfileReadModel]:
    return service.list_customer_profiles()


@router.get("/{customer_id}/profile", response_model=CustomerProfileReadModel)
def get_customer_profile(
    customer_id: int,
    service: CustomerProfileService = Depends(get_customer_profile_service),
) -> CustomerProfileReadModel | JSONResponse:
    try:
        return service.get_customer_profile(customer_id)
    except CustomerProfileNotFoundError as exc:
        return _not_found("CUSTOMER_NOT_FOUND", "Customer not found.", str(exc))


@router.get("/{customer_id}/auth-users", response_model=list[CustomerAuthUserResponse])
def list_customer_auth_users(
    customer_id: int,
    service: AuthUserCustomerLinkService = Depends(
        get_auth_user_customer_link_service
    ),
    profile_service: CustomerProfileService = Depends(get_customer_profile_service),
) -> list[CustomerAuthUserResponse] | JSONResponse:
    try:
        return [
            _auth_user_response(user, profile_service)
            for user in service.list_customer_auth_users(customer_id)
        ]
    except CustomerNotFoundError as exc:
        return _not_found("CUSTOMER_NOT_FOUND", "Customer not found.", str(exc))


@router.post(
    "/{customer_id}/auth-users/{auth_user_id}/link",
    response_model=CustomerAuthUserResponse,
)
def link_customer_auth_user(
    customer_id: int,
    auth_user_id: int,
    current_user: AuthUser = Depends(get_current_employee_user),
    service: AuthUserCustomerLinkService = Depends(
        get_auth_user_customer_link_service
    ),
    profile_service: CustomerProfileService = Depends(get_customer_profile_service),
) -> CustomerAuthUserResponse | JSONResponse:
    try:
        return _auth_user_response(
            service.link_client_user(
                auth_user_id=auth_user_id,
                customer_id=customer_id,
                updated_by_auth_user_id=current_user.id,
            ),
            profile_service,
        )
    except CustomerNotFoundError as exc:
        return _not_found("CUSTOMER_NOT_FOUND", "Customer not found.", str(exc))
    except AuthUserNotFoundError as exc:
        return _not_found("AUTH_USER_NOT_FOUND", "Auth user not found.", str(exc))
    except NonClientAuthUserLinkError as exc:
        return _bad_request("AUTH_USER_NOT_CLIENT", "Only client users can be linked.", str(exc))
    except AuthUserAlreadyLinkedError as exc:
        return _conflict(
            "AUTH_USER_ALREADY_LINKED",
            "Auth user is already linked to another customer.",
            str(exc),
        )


@router.delete(
    "/{customer_id}/auth-users/{auth_user_id}/link",
    response_model=CustomerAuthUserResponse,
)
def unlink_customer_auth_user(
    customer_id: int,
    auth_user_id: int,
    current_user: AuthUser = Depends(get_current_employee_user),
    service: AuthUserCustomerLinkService = Depends(
        get_auth_user_customer_link_service
    ),
    profile_service: CustomerProfileService = Depends(get_customer_profile_service),
) -> CustomerAuthUserResponse | JSONResponse:
    try:
        return _auth_user_response(
            service.unlink_client_user(
                auth_user_id=auth_user_id,
                customer_id=customer_id,
                updated_by_auth_user_id=current_user.id,
            ),
            profile_service,
        )
    except CustomerNotFoundError as exc:
        return _not_found("CUSTOMER_NOT_FOUND", "Customer not found.", str(exc))
    except AuthUserNotFoundError as exc:
        return _not_found("AUTH_USER_NOT_FOUND", "Auth user not found.", str(exc))
    except NonClientAuthUserLinkError as exc:
        return _bad_request("AUTH_USER_NOT_CLIENT", "Only client users can be linked.", str(exc))


@router.post(
    "/{customer_id}/auth-users/{auth_user_id}/relink",
    response_model=CustomerAuthUserRelinkResult,
)
def relink_customer_auth_user(
    customer_id: int,
    auth_user_id: int,
    body: CustomerAuthUserRelinkRequest,
    current_user: AuthUser = Depends(get_current_employee_user),
    service: AuthUserCustomerLinkService = Depends(
        get_auth_user_customer_link_service
    ),
) -> CustomerAuthUserRelinkResult | JSONResponse:
    try:
        return service.relink_client_user(
            auth_user_id=auth_user_id,
            customer_id=customer_id,
            reason=body.reason,
            changed_by_auth_user_id=current_user.id,
        )
    except CustomerNotFoundError as exc:
        return _not_found("CUSTOMER_NOT_FOUND", "Customer not found.", str(exc))
    except AuthUserNotFoundError as exc:
        return _not_found("AUTH_USER_NOT_FOUND", "Auth user not found.", str(exc))
    except NonClientAuthUserLinkError as exc:
        return _bad_request("AUTH_USER_NOT_CLIENT", "Only client users can be linked.", str(exc))
    except AuthUserNotLinkedError as exc:
        return _bad_request("AUTH_USER_NOT_LINKED", "Auth user is not linked.", str(exc))
    except RelinkReasonRequiredError as exc:
        return _bad_request(
            "RELINK_REASON_REQUIRED",
            "A relink reason of at least 10 characters is required.",
            str(exc),
        )


def _auth_user_response(
    user: AuthUser,
    profile_service: CustomerProfileService,
) -> CustomerAuthUserResponse:
    profile_status = _auth_user_profile_status(user, profile_service)
    return CustomerAuthUserResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        client_id=user.client_id,
        customer_profile_status=profile_status,
        requires_customer_profile_completion=user.role == "client"
        and profile_status != "complete",
    )


def _auth_user_profile_status(
    user: AuthUser,
    profile_service: CustomerProfileService,
) -> str | None:
    if user.role != "client":
        return None
    try:
        return profile_service.profile_status_for_user(user)
    except CustomerProfileNotFoundError:
        return "incomplete" if user.client_id is not None else "pending_customer_link"


def _not_found(code: str, message: str, details: str | None = None) -> JSONResponse:
    return _error_response(404, code, message, details)


def _bad_request(code: str, message: str, details: str | None = None) -> JSONResponse:
    return _error_response(400, code, message, details)


def _conflict(code: str, message: str, details: str | None = None) -> JSONResponse:
    return _error_response(409, code, message, details)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: str | None = None,
) -> JSONResponse:
    content: dict[str, object] = {"error": {"code": code, "message": message}}
    if details:
        content["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=content)


__all__ = ["router"]
