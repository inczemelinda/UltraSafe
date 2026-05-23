from __future__ import annotations

import argparse
import os
from typing import Sequence

from dotenv import load_dotenv
import psycopg

from underwright.application.services.legal_document_normalization_service import (
    LegalDocumentNormalizationService,
)
from underwright.application.services.legal_document_template_correlation_service import (
    LegalDocumentTemplateCorrelationService,
)
from underwright.application.services.raw_ingestion_service import RawIngestionService
from underwright.application.services.source_item_processing_service import (
    DeterministicInsuranceClassifier,
    FallbackEventClassifier,
    SummaryWritingEventClassifier,
    SourceItemProcessingService,
)
from underwright.application.services.template_review_correlation_service import (
    TemplateReviewCorrelationService,
)
from underwright.domain.intelligence import (
    IngestionRun,
    ProcessingBatchResult,
    TemplateCorrelationBatchResult,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentNormalizationBatchResult,
    LegalDocumentTemplateCorrelationBatchResult,
)
from underwright.infrastructure.legal_document_parsers import (
    build_legal_document_parser_registry,
)
from underwright.infrastructure.postgres.intelligence_repositories import (
    PostgresContractTemplateRepository,
    PostgresAuditRecordRepository,
    PostgresExternalEventRepository,
    PostgresIngestionRunRepository,
    PostgresLegalDocumentTemplateReviewCandidateRepository,
    PostgresNormalizedLegalDocumentRepository,
    PostgresRawSourceItemRepository,
    PostgresSourceRepository,
    PostgresTemplateReviewCandidateRepository,
)
from underwright.infrastructure.llm.intelligence_classifier import (
    OpenAICompatibleEventClassifier,
    OpenAICompatibleEventSummaryWriter,
    OpenAICompatibleTemplateCandidateExplainer,
)
from underwright.infrastructure.source_connectors.configured_web import (
    ConfiguredWebSourceConnector,
)


_SOURCE_ALIASES = {
    "legislatie-just": "ro_portal_legislativ",
    "legislatie_just": "ro_portal_legislativ",
}


def build_service(connection_factory) -> RawIngestionService:
    connectors = {
        "web_scrape": ConfiguredWebSourceConnector(),
    }
    return RawIngestionService(
        source_repository=PostgresSourceRepository(connection_factory),
        raw_item_repository=PostgresRawSourceItemRepository(connection_factory),
        ingestion_run_repository=PostgresIngestionRunRepository(connection_factory),
        connector_registry=connectors,
    )


def build_classifier():
    deterministic = DeterministicInsuranceClassifier()
    if _ai_summaries_enabled():
        return SummaryWritingEventClassifier(
            classifier=deterministic,
            summary_writer=OpenAICompatibleEventSummaryWriter(),
        )

    if not _ai_classifier_enabled():
        return deterministic

    return FallbackEventClassifier(
        primary=OpenAICompatibleEventClassifier(),
        fallback=deterministic,
    )


def build_template_candidate_explainer():
    if not _ai_classifier_enabled():
        return None
    return OpenAICompatibleTemplateCandidateExplainer()


def build_processing_service(connection_factory) -> SourceItemProcessingService:
    return SourceItemProcessingService(
        source_repository=PostgresSourceRepository(connection_factory),
        raw_item_repository=PostgresRawSourceItemRepository(connection_factory),
        external_event_repository=PostgresExternalEventRepository(connection_factory),
        classifier=build_classifier(),
        audit_repository=PostgresAuditRecordRepository(connection_factory),
    )


def build_template_correlation_service(
    connection_factory,
) -> TemplateReviewCorrelationService:
    return TemplateReviewCorrelationService(
        event_repository=PostgresExternalEventRepository(connection_factory),
        template_repository=PostgresContractTemplateRepository(connection_factory),
        candidate_repository=PostgresTemplateReviewCandidateRepository(
            connection_factory
        ),
        audit_repository=PostgresAuditRecordRepository(connection_factory),
        candidate_explainer=build_template_candidate_explainer(),
    )


def build_legal_template_correlation_service(
    connection_factory,
) -> LegalDocumentTemplateCorrelationService:
    return LegalDocumentTemplateCorrelationService(
        legal_document_repository=PostgresNormalizedLegalDocumentRepository(
            connection_factory
        ),
        template_repository=PostgresContractTemplateRepository(connection_factory),
        candidate_repository=PostgresLegalDocumentTemplateReviewCandidateRepository(
            connection_factory
        ),
    )


def build_legal_document_normalization_service(
    connection_factory,
) -> LegalDocumentNormalizationService:
    return LegalDocumentNormalizationService(
        source_repository=PostgresSourceRepository(connection_factory),
        legal_document_repository=PostgresNormalizedLegalDocumentRepository(
            connection_factory
        ),
        parser_registry=build_legal_document_parser_registry(),
    )


def print_result(run: IngestionRun) -> None:
    error_text = "; ".join(run.errors) if run.errors else "none"

    print(
        f"source={run.source_id} "
        f"status={run.status} "
        f"seen={run.raw_items_seen} "
        f"created={run.raw_items_created} "
        f"errors={len(run.errors)} "
        f"error_details={error_text}"
    )


def print_processing_result(result: ProcessingBatchResult) -> None:
    error_text = "; ".join(result.errors) if result.errors else "none"

    print(
        f"source={result.source_id or 'all'} "
        f"status={result.status} "
        f"seen={result.raw_items_seen} "
        f"events_created={result.events_created} "
        f"classified={result.classified} "
        f"suppressed={result.suppressed} "
        f"failed={result.failed} "
        f"errors={len(result.errors)} "
        f"error_details={error_text}"
    )


def print_preview_items(items) -> None:
    for item in items:
        status = "accepted" if item.accepted else "rejected"
        title = item.title or "-"
        print(
            f"{status} "
            f"url={item.url} "
            f"title={title!r} "
            f"text_chars={item.text_chars} "
            f"attachments={item.attachment_count} "
            f"reason={item.reason}"
        )


def print_template_correlation_result(result: TemplateCorrelationBatchResult) -> None:
    error_text = "; ".join(result.errors) if result.errors else "none"

    print(
        f"source={result.source_id or 'all'} "
        f"status={result.status} "
        f"events_seen={result.events_seen} "
        f"templates_seen={result.templates_seen} "
        f"candidates_created={result.candidates_created} "
        f"failed={result.failed} "
        f"errors={len(result.errors)} "
        f"error_details={error_text}"
    )


def print_legal_template_correlation_result(
    result: LegalDocumentTemplateCorrelationBatchResult,
) -> None:
    error_text = "; ".join(result.errors) if result.errors else "none"

    print(
        f"source={result.source_id or 'all'} "
        f"status={result.status} "
        f"legal_documents_seen={result.legal_documents_seen} "
        f"templates_seen={result.templates_seen} "
        f"candidates_created={result.candidates_created} "
        f"failed={result.failed} "
        f"errors={len(result.errors)} "
        f"error_details={error_text}"
    )


def print_legal_document_normalization_result(
    result: LegalDocumentNormalizationBatchResult,
) -> None:
    error_text = "; ".join(result.errors) if result.errors else "none"

    print(
        f"source={result.source_id or 'all'} "
        f"status={result.status} "
        f"inspected={result.raw_items_seen} "
        f"normalized={result.normalized} "
        f"suppressed_non_legislative={result.suppressed} "
        "skipped_missing_required_fields="
        f"{result.skipped_missing_required_fields} "
        f"duplicate_unchanged={result.duplicate_unchanged} "
        f"parser_failed={result.failed} "
        f"errors={len(result.errors)} "
        f"error_details={error_text}"
    )


def print_legal_document_normalization_error(
    *,
    source_id: str | None,
    error: Exception,
) -> None:
    print(
        f"source={source_id or 'all'} "
        "status=failed "
        "inspected=0 "
        "normalized=0 "
        "suppressed_non_legislative=0 "
        "skipped_missing_required_fields=0 "
        "duplicate_unchanged=0 "
        "parser_failed=0 "
        "errors=1 "
        f"error_details={error}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="underwright-ingest")
    subparsers = parser.add_subparsers(dest="command", required=True)
    once = subparsers.add_parser("once")
    once.add_argument("--source-id", "--source", dest="source_id", default="asf_ro")
    once.add_argument("--limit", type=int)
    preview = subparsers.add_parser("preview")
    preview.add_argument("--source-id", "--source", dest="source_id", default="asf_ro")
    preview.add_argument("--limit", type=int, default=10)
    process = subparsers.add_parser("process")
    process.add_argument("--limit", type=int, default=50)
    process.add_argument("--source-id", "--source", dest="source_id")
    correlate_templates = subparsers.add_parser("correlate-templates")
    correlate_templates.add_argument("--limit", type=int, default=50)
    correlate_templates.add_argument("--source-id", "--source", dest="source_id")
    correlate_legal_templates = subparsers.add_parser("correlate-legal-templates")
    correlate_legal_templates.add_argument("--limit", type=int, default=50)
    correlate_legal_templates.add_argument(
        "--source-id",
        "--source",
        dest="source_id",
    )
    normalize_legal_documents = subparsers.add_parser("normalize-legal-documents")
    normalize_legal_documents.add_argument("--limit", type=int, default=50)
    normalize_legal_documents.add_argument(
        "--source-id",
        "--source",
        dest="source_id",
    )
    return parser


load_dotenv()


def _ai_classifier_enabled() -> bool:
    classifier_mode = os.getenv("INTELLIGENCE_CLASSIFIER", "").strip().lower()
    enabled = os.getenv("INTELLIGENCE_AI_ENABLED", "").strip().lower()
    return classifier_mode == "ai" or enabled in {"1", "true", "yes", "on"}


def _ai_summaries_enabled() -> bool:
    summary_mode = os.getenv("INTELLIGENCE_SUMMARIES", "").strip().lower()
    enabled = os.getenv("INTELLIGENCE_AI_SUMMARIES_ENABLED", "").strip().lower()
    return summary_mode == "ai" or enabled in {"1", "true", "yes", "on"}


def connection_factory():
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ.get("POSTGRES_PORT", 5432),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def _source_id(value: str | None) -> str | None:
    if value is None:
        return None
    return _SOURCE_ALIASES.get(value, value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source_id = _source_id(getattr(args, "source_id", None))

    if args.command == "once":
        service = build_service(connection_factory)
        run = service.run_once(source_id or "asf_ro", limit=args.limit)
        print_result(run)
        return 0 if run.status == "success" else 1

    if args.command == "preview":
        service = build_service(connection_factory)
        items = service.preview(source_id=source_id or "asf_ro", limit=args.limit)
        print_preview_items(items)
        return 0

    if args.command == "process":
        service = build_processing_service(connection_factory)
        result = service.process_batch(limit=args.limit, source_id=source_id)
        print_processing_result(result)
        return 0 if result.status == "success" else 1

    if args.command == "correlate-templates":
        service = build_template_correlation_service(connection_factory)
        result = service.correlate_batch(limit=args.limit, source_id=source_id)
        print_template_correlation_result(result)
        return 0 if result.status == "success" else 1

    if args.command == "correlate-legal-templates":
        service = build_legal_template_correlation_service(connection_factory)
        result = service.correlate_batch(limit=args.limit, source_id=source_id)
        print_legal_template_correlation_result(result)
        return 0 if result.status == "success" else 1

    if args.command == "normalize-legal-documents":
        service = build_legal_document_normalization_service(connection_factory)
        try:
            result = service.process_pending(
                limit=args.limit,
                source_id=source_id,
            )
        except Exception as exc:
            print_legal_document_normalization_error(
                source_id=source_id,
                error=exc,
            )
            return 1
        print_legal_document_normalization_result(result)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
