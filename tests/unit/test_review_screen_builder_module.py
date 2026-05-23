from __future__ import annotations

import unittest
from uuid import UUID

from underwright.application.modules.review_screen_builder_module import (
    ReviewScreenBuilderModule,
)
from underwright.domain.contract_case_context import ContractCaseContext

# This test validates that the review module builds and stores the review view.

CASE_ID = UUID("00000000-0000-0000-0000-000000000001")
CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000001")


class ReviewScreenBuilderModuleTestCase(unittest.TestCase):
    def test_build_writes_review_view_and_returns_module_result(self) -> None:
        context = ContractCaseContext(
            case_metadata={"case_id": CASE_ID, "status": "generated"},
            source_inputs={"contract_id": CONTRACT_ID},
            reference_data={
                "contract_template": {
                    "id": 7,
                    "template_code": "PAD_STANDARD_RO",
                    "name": "PAD Standard RO",
                    "version": "1.0",
                }
            },
            domain_payload={
                "contract_generation_payload": {
                    "document_type": "insurance_contract",
                    "contract_meta": {"contract_id": "PAD-001"},
                    "parties": {"insured": {"full_name": "Ion Popescu"}},
                    "insured_asset": {"asset_type": "apartment"},
                }
            },
            generated_outputs={
                "contract_draft": {
                    "final_document_text": "Draft contract text",
                    "generation_metadata": {"generation_mode": "hybrid"},
                }
            },
        )

        result = ReviewScreenBuilderModule().build(context)

        self.assertEqual(result.module_name, "ReviewScreenBuilderModule")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.summary, "Built contract review screen view.")
        self.assertIsNotNone(context.review_state.contract_review_view)
        self.assertEqual(
            context.review_state.contract_review_view.header.case_id,
            CASE_ID,
        )


if __name__ == "__main__":
    unittest.main()
