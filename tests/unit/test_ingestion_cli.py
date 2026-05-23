from __future__ import annotations

import io
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from underwright.application.services.source_item_processing_service import (
    DeterministicInsuranceClassifier,
    FallbackEventClassifier,
    SummaryWritingEventClassifier,
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
from underwright.infrastructure.llm.intelligence_classifier import (
    OpenAICompatibleEventSummaryWriter,
    OpenAICompatibleTemplateCandidateExplainer,
)
from underwright.ingestion.cli import (
    build_classifier,
    build_legal_document_normalization_service,
    build_legal_template_correlation_service,
    build_parser,
    build_template_candidate_explainer,
    main,
    print_legal_template_correlation_result,
    print_legal_document_normalization_result,
    print_preview_items,
    print_processing_result,
    print_result,
    print_template_correlation_result,
)


class FakeRawIngestionService:
    def __init__(self, run: IngestionRun) -> None:
        self.run = run
        self.source_id = None
        self.preview_source_id = None
        self.limit = None
        self.preview_limit = None

    def run_once(
        self,
        source_id: str,
        limit: int | None = None,
    ) -> IngestionRun:
        self.source_id = source_id
        self.limit = limit
        return self.run

    def preview(self, source_id: str, limit: int):
        self.preview_source_id = source_id
        self.preview_limit = limit
        return [
            SimpleNamespace(
                accepted=True,
                url="https://asfromania.ro/item",
                title="ASF comunicare",
                text_chars=240,
                attachment_count=1,
                reason="accepted",
            )
        ]


class FakeProcessingService:
    def __init__(self, result: ProcessingBatchResult) -> None:
        self.result = result
        self.limit = None
        self.source_id = None

    def process_batch(
        self,
        limit: int,
        source_id: str | None = None,
    ) -> ProcessingBatchResult:
        self.limit = limit
        self.source_id = source_id
        return self.result


class FakeTemplateCorrelationService:
    def __init__(self, result: TemplateCorrelationBatchResult) -> None:
        self.result = result
        self.limit = None
        self.source_id = None

    def correlate_batch(
        self,
        limit: int,
        source_id: str | None = None,
    ) -> TemplateCorrelationBatchResult:
        self.limit = limit
        self.source_id = source_id
        return self.result


class FakeLegalTemplateCorrelationService:
    def __init__(self, result: LegalDocumentTemplateCorrelationBatchResult) -> None:
        self.result = result
        self.limit = None
        self.source_id = None

    def correlate_batch(
        self,
        limit: int,
        source_id: str | None = None,
    ) -> LegalDocumentTemplateCorrelationBatchResult:
        self.limit = limit
        self.source_id = source_id
        return self.result


class FakeLegalDocumentNormalizationService:
    def __init__(
        self,
        result: LegalDocumentNormalizationBatchResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.limit = None
        self.source_id = None

    def process_pending(
        self,
        *,
        limit: int = 50,
        source_id: str | None = None,
    ) -> LegalDocumentNormalizationBatchResult:
        self.limit = limit
        self.source_id = source_id
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def make_run(status: str = "success") -> IngestionRun:
    return IngestionRun(
        run_id=uuid4(),
        source_id="asf_ro",
        status=status,
        raw_items_seen=3,
        raw_items_created=2,
        errors=[] if status == "success" else ["boom"],
        started_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 7, 9, 1, tzinfo=UTC),
    )


def make_processing_result(status: str = "success") -> ProcessingBatchResult:
    return ProcessingBatchResult(
        source_id="asf_ro",
        status=status,
        raw_items_seen=4,
        events_created=3,
        classified=2,
        suppressed=1,
        failed=0 if status == "success" else 1,
        errors=[] if status == "success" else ["db unavailable"],
        started_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 7, 9, 1, tzinfo=UTC),
    )


def make_template_correlation_result(
    status: str = "success",
) -> TemplateCorrelationBatchResult:
    return TemplateCorrelationBatchResult(
        source_id="asf_ro",
        status=status,
        events_seen=4,
        templates_seen=2,
        candidates_created=3,
        failed=0 if status == "success" else 1,
        errors=[] if status == "success" else ["db unavailable"],
        started_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 7, 9, 1, tzinfo=UTC),
    )


def make_legal_template_correlation_result(
    status: str = "success",
) -> LegalDocumentTemplateCorrelationBatchResult:
    return LegalDocumentTemplateCorrelationBatchResult(
        source_id="demo_ro_portal_legislativ",
        status=status,
        legal_documents_seen=1,
        templates_seen=2,
        candidates_created=1,
        failed=0 if status == "success" else 1,
        errors=[] if status == "success" else ["db unavailable"],
    )


def make_legal_document_normalization_result(
    status: str = "success",
) -> LegalDocumentNormalizationBatchResult:
    return LegalDocumentNormalizationBatchResult(
        source_id="ro_portal_legislativ",
        status=status,
        raw_items_seen=5,
        normalized=2,
        suppressed=1,
        skipped_missing_required_fields=1,
        duplicate_unchanged=1,
        failed=0 if status == "success" else 1,
        errors=[] if status == "success" else ["raw-item-id: parser failed"],
    )


def test_build_parser_parses_once_command_with_default_source() -> None:
    args = build_parser().parse_args(["once"])

    assert args.command == "once"
    assert args.source_id == "asf_ro"


def test_build_parser_parses_once_command_with_explicit_source() -> None:
    args = build_parser().parse_args(["once", "--source-id", "asf_ro"])

    assert args.command == "once"
    assert args.source_id == "asf_ro"


def test_build_parser_parses_once_command_with_source_alias_and_limit() -> None:
    args = build_parser().parse_args(
        ["once", "--source", "legislatie-just", "--limit", "20"]
    )

    assert args.command == "once"
    assert args.source_id == "legislatie-just"
    assert args.limit == 20


def test_build_parser_parses_preview_command() -> None:
    args = build_parser().parse_args(
        ["preview", "--source-id", "asf_ro", "--limit", "3"]
    )

    assert args.command == "preview"
    assert args.source_id == "asf_ro"
    assert args.limit == 3


def test_build_parser_parses_process_command() -> None:
    args = build_parser().parse_args(
        ["process", "--limit", "25", "--source-id", "paid_ro"]
    )

    assert args.command == "process"
    assert args.limit == 25
    assert args.source_id == "paid_ro"


def test_build_parser_parses_correlate_templates_command() -> None:
    args = build_parser().parse_args(
        ["correlate-templates", "--limit", "25", "--source-id", "asf_ro"]
    )

    assert args.command == "correlate-templates"
    assert args.limit == 25
    assert args.source_id == "asf_ro"


def test_build_parser_parses_correlate_legal_templates_command() -> None:
    args = build_parser().parse_args(
        [
            "correlate-legal-templates",
            "--limit",
            "25",
            "--source-id",
            "demo_ro_portal_legislativ",
        ]
    )

    assert args.command == "correlate-legal-templates"
    assert args.limit == 25
    assert args.source_id == "demo_ro_portal_legislativ"


def test_build_parser_parses_normalize_legal_documents_command() -> None:
    args = build_parser().parse_args(
        [
            "normalize-legal-documents",
            "--limit",
            "25",
            "--source-id",
            "ro_portal_legislativ",
        ]
    )

    assert args.command == "normalize-legal-documents"
    assert args.limit == 25
    assert args.source_id == "ro_portal_legislativ"


def test_build_parser_normalize_legal_documents_defaults_limit_to_50() -> None:
    args = build_parser().parse_args(["normalize-legal-documents"])

    assert args.command == "normalize-legal-documents"
    assert args.limit == 50
    assert args.source_id is None


def test_build_classifier_uses_deterministic_by_default() -> None:
    with patch.dict(os.environ, {}, clear=True):
        classifier = build_classifier()

    assert isinstance(classifier, DeterministicInsuranceClassifier)


def test_build_classifier_uses_ai_with_deterministic_fallback_when_enabled() -> None:
    with patch.dict(
        os.environ,
        {"INTELLIGENCE_AI_ENABLED": "true", "OPENAI_API_KEY": "test-key"},
        clear=True,
    ):
        classifier = build_classifier()

    assert isinstance(classifier, FallbackEventClassifier)
    assert classifier.primary.model_name == "openai-compatible-event-classifier"
    assert isinstance(classifier.fallback, DeterministicInsuranceClassifier)


def test_build_classifier_uses_ai_summary_writer_when_enabled() -> None:
    with patch.dict(
        os.environ,
        {"INTELLIGENCE_AI_SUMMARIES_ENABLED": "true", "OPENAI_API_KEY": "test-key"},
        clear=True,
    ):
        classifier = build_classifier()

    assert isinstance(classifier, SummaryWritingEventClassifier)
    assert isinstance(classifier.classifier, DeterministicInsuranceClassifier)
    assert isinstance(classifier.summary_writer, OpenAICompatibleEventSummaryWriter)


def test_build_template_candidate_explainer_is_optional() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert build_template_candidate_explainer() is None

    with patch.dict(
        os.environ,
        {"INTELLIGENCE_CLASSIFIER": "ai", "OPENAI_API_KEY": "test-key"},
        clear=True,
    ):
        explainer = build_template_candidate_explainer()

    assert isinstance(explainer, OpenAICompatibleTemplateCandidateExplainer)


def test_build_legal_template_correlation_service_wires_repositories() -> None:
    service = build_legal_template_correlation_service(lambda: None)

    assert service.legal_document_repository is not None
    assert service.template_repository is not None
    assert service.candidate_repository is not None


def test_build_legal_document_normalization_service_wires_repositories() -> None:
    service = build_legal_document_normalization_service(lambda: None)

    assert service.source_repository is not None
    assert service.legal_document_repository is not None
    assert service.parser_registry is not None


def test_print_result_outputs_run_summary() -> None:
    run = make_run()

    with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        print_result(run)

    output = fake_stdout.getvalue()
    assert "source=asf_ro" in output
    assert "status=success" in output
    assert "seen=3" in output
    assert "created=2" in output
    assert "errors=0" in output


def test_print_processing_result_outputs_processing_summary() -> None:
    result = make_processing_result()

    with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        print_processing_result(result)

    output = fake_stdout.getvalue()
    assert "source=asf_ro" in output
    assert "status=success" in output
    assert "seen=4" in output
    assert "events_created=3" in output
    assert "classified=2" in output
    assert "suppressed=1" in output


def test_print_preview_items_outputs_acceptance_decisions() -> None:
    items = [
        SimpleNamespace(
            accepted=True,
            url="https://asfromania.ro/accepted",
            title="Accepted page",
            text_chars=250,
            attachment_count=1,
            reason="accepted",
        ),
        SimpleNamespace(
            accepted=False,
            url="https://asfromania.ro/rejected",
            title="Rejected page",
            text_chars=12,
            attachment_count=0,
            reason="text below min_text_chars: 12 < 100",
        ),
    ]

    with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        print_preview_items(items)

    output = fake_stdout.getvalue()
    assert "accepted url=https://asfromania.ro/accepted" in output
    assert "rejected url=https://asfromania.ro/rejected" in output
    assert "reason=text below min_text_chars" in output


def test_print_template_correlation_result_outputs_summary() -> None:
    result = make_template_correlation_result()

    with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        print_template_correlation_result(result)

    output = fake_stdout.getvalue()
    assert "source=asf_ro" in output
    assert "events_seen=4" in output
    assert "templates_seen=2" in output
    assert "candidates_created=3" in output


def test_print_legal_template_correlation_result_outputs_summary() -> None:
    result = make_legal_template_correlation_result()

    with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        print_legal_template_correlation_result(result)

    output = fake_stdout.getvalue()
    assert "source=demo_ro_portal_legislativ" in output
    assert "legal_documents_seen=1" in output
    assert "templates_seen=2" in output
    assert "candidates_created=1" in output


def test_print_legal_document_normalization_result_outputs_summary() -> None:
    result = make_legal_document_normalization_result()

    with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        print_legal_document_normalization_result(result)

    output = fake_stdout.getvalue()
    assert "source=ro_portal_legislativ" in output
    assert "inspected=5" in output
    assert "normalized=2" in output
    assert "suppressed_non_legislative=1" in output
    assert "skipped_missing_required_fields=1" in output
    assert "duplicate_unchanged=1" in output
    assert "parser_failed=0" in output


def test_main_once_builds_service_runs_source_and_returns_success() -> None:
    service = FakeRawIngestionService(make_run())

    with patch("underwright.ingestion.cli.build_service", return_value=service):
        with patch("sys.stdout", new=io.StringIO()):
            result = main(["once", "--source-id", "asf_ro", "--limit", "7"])

    assert result == 0
    assert service.source_id == "asf_ro"
    assert service.limit == 7


def test_main_once_maps_legislatie_source_alias() -> None:
    service = FakeRawIngestionService(make_run())

    with patch("underwright.ingestion.cli.build_service", return_value=service):
        with patch("sys.stdout", new=io.StringIO()):
            result = main(["once", "--source", "legislatie-just", "--limit", "20"])

    assert result == 0
    assert service.source_id == "ro_portal_legislativ"
    assert service.limit == 20


def test_main_once_returns_failure_status_when_run_fails() -> None:
    service = FakeRawIngestionService(make_run("failed"))

    with patch("underwright.ingestion.cli.build_service", return_value=service):
        with patch("sys.stdout", new=io.StringIO()):
            result = main(["once", "--source-id", "asf_ro"])

    assert result == 1


def test_main_preview_builds_service_previews_source_and_returns_success() -> None:
    service = FakeRawIngestionService(make_run())

    with patch("underwright.ingestion.cli.build_service", return_value=service):
        with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            result = main(["preview", "--source-id", "asf_ro", "--limit", "7"])

    assert result == 0
    assert service.preview_source_id == "asf_ro"
    assert service.preview_limit == 7
    assert "accepted url=https://asfromania.ro/item" in fake_stdout.getvalue()


def test_main_process_builds_service_processes_batch_and_returns_success() -> None:
    service = FakeProcessingService(make_processing_result())

    with patch(
        "underwright.ingestion.cli.build_processing_service",
        return_value=service,
    ):
        with patch("sys.stdout", new=io.StringIO()):
            result = main(["process", "--limit", "25", "--source-id", "asf_ro"])

    assert result == 0
    assert service.limit == 25
    assert service.source_id == "asf_ro"


def test_main_process_returns_failure_status_when_processing_fails() -> None:
    service = FakeProcessingService(make_processing_result("failed"))

    with patch(
        "underwright.ingestion.cli.build_processing_service",
        return_value=service,
    ):
        with patch("sys.stdout", new=io.StringIO()):
            result = main(["process"])

    assert result == 1


def test_main_correlate_templates_runs_batch_and_returns_success() -> None:
    service = FakeTemplateCorrelationService(make_template_correlation_result())

    with patch(
        "underwright.ingestion.cli.build_template_correlation_service",
        return_value=service,
    ):
        with patch("sys.stdout", new=io.StringIO()):
            result = main(
                ["correlate-templates", "--limit", "25", "--source-id", "asf_ro"]
            )

    assert result == 0
    assert service.limit == 25
    assert service.source_id == "asf_ro"


def test_main_correlate_templates_returns_failure_status_when_batch_fails() -> None:
    service = FakeTemplateCorrelationService(make_template_correlation_result("failed"))

    with patch(
        "underwright.ingestion.cli.build_template_correlation_service",
        return_value=service,
    ):
        with patch("sys.stdout", new=io.StringIO()):
            result = main(["correlate-templates"])

    assert result == 1


def test_main_correlate_legal_templates_runs_batch_and_returns_success() -> None:
    service = FakeLegalTemplateCorrelationService(
        make_legal_template_correlation_result()
    )

    with patch(
        "underwright.ingestion.cli.build_legal_template_correlation_service",
        return_value=service,
    ):
        with patch("sys.stdout", new=io.StringIO()):
            result = main(
                [
                    "correlate-legal-templates",
                    "--limit",
                    "25",
                    "--source-id",
                    "demo_ro_portal_legislativ",
                ]
            )

    assert result == 0
    assert service.limit == 25
    assert service.source_id == "demo_ro_portal_legislativ"


def test_main_correlate_legal_templates_returns_failure_when_batch_fails() -> None:
    service = FakeLegalTemplateCorrelationService(
        make_legal_template_correlation_result("failed")
    )

    with patch(
        "underwright.ingestion.cli.build_legal_template_correlation_service",
        return_value=service,
    ):
        with patch("sys.stdout", new=io.StringIO()):
            result = main(["correlate-legal-templates"])

    assert result == 1


def test_main_normalize_legal_documents_calls_service_and_passes_limit() -> None:
    service = FakeLegalDocumentNormalizationService(
        make_legal_document_normalization_result()
    )

    with patch(
        "underwright.ingestion.cli.build_legal_document_normalization_service",
        return_value=service,
    ):
        with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            result = main(
                [
                    "normalize-legal-documents",
                    "--limit",
                    "25",
                    "--source-id",
                    "ro_portal_legislativ",
                ]
            )

    assert result == 0
    assert service.limit == 25
    assert service.source_id == "ro_portal_legislativ"
    assert "inspected=5" in fake_stdout.getvalue()


def test_main_normalize_legal_documents_keeps_parser_failures_non_fatal() -> None:
    service = FakeLegalDocumentNormalizationService(
        make_legal_document_normalization_result("failed")
    )

    with patch(
        "underwright.ingestion.cli.build_legal_document_normalization_service",
        return_value=service,
    ):
        with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            result = main(["normalize-legal-documents"])

    assert result == 0
    assert "status=failed" in fake_stdout.getvalue()
    assert "parser_failed=1" in fake_stdout.getvalue()


def test_main_normalize_legal_documents_fails_when_service_raises() -> None:
    service = FakeLegalDocumentNormalizationService(error=RuntimeError("db down"))

    with patch(
        "underwright.ingestion.cli.build_legal_document_normalization_service",
        return_value=service,
    ):
        with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            result = main(["normalize-legal-documents"])

    assert result == 1
    assert "status=failed" in fake_stdout.getvalue()
    assert "error_details=db down" in fake_stdout.getvalue()
