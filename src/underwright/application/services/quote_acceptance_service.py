from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from underwright.application.ports import (
    ContractRepository,
    QuoteAcceptanceRepository,
    QuoteDocumentRepository,
)
from underwright.application.services.customer_profile_service import CustomerProfileService
from underwright.application.services.quote_request_service import QuoteRequestService
from underwright.domain.auth_user import AuthUser
from underwright.domain.quote_acceptance import (
    QuoteAcceptance,
    QuoteAcceptanceCreate,
    QuoteAcceptanceInput,
)
from underwright.domain.quote_document import QuoteDocument
from underwright.domain.quote_request import QuoteRequest


ACCEPTABLE_QUOTE_STATUSES = {"approved", "auto_accepted"}


class QuoteAcceptanceError(ValueError):
    pass


class QuoteAcceptanceNotFoundError(QuoteAcceptanceError):
    pass


class QuoteAcceptanceOwnershipError(QuoteAcceptanceError):
    pass


class QuoteAcceptanceInvalidStatusError(QuoteAcceptanceError):
    pass


class QuoteAcceptanceDocumentMissingError(QuoteAcceptanceError):
    pass


class QuoteAcceptanceValidationError(QuoteAcceptanceError):
    def __init__(self, message: str, *, missing_fields: list[str]) -> None:
        super().__init__(message)
        self.missing_fields = missing_fields


class QuoteAcceptanceService:
    def __init__(
        self,
        *,
        quote_request_service: QuoteRequestService,
        quote_document_repository: QuoteDocumentRepository,
        quote_acceptance_repository: QuoteAcceptanceRepository,
        customer_profile_service: CustomerProfileService,
        contract_repository: ContractRepository | None = None,
    ) -> None:
        self.quote_request_service = quote_request_service
        self.quote_document_repository = quote_document_repository
        self.quote_acceptance_repository = quote_acceptance_repository
        self.customer_profile_service = customer_profile_service
        self.contract_repository = contract_repository

    def get_acceptance(self, quote_id: UUID) -> QuoteAcceptance:
        acceptance = self.quote_acceptance_repository.get_by_quote_request_id(quote_id)
        if acceptance is None:
            raise QuoteAcceptanceNotFoundError("Quote acceptance not found.")
        return acceptance

    def get_acceptance_for_client(
        self,
        *,
        quote_id: UUID,
        user: AuthUser,
    ) -> QuoteAcceptance:
        quote = self.quote_request_service.get_quote_request_detail(quote_id)
        self._require_quote_owner(quote, user)
        acceptance = self.get_acceptance(quote_id)
        self._require_acceptance_owner(acceptance, user)
        return acceptance

    def accept_quote_for_client(
        self,
        *,
        quote_id: UUID,
        user: AuthUser,
        signer_input: QuoteAcceptanceInput,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> QuoteAcceptance:
        self.customer_profile_service.ensure_complete_profile(user)
        quote = self.quote_request_service.get_quote_request_detail(quote_id)
        self._require_quote_owner(quote, user)

        existing = self.quote_acceptance_repository.get_by_quote_request_id(quote_id)
        if existing is not None:
            self._require_acceptance_owner(existing, user)
            return existing

        self._require_contract_not_declined(quote)
        self._require_acceptable_status(quote)
        self._validate_signer_input(signer_input)
        quote_document = self._latest_successful_document(quote_id)
        acceptance = self.quote_acceptance_repository.create(
            QuoteAcceptanceCreate(
                quote_request_id=quote_id,
                quote_document_id=quote_document.id or 0,
                accepted_by_auth_user_id=user.id,
                accepted_by_customer_id=int(user.client_id),
                signer_name=signer_input.signer_name.strip(),
                signer_email=signer_input.signer_email.strip(),
                signer_role=_clean(signer_input.signer_role),
                acceptance_method="client_portal",
                ip_address=ip_address,
                user_agent=user_agent,
                acceptance_statement=signer_input.acceptance_statement.strip(),
                quote_content_hash=_quote_content_hash(quote_document),
                metadata={
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )
        if quote.request_status != "auto_accepted":
            self.quote_request_service.update_request_status(quote_id, "auto_accepted")
        if self.contract_repository is not None and acceptance.id is not None:
            self.contract_repository.mark_contract_issued_for_quote_acceptance(
                quote_id,
                acceptance.id,
            )
        return acceptance

    def _latest_successful_document(self, quote_id: UUID) -> QuoteDocument:
        quote_document = (
            self.quote_document_repository.get_latest_successful_by_quote_request_id(
                quote_id
            )
        )
        if quote_document is None or quote_document.id is None:
            raise QuoteAcceptanceDocumentMissingError(
                "A successful quote document is required before acceptance."
            )
        return quote_document

    def _require_quote_owner(self, quote: QuoteRequest, user: AuthUser) -> None:
        if user.client_id is None or str(quote.client_id) != str(user.client_id):
            raise QuoteAcceptanceOwnershipError("Quote not found.")

    def _require_acceptance_owner(
        self,
        acceptance: QuoteAcceptance,
        user: AuthUser,
    ) -> None:
        if user.client_id is None or str(acceptance.accepted_by_customer_id) != str(
            user.client_id
        ):
            raise QuoteAcceptanceOwnershipError("Quote acceptance not found.")

    def _require_acceptable_status(self, quote: QuoteRequest) -> None:
        if quote.request_status not in ACCEPTABLE_QUOTE_STATUSES:
            raise QuoteAcceptanceInvalidStatusError(
                f"Quote status '{quote.request_status}' cannot be accepted."
            )

    def _require_contract_not_declined(self, quote: QuoteRequest) -> None:
        if self.contract_repository is None:
            return
        get_contract = getattr(
            self.contract_repository,
            "get_contract_by_source_quote_request_id",
            None,
        )
        if get_contract is None:
            return
        contract = get_contract(
            quote.request_id
        )
        if contract is not None and contract.status == "declined":
            raise QuoteAcceptanceInvalidStatusError(
                "Declined contracts cannot be signed."
            )

    def _validate_signer_input(self, signer_input: QuoteAcceptanceInput) -> None:
        missing_fields: list[str] = []
        for field_name in ("signer_name", "signer_email", "acceptance_statement"):
            if not _clean(getattr(signer_input, field_name)):
                missing_fields.append(field_name)
        if missing_fields:
            raise QuoteAcceptanceValidationError(
                "Signer details are required before quote acceptance.",
                missing_fields=missing_fields,
            )


def _quote_content_hash(quote_document: QuoteDocument) -> str:
    payload = quote_document.rendered_text.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


__all__ = [
    "ACCEPTABLE_QUOTE_STATUSES",
    "QuoteAcceptanceDocumentMissingError",
    "QuoteAcceptanceError",
    "QuoteAcceptanceInvalidStatusError",
    "QuoteAcceptanceNotFoundError",
    "QuoteAcceptanceOwnershipError",
    "QuoteAcceptanceService",
    "QuoteAcceptanceValidationError",
]
