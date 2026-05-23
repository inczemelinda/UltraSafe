from __future__ import annotations

from underwright.application.legal_intelligence_ports import (
    LegalDocumentParserRegistry,
)
from underwright.infrastructure.legal_document_parsers.deterministic import (
    EuEurlexOjParser,
    RoPortalLegislativParser,
)


def build_legal_document_parser_registry() -> LegalDocumentParserRegistry:
    parsers = [
        RoPortalLegislativParser(),
        EuEurlexOjParser(),
    ]
    return LegalDocumentParserRegistry({parser.parser_id: parser for parser in parsers})
