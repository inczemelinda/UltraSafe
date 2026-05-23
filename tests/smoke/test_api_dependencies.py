from underwright.api.dependencies import get_quote_workflow
import underwright.cli
from underwright.application.workflows.quote_workflow import QuoteWorkflow
from underwright.composition import (
    build_quote_workflow,
    build_supplementary_text_generator,
)


def test_build_supplementary_text_generator_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert build_supplementary_text_generator() is None


def test_build_quote_workflow_returns_workflow():
    workflow = build_quote_workflow()

    assert isinstance(workflow, QuoteWorkflow)
    assert workflow.quote_request_service is not None
    assert workflow.template_service is not None
    assert workflow.case_context_service is not None
    assert workflow.audit_service is not None

def test_cli_imports():
    assert callable(underwright.cli.build_quote_workflow)


def test_api_dependencies_import_without_db_connection():
    assert callable(get_quote_workflow)
