import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
import unittest

sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))

from underwright.application.modules.contract_drafting_module import (
    ContractDraftingModule,
)
from underwright.application.services.case_context_service import CaseContextFactory
from underwright.application.services.template_service import TemplateService
from underwright.domain.models import Template
from underwright.infrastructure.templates.renderer import PadTemplateRenderer


class DemoFlowSmokeTest(unittest.TestCase):

    def test_render_basic_contract(self) -> None:
        template = (
            "Asigurător: {{parties.insurer.name}} | "
            "Asigurat: {{parties.insured.full_name}}"
        )

        context = {
            "parties": {
                "insurer": {"name": "Allianz"},
                "insured": {"full_name": "Rad Vladut"},
            }
        }

        renderer = PadTemplateRenderer()
        result = renderer.render(template, context)

        self.assertEqual(result, "Asigurător: Allianz | Asigurat: Rad Vladut")

    def test_render_normalizes_markdown_list_markers(self) -> None:
        renderer = PadTemplateRenderer()
        result = renderer.render("Lista:\n* {{item}}\n  * Subitem", {"item": "Risc"})

        self.assertIn("\N{BULLET} Risc", result)
        self.assertIn("  \N{BULLET} Subitem", result)
        self.assertNotIn("* Risc", result)

    def test_render_normalizes_old_coverage_ascii_table(self) -> None:
        renderer = PadTemplateRenderer()
        result = renderer.render(
            (
                "| Categoria     | Suma Asigurată                                         |\r\n"
                "| ------------- | ------------------------------------------------------ |\r\n"
                "| Locuință      | {{amount}} RON |\r\n"
                "| Bunuri mobile | {{amount}} RON |\r\n"
                "| Total         | {{amount}} RON |"
            ),
            {"amount": "350000.0"},
        )

        self.assertIn("Suma asigurată totală este de 350000.0 RON.", result)
        self.assertIn(
            "\N{BULLET} suma asigurată pentru locuință: 350000.0 RON;",
            result,
        )
        self.assertNotIn("| Categoria", result)

    def test_render_real_template(self) -> None:
        template_path = Path("templates/pad_contract_ro_large.txt")
        template = template_path.read_text(encoding="utf-8")
        context_path = Path("docs/contract-template.json")
        context = json.loads(context_path.read_text(encoding="utf-8"))

        renderer = PadTemplateRenderer()
        placeholders = renderer.extract_placeholders(template)
        self.assertFalse(
            any(
                not all(part == part.lower() for part in placeholder.split("."))
                for placeholder in placeholders
            )
        )

        result = renderer.render(template, context)

        self.assertIn("Asigurator Demo SA", result)
        self.assertIn("Ion Popescu", result)
        self.assertIn("PAD-RISK-2026-000145", result)
        self.assertNotIn("{{", result)

    def test_render_property_template_uses_coverage_placeholders(self) -> None:
        template = Path("templates/property_insurance_template.txt").read_text(
            encoding="utf-8"
        )
        context = json.loads(Path("docs/contract-template.json").read_text())

        result = PadTemplateRenderer().render(template, context)

        self.assertIn("Suma asigurată totală este de 350000 RON.", result)
        self.assertIn(
            "\N{BULLET} suma asigurată pentru locuință: 350000 RON;",
            result,
        )
        self.assertIn(
            "\N{BULLET} suma asigurată pentru bunuri mobile: 350000 RON.",
            result,
        )
        self.assertNotIn("{{", result)
        self.assertNotIn("| Categoria", result)

    def test_seed_template_renders_with_current_payload(self) -> None:
        seed_sql = Path("sql/002_seed_demo_data.sql").read_text(encoding="utf-8")
        match = re.search(r"\$\$(.*?)\$\$", seed_sql, flags=re.DOTALL)
        self.assertIsNotNone(match)
        template_content = match.group(1)

        renderer = PadTemplateRenderer()
        placeholders = renderer.extract_placeholders(template_content)
        self.assertFalse(
            any(placeholder != placeholder.lower() for placeholder in placeholders)
        )

        payload = json.loads(Path("docs/contract-template.json").read_text())
        case_context = CaseContextFactory().create_contract_case_context_from_payload(
            payload
        )
        case_context.reference_data.contract_template = Template(
            id=1,
            template_code="PAD_STANDARD_RO",
            name="PAD Standard RO",
            version="1.0",
            document_type="insurance_contract",
            content=template_content,
            created_at=datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
        )
        module = ContractDraftingModule(
            template_service=TemplateService(
                template_repository=None,
                template_renderer=renderer,
            )
        )

        result = module.generate_draft(case_context)
        rendered = case_context.generated_outputs.contract_draft.final_document_text

        self.assertEqual(result.status, "success")
        self.assertIn("PAD-RISK-2026-000145", rendered)
        self.assertIn("Ion Popescu", rendered)
        self.assertNotIn("{{", rendered)
