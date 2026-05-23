from __future__ import annotations

import re
from typing import Any

from underwright.application.ports import SupplementaryTextGenerator
from underwright.application.services.audit_service import AuditService
from underwright.application.services.template_service import TemplateService
from underwright.domain.module_result import ModuleResult
from underwright.domain.models import Template
from underwright.domain.quote_case_context import QuoteCaseContext, QuoteDocumentOutput


class QuoteDocumentGenerationModule:
    """Generates unsigned quote documents from quote payloads and templates."""

    module_name = "QuoteDocumentGenerationModule"
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

    def generate_document(
        self,
        case_context: QuoteCaseContext,
    ) -> ModuleResult:
        payload = case_context.domain_payload.quote_generation_payload
        if not payload:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary=(
                    "domain_payload.quote_generation_payload is required before "
                    "quote document generation."
                ),
            )

        template = case_context.reference_data.quote_template
        if template is None:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary=(
                    "reference_data.quote_template is required before quote "
                    "document generation."
                ),
            )

        template_content = self._get_template_content(template)
        template_metadata = self._get_template_metadata(template)
        has_supplementary_placeholder = bool(
            self._SUPPLEMENTARY_TEXT_PATTERN.search(template_content)
        )

        draft_shell_template = self._with_supplementary_text(template_content, "")
        try:
            rendered_template = self.template_service.render(
                draft_shell_template,
                payload,
            )
        except (KeyError, ValueError) as exc:
            return self._render_failed(case_context, exc)

        supplementary_text = ""
        if self.supplementary_text_generator is not None:
            supplementary_text = self.supplementary_text_generator.generate(
                payload,
                rendered_template,
            )

        final_template = self._with_supplementary_text(
            template_content,
            supplementary_text,
        )
        try:
            final_document_text = self.template_service.render(final_template, payload)
        except (KeyError, ValueError) as exc:
            return self._render_failed(case_context, exc)
        generation_metadata = {
            "generation_mode": payload.get("generation_mode"),
            "supplementary_text_generator_present": (
                self.supplementary_text_generator is not None
            ),
            "supplementary_text_generated": bool(supplementary_text),
            "supplementary_text_placeholder_present": (
                has_supplementary_placeholder
            ),
        }

        case_context.generated_outputs.quote_document = QuoteDocumentOutput(
            draft_quote=final_document_text,
            rendered_template_text=rendered_template,
            final_document_text=final_document_text,
            template_used=template_metadata,
            template_version=template_metadata.get("template_version"),
            mapped_input_fields={
                "payload_path": (
                    "quote_case_context.domain_payload.quote_generation_payload"
                ),
                "top_level_sections": list(payload.keys()),
                "quote_id": payload.get("quote_meta", {}).get("quote_id"),
                "document_type": payload.get("document_type"),
            },
            generation_rationale=(
                "Rendered the quote generation payload through the active "
                "quote template."
            ),
            llm_drafting_summary=self._llm_drafting_summary(
                payload=payload,
                template_metadata=template_metadata,
                supplementary_text=supplementary_text,
            ),
            generation_metadata=generation_metadata,
        )
        self.audit_service.quote_document_generated(
            case_context,
            generation_metadata,
        )
        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary="Generated unsigned quote document.",
            source_fields_used=[
                "domain_payload.quote_generation_payload",
                "reference_data.quote_template",
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

    def _llm_drafting_summary(
        self,
        *,
        payload: dict[str, Any],
        template_metadata: dict[str, Any],
        supplementary_text: str,
    ) -> str:
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
                "Inserted quote party "
                f"{insured.get('full_name') or 'unknown'} and asset "
                f"{asset.get('asset_type') or 'unknown'} details."
            ),
        ]
        if supplementary_text:
            summary_parts.append("Generated supplementary quote text.")
        else:
            summary_parts.append("No supplementary quote text was generated.")
        return " ".join(summary_parts)

    def _with_supplementary_text(self, template_content: str, text: str) -> str:
        return self._SUPPLEMENTARY_TEXT_PATTERN.sub(text, template_content)

    def _render_failed(
        self,
        case_context: QuoteCaseContext,
        exc: KeyError | ValueError,
    ) -> ModuleResult:
        case_context.generated_outputs.quote_document.unmapped_or_missing_fields.append(
            str(exc)
        )
        return ModuleResult(
            module_name=self.module_name,
            status="failed",
            summary=f"Quote template rendering failed: {exc}",
            source_fields_used=[
                "domain_payload.quote_generation_payload",
                "reference_data.quote_template",
            ],
        )


__all__ = ["QuoteDocumentGenerationModule"]
