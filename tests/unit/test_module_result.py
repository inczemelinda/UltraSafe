from __future__ import annotations

import unittest

from pydantic import ValidationError

from underwright.domain.module_result import ModuleResult


class ModuleResultTestCase(unittest.TestCase):
    def test_accepts_valid_status_and_defaults_timestamp(self) -> None:
        result = ModuleResult(
            module_name="ContractPayloadBuilder",
            status="success",
            summary="Payload built.",
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.source_fields_used, [])
        self.assertIsNotNone(result.timestamp)

    def test_rejects_invalid_status(self) -> None:
        with self.assertRaises(ValidationError):
            ModuleResult(
                module_name="ContractPayloadBuilder",
                status="partial",
                summary="Unsupported status.",
            )


if __name__ == "__main__":
    unittest.main()
