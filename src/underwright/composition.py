from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from underwright.application.modules.claim_classification_module import (
    ClaimClassificationModule,
)
from underwright.application.modules.claim_confidence_module import ClaimConfidenceModule
from underwright.application.modules.claim_review_screen_builder_module import (
    ClaimReviewScreenBuilderModule,
)
from underwright.application.modules.contract_drafting_module import (
    ContractDraftingModule,
)
from underwright.application.modules.contract_payload_builder import (
    ContractPayloadBuilder,
)
from underwright.application.modules.claim_summary_module import ClaimSummaryModule
from underwright.application.modules.claim_validation_module import ClaimValidationModule
from underwright.application.modules.coverage_assessment_module import (
    CoverageAssessmentModule,
)
from underwright.application.modules.document_consistency_module import (
    DocumentConsistencyModule,
)
from underwright.application.modules.evidence_requirement_module import (
    EvidenceRequirementModule,
)
from underwright.application.modules.quote_approval_module import QuoteApprovalModule
from underwright.application.modules.policy_rules_module import PolicyRulesModule
from underwright.application.modules.pricing_calculation_module import (
    PricingCalculationModule,
)
from underwright.application.modules.quote_data_completion_module import (
    QuoteDataCompletionModule,
)
from underwright.application.modules.quote_document_generation_module import (
    QuoteDocumentGenerationModule,
)
from underwright.application.modules.quote_payload_builder import QuotePayloadBuilder
from underwright.application.modules.review_screen_builder_module import (
    ReviewScreenBuilderModule,
)
from underwright.application.services.audit_service import AuditService
from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.claim_data_service import ClaimDataService
from underwright.application.services.extracted_document_data_service import (
    ExtractedDocumentDataService,
)
from underwright.application.services.claim_evidence_ingestion_service import (
    ClaimEvidenceIngestionService,
)
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.application.services.claim_review_query_service import (
    ClaimReviewQueryService,
)
from underwright.application.services.contract_query_service import ContractQueryService
from underwright.application.services.contract_data_service import ContractDataService
from underwright.application.services.contract_document_generation_service import (
    ContractDocumentGenerationService,
)
from underwright.application.services.contract_decline_service import (
    ContractDeclineService,
)
from underwright.application.services.customer_profile_service import (
    CustomerProfileService,
)
from underwright.application.services.coverage_assessment_llm_service import (
    DeterministicCoverageAssessmentService,
)
from underwright.application.services.quote_data_service import QuoteDataService
from underwright.application.services.quote_acceptance_service import (
    QuoteAcceptanceService,
)
from underwright.application.services.quote_request_service import QuoteRequestService
from underwright.application.services.quote_to_contract_conversion_service import (
    QuoteToContractConversionService,
)
from underwright.application.services.generated_document_query_service import (
    GeneratedDocumentQueryService,
)
from underwright.application.services.generated_document_pdf_service import (
    GeneratedDocumentPdfService,
)
from underwright.application.services.review_view_service import ReviewViewService
from underwright.application.services.template_service import TemplateService
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
from underwright.application.workflows.contract_workflow import ContractWorkflow
from underwright.infrastructure.llm.openai_compatible import (
    OpenAICompatibleSupplementaryTextGenerator,
)
from underwright.infrastructure.llm.coverage_assessment import (
    OpenAICompatibleCoverageAssessmentLLMService,
)
from underwright.infrastructure.postgres.case_context_repository import (
    CaseContextRepository,
)
from underwright.infrastructure.postgres.auth_repository import (
    PostgresAuthUserRepository,
)
from underwright.infrastructure.postgres.claim_request_repository import (
    PostgresClaimRequestRepository,
)
from underwright.infrastructure.postgres.contract_repository import (
    PostgresContractRepository,
)
from underwright.infrastructure.postgres.contract_decline_repository import (
    PostgresContractDeclineRepository,
)
from underwright.infrastructure.postgres.generated_document_repository import (
    PostgresGeneratedDocumentRepository,
)
from underwright.infrastructure.pdf.local_storage import LocalPdfArtifactStorage
from underwright.infrastructure.pdf.simple_text_renderer import SimpleTextPdfRenderer
from underwright.infrastructure.postgres.quote_document_repository import (
    PostgresQuoteDocumentRepository,
)
from underwright.infrastructure.postgres.quote_acceptance_repository import (
    PostgresQuoteAcceptanceRepository,
)
from underwright.infrastructure.postgres.quote_request_repository import (
    PostgresQuoteRequestRepository,
)
from underwright.infrastructure.postgres.customer_profile_repository import (
    PostgresCustomerProfileRepository,
)
from underwright.infrastructure.postgres.template_repository import (
    PostgresTemplateRepository,
)
from underwright.infrastructure.postgres.wording_document_repository import (
    PostgresWordingDocumentRepository,
)
from underwright.infrastructure.storage.local_claim_attachment_storage import (
    DEFAULT_CLAIM_UPLOAD_DIR,
    DEFAULT_CLAIM_UPLOAD_MAX_BYTES,
    LocalClaimAttachmentStorageService,
)
from underwright.infrastructure.templates.renderer import PadTemplateRenderer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)


def connection_factory():
    required_database_env = [
        "POSTGRES_HOST",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    missing_database_env = [
        key for key in required_database_env if not os.environ.get(key)
    ]
    if missing_database_env:
        missing = ", ".join(missing_database_env)
        raise RuntimeError(f"Missing database environment variables: {missing}")

    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ.get("POSTGRES_PORT", 5432),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def build_supplementary_text_generator():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAICompatibleSupplementaryTextGenerator(api_key=api_key)


def build_coverage_assessment_service():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return DeterministicCoverageAssessmentService()
    return OpenAICompatibleCoverageAssessmentLLMService(api_key=api_key)


def build_claim_attachment_storage_service() -> LocalClaimAttachmentStorageService:
    return LocalClaimAttachmentStorageService(
        upload_dir=os.getenv(
            "UNDERWRIGHT_CLAIM_UPLOAD_DIR",
            str(DEFAULT_CLAIM_UPLOAD_DIR),
        ),
        max_bytes=_positive_int_env(
            "UNDERWRIGHT_CLAIM_UPLOAD_MAX_BYTES",
            DEFAULT_CLAIM_UPLOAD_MAX_BYTES,
        ),
    )


def build_extracted_document_data_service(
    claim_request_service: ClaimRequestService,
) -> ExtractedDocumentDataService:
    demo_enabled = os.getenv(
        "UNDERWRIGHT_CLAIM_DOCUMENT_DEMO_EXTRACTION",
        "",
    ).lower() in {"1", "true", "yes", "on"}
    return ExtractedDocumentDataService(
        claim_request_service,
        allow_demo_filename_extraction=demo_enabled,
    )


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def build_quote_workflow() -> QuoteWorkflow:
    audit_service = AuditService()
    quote_request_repository = PostgresQuoteRequestRepository(connection_factory)
    quote_request_service = QuoteRequestService(quote_request_repository)
    contract_repository = PostgresContractRepository(connection_factory)
    template_service = TemplateService(
        template_repository=PostgresTemplateRepository(connection_factory),
        template_renderer=PadTemplateRenderer(),
    )

    return QuoteWorkflow(
        quote_request_service=quote_request_service,
        quote_data_service=QuoteDataService(quote_request_service),
        template_service=template_service,
        quote_document_repository=PostgresQuoteDocumentRepository(connection_factory),
        quote_data_completion_module=QuoteDataCompletionModule(),
        policy_rules_module=PolicyRulesModule(),
        pricing_calculation_module=PricingCalculationModule(),
        quote_approval_module=QuoteApprovalModule(),
        quote_payload_builder=QuotePayloadBuilder(
            default_insurer_provider=contract_repository,
        ),
        quote_document_generation_module=QuoteDocumentGenerationModule(
            template_service=template_service,
            supplementary_text_generator=build_supplementary_text_generator(),
            audit_service=audit_service,
        ),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(
            CaseContextRepository(connection_factory)
        ),
        audit_service=audit_service,
    )


def build_contract_query_service() -> ContractQueryService:
    return ContractQueryService(PostgresContractRepository(connection_factory))


def build_contract_decline_service() -> ContractDeclineService:
    return ContractDeclineService(
        contract_repository=PostgresContractRepository(connection_factory),
        contract_decline_repository=PostgresContractDeclineRepository(
            connection_factory
        ),
    )


def build_wording_document_service() -> WordingDocumentService:
    return WordingDocumentService(
        PostgresWordingDocumentRepository(connection_factory),
    )


def build_contract_workflow() -> ContractWorkflow:
    audit_service = AuditService()
    template_service = TemplateService(
        template_repository=PostgresTemplateRepository(connection_factory),
        template_renderer=PadTemplateRenderer(),
    )
    contract_repository = PostgresContractRepository(connection_factory)
    return ContractWorkflow(
        contract_data_service=ContractDataService(contract_repository),
        template_service=template_service,
        generated_document_repository=PostgresGeneratedDocumentRepository(
            connection_factory
        ),
        contract_payload_builder=ContractPayloadBuilder(),
        contract_drafting_module=ContractDraftingModule(
            template_service=template_service,
            supplementary_text_generator=build_supplementary_text_generator(),
            audit_service=audit_service,
        ),
        review_screen_builder_module=ReviewScreenBuilderModule(ReviewViewService()),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(
            CaseContextRepository(connection_factory)
        ),
        audit_service=audit_service,
    )


def build_contract_document_generation_service() -> ContractDocumentGenerationService:
    contract_repository = PostgresContractRepository(connection_factory)
    return ContractDocumentGenerationService(
        contract_repository=contract_repository,
        contract_workflow=build_contract_workflow(),
    )


def build_generated_document_query_service() -> GeneratedDocumentQueryService:
    return GeneratedDocumentQueryService(
        contract_repository=PostgresContractRepository(connection_factory),
        generated_document_repository=PostgresGeneratedDocumentRepository(
            connection_factory
        ),
    )


def build_generated_document_pdf_service() -> GeneratedDocumentPdfService:
    return GeneratedDocumentPdfService(
        generated_document_repository=PostgresGeneratedDocumentRepository(
            connection_factory
        ),
        pdf_renderer=SimpleTextPdfRenderer(),
        pdf_storage=LocalPdfArtifactStorage.from_environment(),
    )


def build_quote_to_contract_conversion_service() -> QuoteToContractConversionService:
    quote_request_repository = PostgresQuoteRequestRepository(connection_factory)
    return QuoteToContractConversionService(
        contract_repository=PostgresContractRepository(connection_factory),
        quote_request_service=QuoteRequestService(quote_request_repository),
        quote_document_repository=PostgresQuoteDocumentRepository(connection_factory),
        quote_acceptance_repository=PostgresQuoteAcceptanceRepository(
            connection_factory
        ),
    )


def build_quote_acceptance_service() -> QuoteAcceptanceService:
    quote_request_repository = PostgresQuoteRequestRepository(connection_factory)
    return QuoteAcceptanceService(
        quote_request_service=QuoteRequestService(quote_request_repository),
        quote_document_repository=PostgresQuoteDocumentRepository(connection_factory),
        quote_acceptance_repository=PostgresQuoteAcceptanceRepository(
            connection_factory
        ),
        customer_profile_service=CustomerProfileService(
            PostgresCustomerProfileRepository(connection_factory),
            PostgresAuthUserRepository(connection_factory),
        ),
        contract_repository=PostgresContractRepository(connection_factory),
    )


def build_claim_workflow() -> ClaimWorkflow:
    claim_request_repository = PostgresClaimRequestRepository(connection_factory)
    claim_request_service = ClaimRequestService(claim_request_repository)
    return ClaimWorkflow(
        claim_request_service=claim_request_service,
        claim_data_service=ClaimDataService(
            claim_request_service,
            extracted_document_data_service=build_extracted_document_data_service(
                claim_request_service
            ),
        ),
        validation_module=ClaimValidationModule(),
        classification_module=ClaimClassificationModule(),
        summary_module=ClaimSummaryModule(),
        coverage_assessment_module=CoverageAssessmentModule(
            coverage_assessment_service=build_coverage_assessment_service()
        ),
        document_consistency_module=DocumentConsistencyModule(),
        evidence_requirement_module=EvidenceRequirementModule(),
        confidence_module=ClaimConfidenceModule(),
        review_screen_builder_module=ClaimReviewScreenBuilderModule(),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(
            CaseContextRepository(connection_factory)
        ),
    )


def build_coverage_precheck_workflow() -> CoveragePrecheckWorkflow:
    claim_request_repository = PostgresClaimRequestRepository(connection_factory)
    claim_request_service = ClaimRequestService(claim_request_repository)
    return CoveragePrecheckWorkflow(
        claim_request_service=claim_request_service,
        claim_data_service=ClaimDataService(
            claim_request_service,
            extracted_document_data_service=build_extracted_document_data_service(
                claim_request_service
            ),
        ),
        coverage_assessment_module=CoverageAssessmentModule(
            coverage_assessment_service=build_coverage_assessment_service()
        ),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(
            CaseContextRepository(connection_factory)
        ),
    )


def build_claim_evidence_ingestion_service() -> ClaimEvidenceIngestionService:
    claim_request_repository = PostgresClaimRequestRepository(connection_factory)
    claim_request_service = ClaimRequestService(claim_request_repository)
    return ClaimEvidenceIngestionService(
        claim_request_service=claim_request_service,
        claim_data_service=ClaimDataService(
            claim_request_service,
            extracted_document_data_service=build_extracted_document_data_service(
                claim_request_service
            ),
        ),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(
            CaseContextRepository(connection_factory)
        ),
    )


def build_claim_review_query_service() -> ClaimReviewQueryService:
    claim_request_service = ClaimRequestService(
        PostgresClaimRequestRepository(connection_factory)
    )
    return ClaimReviewQueryService(
        claim_request_service=claim_request_service,
        case_context_service=CaseContextService(
            CaseContextRepository(connection_factory)
        ),
    )


def build_evidence_refresh_workflow() -> EvidenceRefreshWorkflow:
    claim_request_repository = PostgresClaimRequestRepository(connection_factory)
    claim_request_service = ClaimRequestService(claim_request_repository)
    return EvidenceRefreshWorkflow(
        claim_request_service=claim_request_service,
        claim_data_service=ClaimDataService(
            claim_request_service,
            extracted_document_data_service=build_extracted_document_data_service(
                claim_request_service
            ),
        ),
        document_consistency_module=DocumentConsistencyModule(),
        evidence_requirement_module=EvidenceRequirementModule(),
        review_screen_builder_module=ClaimReviewScreenBuilderModule(),
        coverage_assessment_module=CoverageAssessmentModule(
            coverage_assessment_service=build_coverage_assessment_service()
        ),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(
            CaseContextRepository(connection_factory)
        ),
    )


__all__ = [
    "build_claim_attachment_storage_service",
    "build_claim_evidence_ingestion_service",
    "build_claim_review_query_service",
    "build_claim_workflow",
    "build_contract_document_generation_service",
    "build_contract_query_service",
    "build_contract_decline_service",
    "build_contract_workflow",
    "build_coverage_assessment_service",
    "build_coverage_precheck_workflow",
    "build_evidence_refresh_workflow",
    "build_extracted_document_data_service",
    "build_generated_document_pdf_service",
    "build_generated_document_query_service",
    "build_quote_workflow",
    "build_quote_acceptance_service",
    "build_quote_to_contract_conversion_service",
    "build_supplementary_text_generator",
    "build_wording_document_service",
    "connection_factory",
]
