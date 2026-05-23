from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from hashlib import sha256
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import urljoin

from underwright.application.services.legal_reference_extraction_service import (
    LegalReferenceExtractionService,
)
from underwright.domain.intelligence import RawSourceItem


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

_ACT_TYPES = (
    "DECIZIE",
    "LEGE",
    "ORDIN",
    "ORDONANTA",
    "ORDONANTA DE URGENTA",
    "HOTARARE",
    "NORMA",
    "REGULAMENT",
)


@dataclass(frozen=True)
class LegislatieListingItem:
    title: str
    heading: str
    issuer: str | None
    publication_metadata: str | None
    effective_date: date | None
    detail_url: str


@dataclass(frozen=True)
class LegislatieArticle:
    article_id: str
    title: str
    text: str
    order: int


@dataclass(frozen=True)
class LegislatieDetailDocument:
    title: str
    act_type: str | None
    act_number: str | None
    act_date: date | None
    issuer: str | None
    publication_details: str | None
    effective_date: date | None
    full_text: str
    articles: list[LegislatieArticle]
    legal_references: list[str]
    source_url: str


@dataclass
class _Link:
    href: str
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return _clean_text(" ".join(self.text_parts))


@dataclass
class _Block:
    kind: str
    depth: int
    start_index: int = 0
    end_index: int = 0
    text_parts: list[str] = field(default_factory=list)
    links: list[_Link] = field(default_factory=list)


class _LegislatieHtmlParser(HTMLParser):
    _SKIP_TAGS = {
        "aside",
        "button",
        "canvas",
        "footer",
        "form",
        "header",
        "iframe",
        "input",
        "nav",
        "noscript",
        "option",
        "script",
        "select",
        "style",
        "svg",
        "textarea",
        "title",
    }
    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
    _BLOCK_TAGS = {
        "article",
        "div",
        "h1",
        "h2",
        "h3",
        "li",
        "main",
        "p",
        "section",
        "span",
    }

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.result_blocks: list[_Block] = []
        self.content_blocks: list[_Block] = []
        self.article_blocks: list[_Block] = []
        self.links: list[_Link] = []
        self._skip_depth = 0
        self._depth = 0
        self._sequence = 0
        self._line_parts: list[str] = []
        self._open_blocks: list[_Block] = []
        self._open_links: list[_Link] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._depth += 1
        attrs_map = {key.lower(): value or "" for key, value in attrs if key}
        if tag in self._VOID_TAGS:
            if not self._skip_depth and tag in {"br", "hr"}:
                self._flush_line()
            self._depth = max(0, self._depth - 1)
            return
        if self._skip_depth:
            self._skip_depth += 1
            return
        if tag in self._SKIP_TAGS or _is_hidden_or_control(attrs_map):
            self._skip_depth += 1
            return

        kind = self._block_kind(tag, attrs_map)
        if kind:
            self._sequence += 1
            self._open_blocks.append(
                _Block(
                    kind=kind,
                    depth=self._depth,
                    start_index=self._sequence,
                )
            )
        if tag == "a" and attrs_map.get("href"):
            link = _Link(href=attrs_map["href"])
            self._open_links.append(link)
            self.links.append(link)
            for block in self._open_blocks:
                block.links.append(link)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._skip_depth:
            self._skip_depth -= 1
            self._depth -= 1
            return
        if not self._skip_depth:
            if tag == "a" and self._open_links:
                self._open_links.pop()
            if tag in self._BLOCK_TAGS:
                self._flush_line()
            while self._open_blocks and self._open_blocks[-1].depth >= self._depth:
                block = self._open_blocks.pop()
                self._store_block(block)
        self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = _clean_text(data)
        if not text:
            return
        self._line_parts.append(text)
        for block in self._open_blocks:
            block.text_parts.append(text)
        for link in self._open_links:
            link.text_parts.append(text)

    def close(self) -> None:
        self._flush_line()
        super().close()

    def _flush_line(self) -> None:
        line = _clean_text(" ".join(self._line_parts))
        self._line_parts = []
        if line and not _is_chrome_line(line):
            self.lines.append(line)

    def _store_block(self, block: _Block) -> None:
        text = _clean_text(" ".join(block.text_parts))
        if not text:
            return
        self._sequence += 1
        block.end_index = self._sequence
        if block.kind == "result":
            self.result_blocks.append(block)
        elif block.kind == "content":
            self.content_blocks.append(block)
        elif block.kind == "article":
            self.article_blocks.append(block)

    def _block_kind(self, tag: str, attrs: dict[str, str]) -> str | None:
        class_tokens = {
            _ascii_lower(token) for token in attrs.get("class", "").split()
        }
        if "s_art" in class_tokens:
            return "article"
        marker = _ascii_lower(
            " ".join([tag, attrs.get("class", ""), attrs.get("id", "")])
        )
        if any(
            token in marker
            for token in ["search-result", "result-item", "rezultat"]
        ):
            return "result"
        if any(token in marker for token in ["article", "articol"]):
            return "article"
        if any(
            token in marker
            for token in [
                "document-detail",
                "document-body",
                "legal-body",
                "act-content",
                "content_forma_act",
                "document_info",
                "text-document",
                "continut-document",
            ]
        ):
            return "content"
        return None


def parse_listing_html(html: str, *, base_url: str) -> list[LegislatieListingItem]:
    parser = _parse_html(html)
    blocks = parser.result_blocks or [
        _Block(
            kind="result",
            depth=0,
            text_parts=parser.lines,
            links=parser.links,
        )
    ]
    items: list[LegislatieListingItem] = []
    for block in blocks:
        lines = _dedupe_lines(_split_block_lines(block.text_parts))
        detail_url = _detail_url(block.links, base_url)
        if not detail_url:
            continue
        title = _first_act_line(lines)
        heading = _first_heading(lines, title)
        items.append(
            LegislatieListingItem(
                title=title,
                heading=heading,
                issuer=_line_value(lines, "Emitent"),
                publication_metadata=_publication_line(lines),
                effective_date=_effective_date(lines),
                detail_url=detail_url,
            )
        )
    return items


def parse_detail_html(html: str, *, source_url: str) -> LegislatieDetailDocument:
    parser = _parse_html(html)
    content_lines = _content_lines(parser)
    title = _first_heading(content_lines, "")
    act_type, act_number, act_date = _act_fields(title)
    publication_details = _publication_line(content_lines)
    articles = _article_blocks(parser.article_blocks)
    if not articles:
        articles = _articles_from_lines(content_lines)
    full_text = _full_text(content_lines, articles)
    references = LegalReferenceExtractionService().extract_references(
        f"{title}\n{full_text}"
    )
    return LegislatieDetailDocument(
        title=title,
        act_type=act_type,
        act_number=act_number,
        act_date=act_date,
        issuer=_line_value(content_lines, "Emitent"),
        publication_details=publication_details,
        effective_date=_effective_date(content_lines),
        full_text=full_text,
        articles=articles,
        legal_references=references,
        source_url=source_url,
    )


def build_raw_source_item_from_detail_html(
    *,
    source_id: str,
    url: str,
    html: str,
    fetched_at: datetime | None = None,
) -> RawSourceItem:
    document = parse_detail_html(html, source_url=url)
    now = fetched_at or datetime.now(UTC)
    extracted_text = _raw_item_text(document)
    return RawSourceItem(
        source_id=source_id,
        original_url=url,
        canonical_url=url,
        fetched_at=now,
        title=document.title[:300],
        raw_html=html,
        extracted_text=extracted_text,
        metadata_json=_raw_item_metadata(document),
        content_hash=sha256(_hash_text(extracted_text).encode("utf-8")).hexdigest(),
        created_at=now,
    )


def _parse_html(html: str) -> _LegislatieHtmlParser:
    parser = _LegislatieHtmlParser()
    parser.feed(html)
    parser.close()
    return parser


def _content_lines(parser: _LegislatieHtmlParser) -> list[str]:
    content_blocks = parser.content_blocks
    if content_blocks:
        largest = max(content_blocks, key=lambda block: len(block.text_parts))
        return _dedupe_lines(_split_block_lines(largest.text_parts))
    return _dedupe_lines([line for line in parser.lines if not _is_chrome_line(line)])


def _article_blocks(blocks: list[_Block]) -> list[LegislatieArticle]:
    articles: list[LegislatieArticle] = []
    candidate_blocks: list[tuple[_Block, list[str]]] = []
    for block in blocks:
        lines = _dedupe_lines(_split_block_lines(block.text_parts))
        if not lines:
            continue
        match = _article_match(lines[0])
        if not match:
            continue
        candidate_blocks.append((block, lines))
    if candidate_blocks:
        candidate_blocks = [
            (block, lines)
            for block, lines in candidate_blocks
            if not any(
                other_block is not block
                and other_block.start_index < block.start_index
                and block.end_index < other_block.end_index
                for other_block, _other_lines in candidate_blocks
            )
        ]
        candidate_blocks.sort(key=lambda candidate: candidate[0].start_index)
    for _block, lines in candidate_blocks:
        match = _article_match(lines[0])
        if not match:
            continue
        article_id = f"Articolul {match.group('number')}"
        text = _clean_text(" ".join(lines[1:]))
        articles.append(
            LegislatieArticle(
                article_id=article_id,
                title=lines[0],
                text=text,
                order=len(articles) + 1,
            )
        )
    return articles


def _articles_from_lines(lines: list[str]) -> list[LegislatieArticle]:
    articles: list[LegislatieArticle] = []
    current_title: str | None = None
    current_text: list[str] = []
    for line in lines:
        if _article_match(line):
            if current_title is not None:
                articles.append(
                    LegislatieArticle(
                        article_id=_article_id(current_title),
                        title=current_title,
                        text=_clean_text(" ".join(current_text)),
                        order=len(articles) + 1,
                    )
                )
            current_title = line
            current_text = []
            continue
        if current_title is not None:
            current_text.append(line)
    if current_title is not None:
        articles.append(
            LegislatieArticle(
                article_id=_article_id(current_title),
                title=current_title,
                text=_clean_text(" ".join(current_text)),
                order=len(articles) + 1,
            )
        )
    return articles


def _full_text(lines: list[str], articles: list[LegislatieArticle]) -> str:
    if articles:
        article_lines: list[str] = []
        for article in articles:
            article_lines.append(article.title)
            if article.text:
                article_lines.append(article.text)
        return "\n".join(article_lines)
    body_lines = [
        line
        for line in lines
        if not _is_metadata_line(line) and not _is_chrome_line(line)
    ]
    return "\n".join(body_lines)


def _raw_item_text(document: LegislatieDetailDocument) -> str:
    lines = [document.title]
    if document.issuer:
        lines.append(f"Emitent: {document.issuer}")
    if document.publication_details:
        lines.append(document.publication_details)
    if document.effective_date:
        lines.append(f"Data intrarii in vigoare: {document.effective_date.isoformat()}")
    if document.full_text:
        lines.append(document.full_text)
    return "\n".join(lines)


def _raw_item_metadata(document: LegislatieDetailDocument) -> dict[str, object]:
    return {
        "extractor_id": "legislatie_just",
        "issuer": document.issuer,
        "publication_details": document.publication_details,
        "effective_date": _date_value(document.effective_date),
        "act_type": document.act_type,
        "act_number": document.act_number,
        "act_date": _date_value(document.act_date),
        "legal_references": document.legal_references,
        "article_count": len(document.articles),
        "articles": [
            {
                "article_id": article.article_id,
                "title": article.title,
                "order": article.order,
            }
            for article in document.articles
        ],
    }


def _date_value(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _hash_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _detail_url(links: list[_Link], base_url: str) -> str | None:
    for link in links:
        href = link.href
        text = _ascii_lower(link.text)
        if "detaliidocument" in href.lower() or "vizualizeaza" in text:
            return urljoin(base_url, href)
    return None


def _first_act_line(lines: list[str]) -> str:
    for line in lines:
        if _looks_like_act_line(line):
            return line
    return lines[0] if lines else ""


def _first_heading(lines: list[str], fallback: str) -> str:
    for index, line in enumerate(lines):
        if _looks_like_detailed_heading(line):
            return _combined_heading(lines, index)
    for index, line in enumerate(lines):
        if _looks_like_act_line(line):
            return _combined_heading(lines, index)
    return fallback or (lines[0] if lines else "")


def _combined_heading(lines: list[str], index: int) -> str:
    heading = lines[index]
    if index + 1 >= len(lines):
        return heading
    next_line = lines[index + 1]
    normalized_next = _ascii_lower(next_line)
    if (
        normalized_next.startswith(("emitent", "publicat", "data intrarii"))
        or _article_match(next_line)
        or _looks_like_act_line(next_line)
    ):
        return heading
    if normalized_next.startswith(("privind ", "pentru ", "referitoare ")):
        return _clean_text(f"{heading} {next_line}")
    return heading


def _line_value(lines: list[str], label: str) -> str | None:
    prefix = f"{_ascii_lower(label)}:"
    label_key = _ascii_lower(label)
    for index, line in enumerate(lines):
        normalized = _ascii_lower(line)
        if normalized.startswith(prefix):
            return _clean_text(line.split(":", 1)[1])
        if normalized == label_key and index + 1 < len(lines):
            return _clean_text(lines[index + 1])
        if normalized.startswith(f"{label_key} "):
            return _clean_text(line[len(label) :])
    return None


def _publication_line(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        normalized = _ascii_lower(line)
        if normalized.startswith("publicat"):
            joined = line
            if index + 1 < len(lines) and "monitorul oficial" in _ascii_lower(
                lines[index + 1]
            ):
                joined = f"{line} {lines[index + 1]}"
            return _trim_publication_line(joined)
        if "monitorul oficial" in normalized:
            return _trim_publication_line(line)
    return None


def _effective_date(lines: list[str]) -> date | None:
    for line in lines:
        normalized = _ascii_lower(line)
        if "intrarii in vigoare" in normalized or "intra in vigoare" in normalized:
            parsed = _parse_date(line)
            if parsed is not None:
                return parsed
    return None


def _act_fields(title: str) -> tuple[str | None, str | None, date | None]:
    normalized_title = _ascii_upper(title)
    type_match = next(
        (act_type for act_type in _ACT_TYPES if normalized_title.startswith(act_type)),
        None,
    )
    match = re.search(
        r"(?:nr\.?\s*)?(?P<number>[\d.]+)\s+(?:din\s+)?"
        r"(?P<date>\d{1,2}(?:/|\s+)[^,]+?\d{4})",
        title,
        re.IGNORECASE,
    )
    if not match:
        return type_match, None, None
    number = match.group("number").replace(".", "")
    return type_match, number, _parse_date(match.group("date"))


def _parse_date(value: str) -> date | None:
    numeric = re.search(
        r"(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})",
        value,
    )
    if numeric:
        try:
            return date(
                int(numeric.group("year")),
                int(numeric.group("month")),
                int(numeric.group("day")),
            )
        except ValueError:
            return None
    normalized = _ascii_lower(value)
    match = re.search(
        r"(?P<day>\d{1,2})\s+(?P<month>[a-z]+)\s+(?P<year>\d{4})",
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


def _split_block_lines(parts: list[str]) -> list[str]:
    lines: list[str] = []
    for part in parts:
        for line in part.splitlines():
            cleaned = _clean_text(line)
            if cleaned and not _is_chrome_line(cleaned):
                lines.append(cleaned)
    return lines


def _dedupe_lines(lines: list[str]) -> list[str]:
    deduped: list[str] = []
    for line in lines:
        if deduped and deduped[-1] == line:
            continue
        deduped.append(line)
    return deduped


def _article_match(line: str) -> re.Match[str] | None:
    return re.match(
        r"^\+?\s*Articolul\s+(?P<number>[0-9IVXLCDM]+)\b",
        line,
        re.IGNORECASE,
    )


def _article_id(title: str) -> str:
    match = _article_match(title)
    return f"Articolul {match.group('number')}" if match else title


def _looks_like_act_line(line: str) -> bool:
    normalized = _ascii_upper(line)
    return any(normalized.startswith(act_type) for act_type in _ACT_TYPES)


def _looks_like_detailed_heading(line: str) -> bool:
    return _looks_like_act_line(line) and (
        " nr." in _ascii_lower(line) or " din " in _ascii_lower(line)
    )


def _is_metadata_line(line: str) -> bool:
    normalized = _ascii_lower(line)
    return normalized.startswith(("emitent:", "publicat", "data intrarii"))


def _is_chrome_line(line: str) -> bool:
    normalized = _ascii_lower(line)
    chrome_values = {
        "acasa",
        "cautare",
        "cautare avansata",
        "legislatie",
        "legislatie.just.ro",
        "meniul principal",
        "pagina principala",
        "print",
        "forma printabila",
        "reveniti in topul paginii",
        "rezultatele cautarii",
        "vizualizeaza",
    }
    return normalized in chrome_values or normalized.startswith("pagina ")


def _is_hidden_or_control(attrs: dict[str, str]) -> bool:
    marker = _ascii_lower(" ".join([attrs.get("class", ""), attrs.get("style", "")]))
    return (
        "display:none" in marker.replace(" ", "")
        or "tag_collapsed" in marker
        or "_short" in marker
    )


def _trim_publication_line(line: str) -> str:
    match = re.search(
        r"(Publicat(?:ă)?\s+în\s+MONITORUL OFICIAL\s+nr\.?\s*\d+"
        r"\s+din\s+\d{1,2}\s+[A-Za-zăâîșțĂÂÎȘȚ]+"
        r"\s+\d{4})",
        line,
        re.IGNORECASE,
    )
    return _clean_text(match.group(1) if match else line)


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _ascii_lower(value: str) -> str:
    return _ascii(value).lower()


def _ascii_upper(value: str) -> str:
    return _ascii(value).upper()


def _ascii(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


__all__ = [
    "LegislatieArticle",
    "LegislatieDetailDocument",
    "LegislatieListingItem",
    "build_raw_source_item_from_detail_html",
    "parse_detail_html",
    "parse_listing_html",
]
