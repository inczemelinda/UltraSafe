from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from underwright.application.legal_intelligence_ports import (
    LegalDocumentParserRegistry,
)
from underwright.domain.intelligence import RawSourceItem, Source
from underwright.domain.legal_intelligence import (
    NormalizedLegalDocument,
    SuppressionResult,
)
from underwright.infrastructure.legal_document_parsers import (
    build_legal_document_parser_registry,
)
from underwright.infrastructure.source_connectors.legislatie_just import (
    build_raw_source_item_from_detail_html,
)


ROOT = Path(__file__).resolve().parents[2]
LEGISLATIE_FIXTURES = ROOT / "tests/fixtures/legislatie_just"


class RecordingParser:
    parser_id = "recording_parser"

    def __init__(self) -> None:
        self.raw_item = None
        self.source = None

    def parse(
        self,
        raw_item: RawSourceItem,
        source: Source,
    ) -> SuppressionResult:
        self.raw_item = raw_item
        self.source = source
        return SuppressionResult(
            raw_source_item_id=raw_item.raw_item_id,
            source_id=source.source_id,
            parser_id=self.parser_id,
            status="suppressed_non_legislative",
            reason="Recorded parser input.",
            source_metadata={"title": raw_item.title},
        )


def make_source(parser_id: str = "recording_parser") -> Source:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    return Source(
        source_id="ro_portal_legislativ",
        name="Portal Legislativ Romania",
        country="RO",
        source_type="legal_portal",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=False,
        config_json={
            "pipeline_domain": "legal_documents",
            "parser_id": parser_id,
            "jurisdiction": "RO",
        },
        created_at=now,
        updated_at=now,
    )


def make_raw_item() -> RawSourceItem:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)
    return RawSourceItem(
        raw_item_id=UUID("40000000-0000-0000-0000-000000000001"),
        source_id="ro_portal_legislativ",
        original_url="https://legislatie.just.ro/Public/DetaliiDocument/2602008",
        canonical_url="https://legislatie.just.ro/Public/DetaliiDocument/2602008",
        fetched_at=now,
        title="Legea nr. 260/2008",
        raw_html="<html>Legea nr. 260/2008</html>",
        extracted_text="Text extras pentru Legea nr. 260/2008.",
        content_hash="hash-1",
        created_at=now,
    )


def test_registry_selects_parser_from_source_config_and_passes_raw_context() -> None:
    parser = RecordingParser()
    registry = LegalDocumentParserRegistry({parser.parser_id: parser})
    source = make_source()
    raw_item = make_raw_item()

    selected_parser = registry.parser_for_source(source)
    result = selected_parser.parse(raw_item, source)

    assert result.status == "suppressed_non_legislative"
    assert parser.raw_item.raw_html == "<html>Legea nr. 260/2008</html>"
    assert parser.raw_item.extracted_text.startswith("Text extras")
    assert parser.raw_item.original_url.endswith("/2602008")
    assert parser.raw_item.title == "Legea nr. 260/2008"
    assert parser.source.config_json["parser_id"] == "recording_parser"


def test_registry_unknown_parser_id_fails_clearly() -> None:
    registry = LegalDocumentParserRegistry({})

    with pytest.raises(ValueError, match="Unknown legal document parser_id: missing"):
        registry.get("missing")


def test_registry_missing_source_parser_id_fails_clearly() -> None:
    registry = LegalDocumentParserRegistry({})
    source = make_source(parser_id="")

    with pytest.raises(ValueError, match="missing config_json.parser_id"):
        registry.parser_for_source(source)


def test_default_registry_wires_required_deterministic_parsers() -> None:
    registry = build_legal_document_parser_registry()
    raw_item = make_raw_item()

    ro_result = registry.parser_for_source(make_source("ro_portal_legislativ")).parse(
        raw_item,
        make_source("ro_portal_legislativ"),
    )
    eu_result = registry.parser_for_source(make_source("eu_eurlex_oj")).parse(
        raw_item,
        make_source("eu_eurlex_oj"),
    )

    assert isinstance(ro_result, NormalizedLegalDocument)
    assert ro_result.parser_id == "ro_portal_legislativ"
    assert ro_result.jurisdiction == "RO"
    assert eu_result.status == "suppressed_non_legislative"
    assert eu_result.parser_id == "eu_eurlex_oj"


def test_default_registry_normalizes_legislatie_just_raw_item_metadata() -> None:
    registry = build_legal_document_parser_registry()
    raw_item = build_raw_source_item_from_detail_html(
        source_id="ro_portal_legislativ",
        url="https://legislatie.just.ro/Public/DetaliiDocument/207887",
        html=(LEGISLATIE_FIXTURES / "detail_decizie_1074.html").read_text(
            encoding="utf-8"
        ),
        fetched_at=datetime(2026, 5, 11, 10, 0, tzinfo=UTC),
    )

    result = registry.parser_for_source(make_source("ro_portal_legislativ")).parse(
        raw_item,
        make_source("ro_portal_legislativ"),
    )

    assert isinstance(result, NormalizedLegalDocument)
    assert result.source_key == "ro:decizie:1074:2018"
    assert result.external_identifier == "ro:decizie:1074:2018"
    assert result.instrument_type == "decizie"
    assert result.instrument_number == "1074"
    assert result.instrument_date is not None
    assert result.issuer == "CURTEA CONSTITUȚIONALĂ"
    assert [clause["clause_id"] for clause in result.structured_clauses] == [
        "Articolul 1",
        "Articolul 2",
    ]
