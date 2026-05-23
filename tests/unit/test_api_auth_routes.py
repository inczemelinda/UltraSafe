from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from underwright.api.dependencies import get_auth_service
from underwright.api.main import create_app
from underwright.domain.auth_user import AuthUser


class FakeAuthService:
    def register_client(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        phone: str | None = None,
    ) -> AuthUser:
        return AuthUser(
            id=1,
            email=email,
            password_hash="fake-hash",
            role="client",
            full_name=full_name,
            phone=phone,
            client_id=101,
            is_active=True,
        )

    def login(
        self,
        *,
        email: str,
        password: str,
        expected_role: str | None = None,
    ) -> dict:
        role = expected_role or "client"

        return {
            "access_token": "fake-token",
            "token_type": "bearer",
            "user_id": 1 if role == "client" else 2,
            "email": email,
            "role": role,
            "client_id": 101 if role == "client" else None,
            "full_name": "Ion Popescu" if role == "client" else "Underwriter User",
        }


class AuthRoutesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.fake_auth_service = FakeAuthService()
        self.app.dependency_overrides[get_auth_service] = (
            lambda: self.fake_auth_service
        )
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_client_register_returns_client_token(self) -> None:
        response = self.client.post(
            "/auth/client/register",
            json={
                "email": "client@example.test",
                "password": "secret",
                "full_name": "Ion Popescu",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], "client")
        self.assertEqual(payload["token_type"], "bearer")
        self.assertIn("access_token", payload)
        self.assertIn("user_id", payload)

    def test_client_login_returns_client_token(self) -> None:
        response = self.client.post(
            "/auth/client/login",
            json={"email": "client@example.test", "password": "secret"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], "client")
        self.assertEqual(payload["token_type"], "bearer")
        self.assertIn("access_token", payload)

    def test_underwriter_login_returns_underwriter_token(self) -> None:
        response = self.client.post(
            "/auth/underwriter/login",
            json={"email": "uw@example.test", "password": "secret"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], "underwriter")
        self.assertEqual(payload["client_id"], None)
        self.assertIn("access_token", payload)


if __name__ == "__main__":
    unittest.main()