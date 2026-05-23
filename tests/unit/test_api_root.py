from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from underwright.api.main import create_app


class RootRouteTestCase(unittest.TestCase):
    # Verifies service root is reachable for basic smoke checks.
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_root_returns_hello_world(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"Hello": "World"})


if __name__ == "__main__":
    unittest.main()
