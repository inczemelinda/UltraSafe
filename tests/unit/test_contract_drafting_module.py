from __future__ import annotations

from datetime import datetime, timezone
import unittest
from uuid import UUID

from underwright.application.modules.contract_drafting_module import (
    ContractDraftingModule,
)
from underwright.application.services.audit_service import AuditService
from underwright.application.services.case_context_service import CaseContextFactory
from underwright.application.services.template_service import TemplateService
from underwright.domain.models import Template
from underwright.infrastructure.templates.renderer import PadTemplateRenderer

CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000001")


class UnusedTemplateRepository:
    def get_active_template(self, template_code: str) -> Template:
        raise AssertionError("Template repository should not be used in this test.")


class CapturingSupplementaryTextGenerator:
    def __init__(self) -> None:
        self.context = None
        self.rendered_template = None

    def generate(self, context, rendered_template: str) -> str:
        self.context = context
        self.rendered_template = rendered_template
        return "Rezumat suplimentar de risc."


class ContractDraftingModuleTestCase(unittest.TestCase):
    def test_generates_draft_and_passes_rendered_template_to_generator(self) -> None:
        generator = CapturingSupplementaryTextGenerator()
        template_service = TemplateService(
            template_repository=UnusedTemplateRepository(),
            template_renderer=PadTemplateRenderer(),
        )
        module = ContractDraftingModule(
            template_service=template_service,
            supplementary_text_generator=generator,
            audit_service=AuditService(),
        )
        template = Template(
            id=10,
            template_code="PAD_STANDARD_RO",
            name="PAD Standard RO",
            version="1.0",
            document_type="insurance_contract",
            content=(
                "Poliță: {{contract_meta.contract_id}}\n"
                "{{ supplementary_text }}"
            ),
            created_at=datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
        )
        payload = {
            "document_type": "insurance_contract",
            "generation_mode": "hybrid_template_plus_llm",
            "contract_meta": {"contract_id": "PAD-001"},
            "parties": {"insured": {"full_name": "Ion Popescu"}},
            "insured_asset": {"asset_type": "apartment"},
            "risk_profile": {
                "factors": [
                    {
                        "contract_impact": {
                            "clause_tags": ["flood_specific"],
                        }
                    }
                ]
            },
            "pricing": {"adjustments": [{"source": "FLOOD_EXPOSURE"}]},
        }
        case_context = CaseContextFactory().create_contract_case_context_from_payload(
            payload
        )
        case_context.reference_data.contract_template = template

        result = module.generate_draft(case_context)
        draft_output = case_context.generated_outputs.contract_draft

        self.assertEqual(result.status, "success")
        self.assertEqual(result.module_name, "ContractDraftingModule")
        self.assertEqual(generator.context, payload)
        self.assertEqual(generator.rendered_template, "Poliță: PAD-001\n")
        self.assertEqual(
            draft_output.final_document_text,
            "Poliță: PAD-001\nRezumat suplimentar de risc.",
        )
        self.assertEqual(draft_output.template_used["template_version"], "1.0")
        self.assertEqual(draft_output.mapped_input_fields["contract_id"], "PAD-001")
        self.assertIsNotNone(draft_output.llm_drafting_summary)
        self.assertTrue(
            draft_output.generation_metadata["rendered_template_provided_to_generator"]
        )
        self.assertIn(
            "draft_generated",
            [entry.event_type for entry in case_context.audit_trail],
        )

    def test_returns_failed_result_when_payload_is_missing(self) -> None:
        template_service = TemplateService(
            template_repository=UnusedTemplateRepository(),
            template_renderer=PadTemplateRenderer(),
        )
        module = ContractDraftingModule(template_service=template_service)
        case_context = (
            CaseContextFactory().create_contract_case_context_from_contract_id(
                CONTRACT_ID
            )
        )

        result = module.generate_draft(case_context)

        self.assertEqual(result.status, "failed")
        self.assertIn("contract_generation_payload", result.summary)

    def test_returns_failed_result_when_template_is_missing(self) -> None:
        template_service = TemplateService(
            template_repository=UnusedTemplateRepository(),
            template_renderer=PadTemplateRenderer(),
        )
        module = ContractDraftingModule(template_service=template_service)
        case_context = CaseContextFactory().create_contract_case_context_from_payload(
            {"contract_meta": {"contract_id": "PAD-001"}}
        )

        result = module.generate_draft(case_context)

        self.assertEqual(result.status, "failed")
        self.assertIn("contract_template", result.summary)
