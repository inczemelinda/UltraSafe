from __future__ import annotations

import unittest
from uuid import UUID

from underwright.application.services.audit_service import AuditService
from underwright.application.services.review_view_service import ReviewViewService
from underwright.domain.contract_case_context import ContractCaseContext

# Tests that ReviewViewService builds a complete ContractReviewView from case context,
# including the new GuidancePanel, ExternalSignalsPanel, and available_user_actions fields.

CASE_ID_1 = UUID("00000000-0000-0000-0000-000000000001")
CASE_ID_2 = UUID("00000000-0000-0000-0000-000000000002")
CONTRACT_ID_1 = UUID("10000000-0000-0000-0000-000000000001")
CONTRACT_ID_2 = UUID("10000000-0000-0000-0000-000000000002")


class ReviewViewServiceTestCase(unittest.TestCase):
    def test_builds_contract_review_view_from_minimal_case_context(self) -> None:
        context = ContractCaseContext(
            case_metadata={
                "case_id": CASE_ID_1,
                "status": "generated",
            },
            source_inputs={"contract_id": CONTRACT_ID_1},
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
                    "parties": {
                        "insured": {
                            "type": "individual",
                            "full_name": "Ion Popescu",
                            "email": "ion@example.test",
                        }
                    },
                    "insured_asset": {
                        "asset_type": "apartment",
                        "usage_type": "residential",
                        "area_sqm": 68,
                    },
                    "pricing": {},
                }
            },
            generated_outputs={
                "contract_draft": {
                    "final_document_text": "Draft contract text",
                    "generation_metadata": {"generation_mode": "hybrid"},
                    "template_used": {"template_version": "1.0"},
                }
            },
        )
        audit_service = AuditService()
        audit_service.workflow_started(
            context,
            {"contract_id": str(CONTRACT_ID_1)},
        )
        audit_service.payload_built(context, {"top_level_sections": ["document_type"]})
        audit_service.draft_generated(context, {"status": "success"})

        view = ReviewViewService().build_contract_review_view(context)

        # existing panels
        self.assertEqual(view.header.case_id, CASE_ID_1)
        self.assertEqual(view.header.contract_id, CONTRACT_ID_1)
        self.assertEqual(view.header.domain, "contracts")
        self.assertEqual(view.header.workflow_status, "generated")
        self.assertEqual(
            view.source_input_panel.customer_summary["full_name"],
            "Ion Popescu",
        )
        self.assertEqual(
            view.source_input_panel.insured_asset_summary["asset_type"],
            "apartment",
        )
        self.assertEqual(
            view.generated_output_panel.draft_contract_text,
            "Draft contract text",
        )
        self.assertEqual(view.template_panel.template_code, "PAD_STANDARD_RO")
        self.assertEqual(
            view.rationale_panel.payload_sections_used,
            [
                "document_type",
                "contract_meta",
                "parties",
                "insured_asset",
                "pricing",
            ],
        )
        self.assertEqual(
            view.rationale_panel.generation_metadata["generation_mode"],
            "hybrid",
        )
        self.assertEqual(
            [entry.event_type for entry in view.audit_summary],
            ["workflow_started", "payload_built", "draft_generated"],
        )
        self.assertEqual(view.warnings_panel.missing_fields, [])

        # new panels added in Task 2
        self.assertIsNotNone(view.guidance_panel)
        self.assertEqual(view.guidance_panel.guidance_items, [])
        self.assertIsNotNone(view.external_signals_panel)
        self.assertEqual(view.external_signals_panel.location_signals, {})
        self.assertIn("approve", view.available_user_actions)
        self.assertIn("reject", view.available_user_actions)

    def test_available_user_actions_are_limited_on_failed_status(self) -> None:
        context = ContractCaseContext(
            case_metadata={"case_id": CASE_ID_2, "status": "failed"},
            source_inputs={"contract_id": CONTRACT_ID_2},
            reference_data={},
            domain_payload={"contract_generation_payload": {}},
            generated_outputs={},
        )

        view = ReviewViewService().build_contract_review_view(context)

        self.assertIn("view_details", view.available_user_actions)
        self.assertIn("resolve_errors", view.available_user_actions)
        self.assertNotIn("approve", view.available_user_actions)
