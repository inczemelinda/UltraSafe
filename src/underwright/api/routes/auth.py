from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from underwright.api.dependencies import get_auth_service
from underwright.application.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


class ClientRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    phone: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int | None
    email: str
    role: str
    client_id: int | None = None
    full_name: str
    phone: str | None = None
    customer_profile_status: str | None = None
    requires_customer_profile_completion: bool = False


@router.post("/client/register", response_model=AuthResponse)
def register_client(
    body: ClientRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        auth_service.register_client(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            phone=body.phone,
        )
        login_result = auth_service.login(
            email=body.email,
            password=body.password,
            expected_role="client",
        )
        return AuthResponse(**login_result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)})


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        return AuthResponse(**auth_service.login(email=body.email, password=body.password))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"error": str(exc)})


@router.post("/client/login", response_model=AuthResponse)
def login_client(
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        return AuthResponse(
            **auth_service.login(
                email=body.email,
                password=body.password,
                expected_role="client",
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"error": str(exc)})


@router.post("/underwriter/login", response_model=AuthResponse)
def login_underwriter(
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        return AuthResponse(
            **auth_service.login(
                email=body.email,
                password=body.password,
                expected_role="underwriter",
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"error": str(exc)})
