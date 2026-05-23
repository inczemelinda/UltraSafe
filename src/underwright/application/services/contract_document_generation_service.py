from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from underwright.application.ports import ContractRepository
from underwright.application.workflows.contract_workflow import ContractWorkflow
from underwright.domain.generated_document_lifecycle import (
    ContractDocumentGenerationResult,
    ContractGenerationIssue,
    ContractGenerationValidation,
    GeneratedDocumentReadModel,
)
from underwright.domain.models import ContractContextSource, GeneratedDocument


DEFAULT_CONTRACT_TEMPLATE_CODE = "PAD_PROPERTY_RO"


class ContractGenerationReadinessValidator:
    """Checks normalized contract data before document generation."""

    def __init__(self, contract_repository: ContractRepository) -> None:
        self.contract_repository = contract_repository

    def validate(self, contract_id: UUID) -> ContractGenerationValidation:
        errors: list[ContractGenerationIssue] = []
        warnings: list[ContractGenerationIssue] = []

        contract = self.contract_repository.get_contract_by_id(contract_id)
        if contract.source_quote_request_id is None:
            errors.append(
                ContractGenerationIssue(
                    code="SOURCE_QUOTE_PROVENANCE_MISSING",
                    field="contract.source_quote_request_id",
                    message=(
                        "Contract must be linked to a source quote before document "
                        "generation."
                    ),
                )
            )
        if contract.source_quote_document_id is None:
            errors.append(
                ContractGenerationIssue(
                    code="SOURCE_QUOTE_DOCUMENT_MISSING",
                    field="contract.source_quote_document_id",
                    message=(
                        "Contract must be linked to the accepted quote document "
                        "before generation."
                    ),
                )
            )

        try:
            source = self.contract_repository.get_contract_context_source(contract_id)
        except ValueError as exc:
            errors.append(
                ContractGenerationIssue(
                    code="CONTRACT_SOURCE_INCOMPLETE",
                    message=str(exc),
                )
            )
            return ContractGenerationValidation(
                can_generate=False,
                blocking_errors=errors,
                warnings=warnings,
            )

        self._validate_customer(source, errors)
        self._validate_asset(source, errors)
        self._validate_pricing(source, errors)

        return ContractGenerationValidation(
            can_generate=not errors,
            blocking_errors=errors,
            warnings=warnings,
        )

    def _validate_customer(
        self,
        source: ContractContextSource,
        errors: list[ContractGenerationIssue],
    ) -> None:
        customer = source.customer
        for field_name in ("full_name", "email", "phone"):
            if not self._has_value(getattr(customer, field_name)):
                errors.append(
                    ContractGenerationIssue(
                        code="CUSTOMER_FIELD_MISSING",
                        field=f"customer.{field_name}",
                        message=f"customer.{field_name} is required.",
                    )
                )

        if customer.type == "company":
            if not self._has_value(customer.company_id):
                errors.append(
                    ContractGenerationIssue(
                        code="CUSTOMER_LEGAL_ID_MISSING",
                        field="customer.company_id",
                        message="customer.company_id is required for company contracts.",
                    )
                )
        elif not self._has_value(customer.national_id):
            errors.append(
                ContractGenerationIssue(
                    code="CUSTOMER_LEGAL_ID_MISSING",
                    field="customer.national_id",
                    message="customer.national_id is required for individual contracts.",
                )
            )

        if not self._has_value(source.customer_address.full_text):
            errors.append(
                ContractGenerationIssue(
                    code="CUSTOMER_ADDRESS_MISSING",
                    field="customer_address.full_text",
                    message="customer_address.full_text is required.",
                )
            )

    def _validate_asset(
        self,
        source: ContractContextSource,
        errors: list[ContractGenerationIssue],
    ) -> None:
        asset = source.insured_asset
        for field_name in (
            "asset_type",
            "usage_type",
            "construction_type",
            "year_built",
            "area_sqm",
            "declared_value",
            "occupancy",
        ):
            if not self._has_value(getattr(asset, field_name)):
                errors.append(
                    ContractGenerationIssue(
                        code="ASSET_FIELD_MISSING",
                        field=f"insured_asset.{field_name}",
                        message=f"insured_asset.{field_name} is required.",
                    )
                )

        for field_name in ("year_built", "area_sqm", "declared_value"):
            if self._decimal(getattr(asset, field_name)) <= 0:
                errors.append(
                    ContractGenerationIssue(
                        code="ASSET_NUMBER_INVALID",
                        field=f"insured_asset.{field_name}",
                        message=f"insured_asset.{field_name} must be positive.",
                    )
                )

        if not self._has_value(source.insured_asset_address.full_text):
            errors.append(
                ContractGenerationIssue(
                    code="ASSET_ADDRESS_MISSING",
                    field="insured_asset_address.full_text",
                    message="insured_asset_address.full_text is required.",
                )
            )

    def _validate_pricing(
        self,
        source: ContractContextSource,
        errors: list[ContractGenerationIssue],
    ) -> None:
        pricing = source.pricing
        for field_name in ("base_premium_ron", "final_premium_ron"):
            if self._decimal(getattr(pricing, field_name)) <= 0:
                errors.append(
                    ContractGenerationIssue(
                        code="PRICING_FIELD_INVALID",
                        field=f"pricing.{field_name}",
                        message=f"pricing.{field_name} must be positive.",
                    )
                )

        if not self._has_value(pricing.payment_plan_type):
            errors.append(
                ContractGenerationIssue(
                    code="PRICING_FIELD_MISSING",
                    field="pricing.payment_plan_type",
                    message="pricing.payment_plan_type is required.",
                )
            )
        if pricing.installments <= 0:
            errors.append(
                ContractGenerationIssue(
                    code="PRICING_FIELD_INVALID",
                    field="pricing.installments",
                    message="pricing.installments must be positive.",
                )
            )

    def _has_value(self, value: Any) -> bool:
        return value is not None and value != "" and value != [] and value != {}

    def _decimal(self, value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        return Decimal(str(value))


class ContractDocumentGenerationService:
    """Runs explicit backend-owned contract document generation."""

    def __init__(
        self,
        contract_repository: ContractRepository,
        contract_workflow: ContractWorkflow,
        readiness_validator: ContractGenerationReadinessValidator | None = None,
    ) -> None:
        self.contract_repository = contract_repository
        self.contract_workflow = contract_workflow
        self.readiness_validator = readiness_validator or (
            ContractGenerationReadinessValidator(contract_repository)
        )

    def generate(
        self,
        contract_id: UUID,
        template_code: str = DEFAULT_CONTRACT_TEMPLATE_CODE,
    ) -> ContractDocumentGenerationResult:
        validation = self.readiness_validator.validate(contract_id)
        if not validation.can_generate:
            return ContractDocumentGenerationResult(
                status="failed",
                validation=validation,
            )

        try:
            result = self.contract_workflow.run(
                contract_id=contract_id,
                template_code=template_code,
            )
        except KeyError as exc:
            return self._failure(
                code="TEMPLATE_PLACEHOLDER_MISSING",
                message=str(exc),
                validation=validation,
            )
        except ValueError as exc:
            return self._failure(
                code=self._value_error_code(exc),
                message=str(exc),
                validation=validation,
            )

        if result.generated_document is None:
            return ContractDocumentGenerationResult(
                status="failed",
                validation=ContractGenerationValidation(
                    can_generate=False,
                    blocking_errors=[
                        ContractGenerationIssue(
                            code="CONTRACT_WORKFLOW_FAILED",
                            message="Contract workflow did not produce a document.",
                        )
                    ],
                ),
                module_results=result.module_results,
            )

        document = self._document_read_model(result.generated_document)
        return ContractDocumentGenerationResult(
            status="success",
            document=document,
            validation=validation,
            module_results=result.module_results,
        )

    def _failure(
        self,
        *,
        code: str,
        message: str,
        validation: ContractGenerationValidation,
    ) -> ContractDocumentGenerationResult:
        return ContractDocumentGenerationResult(
            status="failed",
            validation=ContractGenerationValidation(
                can_generate=False,
                blocking_errors=[
                    *validation.blocking_errors,
                    ContractGenerationIssue(code=code, message=message),
                ],
                warnings=validation.warnings,
            ),
        )

    def _value_error_code(self, exc: ValueError) -> str:
        message = str(exc)
        if "Placeholder" in message or "placeholder" in message:
            return "TEMPLATE_PLACEHOLDER_INVALID"
        if "Template" in message or "template" in message:
            return "ACTIVE_TEMPLATE_NOT_FOUND"
        return "CONTRACT_GENERATION_FAILED"

    def _document_read_model(
        self,
        document: GeneratedDocument,
    ) -> GeneratedDocumentReadModel:
        if document.id is None:
            raise ValueError("GeneratedDocument id is required after persistence")

        payload_snapshot = (
            document.payload_snapshot
            or document.rendered_json.get("contract_generation_payload")
            or {}
        )
        template_used = document.rendered_json.get("template_used") or {}
        generation_metadata = (
            document.generation_metadata
            or document.rendered_json.get("generation_metadata")
            or {}
        )
        return GeneratedDocumentReadModel(
            id=document.id,
            contract_id=document.contract_id,
            document_type=payload_snapshot.get("document_type"),
            template_id=document.template_id,
            template_code=document.template_code
            or template_used.get("template_code"),
            template_version=document.template_version
            or template_used.get("template_version"),
            template_version_hash=document.template_version_hash
            or document.rendered_json.get("template_version_hash"),
            rendered_text=document.rendered_text,
            payload_snapshot=payload_snapshot,
            generation_metadata=generation_metadata,
            content_hash=document.content_hash,
            created_at=document.created_at,
            updated_at=document.updated_at,
            status=document.generation_status,
        )


__all__ = [
    "DEFAULT_CONTRACT_TEMPLATE_CODE",
    "ContractDocumentGenerationService",
    "ContractGenerationReadinessValidator",
]
