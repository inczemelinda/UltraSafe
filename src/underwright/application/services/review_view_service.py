from __future__ import annotations

from datetime import datetime
from typing import Any

from underwright.domain.contract_case_context import ContractCaseContext
from underwright.domain.models import GeneratedDocument
from underwright.domain.review_models import (
    AuditSummaryItem,
    ContractReviewView,
    ExternalSignalsPanel,
    GeneratedOutputPanel,
    GuidancePanel,
    RationalePanel,
    ReviewHeader,
    SourceInputPanel,
    TemplatePanel,
    WarningsPanel,
)


class ReviewViewService:
    """Builds UI-ready review views from case context state."""

    def build_contract_review_view(
        self,
        case_context: ContractCaseContext,
    ) -> ContractReviewView:
        payload = case_context.domain_payload.contract_generation_payload
        contract_source = case_context.reference_data.contract_source
        template = case_context.reference_data.contract_template
        generated_output = case_context.generated_outputs.contract_draft
        output_panel = self._build_generated_output_panel(generated_output)

        generation_metadata = self._generation_metadata(generated_output)
        template_panel = self._build_template_panel(template, generated_output)
        view = ContractReviewView(
            header=ReviewHeader(
                # UUIDs identify the workflow and contract.
                case_id=case_context.case_metadata.case_id,
                contract_id=case_context.source_inputs.contract_id,
                domain=case_context.case_metadata.domain,
                workflow_status=case_context.case_metadata.status,
            ),
            source_input_panel=SourceInputPanel(
                # Review screens display the contract UUID.
                contract_id=case_context.source_inputs.contract_id,
                customer_summary=self._customer_summary(contract_source, payload),
                insured_asset_summary=self._insured_asset_summary(
                    contract_source,
                    payload,
                ),
            ),
            generated_output_panel=output_panel,
            template_panel=template_panel,
            warnings_panel=self._build_warnings_panel(
                payload=payload,
                output_panel=output_panel,
                template_panel=template_panel,
            ),
            rationale_panel=RationalePanel(
                payload_sections_used=list(payload.keys()),
                generation_metadata=generation_metadata,
            ),
            guidance_panel=GuidancePanel(),
            external_signals_panel=ExternalSignalsPanel(),
            audit_summary=[
                self._audit_summary_item(entry) for entry in case_context.audit_trail
            ],
            available_user_actions=self._available_user_actions(case_context),
        )

        return view

    def _customer_summary(
        self,
        contract_source: Any,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        customer = self._get(contract_source, "customer")
        if customer is not None:
            return {
                "type": self._get(customer, "type"),
                "full_name": self._get(customer, "full_name"),
                "email": self._get(customer, "email"),
                "phone": self._get(customer, "phone"),
            }

        insured = payload.get("parties", {}).get("insured")
        if isinstance(insured, dict):
            return {
                "type": insured.get("type"),
                "full_name": insured.get("full_name"),
                "email": insured.get("email"),
                "phone": insured.get("phone"),
                "address": insured.get("address"),
            }

        return None

    def _insured_asset_summary(
        self,
        contract_source: Any,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        insured_asset = self._get(contract_source, "insured_asset")
        insured_asset_address = self._get(contract_source, "insured_asset_address")
        if insured_asset is not None:
            return {
                "asset_type": self._get(insured_asset, "asset_type"),
                "usage_type": self._get(insured_asset, "usage_type"),
                "construction_type": self._get(insured_asset, "construction_type"),
                "area_sqm": self._get(insured_asset, "area_sqm"),
                "declared_value": self._get(insured_asset, "declared_value"),
                "address": self._get(insured_asset_address, "full_text"),
            }

        payload_asset = payload.get("insured_asset")
        if isinstance(payload_asset, dict):
            return {
                "asset_type": payload_asset.get("asset_type"),
                "usage_type": payload_asset.get("usage_type"),
                "construction_type": payload_asset.get("construction_type"),
                "area_sqm": payload_asset.get("area_sqm"),
                "declared_value": payload_asset.get("declared_value"),
                "address": payload_asset.get("address"),
            }

        return None

    def _build_generated_output_panel(
        self,
        generated_output: Any,
    ) -> GeneratedOutputPanel:
        if isinstance(generated_output, str):
            return GeneratedOutputPanel(draft_contract_text=generated_output)

        if isinstance(generated_output, GeneratedDocument):
            return GeneratedOutputPanel(
                draft_contract_text=generated_output.rendered_text,
                generated_document_reference={
                    "id": generated_output.id,
                    "contract_id": generated_output.contract_id,
                    "template_id": generated_output.template_id,
                    "file_url": generated_output.file_url,
                },
                status=generated_output.generation_status,
            )

        if isinstance(generated_output, dict):
            return GeneratedOutputPanel(
                draft_contract_text=generated_output.get("draft_text")
                or generated_output.get("rendered_text")
                or generated_output.get("final_document_text")
                or generated_output.get("draft_contract"),
                generated_document_reference=generated_output.get(
                    "generated_document_reference"
                ),
                status=generated_output.get("generation_status")
                or generated_output.get("status"),
            )

        final_document_text = self._get(generated_output, "final_document_text")
        draft_contract = self._get(generated_output, "draft_contract")
        if final_document_text is not None or draft_contract is not None:
            return GeneratedOutputPanel(
                draft_contract_text=final_document_text or draft_contract,
                generated_document_reference=self._get(
                    generated_output,
                    "generated_document_reference",
                ),
            )

        return GeneratedOutputPanel()

    def _build_template_panel(
        self,
        template: Any,
        generated_output: Any,
    ) -> TemplatePanel:
        template_used = self._rendered_json(generated_output).get("template_used", {})
        if not template_used:
            template_used = self._get(generated_output, "template_used") or {}
        return TemplatePanel(
            template_id=self._get(template, "id")
            or self._get(template, "template_id")
            or template_used.get("template_id"),
            template_code=self._get(template, "template_code")
            or template_used.get("template_code"),
            template_name=self._get(template, "name")
            or self._get(template, "template_name")
            or template_used.get("template_name"),
            template_version=self._get(template, "version")
            or self._get(template, "template_version")
            or template_used.get("template_version"),
        )

    def _build_warnings_panel(
        self,
        payload: dict[str, Any],
        output_panel: GeneratedOutputPanel,
        template_panel: TemplatePanel,
    ) -> WarningsPanel:
        missing_fields: list[str] = []
        if not payload:
            missing_fields.append("domain_payload.contract_generation_payload")
        if output_panel.draft_contract_text is None and (
            output_panel.generated_document_reference is None
        ):
            missing_fields.append("generated_outputs.contract_draft")
        if template_panel.template_id is None and template_panel.template_code is None:
            missing_fields.append("reference_data.contract_template")

        return WarningsPanel(missing_fields=missing_fields)

    def _generation_metadata(self, generated_output: Any) -> dict[str, Any]:
        rendered_json = self._rendered_json(generated_output)
        if rendered_json:
            return rendered_json.get("generation_metadata", {})

        metadata = self._get(generated_output, "generation_metadata")
        if isinstance(metadata, dict):
            return metadata
        return {}

    def _rendered_json(self, generated_output: Any) -> dict[str, Any]:
        if isinstance(generated_output, GeneratedDocument):
            return generated_output.rendered_json
        if isinstance(generated_output, dict):
            return generated_output.get("rendered_json", {})
        return {}

    def _audit_summary_item(self, entry: Any) -> AuditSummaryItem:
        timestamp = self._get(entry, "timestamp")
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()

        return AuditSummaryItem(
            timestamp=timestamp,
            event_type=self._get(entry, "event_type"),
            module_or_service=self._get(entry, "module_or_service"),
            summary=self._get(entry, "summary"),
        )

    def _get(self, value: Any, key: str) -> Any:
        if value is None:
            return None
        if isinstance(value, dict):
            return value.get(key)
        return getattr(value, key, None)

    def _available_user_actions(self, case_context: ContractCaseContext) -> list[str]:
        """Return MVP standard review actions; fewer options on failed status."""
        status = case_context.case_metadata.status
        if status == "failed":
            return ["view_details", "resolve_errors"]
        return ["view_details", "approve", "reject", "request_changes"]


__all__ = ["ReviewViewService"]
