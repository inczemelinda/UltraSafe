"""
FastAPI dependency providers for Underwright routes.

Centralizes construction of application services used via Depends().
Override these in tests using app.dependency_overrides.
"""

from __future__ import annotations

import os
import secrets

from fastapi import Depends, Header, HTTPException, status

from underwright.application.services.auth_service import AuthService
from underwright.application.services.auth_user_customer_link_service import (
    AuthUserCustomerLinkService,
)
from underwright.application.services.auth_user_search_service import (
    AuthUserSearchService,
)
from underwright.application.services.case_context_service import CaseContextService
from underwright.application.services.claim_attachment_storage_service import (
    ClaimAttachmentStorageService,
)
from underwright.application.services.claim_attachment_processing_service import (
    ClaimAttachmentProcessingService,
)
from underwright.application.services.claim_decision_rewording_service import (
    ClaimDecisionRewordingService,
)
from underwright.application.services.claim_evidence_ingestion_service import (
    ClaimEvidenceIngestionService,
)
from underwright.application.services.claim_precheck_policy_service import (
    ClaimPrecheckPolicyService,
)
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.application.services.claim_review_query_service import (
    ClaimReviewQueryService,
)
from underwright.application.services.contract_document_generation_service import (
    ContractDocumentGenerationService,
)
from underwright.application.services.contract_decline_service import (
    ContractDeclineService,
)
from underwright.application.services.contract_query_service import ContractQueryService
from underwright.application.services.contract_request_service import (
    ContractRequestService,
)
from underwright.application.services.customer_profile_service import (
    CustomerProfileService,
)
from underwright.application.services.customer_profile_document_service import (
    CustomerProfileDocumentService,
)
from underwright.application.services.email_service import EmailService
from underwright.application.services.evidence_request_draft_service import (
    EvidenceRequestDraftService,
)
from underwright.application.services.generated_document_pdf_service import (
    GeneratedDocumentPdfService,
)
from underwright.application.services.generated_document_query_service import (
    GeneratedDocumentQueryService,
)
from underwright.application.services.quote_acceptance_service import (
    QuoteAcceptanceService,
)
from underwright.application.services.quote_request_service import QuoteRequestService
from underwright.application.services.quote_to_contract_conversion_service import (
    QuoteToContractConversionService,
)
from underwright.application.services.wording_document_service import (
    WordingDocumentService,
)
from underwright.application.workflows.claim_workflow import ClaimWorkflow
from underwright.application.workflows.coverage_precheck_workflow import (
    CoveragePrecheckWorkflow,
)
from underwright.application.workflows.evidence_refresh_workflow import (
    EvidenceRefreshWorkflow,
)
from underwright.application.workflows.quote_workflow import QuoteWorkflow
from underwright.composition import build_claim_attachment_storage_service
from underwright.composition import build_claim_evidence_ingestion_service
from underwright.composition import build_claim_review_query_service
from underwright.composition import build_claim_workflow
from underwright.composition import build_contract_document_generation_service
from underwright.composition import build_contract_decline_service
from underwright.composition import build_contract_query_service
from underwright.composition import build_coverage_precheck_workflow
from underwright.composition import build_evidence_refresh_workflow
from underwright.composition import build_generated_document_pdf_service
from underwright.composition import build_generated_document_query_service
from underwright.composition import build_quote_acceptance_service
from underwright.composition import build_quote_to_contract_conversion_service
from underwright.composition import build_quote_workflow
from underwright.composition import build_wording_document_service
from underwright.composition import connection_factory
from underwright.domain.auth_user import AuthUser
from underwright.infrastructure.email.local_email_provider import LocalEmailProvider
from underwright.infrastructure.email.smtp_email_provider import SmtpEmailProvider
from underwright.infrastructure.llm.openai_responses_rewording import (
    OpenAIResponsesClaimDecisionRewordingProvider,
)
from underwright.infrastructure.llm.claim_attachment_extraction import (
    DisabledClaimAttachmentSummaryGenerator,
    DisabledClaimAttachmentTextExtractor,
    OpenAIClaimAttachmentSummaryGenerator,
    OpenAIClaimAttachmentTextExtractor,
)
from underwright.infrastructure.postgres.auth_repository import (
    PostgresAuthUserRepository,
)
from underwright.infrastructure.postgres.case_context_repository import (
    CaseContextRepository,
)
from underwright.infrastructure.postgres.claim_request_repository import (
    PostgresClaimRequestRepository,
)
from underwright.infrastructure.postgres.contract_request_repository import (
    PostgresContractRequestRepository,
)
from underwright.infrastructure.postgres.customer_profile_repository import (
    PostgresCustomerProfileRepository,
)
from underwright.infrastructure.postgres.customer_profile_document_repository import (
    PostgresCustomerProfileDocumentRepository,
)
from underwright.infrastructure.postgres.email_repository import (
    PostgresEmailMessageRepository,
)
from underwright.infrastructure.postgres.quote_request_repository import (
    PostgresQuoteRequestRepository,
)
from underwright.infrastructure.postgres.underwriting_rules_repository import (
    PostgresUnderwritingRulesRepository,
)


def get_email_read_service() -> EmailService:
    return EmailService(
        repository=PostgresEmailMessageRepository(connection_factory),
    )


def get_email_send_service() -> EmailService:
    return _configured_email_send_service()


def get_claim_decision_email_send_service() -> EmailService:
    try:
        return _configured_email_send_service()
    except RuntimeError as exc:
        if not str(exc).startswith("Missing email environment variables:"):
            raise

    from_email = os.environ.get("EMAIL_FROM") or "claims@underwright.local"
    return EmailService(
        repository=PostgresEmailMessageRepository(connection_factory),
        provider=LocalEmailProvider(prefix="claim-decision-email"),
        from_email=from_email,
    )


class _DisabledEmailProvider:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
        reply_to: str | None = None,
        attachments=None,
    ) -> str:
        raise RuntimeError(self.reason)


def get_evidence_request_email_send_service() -> EmailService:
    try:
        return _configured_email_send_service()
    except RuntimeError as exc:
        if not str(exc).startswith("Missing email environment variables:"):
            raise
        missing_email_config_reason = str(exc)

    return EmailService(
        repository=PostgresEmailMessageRepository(connection_factory),
        provider=_DisabledEmailProvider(missing_email_config_reason),
        from_email=os.environ.get("EMAIL_FROM") or "claims@underwright.local",
    )


def _configured_email_send_service() -> EmailService:
    postmark_token = os.environ.get("POSTMARK_SERVER_TOKEN")
    host = os.environ.get("EMAIL_SMTP_HOST") or (
        "smtp.postmarkapp.com" if postmark_token else None
    )
    username = os.environ.get("EMAIL_USERNAME") or postmark_token
    password = os.environ.get("EMAIL_PASSWORD") or postmark_token
    from_email = os.environ.get("EMAIL_FROM")
    missing = [
        name
        for name, value in {
            "EMAIL_SMTP_HOST": host,
            "EMAIL_USERNAME or POSTMARK_SERVER_TOKEN": username,
            "EMAIL_PASSWORD or POSTMARK_SERVER_TOKEN": password,
            "EMAIL_FROM": from_email,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing email environment variables: {', '.join(missing)}")

    provider = SmtpEmailProvider(
        host=host,
        port=int(os.environ.get("EMAIL_SMTP_PORT", "587")),
        username=username,
        password=password,
        from_email=from_email,
    )

    return EmailService(
        repository=PostgresEmailMessageRepository(connection_factory),
        provider=provider,
        from_email=from_email,
    )


def get_claim_decision_rewording_service() -> ClaimDecisionRewordingService:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ClaimDecisionRewordingService()
    provider = OpenAIResponsesClaimDecisionRewordingProvider(
        api_key=api_key,
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        timeout_seconds=float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "15")),
    )
    return ClaimDecisionRewordingService(provider)


def get_quote_workflow() -> QuoteWorkflow:
    """Provide a quote workflow instance for API routes.

    MVP: simple per-request construction that reuses package composition.
    """
    return build_quote_workflow()


def get_claim_workflow() -> ClaimWorkflow:
    return build_claim_workflow()


def get_claim_attachment_storage_service() -> ClaimAttachmentStorageService:
    return build_claim_attachment_storage_service()


def get_coverage_precheck_workflow() -> CoveragePrecheckWorkflow:
    return build_coverage_precheck_workflow()


def get_claim_evidence_ingestion_service() -> ClaimEvidenceIngestionService:
    return build_claim_evidence_ingestion_service()


def get_claim_review_query_service() -> ClaimReviewQueryService:
    return build_claim_review_query_service()


def get_evidence_refresh_workflow() -> EvidenceRefreshWorkflow:
    return build_evidence_refresh_workflow()


def get_quote_request_service() -> QuoteRequestService:
    return QuoteRequestService(PostgresQuoteRequestRepository(connection_factory))


def get_quote_acceptance_service() -> QuoteAcceptanceService:
    return build_quote_acceptance_service()


def get_contract_query_service() -> ContractQueryService:
    return build_contract_query_service()


def get_contract_document_generation_service() -> ContractDocumentGenerationService:
    return build_contract_document_generation_service()


def get_contract_decline_service() -> ContractDeclineService:
    return build_contract_decline_service()


def get_generated_document_query_service() -> GeneratedDocumentQueryService:
    return build_generated_document_query_service()


def get_generated_document_pdf_service() -> GeneratedDocumentPdfService:
    return build_generated_document_pdf_service()


def get_quote_to_contract_conversion_service() -> QuoteToContractConversionService:
    return build_quote_to_contract_conversion_service()


def get_wording_document_service() -> WordingDocumentService:
    return build_wording_document_service()


def get_contract_request_service() -> ContractRequestService:
    return ContractRequestService(PostgresContractRequestRepository(connection_factory))


def get_claim_request_service() -> ClaimRequestService:
    return ClaimRequestService(PostgresClaimRequestRepository(connection_factory))


def get_claim_attachment_processing_service() -> ClaimAttachmentProcessingService:
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        text_extractor = OpenAIClaimAttachmentTextExtractor(
            api_key=api_key,
            model=os.environ.get("OPENAI_ATTACHMENT_EXTRACTION_MODEL", "gpt-4.1-mini"),
        )
        summary_generator = OpenAIClaimAttachmentSummaryGenerator(
            api_key=api_key,
            model=os.environ.get("OPENAI_ATTACHMENT_SUMMARY_MODEL", "gpt-4o-mini"),
        )
    else:
        reason = "OPENAI_API_KEY is not set."
        text_extractor = DisabledClaimAttachmentTextExtractor(reason)
        summary_generator = DisabledClaimAttachmentSummaryGenerator(reason)

    return ClaimAttachmentProcessingService(
        claim_request_service=get_claim_request_service(),
        storage_service=get_claim_attachment_storage_service(),
        precheck_policy_service=ClaimPrecheckPolicyService(),
        text_extractor=text_extractor,
        summary_generator=summary_generator,
    )


def get_case_context_service() -> CaseContextService:
    return CaseContextService(CaseContextRepository(connection_factory))


def get_evidence_request_draft_service() -> EvidenceRequestDraftService:
    return EvidenceRequestDraftService()


def get_auth_service() -> AuthService:
    return AuthService(
        PostgresAuthUserRepository(connection_factory),
        PostgresCustomerProfileRepository(connection_factory),
    )


def get_customer_profile_service() -> CustomerProfileService:
    return CustomerProfileService(
        PostgresCustomerProfileRepository(connection_factory),
        PostgresAuthUserRepository(connection_factory),
    )


def get_customer_profile_document_service() -> CustomerProfileDocumentService:
    return CustomerProfileDocumentService(
        PostgresCustomerProfileDocumentRepository(connection_factory),
    )


def get_auth_user_customer_link_service() -> AuthUserCustomerLinkService:
    return AuthUserCustomerLinkService(
        PostgresAuthUserRepository(connection_factory),
        get_customer_profile_service(),
    )


def get_auth_user_search_service() -> AuthUserSearchService:
    return AuthUserSearchService(PostgresAuthUserRepository(connection_factory))


def get_current_auth_user(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthUser:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Missing bearer token"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid authorization header"},
        )

    try:
        return auth_service.get_user_from_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": str(exc)},
        ) from exc


def get_current_client_user(
    current_user: AuthUser = Depends(get_current_auth_user),
) -> AuthUser:
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Client access required"},
        )
    return current_user


def get_current_employee_user(
    current_user: AuthUser = Depends(get_current_auth_user),
) -> AuthUser:
    if current_user.role not in {"employee", "underwriter", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Employee access required"},
        )
    return current_user


def require_internal_api_key(
    x_underwright_internal_key: str | None = Header(
        default=None,
        alias="X-Underwright-Internal-Key",
    ),
) -> bool:
    expected_key = os.environ.get("UNDERWRIGHT_INTERNAL_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Internal API key is not configured"},
        )
    if not x_underwright_internal_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Internal API key required"},
        )
    if not secrets.compare_digest(x_underwright_internal_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Invalid internal API key"},
        )
    return True


def get_underwriting_rules_repository() -> PostgresUnderwritingRulesRepository:
    return PostgresUnderwritingRulesRepository(connection_factory)
