from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
import os

import bcrypt
import jwt

from underwright.domain.auth_user import AuthUser
from underwright.application.services.customer_profile_service import (
    CustomerProfileNotFoundError,
    CustomerProfileService,
)


class AuthService:
    def __init__(self, auth_user_repository, customer_profile_repository=None) -> None:
        self.auth_user_repository = auth_user_repository
        self.customer_profile_service = (
            CustomerProfileService(customer_profile_repository, auth_user_repository)
            if customer_profile_repository is not None
            else None
        )

    def register_client(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        phone: str | None = None,
    ) -> AuthUser:
        if self.auth_user_repository.email_exists(email):
            raise ValueError("Email already exists")

        password_hash = self._hash_password(password)

        user = AuthUser(
            email=email,
            password_hash=password_hash,
            role="client",
            full_name=full_name,
            phone=phone,
            client_id=None,
            is_active=True,
        )

        return self.auth_user_repository.create_user(user)

    def login(
        self,
        *,
        email: str,
        password: str,
        expected_role: Literal["client", "employee", "underwriter", "admin"] | None = None,
    ) -> dict[str, Any]:
        user = self.auth_user_repository.get_user_by_email(email)

        if not user.is_active:
            raise ValueError("User is inactive")

        if expected_role is not None and user.role != expected_role:
            raise ValueError("Invalid role for this login")

        if not self._verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")

        token = self._create_access_token(user)

        profile_status = self._customer_profile_status(user)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "client_id": user.client_id,
            "full_name": user.full_name,
            "phone": user.phone,
            "customer_profile_status": profile_status,
            "requires_customer_profile_completion": (
                user.role == "client" and profile_status != "complete"
            ),
        }

    def get_user_from_access_token(self, token: str) -> AuthUser:
        secret = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")
        algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
        try:
            payload = jwt.decode(token, secret, algorithms=[algorithm])
        except jwt.PyJWTError as exc:
            raise ValueError("Invalid access token") from exc

        user_id = payload.get("sub")
        if user_id is None:
            raise ValueError("Invalid access token")

        try:
            user = self.auth_user_repository.get_user_by_id(int(user_id))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid access token") from exc

        if not user.is_active:
            raise ValueError("User is inactive")
        return user

    def _hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    def _create_access_token(self, user: AuthUser) -> str:
        secret = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")
        algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
        expires_minutes = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

        now = datetime.now(timezone.utc)

        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "client_id": user.client_id,
            "iat": now,
            "exp": now + timedelta(minutes=expires_minutes),
        }

        return jwt.encode(payload, secret, algorithm=algorithm)

    def _customer_profile_status(self, user: AuthUser) -> str | None:
        if user.role != "client":
            return None
        if user.client_id is None:
            return "pending_customer_link"
        if self.customer_profile_service is None:
            return "complete"
        try:
            return self.customer_profile_service.profile_status_for_user(user)
        except CustomerProfileNotFoundError:
            return "incomplete"
