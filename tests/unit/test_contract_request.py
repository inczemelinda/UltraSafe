from __future__ import annotations

import unittest

from underwright.domain.contract_request import ContractRequest


class ContractRequestTestCase(unittest.TestCase):
    def test_creates_valid_request_with_defaults(self) -> None:
        request = ContractRequest(
            request_id=101,
            client_id=202,
        )

        self.assertEqual(request.request_id, 101)
        self.assertEqual(request.client_id, 202)
        self.assertEqual(request.request_status, "created")
        self.assertEqual(request.client_data, {})
        self.assertEqual(request.insured_data, {})
        self.assertEqual(request.request_details, {})
        self.assertEqual(request.attachments, {})
        self.assertIsNotNone(request.created_at)


if __name__ == "__main__":
    unittest.main()