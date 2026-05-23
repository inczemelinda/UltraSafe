"""
FastAPI dependency providers for intelligence routes.

Kept separate from the app-wide dependency module so the intelligence slice can
be merged as an additive feature.
"""

from __future__ import annotations

import os

from underwright.application.services.intelligence_insight_query_service import (
    IntelligenceInsightQueryService,
)
from underwright.application.services.intelligence_service import (
    IntelligenceService,
    build_demo_intelligence_service,
)
from underwright.application.services.raw_ingestion_query_service import (
    RawIngestionQueryService,
)
from underwright.application.services.template_review_query_service import (
    TemplateReviewQueryService,
)
from underwright.application.services.template_change_suggestion_service import (
    LEGAL_APPROVAL_FROM_EMAIL,
    LEGAL_APPROVAL_TO_EMAIL,
    TemplateChangeSuggestionService,
)
from underwright.application.services.email_service import EmailService
from underwright.application.services.legal_review_wording_impact_service import (
    LegalReviewWordingImpactService,
)
from underwright.application.services.wording_document_service import (
    WordingDocumentService,
)
from underwright.ingestion.cli import connection_factory
from underwright.infrastructure.llm.template_change_suggestion_generator import (
    DeterministicDemoTemplateChangeSuggestionGenerator,
    OpenAICompatibleTemplateChangeSuggestionGenerator,
)
from underwright.infrastructure.postgres.intelligence_repositories import (
    PostgresInsightCardRepository,
    PostgresIngestionRunRepository,
    PostgresContractTemplateRepository,
    PostgresLegalDocumentTemplateReviewCandidateRepository,
    PostgresNormalizedLegalDocumentRepository,
    PostgresRawSourceItemRepository,
    PostgresTemplateChangeSuggestionRepository,
    PostgresTemplateReviewCandidateRepository,
)
from underwright.infrastructure.email.smtp_email_provider import SmtpEmailProvider
from underwright.infrastructure.postgres.email_repository import (
    PostgresEmailMessageRepository,
)
from underwright.infrastructure.postgres.wording_document_repository import (
    PostgresWordingDocumentRepository,
)


_intelligence_service: IntelligenceService | None = None


def get_intelligence_service() -> IntelligenceService:
    global _intelligence_service
    if _intelligence_service is None:
        _intelligence_service = build_demo_intelligence_service()
    return _intelligence_service


def get_raw_ingestion_query_service() -> RawIngestionQueryService:
    return RawIngestionQueryService(
        raw_item_repository=PostgresRawSourceItemRepository(connection_factory),
        ingestion_run_repository=PostgresIngestionRunRepository(connection_factory),
    )


def get_intelligence_insight_query_service() -> IntelligenceInsightQueryService:
    return IntelligenceInsightQueryService(
        insight_repository=PostgresInsightCardRepository(connection_factory),
    )


def get_template_review_query_service() -> TemplateReviewQueryService:
    return TemplateReviewQueryService(
        candidate_repository=PostgresTemplateReviewCandidateRepository(
            connection_factory
        ),
    )


def get_legal_template_review_candidate_repository():
    return PostgresLegalDocumentTemplateReviewCandidateRepository(connection_factory)


def get_legal_review_wording_impact_service() -> LegalReviewWordingImpactService:
    return LegalReviewWordingImpactService(
        WordingDocumentService(
            PostgresWordingDocumentRepository(connection_factory),
        )
    )


def get_template_change_suggestion_service() -> TemplateChangeSuggestionService:
    return TemplateChangeSuggestionService(
        candidate_repository=PostgresLegalDocumentTemplateReviewCandidateRepository(
            connection_factory
        ),
        legal_document_repository=PostgresNormalizedLegalDocumentRepository(
            connection_factory
        ),
        template_repository=PostgresContractTemplateRepository(connection_factory),
        suggestion_repository=PostgresTemplateChangeSuggestionRepository(
            connection_factory
        ),
        suggestion_generator=_build_template_change_suggestion_generator(),
        approval_email_service=_LazyLegalApprovalEmailService(),
        legal_approval_to_email=LEGAL_APPROVAL_TO_EMAIL,
    )


class _LazyLegalApprovalEmailService:
    def send_case_email(self, **kwargs):
        return _build_legal_approval_email_service().send_case_email(**kwargs)


def _build_legal_approval_email_service() -> EmailService:
    postmark_token = os.environ.get("POSTMARK_SERVER_TOKEN")
    username = os.environ.get("EMAIL_USERNAME") or postmark_token
    password = os.environ.get("EMAIL_PASSWORD") or postmark_token
    missing = [
        name
        for name, value in {
            "EMAIL_USERNAME or POSTMARK_SERVER_TOKEN": username,
            "EMAIL_PASSWORD or POSTMARK_SERVER_TOKEN": password,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing Postmark email environment variables: {', '.join(missing)}")

    provider = SmtpEmailProvider(
        host="smtp.postmarkapp.com",
        port=int(os.environ.get("EMAIL_SMTP_PORT", "587")),
        username=username,
        password=password,
        from_email=LEGAL_APPROVAL_FROM_EMAIL,
    )
    return EmailService(
        repository=PostgresEmailMessageRepository(connection_factory),
        provider=provider,
        from_email=LEGAL_APPROVAL_FROM_EMAIL,
    )


def _build_template_change_suggestion_generator():
    enabled = os.getenv("TEMPLATE_CHANGE_SUGGESTIONS_AI_ENABLED", "").lower()
    if enabled in {"1", "true", "yes", "on"}:
        return OpenAICompatibleTemplateChangeSuggestionGenerator()
    return DeterministicDemoTemplateChangeSuggestionGenerator()
