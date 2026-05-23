from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, TypeAlias

from underwright.domain.intelligence import RawSourceItem, Source
from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewCandidate,
    NormalizedLegalDocument,
    SuppressionResult,
)
from underwright.domain.models import Template


LegalDocumentParseResult: TypeAlias = NormalizedLegalDocument | SuppressionResult


class LegalDocumentParser(Protocol):
    parser_id: str

    def parse(
        self,
        raw_item: RawSourceItem,
        source: Source,
    ) -> LegalDocumentParseResult: ...


class LegalDocumentParserRegistry:
    def __init__(self, parsers: Mapping[str, LegalDocumentParser]) -> None:
        self._parsers = dict(parsers)

    def get(self, parser_id: str) -> LegalDocumentParser:
        parser = self._parsers.get(parser_id)
        if parser is None:
            known = ", ".join(sorted(self._parsers)) or "none"
            raise ValueError(
                f"Unknown legal document parser_id: {parser_id}. "
                f"Registered parser_ids: {known}."
            )
        return parser

    def parser_for_source(self, source: Source) -> LegalDocumentParser:
        parser_id = str(source.config_json.get("parser_id") or "").strip()
        if not parser_id:
            raise ValueError(
                f"Legal document source {source.source_id} is missing "
                "config_json.parser_id."
            )
        return self.get(parser_id)


class TemplateChangeSuggestionGenerator(Protocol):
    model_name: str
    model_version: str
    prompt_version: str | None

    def generate(
        self,
        *,
        legal_document: NormalizedLegalDocument,
        template: Template,
        candidate: LegalDocumentTemplateReviewCandidate,
        relevant_template_content: str,
    ) -> dict: ...
