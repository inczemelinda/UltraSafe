from __future__ import annotations

import unittest
from uuid import UUID

from underwright.application.services.case_context_service import CaseContextFactory
from underwright.domain.case_context_base import BaseCaseContext
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.contract_case_context import ContractCaseContext
from underwright.domain.quote_case_context import QuoteCaseContext

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000001")


def canonical_payload() -> dict:
    return {
        "document_type": "insurance_contract",
        "document_version": "1.0",
        "language": "ro-RO",
        "generation_mode": "hybrid_template_plus_llm",
        "contract_meta": {"contract_id": "PAD-001"},
        "parties": {
            "insured": {"full_name": "Ion Popescu"},
            "insurer": {"name": "Asigurator Demo SA"},
        },
        "insured_asset": {"asset_type": "apartment"},
        "risk_profile": {"overall_risk_level": "medium"},
        "pricing": {"final_premium_ron": 1490.0},
    }


class ClaimCaseContextTestCase(unittest.TestCase):
    def test_claim_case_context_specializes_base_envelope(self) -> None:
        request_id = UUID("20000000-0000-0000-0000-000000000001")

        context = ClaimCaseContext(source_inputs={"request_id": request_id})

        self.assertIsInstance(context, BaseCaseContext)
        self.assertEqual(context.case_metadata.domain, "claims")
        self.assertEqual(context.case_metadata.workflow_name, "claim_ai_review")
        self.assertEqual(context.source_inputs.request_id, request_id)

        for section_name in (
            "case_metadata",
            "source_inputs",
            "reference_data",
            "domain_payload",
            "generated_outputs",
            "checks_and_warnings",
            "guidance",
            "external_signals",
            "review_state",
            "audit_trail",
        ):
            self.assertTrue(hasattr(context, section_name))

    def test_claim_case_context_serializes_cleanly(self) -> None:
        request_id = UUID("20000000-0000-0000-0000-000000000001")

        context = ClaimCaseContext(source_inputs={"request_id": request_id})
        context.domain_payload.claim_intake_payload = {
            "claim_type": "property_damage",
            "description": "Water leak caused ceiling damage",
        }
        context.checks_and_warnings.claim_warnings.append(
            "Missing invoice attachment."
        )

        serialized = context.model_dump(mode="json")

        self.assertEqual(serialized["case_metadata"]["domain"], "claims")
        self.assertEqual(
            serialized["case_metadata"]["workflow_name"],
            "claim_ai_review",
        )
        self.assertEqual(
            serialized["source_inputs"]["request_id"],
            str(request_id),
        )
        self.assertEqual(
            serialized["domain_payload"]["claim_intake_payload"]["claim_type"],
            "property_damage",
        )
        self.assertEqual(
            serialized["checks_and_warnings"]["claim_warnings"],
            ["Missing invoice attachment."],
        )

    def test_claim_case_context_does_not_include_contract_specific_fields(self) -> None:
        context = ClaimCaseContext()

        self.assertFalse(hasattr(context.source_inputs, "contract_id"))
        self.assertFalse(hasattr(context.domain_payload, "contract_generation_payload"))
        self.assertFalse(hasattr(context.generated_outputs, "contract_draft"))

    def test_wraps_existing_contract_generation_payload_unchanged(self) -> None:
        payload = canonical_payload()

        context = CaseContextFactory().create_contract_case_context_from_payload(
            payload
        )

        self.assertIsInstance(context.source_inputs.contract_id, UUID)
        self.assertEqual(context.case_metadata.status, "payload_ready")
        self.assertEqual(
            context.domain_payload.contract_generation_payload,
            payload,
        )
        self.assertEqual(
            context.domain_payload.contract_generation_payload["contract_meta"],
            payload["contract_meta"],
        )
        self.assertEqual(
            context.domain_payload.contract_generation_payload["parties"],
            payload["parties"],
        )
        self.assertEqual(
            context.domain_payload.contract_generation_payload["insured_asset"],
            payload["insured_asset"],
        )
        self.assertEqual(
            context.domain_payload.contract_generation_payload["risk_profile"],
            payload["risk_profile"],
        )
        self.assertEqual(
            context.domain_payload.contract_generation_payload["pricing"],
            payload["pricing"],
        )
        self.assertEqual(
            [entry.event_type for entry in context.audit_trail],
            ["case_context_created", "contract_payload_attached"],
        )

class QuoteCaseContextTestCase(unittest.TestCase):
    def test_quote_case_context_specializes_base_envelope(self) -> None:
        request_id = UUID("60000000-0000-0000-0000-000000000001")

        context = QuoteCaseContext(source_inputs={"request_id": request_id})

        self.assertIsInstance(context, BaseCaseContext)
        self.assertEqual(context.case_metadata.domain, "quotes")
        self.assertEqual(context.case_metadata.workflow_name, "quote_generation")
        self.assertEqual(context.source_inputs.request_id, request_id)

        for section_name in (
            "case_metadata",
            "source_inputs",
            "reference_data",
            "domain_payload",
            "generated_outputs",
            "checks_and_warnings",
            "guidance",
            "external_signals",
            "review_state",
            "audit_trail",
        ):
            self.assertTrue(hasattr(context, section_name))

    def test_quote_case_context_serializes_cleanly(self) -> None:
        request_id = UUID("60000000-0000-0000-0000-000000000001")

        context = QuoteCaseContext(source_inputs={"request_id": request_id})
        context.domain_payload.rule_outcomes = {
            "mandatory_data_complete": True,
            "requires_underwriter": False,
        }
        context.generated_outputs.pricing_outputs.final_premium_ron = 1200.0
        context.generated_outputs.ai_insights = {
            "risk_summary": "Low risk residential quote."
        }
        context.review_state.quote_review_view = {
            "status": "quote_ready",
            "available_actions": ["approve", "disapprove"],
        }

        serialized = context.model_dump(mode="json")

        self.assertEqual(serialized["case_metadata"]["domain"], "quotes")
        self.assertEqual(
            serialized["case_metadata"]["workflow_name"],
            "quote_generation",
        )
        self.assertEqual(
            serialized["source_inputs"]["request_id"],
            str(request_id),
        )
        self.assertTrue(
            serialized["domain_payload"]["rule_outcomes"][
                "mandatory_data_complete"
            ]
        )
        self.assertEqual(
            serialized["generated_outputs"]["pricing_outputs"][
                "final_premium_ron"
            ],
            1200.0,
        )
        self.assertEqual(
            serialized["generated_outputs"]["ai_insights"]["risk_summary"],
            "Low risk residential quote.",
        )
        self.assertEqual(
            serialized["review_state"]["quote_review_view"]["status"],
            "quote_ready",
        )

    def test_quote_case_context_does_not_change_contract_context_behavior(self) -> None:
        contract_context = ContractCaseContext()

        self.assertEqual(contract_context.case_metadata.domain, "contracts")
        self.assertEqual(
            contract_context.case_metadata.workflow_name,
            "contract_drafting",
        )
        self.assertTrue(hasattr(contract_context.domain_payload, "contract_generation_payload"))
        self.assertFalse(hasattr(contract_context.domain_payload, "quote_intake_payload"))
