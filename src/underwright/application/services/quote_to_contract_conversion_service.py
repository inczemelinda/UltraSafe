from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from underwright.application.ports import (
    ContractSourceQuoteConflictError,
    ContractRepository,
    QuoteAcceptanceRepository,
    QuoteDocumentRepository,
)
from underwright.application.services.quote_request_service import QuoteRequestService
from underwright.domain.contract_lifecycle import (
    AddressSnapshot,
    ContractConversionIssue,
    ContractConversionValidation,
    ContractCreationData,
    QuoteContractResolution,
    QuoteToContractConversionResult,
)
from underwright.domain.quote_acceptance import QuoteAcceptance
from underwright.domain.quote_document import QuoteDocument
from underwright.domain.quote_request import QuoteRequest


CONVERTIBLE_QUOTE_STATUSES = {"auto_accepted", "approved"}
BLOCKED_QUOTE_STATUSES = {
    "draft",
    "pricing_in_progress",
    "quote_ready",
    "underwriter_review",
    "disapproved",
    "field_review_required",
    "failed",
}


class ContractConversionValidator:
    """Validates whether a quote can become a normalized backend contract."""

    def validate(
        self,
        quote: QuoteRequest,
        accepted_quote_document: QuoteDocument | None,
        quote_acceptance: QuoteAcceptance | None,
        *,
        require_acceptance: bool = True,
    ) -> ContractConversionValidation:
        errors: list[ContractConversionIssue] = []
        warnings: list[ContractConversionIssue] = []

        if quote.request_status not in CONVERTIBLE_QUOTE_STATUSES:
            errors.append(
                ContractConversionIssue(
                    code="QUOTE_NOT_ACCEPTED",
                    field="request_status",
                    message=(
                        "Quote must be approved or auto-accepted before contract "
                        "conversion."
                    ),
                )
            )

        if quote.request_status in BLOCKED_QUOTE_STATUSES:
            errors.append(
                ContractConversionIssue(
                    code=f"QUOTE_STATUS_{quote.request_status.upper()}",
                    field="request_status",
                    message=f"Quote status '{quote.request_status}' blocks conversion.",
                )
            )

        if quote_acceptance is None and require_acceptance:
            errors.append(
                ContractConversionIssue(
                    code="QUOTE_ACCEPTANCE_REQUIRED",
                    field="quote_acceptance",
                    message="Quote must be accepted before contract conversion.",
                )
            )

        if accepted_quote_document is None:
            errors.append(
                ContractConversionIssue(
                    code="QUOTE_DOCUMENT_MISSING",
                    field="quote_document",
                    message=(
                        "A successful generated quote document is required before "
                        "contract conversion."
                    ),
                )
            )
        elif accepted_quote_document.quote_request_id != quote.request_id:
            errors.append(
                ContractConversionIssue(
                    code="SOURCE_QUOTE_DOCUMENT_MISMATCH",
                    field="quote_document.quote_request_id",
                    message=(
                        "Source quote document must belong to the same quote "
                        "request before contract conversion."
                    ),
                )
            )
        elif accepted_quote_document.generation_status != "success":
            errors.append(
                ContractConversionIssue(
                    code="ACCEPTED_QUOTE_DOCUMENT_NOT_SUCCESSFUL",
                    field="quote_document.generation_status",
                    message="Accepted quote document must be successfully generated.",
                )
            )

        if quote_acceptance is not None:
            if str(quote_acceptance.accepted_by_customer_id) != str(quote.client_id):
                errors.append(
                    ContractConversionIssue(
                        code="QUOTE_ACCEPTANCE_CUSTOMER_MISMATCH",
                        field="quote_acceptance.accepted_by_customer_id",
                        message="Quote acceptance customer does not match quote customer.",
                    )
                )
            if (
                accepted_quote_document is not None
                and quote_acceptance.quote_document_id != accepted_quote_document.id
            ):
                errors.append(
                    ContractConversionIssue(
                        code="QUOTE_ACCEPTANCE_DOCUMENT_MISMATCH",
                        field="quote_acceptance.quote_document_id",
                        message="Quote acceptance document does not match the accepted quote document.",
                    )
                )

        self._require_client_fields(quote.client_data, errors)
        self._require_asset_fields(quote.asset_data, errors)
        self._require_pricing_fields(quote.pricing_preview, errors)

        warnings.append(
            ContractConversionIssue(
                code="QUOTE_EXPIRATION_NOT_MODELED",
                message=(
                    "Quote expiration/staleness is not modeled yet and cannot be "
                    "validated during conversion."
                ),
            )
        )

        return ContractConversionValidation(
            can_convert=not errors,
            blocking_errors=errors,
            warnings=warnings,
            model_gaps=[
                "quote_expiration",
            ],
        )

    def _require_client_fields(
        self,
        client_data: dict[str, Any],
        errors: list[ContractConversionIssue],
    ) -> None:
        for field_name in ("full_name", "email", "phone", "address"):
            self._require_value(client_data, f"client_data.{field_name}", errors)

        customer_type = str(client_data.get("type") or "individual")
        if customer_type == "company":
            self._require_value(client_data, "client_data.company_id", errors)
        else:
            self._require_value(client_data, "client_data.national_id", errors)

    def _require_asset_fields(
        self,
        asset_data: dict[str, Any],
        errors: list[ContractConversionIssue],
    ) -> None:
        for field_name in (
            "asset_type",
            "usage_type",
            "construction_type",
            "year_built",
            "area_sqm",
            "declared_value",
            "occupancy",
            "address",
        ):
            self._require_value(asset_data, f"asset_data.{field_name}", errors)

        for field_name in ("year_built", "area_sqm", "declared_value"):
            value = self._decimal(asset_data.get(field_name))
            if value is None or value <= 0:
                errors.append(
                    ContractConversionIssue(
                        code="INVALID_ASSET_NUMBER",
                        field=f"asset_data.{field_name}",
                        message=f"asset_data.{field_name} must be a positive number.",
                    )
                )

    def _require_pricing_fields(
        self,
        pricing_preview: dict[str, Any],
        errors: list[ContractConversionIssue],
    ) -> None:
        final_premium = _extract_final_premium(pricing_preview)
        if final_premium is None or final_premium <= 0:
            errors.append(
                ContractConversionIssue(
                    code="PRICING_MISSING",
                    field="pricing_preview",
                    message="A positive final premium is required before conversion.",
                )
            )

    def _require_value(
        self,
        data: dict[str, Any],
        path: str,
        errors: list[ContractConversionIssue],
    ) -> None:
        field_name = path.split(".")[-1]
        value = data.get(field_name)
        if value is None or value == "" or value == [] or value == {}:
            errors.append(
                ContractConversionIssue(
                    code="REQUIRED_FIELD_MISSING",
                    field=path,
                    message=f"{path} is required for contract conversion.",
                )
            )

    def _decimal(self, value: Any) -> Decimal | None:
        return _to_decimal(value)


class QuoteToContractConversionService:
    """Coordinates explicit quote-to-contract lifecycle transitions."""

    def __init__(
        self,
        contract_repository: ContractRepository,
        quote_request_service: QuoteRequestService,
        quote_document_repository: QuoteDocumentRepository,
        quote_acceptance_repository: QuoteAcceptanceRepository,
        validator: ContractConversionValidator | None = None,
    ) -> None:
        self.contract_repository = contract_repository
        self.quote_request_service = quote_request_service
        self.quote_document_repository = quote_document_repository
        self.quote_acceptance_repository = quote_acceptance_repository
        self.validator = validator or ContractConversionValidator()

    def resolve_quote_contract(self, quote_id: UUID) -> QuoteContractResolution:
        quote = self.quote_request_service.get_quote_request_detail(quote_id)
        existing = self.contract_repository.get_contract_by_source_quote_request_id(
            quote_id
        )
        if existing is not None:
            return QuoteContractResolution(
                quote_id=quote_id,
                already_converted=True,
                conversion_status="converted",
                contract_id=existing.id,
                contract=existing,
                validation=ContractConversionValidation(can_convert=False),
            )

        validation = self._validate(quote)
        return QuoteContractResolution(
            quote_id=quote_id,
            already_converted=False,
            conversion_status="eligible" if validation.can_convert else "blocked",
            validation=validation,
        )

    def convert_quote(self, quote_id: UUID) -> QuoteToContractConversionResult:
        quote = self.quote_request_service.get_quote_request_detail(quote_id)
        existing = self.contract_repository.get_contract_by_source_quote_request_id(
            quote_id
        )
        if existing is not None:
            return QuoteToContractConversionResult(
                quote_id=quote_id,
                result="already_exists",
                contract_id=existing.id,
                contract=existing,
                validation=ContractConversionValidation(can_convert=False),
            )

        quote_acceptance = self.quote_acceptance_repository.get_by_quote_request_id(
            quote_id
        )
        accepted_quote_document = self._accepted_quote_document(quote_acceptance)
        validation = self._validate_with_document(
            quote,
            accepted_quote_document,
            quote_acceptance,
        )
        if not validation.can_convert:
            return QuoteToContractConversionResult(
                quote_id=quote_id,
                result="blocked",
                validation=validation,
            )

        if (
            accepted_quote_document is None
            or accepted_quote_document.id is None
            or quote_acceptance is None
            or quote_acceptance.id is None
        ):
            raise ValueError("Quote acceptance and accepted QuoteDocument are required")

        try:
            contract = self.contract_repository.create_contract_from_quote_data(
                self._build_creation_data(
                    quote=quote,
                    quote_document=accepted_quote_document,
                    quote_acceptance=quote_acceptance,
                )
            )
        except ContractSourceQuoteConflictError:
            existing = self.contract_repository.get_contract_by_source_quote_request_id(
                quote_id
            )
            if existing is None:
                raise
            return QuoteToContractConversionResult(
                quote_id=quote_id,
                result="already_exists",
                contract_id=existing.id,
                contract=existing,
                validation=ContractConversionValidation(can_convert=False),
            )
        return QuoteToContractConversionResult(
            quote_id=quote_id,
            result="created",
            contract_id=contract.id,
            contract=contract,
            validation=validation,
        )

    def publish_approved_quote(
        self,
        quote_id: UUID,
        *,
        quote_document: QuoteDocument | None = None,
    ) -> QuoteToContractConversionResult:
        quote = self.quote_request_service.get_quote_request_detail(quote_id)
        existing = self.contract_repository.get_contract_by_source_quote_request_id(
            quote_id
        )
        if existing is not None:
            return QuoteToContractConversionResult(
                quote_id=quote_id,
                result="already_exists",
                contract_id=existing.id,
                contract=existing,
                validation=ContractConversionValidation(can_convert=False),
            )

        latest_quote_document = quote_document or (
            self.quote_document_repository.get_latest_successful_by_quote_request_id(
                quote_id
            )
        )
        quote_acceptance = self.quote_acceptance_repository.get_by_quote_request_id(
            quote_id
        )
        validation = self._validate_with_document(
            quote,
            latest_quote_document,
            quote_acceptance,
            require_acceptance=False,
        )
        if not validation.can_convert:
            return QuoteToContractConversionResult(
                quote_id=quote_id,
                result="blocked",
                validation=validation,
            )

        if latest_quote_document is None or latest_quote_document.id is None:
            raise ValueError("A successful QuoteDocument is required")

        try:
            contract = self.contract_repository.create_contract_from_quote_data(
                self._build_creation_data(
                    quote=quote,
                    quote_document=latest_quote_document,
                    quote_acceptance=quote_acceptance,
                )
            )
        except ContractSourceQuoteConflictError:
            existing = self.contract_repository.get_contract_by_source_quote_request_id(
                quote_id
            )
            if existing is None:
                raise
            return QuoteToContractConversionResult(
                quote_id=quote_id,
                result="already_exists",
                contract_id=existing.id,
                contract=existing,
                validation=ContractConversionValidation(can_convert=False),
            )
        return QuoteToContractConversionResult(
            quote_id=quote_id,
            result="created",
            contract_id=contract.id,
            contract=contract,
            validation=validation,
        )

    def latest_successful_quote_document(self, quote_id: UUID) -> QuoteDocument | None:
        return self.quote_document_repository.get_latest_successful_by_quote_request_id(
            quote_id
        )

    def _validate(self, quote: QuoteRequest) -> ContractConversionValidation:
        quote_acceptance = self.quote_acceptance_repository.get_by_quote_request_id(
            quote.request_id
        )
        accepted_quote_document = self._accepted_quote_document(quote_acceptance)
        validation = self._validate_with_document(
            quote,
            accepted_quote_document,
            quote_acceptance,
        )
        return validation

    def _validate_with_document(
        self,
        quote: QuoteRequest,
        accepted_quote_document: QuoteDocument | None,
        quote_acceptance: QuoteAcceptance | None,
        *,
        require_acceptance: bool = True,
    ) -> ContractConversionValidation:
        validation = self.validator.validate(
            quote,
            accepted_quote_document,
            quote_acceptance,
            require_acceptance=require_acceptance,
        )
        if not self.contract_repository.has_default_insurer():
            validation.blocking_errors.append(
                ContractConversionIssue(
                    code="DEFAULT_INSURER_MISSING",
                    field="insurer",
                    message="A default insurer record is required before conversion.",
                )
            )
            validation.can_convert = False
        return validation

    def _accepted_quote_document(
        self,
        quote_acceptance: QuoteAcceptance | None,
    ) -> QuoteDocument | None:
        if quote_acceptance is None:
            return None
        try:
            return self.quote_document_repository.get_by_id(
                quote_acceptance.quote_document_id
            )
        except ValueError:
            return None

    def _build_creation_data(
        self,
        *,
        quote: QuoteRequest,
        quote_document: QuoteDocument,
        quote_acceptance: QuoteAcceptance | None,
    ) -> ContractCreationData:
        now = datetime.now(timezone.utc)
        issue_date = now.date()
        effective_date = issue_date
        expiration_date = _one_year_minus_one_day(effective_date)
        pricing_preview = quote.pricing_preview
        final_premium = _extract_final_premium(pricing_preview)
        if final_premium is None:
            raise ValueError("Final premium is required")
        base_premium = _extract_base_premium(pricing_preview) or final_premium

        # TODO(Product): confirm whether conversion should reuse the normalized
        # customer referenced by quote.client_id instead of persisting a contract
        # snapshot customer and insured asset from the accepted quote payload.
        return ContractCreationData(
            id=uuid4(),
            contract_number=_contract_number(quote.request_id, issue_date),
            source_quote_request_id=quote.request_id,
            source_quote_document_id=quote_document.id,
            source_quote_acceptance_id=(
                quote_acceptance.id if quote_acceptance is not None else None
            ),
            status="issued" if quote_acceptance is not None else "generated",
            customer_type=(
                "company"
                if str(quote.client_data.get("type") or "").lower() == "company"
                else "individual"
            ),
            customer_full_name=str(quote.client_data["full_name"]),
            customer_national_id=_optional_str(quote.client_data.get("national_id")),
            customer_company_id=_optional_str(quote.client_data.get("company_id")),
            customer_email=str(quote.client_data["email"]),
            customer_phone=str(quote.client_data["phone"]),
            customer_address=_address_snapshot(quote.client_data["address"]),
            asset_type=str(quote.asset_data["asset_type"]),
            usage_type=str(quote.asset_data["usage_type"]),
            construction_type=str(quote.asset_data["construction_type"]),
            year_built=int(quote.asset_data["year_built"]),
            floor=_optional_int(quote.asset_data.get("floor")),
            area_sqm=Decimal(str(quote.asset_data["area_sqm"])),
            declared_value=Decimal(str(quote.asset_data["declared_value"])),
            occupancy=str(quote.asset_data["occupancy"]),
            previous_claims_count=int(
                quote.asset_data.get("previous_claims_count") or 0
            ),
            asset_address=_address_snapshot(quote.asset_data["address"]),
            issue_date=issue_date,
            effective_date=effective_date,
            expiration_date=expiration_date,
            currency=str(pricing_preview.get("currency") or "RON"),
            overall_risk_level=_risk_level(quote),
            risk_score=_risk_score(quote),
            base_premium_ron=base_premium,
            pricing_adjustments=_pricing_adjustments(pricing_preview),
            final_premium_ron=final_premium,
            payment_plan_type=str(
                pricing_preview.get("payment_plan_type")
                or pricing_preview.get("paymentPlanType")
                or "annual"
            ),
            installments=int(pricing_preview.get("installments") or 1),
            created_at=now,
            updated_at=now,
        )


def _contract_number(quote_id: UUID, issue_date: date) -> str:
    # Demo quote UUIDs share long prefixes, so include the tail where they differ.
    return f"PAD-Q-{issue_date.year}-{quote_id.hex[:8].upper()}{quote_id.hex[-8:].upper()}"


def _one_year_minus_one_day(effective_date: date) -> date:
    try:
        return effective_date.replace(year=effective_date.year + 1) - timedelta(days=1)
    except ValueError:
        return effective_date.replace(
            year=effective_date.year + 1,
            day=28,
        ) - timedelta(days=1)


def _address_snapshot(value: Any) -> AddressSnapshot:
    if isinstance(value, dict):
        full_text = str(value.get("full_text") or value.get("fullText") or "")
        street = str(value.get("street") or full_text or "Unknown")
        number = str(value.get("number") or "N/A")
        city = str(value.get("city") or "Unknown")
        county = str(value.get("county") or city)
        country = str(value.get("country") or "Romania")
        postal_code = str(value.get("postal_code") or value.get("postalCode") or "N/A")
        return AddressSnapshot(
            country=country,
            county=county,
            city=city,
            street=street,
            number=number,
            postal_code=postal_code,
            full_text=full_text
            or f"{street} {number}, {city}, {county}, {country}",
        )

    full_text = str(value)
    return AddressSnapshot(
        country="Romania",
        county="Unknown",
        city="Unknown",
        street=full_text,
        number="N/A",
        postal_code="N/A",
        full_text=full_text,
    )


def _extract_final_premium(pricing_preview: dict[str, Any]) -> Decimal | None:
    pricing_result = _object(pricing_preview.get("pricing_result"))
    pricing = _object(pricing_preview.get("pricing"))
    return _first_decimal(
        pricing_preview.get("estimated_premium"),
        pricing_preview.get("final_premium"),
        pricing_result.get("final_premium"),
        pricing.get("finalPremium"),
        pricing.get("final_premium"),
    )


def _extract_base_premium(pricing_preview: dict[str, Any]) -> Decimal | None:
    pricing_result = _object(pricing_preview.get("pricing_result"))
    pricing = _object(pricing_preview.get("pricing"))
    return _first_decimal(
        pricing_preview.get("base_premium"),
        pricing_result.get("base_premium"),
        pricing.get("basePremium"),
        pricing.get("base_premium"),
    )


def _pricing_adjustments(pricing_preview: dict[str, Any]) -> list[dict[str, Any]]:
    pricing_result = _object(pricing_preview.get("pricing_result"))
    adjustments = pricing_result.get("pricing_adjustments") or []
    if isinstance(adjustments, list):
        return [
            _contract_pricing_adjustment(adjustment)
            for adjustment in adjustments
            if isinstance(adjustment, dict)
        ]
    return []


def _contract_pricing_adjustment(adjustment: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(adjustment)
    source = normalized.get("source") or normalized.get("code")
    adjustment_type = normalized.get("type") or normalized.get("adjustment_type")
    if source is not None:
        normalized["source"] = str(source)
    if adjustment_type is not None:
        normalized["type"] = str(adjustment_type)
    return normalized


def _risk_score(quote: QuoteRequest) -> int:
    raw_score = (
        quote.pricing_preview.get("risk_score")
        or quote.pricing_preview.get("riskScore")
        or quote.asset_data.get("risk_score")
    )
    value = _to_decimal(raw_score)
    if value is None:
        return 0
    return int(max(0, min(100, value)))


def _risk_level(quote: QuoteRequest) -> str:
    score = _risk_score(quote)
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    if score > 0:
        return "low"
    return "standard"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_decimal(*values: Any) -> Decimal | None:
    for value in values:
        converted = _to_decimal(value)
        if converted is not None:
            return converted
    return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "BLOCKED_QUOTE_STATUSES",
    "CONVERTIBLE_QUOTE_STATUSES",
    "ContractConversionValidator",
    "QuoteToContractConversionService",
]
