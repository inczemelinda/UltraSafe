from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
import re
from typing import Any
import unicodedata
from uuid import uuid4

from underwright.application.services.legal_reference_extraction_service import (
    LegalReferenceExtractionService,
)
from underwright.domain.intelligence import RawSourceItem, Source
from underwright.domain.legal_intelligence import (
    NormalizedLegalDocument,
    SuppressionResult,
)


_RO_MONTHS = {
    "ianuarie": 1,
    "februarie": 2,
    "martie": 3,
    "aprilie": 4,
    "mai": 5,
    "iunie": 6,
    "iulie": 7,
    "august": 8,
    "septembrie": 9,
    "octombrie": 10,
    "noiembrie": 11,
    "decembrie": 12,
}
_EN_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


class _DeterministicLegalDocumentParser:
    parser_id: str
    jurisdiction: str
    issuer: str
    publication_reference_pattern: re.Pattern[str]

    def __init__(self) -> None:
        self.reference_service = LegalReferenceExtractionService()

    def parse(
        self,
        raw_item: RawSourceItem,
        source: Source,
    ) -> NormalizedLegalDocument | SuppressionResult:
        text = raw_item.extracted_text.strip()
        references = self._references(raw_item, text)
        main_reference = self._metadata_reference(raw_item) or self._main_reference(
            references
        )
        if main_reference is None:
            return self._suppressed(raw_item, source, "No supported legal act found.")

        instrument = self._instrument_from_reference(main_reference)
        relationships = self.reference_service.extract_amendment_relationships(text)
        amends = [
            reference
            for reference in relationships["amends"]
            if reference != main_reference
        ]
        repeals = [
            reference
            for reference in relationships["repeals"]
            if reference != main_reference
        ]
        now = datetime.now(UTC)
        full_text = self._full_text(raw_item, text)
        structured_clauses = self._structured_clauses(raw_item, full_text)

        return NormalizedLegalDocument(
            id=uuid4(),
            raw_source_item_id=raw_item.raw_item_id,
            source_id=raw_item.source_id,
            source_key=main_reference,
            jurisdiction=self.jurisdiction,
            parser_id=self.parser_id,
            canonical_url=raw_item.canonical_url,
            source_url=raw_item.original_url,
            external_identifier=main_reference,
            title=self._title(raw_item, text),
            language=source.language,
            issuer=self._issuer(raw_item),
            instrument_type=self._instrument_type(raw_item, instrument),
            instrument_number=self._instrument_number(raw_item, instrument),
            instrument_year=self._instrument_year(raw_item, instrument),
            instrument_date=self._instrument_date(raw_item),
            publication_reference=self._publication_reference_for(raw_item, text),
            publication_date=self._publication_date_for(raw_item, text),
            effective_date=self._effective_date_for(raw_item, text),
            status="in_force",
            legal_references=self._reference_dicts(references),
            structured_clauses=structured_clauses,
            amends=self._reference_dicts(amends),
            repeals=self._reference_dicts(repeals),
            full_text=full_text,
            summary=None,
            document_hash=self._document_hash(full_text),
            extraction_confidence=self._extraction_confidence(text, relationships),
            parser_warnings=[],
            source_metadata=self._source_metadata(
                raw_item,
                source,
                text,
                structured_clauses,
            ),
            created_at=now,
            updated_at=now,
        )

    def _references(self, raw_item: RawSourceItem, text: str) -> list[str]:
        references = self.reference_service.extract_references(text)
        metadata_references = raw_item.metadata_json.get("legal_references") or []
        if isinstance(metadata_references, list):
            references.extend(
                reference
                for reference in metadata_references
                if isinstance(reference, str)
            )
        metadata_reference = self._metadata_reference(raw_item)
        if metadata_reference is not None:
            references.insert(0, metadata_reference)
        return self._dedupe(references)

    def _metadata_reference(self, raw_item: RawSourceItem) -> str | None:
        if self.jurisdiction != "RO":
            return None
        act_type = self._metadata_act_type(raw_item)
        act_number = raw_item.metadata_json.get("act_number")
        act_date = self._instrument_date(raw_item)
        if not act_type or not act_number or act_date is None:
            return None
        return f"ro:{act_type}:{act_number}:{act_date.year}"

    def _main_reference(self, references: list[str]) -> str | None:
        for reference in references:
            if reference.startswith(self._reference_prefix()):
                return reference
        return None

    def _reference_prefix(self) -> str:
        raise NotImplementedError

    def _instrument_from_reference(self, reference: str) -> dict[str, str]:
        raise NotImplementedError

    def _publication_date(self, text: str) -> date | None:
        return None

    def _effective_date(self, text: str) -> date | None:
        return None

    def _issuer(self, raw_item: RawSourceItem) -> str:
        issuer = raw_item.metadata_json.get("issuer")
        if isinstance(issuer, str) and issuer.strip():
            return issuer.strip()
        return self.issuer

    def _instrument_type(
        self,
        raw_item: RawSourceItem,
        instrument: dict[str, str],
    ) -> str:
        return self._metadata_act_type(raw_item) or instrument["instrument_type"]

    def _instrument_number(
        self,
        raw_item: RawSourceItem,
        instrument: dict[str, str],
    ) -> str:
        act_number = raw_item.metadata_json.get("act_number")
        if isinstance(act_number, str) and act_number.strip():
            return act_number.strip()
        return instrument["instrument_number"]

    def _instrument_year(
        self,
        raw_item: RawSourceItem,
        instrument: dict[str, str],
    ) -> int:
        instrument_date = self._instrument_date(raw_item)
        if instrument_date is not None:
            return instrument_date.year
        return int(instrument["instrument_year"])

    def _instrument_date(self, raw_item: RawSourceItem) -> date | None:
        return self._date_value(raw_item.metadata_json.get("act_date"))

    def _publication_reference_for(
        self,
        raw_item: RawSourceItem,
        text: str,
    ) -> str | None:
        publication_details = raw_item.metadata_json.get("publication_details")
        if isinstance(publication_details, str) and publication_details.strip():
            return publication_details.strip()
        return self._publication_reference(text)

    def _publication_date_for(
        self,
        raw_item: RawSourceItem,
        text: str,
    ) -> date | None:
        publication_details = raw_item.metadata_json.get("publication_details")
        if isinstance(publication_details, str):
            parsed = self._parse_ro_date(publication_details)
            if parsed is not None:
                return parsed
        return self._publication_date(text)

    def _effective_date_for(
        self,
        raw_item: RawSourceItem,
        text: str,
    ) -> date | None:
        effective_date = self._date_value(raw_item.metadata_json.get("effective_date"))
        if effective_date is not None:
            return effective_date
        return self._effective_date(text)

    def _publication_reference(self, text: str) -> str | None:
        match = self.publication_reference_pattern.search(text)
        return match.group(1).strip() if match else None

    def _extraction_confidence(
        self,
        text: str,
        relationships: dict[str, list[str]],
    ) -> float:
        confidence = 0.78
        if self._publication_reference(text):
            confidence += 0.08
        if self._effective_date(text):
            confidence += 0.06
        if relationships["amends"] or relationships["repeals"]:
            confidence += 0.04
        return min(confidence, 0.96)

    def _title(self, raw_item: RawSourceItem, text: str) -> str:
        title = raw_item.title.strip()
        if title:
            return title
        return next(line.strip() for line in text.splitlines() if line.strip())

    def _full_text(self, raw_item: RawSourceItem, text: str) -> str:
        if raw_item.metadata_json.get("extractor_id") != "legislatie_just":
            return text

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if self._article_match(line):
                return "\n".join(lines[index:])
        return "\n".join(
            line for line in lines if not self._is_legislatie_metadata_line(line)
        )

    def _structured_clauses(
        self,
        raw_item: RawSourceItem,
        full_text: str,
    ) -> list[dict[str, Any]]:
        clauses: list[dict[str, Any]] = []
        current_title: str | None = None
        current_text: list[str] = []

        for line in [line.strip() for line in full_text.splitlines() if line.strip()]:
            if self._article_match(line):
                if current_title is not None:
                    clauses.append(
                        self._clause(
                            title=current_title,
                            text=current_text,
                            order=len(clauses) + 1,
                        )
                    )
                current_title = line
                current_text = []
                continue
            if current_title is not None:
                current_text.append(line)

        if current_title is not None:
            clauses.append(
                self._clause(
                    title=current_title,
                    text=current_text,
                    order=len(clauses) + 1,
                )
            )

        if clauses:
            return clauses

        metadata_articles = raw_item.metadata_json.get("articles") or []
        if not isinstance(metadata_articles, list):
            return []
        return [
            {
                "clause_id": str(article.get("article_id") or ""),
                "title": str(article.get("title") or ""),
                "text": "",
                "order": int(article.get("order") or index + 1),
            }
            for index, article in enumerate(metadata_articles)
            if isinstance(article, dict)
        ]

    def _clause(
        self,
        *,
        title: str,
        text: list[str],
        order: int,
    ) -> dict[str, Any]:
        return {
            "clause_id": title,
            "title": title,
            "text": " ".join(text).strip(),
            "order": order,
        }

    def _reference_dicts(self, references: list[str]) -> list[dict[str, str]]:
        return [{"canonical": reference} for reference in references]

    def _document_hash(self, text: str) -> str:
        normalized_text = "\n".join(line.strip() for line in text.splitlines())
        return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

    def _source_metadata(
        self,
        raw_item: RawSourceItem,
        source: Source,
        text: str,
        structured_clauses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        metadata = dict(raw_item.metadata_json)
        metadata.update(
            {
                "source_id": source.source_id,
                "parser_id": self.parser_id,
                "source_config": source.config_json,
                "source_item_id": str(raw_item.raw_item_id),
                "structured_clause_count": len(structured_clauses),
                "synthetic": self._is_synthetic(raw_item, text),
                "dataset": "demo" if self._is_synthetic(raw_item, text) else None,
            }
        )
        return metadata

    def _is_synthetic(self, raw_item: RawSourceItem, text: str) -> bool:
        return "demo" in f"{raw_item.title} {text}".lower()

    def _suppressed(
        self,
        raw_item: RawSourceItem,
        source: Source,
        reason: str,
    ) -> SuppressionResult:
        return SuppressionResult(
            raw_source_item_id=raw_item.raw_item_id,
            source_id=raw_item.source_id,
            parser_id=self.parser_id,
            status="suppressed_non_legislative",
            reason=reason,
            source_metadata={
                "source_id": source.source_id,
                "parser_id": self.parser_id,
                "raw_title": raw_item.title,
                "raw_url": raw_item.original_url,
                "canonical_url": raw_item.canonical_url,
                "synthetic": self._is_synthetic(raw_item, raw_item.extracted_text),
            },
        )

    def _normalize_text(self, text: str) -> str:
        without_diacritics = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        return " ".join(without_diacritics.lower().split())

    def _metadata_act_type(self, raw_item: RawSourceItem) -> str | None:
        act_type = raw_item.metadata_json.get("act_type")
        if not isinstance(act_type, str) or not act_type.strip():
            return None
        normalized = self._normalize_text(act_type).replace(" ", "_")
        mappings = {
            "decizie": "decizie",
            "lege": "lege",
            "ordin": "ordin",
            "norma": "norma-asf"
            if "asf" in self._normalize_text(raw_item.title)
            else "norma",
            "ordonanta": "og",
            "ordonanta_de_urgenta": "oug",
        }
        return mappings.get(normalized, normalized)

    def _date_value(self, value: Any) -> date | None:
        if isinstance(value, date):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return self._parse_ro_date(value)

    def _parse_ro_date(self, value: str) -> date | None:
        normalized = self._normalize_text(value)
        match = re.search(
            r"(?P<day>\d{1,2}) (?P<month>[a-z]+) (?P<year>\d{4})",
            normalized,
        )
        if not match:
            return None
        month = _RO_MONTHS.get(match.group("month"))
        if month is None:
            return None
        try:
            return date(int(match.group("year")), month, int(match.group("day")))
        except ValueError:
            return None

    def _article_match(self, line: str) -> re.Match[str] | None:
        return re.match(r"^\+?\s*Articolul\s+[0-9IVXLCDM]+\b", line, re.IGNORECASE)

    def _is_legislatie_metadata_line(self, line: str) -> bool:
        normalized = self._normalize_text(line)
        return normalized.startswith(
            (
                "emitent:",
                "publicat",
                "data intrarii in vigoare:",
            )
        )

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped = []
        seen = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped


class RoPortalLegislativParser(_DeterministicLegalDocumentParser):
    parser_id = "ro_portal_legislativ"
    jurisdiction = "RO"
    issuer = "Parlamentul Romaniei"
    publication_reference_pattern = re.compile(
        r"(Monitorul Oficial\s+nr\.?\s*\d+/\d{4})",
        re.IGNORECASE,
    )

    def _reference_prefix(self) -> str:
        return "ro:"

    def _instrument_from_reference(self, reference: str) -> dict[str, str]:
        _, instrument_type, number, year = reference.split(":")
        return {
            "instrument_type": instrument_type,
            "instrument_number": number,
            "instrument_year": year,
        }

    def _effective_date(self, text: str) -> date | None:
        normalized_text = self._normalize_text(text)
        match = re.search(
            r"intra in vigoare la data de (?P<day>\d{1,2}) "
            r"(?P<month>[a-z]+) (?P<year>\d{4})",
            normalized_text,
        )
        if not match:
            return None
        month = _RO_MONTHS.get(match.group("month"))
        if month is None:
            return None
        return date(int(match.group("year")), month, int(match.group("day")))


class EuEurlexOjParser(_DeterministicLegalDocumentParser):
    parser_id = "eu_eurlex_oj"
    jurisdiction = "EU"
    issuer = "European Union"
    publication_reference_pattern = re.compile(
        r"(Official Journal of the European Union)",
        re.IGNORECASE,
    )

    def _reference_prefix(self) -> str:
        return "eu:"

    def _instrument_from_reference(self, reference: str) -> dict[str, str]:
        _, instrument_type, year, number = reference.split(":")
        return {
            "instrument_type": instrument_type,
            "instrument_number": number,
            "instrument_year": year,
        }

    def _effective_date(self, text: str) -> date | None:
        match = re.search(
            r"Date of entry into force:\s*(?P<day>\d{1,2}) "
            r"(?P<month>[A-Za-z]+) (?P<year>\d{4})",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        month = _EN_MONTHS.get(match.group("month").lower())
        if month is None:
            return None
        return date(int(match.group("year")), month, int(match.group("day")))
