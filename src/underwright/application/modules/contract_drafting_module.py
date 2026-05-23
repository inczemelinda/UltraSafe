from __future__ import annotations

import re
from typing import Any

from underwright.application.ports import SupplementaryTextGenerator
from underwright.application.services.audit_service import AuditService
from underwright.application.services.template_service import TemplateService
from underwright.domain.contract_case_context import (
    ContractCaseContext,
    ContractDraftOutput,
)
from underwright.domain.module_result import ModuleResult
from underwright.domain.models import Template


class ContractDraftingModule:
    """Generates contract drafts by reading and writing ContractCaseContext."""

    _SUPPLEMENTARY_TEXT_PATTERN = re.compile(r"{{\s*supplementary_text\s*}}")

    def __init__(
        self,
        template_service: TemplateService,
        supplementary_text_generator: SupplementaryTextGenerator | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self.template_service = template_service
        self.supplementary_text_generator = supplementary_text_generator
        self.audit_service = audit_service or AuditService()

    def generate_draft(
        self,
        case_context: ContractCaseContext,
    ) -> ModuleResult:
        payload = case_context.domain_payload.contract_generation_payload
        if not payload:
            return ModuleResult(
                module_name="ContractDraftingModule",
                status="failed",
                summary=(
                    "domain_payload.contract_generation_payload is required "
                    "before contract drafting."
                ),
            )

        template = case_context.reference_data.contract_template
        if template is None:
            return ModuleResult(
                module_name="ContractDraftingModule",
                status="failed",
                summary=(
                    "reference_data.contract_template is required before "
                    "contract drafting."
                ),
            )

        template_content = self._get_template_content(template)
        template_metadata = self._get_template_metadata(template)
        has_supplementary_placeholder = bool(
            self._SUPPLEMENTARY_TEXT_PATTERN.search(template_content)
        )

        draft_shell_template = self._with_supplementary_text(template_content, "")
        rendered_template = self.template_service.render(
            draft_shell_template,
            payload,
        )

        supplementary_text = ""
        if self.supplementary_text_generator is not None:
            # The generator receives the populated draft shell so its response
            # can be grounded in the exact contract data already inserted.
            supplementary_text = self.supplementary_text_generator.generate(
                payload,
                rendered_template,
            )

        final_template = self._with_supplementary_text(
            template_content,
            supplementary_text,
        )
        final_document_text = self.template_service.render(final_template, payload)

        generation_metadata = self._generation_metadata(
            payload=payload,
            supplementary_text=supplementary_text,
            has_supplementary_placeholder=has_supplementary_placeholder,
        )
        draft_output = ContractDraftOutput(
            draft_contract=final_document_text,
            rendered_template_text=rendered_template,
            final_document_text=final_document_text,
            template_used=template_metadata,
            template_version=template_metadata.get("template_version"),
            mapped_input_fields=self._mapped_input_fields(payload),
            unmapped_or_missing_fields=[],
            generation_rationale=(
                "Rendered the canonical Underwright contract generation payload "
                "through the active contract template."
            ),
            llm_drafting_summary=self._llm_drafting_summary(
                payload=payload,
                template_metadata=template_metadata,
                supplementary_text=supplementary_text,
            ),
            generation_metadata=generation_metadata,
        )
        case_context.generated_outputs.contract_draft = draft_output

        self.audit_service.template_rendered(case_context, template_metadata)
        self.audit_service.draft_generated(case_context, generation_metadata)
        return ModuleResult(
            module_name="ContractDraftingModule",
            status="success",
            summary="Generated contract draft.",
            source_fields_used=[
                "domain_payload.contract_generation_payload",
                "reference_data.contract_template",
            ],
        )

    def _get_template_content(self, template: Template | dict[str, Any]) -> str:
        if isinstance(template, dict):
            return str(template.get("content", ""))
        return template.content

    def _get_template_metadata(
        self,
        template: Template | dict[str, Any],
    ) -> dict[str, Any]:
        if isinstance(template, dict):
            return {
                "template_id": template.get("id") or template.get("template_id"),
                "template_code": template.get("template_code"),
                "template_name": template.get("name")
                or template.get("template_name"),
                "template_version": template.get("version")
                or template.get("template_version"),
            }
        return self.template_service.get_template_metadata(template)

    def _mapped_input_fields(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "payload_path": (
                "contract_case_context.domain_payload."
                "contract_generation_payload"
            ),
            "top_level_sections": list(payload.keys()),
            "contract_id": payload.get("contract_meta", {}).get("contract_id"),
            "document_type": payload.get("document_type"),
        }

    def _generation_metadata(
        self,
        *,
        payload: dict[str, Any],
        supplementary_text: str,
        has_supplementary_placeholder: bool,
    ) -> dict[str, Any]:
        return {
            "generation_mode": payload.get("generation_mode"),
            "rendered_template_provided_to_generator": (
                self.supplementary_text_generator is not None
            ),
            "supplementary_text_generator_present": (
                self.supplementary_text_generator is not None
            ),
            "supplementary_text_generated": bool(supplementary_text),
            "supplementary_text_placeholder_present": (
                has_supplementary_placeholder
            ),
        }

    def _llm_drafting_summary(
        self,
        *,
        payload: dict[str, Any],
        template_metadata: dict[str, Any],
        supplementary_text: str,
    ) -> str:
        risk_factors = payload.get("risk_profile", {}).get("factors", [])
        clause_tags = [
            tag
            for factor in risk_factors
            for tag in factor.get("contract_impact", {}).get("clause_tags", [])
        ]
        pricing_adjustments = payload.get("pricing", {}).get("adjustments", [])
        insured = payload.get("parties", {}).get("insured", {})
        asset = payload.get("insured_asset", {})

        summary_parts = [
            (
                "Template "
                f"{template_metadata.get('template_code') or 'unknown'}"
                f" v{template_metadata.get('template_version') or 'unknown'}"
                " was applied."
            ),
            (
                "Inserted insured party "
                f"{insured.get('full_name') or 'unknown'} and asset "
                f"{asset.get('asset_type') or 'unknown'} details."
            ),
            f"Applied {len(risk_factors)} risk factor(s).",
            f"Applied {len(clause_tags)} clause tag(s).",
            f"Applied {len(pricing_adjustments)} pricing adjustment(s).",
        ]
        if supplementary_text:
            summary_parts.append("Generated supplementary drafting text for review.")
        else:
            summary_parts.append("No supplementary drafting text was generated.")

        return " ".join(summary_parts)

    def _with_supplementary_text(self, template_content: str, text: str) -> str:
        return self._SUPPLEMENTARY_TEXT_PATTERN.sub(text, template_content)


__all__ = ["ContractDraftingModule"]
