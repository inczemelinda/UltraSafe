from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

from underwright.application.services.legal_document_quality_service import (
    LegalDocumentQualityExpectation,
    LegalDocumentQualityService,
)
from underwright.application.services.legal_reference_extraction_service import (
    LegalReferenceExtractionService,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentNormalizationResult,
    NormalizedLegalDocument,
)


REFERENCE_SERVICE = LegalReferenceExtractionService()
NOW = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)


def test_quality_report_measures_mvp_ingestion_targets() -> None:
    documents = [
        _make_document(
            raw_source_item_id=UUID("50000000-0000-0000-0000-000000000001"),
            source_key="ro-lege-260-2008",
            title="Legea nr. 260/2008",
            jurisdiction="RO",
            parser_id="ro_portal_legislativ",
            canonical_url="https://legislatie.just.ro/Public/DetaliiDocument/2602008",
            external_identifier="RO-LEGE-260-2008",
            instrument_type="lege",
            instrument_number="260",
            instrument_year=2008,
            publication_date=date(2008, 11, 4),
            effective_date=date(2008, 11, 7),
            full_text=(
                "Legea nr. 260/2008 modifica Legea nr. 132/2017 si "
                "OUG nr.50/2010. Abroga OG nr. 21/1992. "
                "Ordinul ASF nr. 10/2024 si Norma ASF nr. 20/2017 "
                "sunt mentionate ca referinte."
            ),
            document_hash="hash-ro-260",
        ),
        _make_document(
            raw_source_item_id=UUID("50000000-0000-0000-0000-000000000002"),
            source_key="eu-regulation-2024-1234",
            title="Regulation (EU) 2024/1234",
            jurisdiction="EU",
            parser_id="eu_eurlex_oj",
            canonical_url="https://eur-lex.europa.eu/eli/reg/2024/1234/oj",
            external_identifier="CELEX:32024R1234",
            instrument_type="regulation",
            instrument_number="1234",
            instrument_year=2024,
            publication_date=date(2024, 6, 12),
            effective_date=date(2024, 7, 1),
            full_text=(
                "Regulation (EU) 2024/1234 amending Directive (EU) "
                "2023/1234 and repealing Decision (EU) 2024/999. "
                "Regulamentul (UE) 2025/42 is cited for comparison."
            ),
            document_hash="hash-eu-1234",
        ),
        _make_document(
            raw_source_item_id=UUID("50000000-0000-0000-0000-000000000003"),
            source_key="ro-ordin-10-2024",
            title="Ordinul nr. 10/2024",
            jurisdiction="RO",
            parser_id="ro_portal_legislativ",
            canonical_url="https://legislatie.just.ro/Public/DetaliiDocument/10-2024",
            external_identifier="RO-ORDIN-10-2024",
            instrument_type="ordin",
            instrument_number="10",
            instrument_year=2024,
            publication_date=date(2024, 2, 2),
            effective_date=date(2024, 2, 10),
            full_text=(
                "Ordinul nr. 10/2024 pentru modificarea Legii 260 din "
                "2008. Decizia nr.123/2024 completeaza Ordonanta de "
                "urgenta nr. 50/2010."
            ),
            document_hash="hash-ro-ordin-10",
        ),
    ]
    expectations = [
        LegalDocumentQualityExpectation(
            source_key="ro-lege-260-2008",
            legal_references=(
                "ro:lege:260:2008",
                "ro:lege:132:2017",
                "ro:oug:50:2010",
                "ro:og:21:1992",
                "ro:ordin-asf:10:2024",
                "ro:norma-asf:20:2017",
            ),
            amends=("ro:lege:132:2017", "ro:oug:50:2010"),
            repeals=("ro:og:21:1992",),
            publication_date=date(2008, 11, 4),
            instrument_type="lege",
        ),
        LegalDocumentQualityExpectation(
            source_key="eu-regulation-2024-1234",
            legal_references=(
                "eu:regulation:2024:1234",
                "eu:directive:2023:1234",
                "eu:decision:2024:999",
                "eu:regulation:2025:42",
            ),
            amends=("eu:directive:2023:1234",),
            repeals=("eu:decision:2024:999",),
            publication_date=date(2024, 6, 12),
            instrument_type="regulation",
        ),
        LegalDocumentQualityExpectation(
            source_key="ro-ordin-10-2024",
            legal_references=(
                "ro:ordin:10:2024",
                "ro:lege:260:2008",
                "ro:decizie:123:2024",
                "ro:oug:50:2010",
            ),
            amends=("ro:lege:260:2008",),
            publication_date=date(2024, 2, 2),
            instrument_type="ordin",
        ),
    ]

    report = LegalDocumentQualityService().evaluate(
        documents=documents,
        normalization_results=[_normalized_result(document) for document in documents],
        expectations=expectations,
    )

    assert report.metrics["legal_reference_extraction_accuracy"] >= 0.9
    assert report.metrics["required_field_extraction_rate"] == 1.0
    assert report.metrics["legal_reference_extraction_accuracy"] == 1.0
    assert report.metrics["amendment_relationship_accuracy"] == 1.0
    assert report.metrics["publication_date_extraction_accuracy"] == 1.0
    assert report.metrics["instrument_type_accuracy"] == 1.0
    assert report.metrics["deduplication_accuracy"] == 1.0
    assert report.metrics["parser_failure_rate"] == 0.0
    assert report.metrics["normalization_rate"] == 1.0
    assert report.metrics["synthetic_document_marking_rate"] == 1.0


def test_quality_report_flags_duplicates_and_parser_failures() -> None:
    first_document = _make_document(
        raw_source_item_id=UUID("50000000-0000-0000-0000-000000000010"),
        source_key="duplicate-a",
        title="Legea nr. 260/2008",
        jurisdiction="RO",
        parser_id="ro_portal_legislativ",
        canonical_url="https://legislatie.just.ro/Public/DetaliiDocument/2602008",
        external_identifier="RO-LEGE-260-2008",
        instrument_type="lege",
        instrument_number="260",
        instrument_year=2008,
        publication_date=date(2008, 11, 4),
        effective_date=date(2008, 11, 7),
        full_text="Legea nr. 260/2008",
        document_hash="hash-ro-260",
    )
    duplicate_document = first_document.model_copy(
        update={
            "id": UUID("60000000-0000-0000-0000-000000000010"),
            "raw_source_item_id": UUID("50000000-0000-0000-0000-000000000011"),
            "source_key": "duplicate-b",
            "document_hash": "hash-ro-260-again",
        }
    )
    incomplete_document = first_document.model_copy(update={"issuer": None})
    parser_failed_result = LegalDocumentNormalizationResult(
        raw_source_item_id=UUID("50000000-0000-0000-0000-000000000012"),
        source_id="ro_portal_legislativ",
        parser_id="ro_portal_legislativ",
        status="parser_failed",
        reason="Could not parse synthetic fixture.",
        created_at=NOW,
        updated_at=NOW,
    )

    report = LegalDocumentQualityService().evaluate(
        documents=[incomplete_document, duplicate_document],
        normalization_results=[
            _normalized_result(incomplete_document),
            parser_failed_result,
        ],
        expectations=[],
    )

    assert report.metrics["required_field_extraction_rate"] < 1.0
    assert report.metrics["deduplication_accuracy"] == 0.5
    assert report.metrics["parser_failure_rate"] == 0.5
    assert report.metrics["normalization_rate"] == 0.5


def test_current_legal_normalization_stack_does_not_import_ai_classifier() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    legal_stack_files = [
        "src/underwright/application/legal_intelligence_ports.py",
        "src/underwright/application/services/legal_document_quality_service.py",
        "src/underwright/application/services/legal_reference_extraction_service.py",
        "src/underwright/infrastructure/legal_document_parsers/registry.py",
        "src/underwright/infrastructure/legal_document_parsers/deterministic.py",
    ]
    blocked_patterns = (
        "underwright.infrastructure.llm",
        "intelligence_classifier",
        "chat.completions",
    )

    for relative_path in legal_stack_files:
        source_text = (repo_root / relative_path).read_text()
        for blocked_pattern in blocked_patterns:
            assert blocked_pattern not in source_text


def _make_document(
    *,
    raw_source_item_id: UUID,
    source_key: str,
    title: str,
    jurisdiction: str,
    parser_id: str,
    canonical_url: str,
    external_identifier: str,
    instrument_type: str,
    instrument_number: str,
    instrument_year: int,
    publication_date: date,
    effective_date: date,
    full_text: str,
    document_hash: str,
) -> NormalizedLegalDocument:
    relationships = REFERENCE_SERVICE.extract_amendment_relationships(full_text)
    return NormalizedLegalDocument(
        raw_source_item_id=raw_source_item_id,
        source_id=_source_id_for_parser(parser_id),
        source_key=source_key,
        jurisdiction=jurisdiction,
        parser_id=parser_id,
        canonical_url=canonical_url,
        source_url=canonical_url,
        external_identifier=external_identifier,
        title=title,
        language="ro" if jurisdiction == "RO" else "en",
        issuer="Parlamentul Romaniei" if jurisdiction == "RO" else "European Union",
        instrument_type=instrument_type,
        instrument_number=instrument_number,
        instrument_year=instrument_year,
        publication_reference="synthetic publication",
        publication_date=publication_date,
        effective_date=effective_date,
        status="in_force",
        legal_references=_as_reference_dicts(
            REFERENCE_SERVICE.extract_references(full_text)
        ),
        amends=_as_reference_dicts(relationships["amends"]),
        repeals=_as_reference_dicts(relationships["repeals"]),
        full_text=full_text,
        document_hash=document_hash,
        extraction_confidence=1.0,
        source_metadata={"synthetic": True, "dataset": "demo"},
        created_at=NOW,
        updated_at=NOW,
    )


def _as_reference_dicts(canonical_references: list[str]) -> list[dict[str, str]]:
    return [{"canonical": canonical_reference} for canonical_reference in canonical_references]


def _normalized_result(
    document: NormalizedLegalDocument,
) -> LegalDocumentNormalizationResult:
    return LegalDocumentNormalizationResult(
        raw_source_item_id=document.raw_source_item_id,
        source_id=document.source_id,
        parser_id=document.parser_id,
        normalized_legal_document_id=document.id,
        status="normalized",
        created_at=NOW,
        updated_at=NOW,
    )


def _source_id_for_parser(parser_id: str) -> str:
    if parser_id == "eu_eurlex_oj":
        return "eu_eurlex_oj_l_series"
    return "ro_portal_legislativ"
