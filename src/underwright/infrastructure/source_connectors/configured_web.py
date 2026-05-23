from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx

from underwright.domain.intelligence import RawSourceItem, Source
from underwright.infrastructure.source_connectors.legislatie_just import (
    build_raw_source_item_from_detail_html,
)


@dataclass(frozen=True)
class SourcePreviewItem:
    url: str
    accepted: bool
    reason: str
    title: str = ""
    text_chars: int = 0
    attachment_count: int = 0
    item: RawSourceItem | None = None


class _ReadableHtmlParser(HTMLParser):
    _SKIP_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "iframe",
        "header",
        "footer",
        "nav",
        "form",
        "button",
        "select",
        "option",
        "input",
        "textarea",
    }

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.canonical_href: str | None = None
        self.meta_title: str | None = None
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._tag_stack.append(tag)
        attrs_map = {key.lower(): value for key, value in attrs if key}
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag == "a":
            href = attrs_map.get("href")
            if href:
                self.links.append(href)
        if tag == "link":
            rel = (attrs_map.get("rel") or "").lower()
            href = attrs_map.get("href")
            if href and "canonical" in rel:
                self.canonical_href = href
        if tag == "meta":
            name = (attrs_map.get("name") or attrs_map.get("property") or "").lower()
            content = attrs_map.get("content")
            if content and name in {"og:title", "twitter:title"}:
                self.meta_title = self._clean_text(content)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = self._clean_text(data)
            if text:
                current_tag = self._tag_stack[-1] if self._tag_stack else ""
                if current_tag == "title":
                    self.title_parts.append(text)
                if current_tag == "h1":
                    self.h1_parts.append(text)
                self.text_parts.append(text)

    @property
    def text(self) -> str:
        deduped = []
        seen = set()
        for part in self.text_parts:
            if part in seen:
                continue
            seen.add(part)
            deduped.append(part)
        return "\n".join(deduped)

    @property
    def title(self) -> str | None:
        candidates = [
            " ".join(self.h1_parts),
            self.meta_title or "",
            " ".join(self.title_parts),
        ]
        for candidate in candidates:
            cleaned = self._clean_text(candidate)
            if cleaned:
                return cleaned
        return None

    def _clean_text(self, text: str) -> str:
        return " ".join(text.split())


class ConfiguredWebSourceConnector:
    """
    Configured web connector.

    Source-specific URL choices live in Source.config_json; the ingestion
    service only sees normalized RawSourceItem objects.
    """

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=15, follow_redirects=True)

    def fetch_items(
        self,
        source: Source,
        limit: int | None = None,
    ) -> list[RawSourceItem]:
        return [
            preview.item
            for preview in self._preview_items(
                source,
                limit=limit,
                stop_after_accepted=True,
            )
            if preview.accepted and preview.item is not None
        ]

    def preview_items(
        self,
        source: Source,
        limit: int | None = None,
    ) -> list[SourcePreviewItem]:
        return self._preview_items(source, limit=limit, stop_after_accepted=False)

    def _preview_items(
        self,
        source: Source,
        limit: int | None = None,
        stop_after_accepted: bool = False,
    ) -> list[SourcePreviewItem]:
        target_count = limit or int(source.config_json.get("max_items", 20))
        detail_urls = source.config_json.get("detail_urls")
        if detail_urls:
            return [
                self._preview_url(source, self._canonicalize_url(url), list_url=None)
                for url in detail_urls[:target_count]
            ]

        list_url = source.config_json.get("list_url")
        if not list_url:
            raise ValueError("Web source config requires list_url or detail_urls")

        list_response = self.client.get(
            list_url,
            headers=self._request_headers(source),
        )
        list_response.raise_for_status()
        parser = _ReadableHtmlParser()
        parser.feed(list_response.text)

        previews: list[SourcePreviewItem] = []
        accepted_count = 0
        for url in self._candidate_urls(source, list_url, parser):
            preview = self._preview_url(source, url, list_url=list_url)
            previews.append(preview)
            if preview.accepted:
                accepted_count += 1

            if stop_after_accepted and accepted_count >= target_count:
                break
            if not stop_after_accepted and len(previews) >= target_count:
                break

        return previews

    def _candidate_urls(
        self,
        source: Source,
        list_url: str,
        parser: _ReadableHtmlParser,
    ) -> list[str]:
        allow_external = bool(
            source.config_json.get("allow_external_detail_urls", False)
        )
        allowed_hosts = self._allowed_detail_hosts(source, list_url)
        allowed_fragments = source.config_json.get("allowed_path_fragments") or [
            "comunicate",
            "stiri",
            "noutati",
            "consumatori",
        ]
        urls = []
        for href in parser.links:
            url = self._canonicalize_url(urljoin(list_url, href))
            if url in urls:
                continue
            if not self._is_http_url(url):
                continue
            if not allow_external and self._host(url) not in allowed_hosts:
                continue
            if not any(fragment in url.lower() for fragment in allowed_fragments):
                continue
            urls.append(url)

        return urls

    def _preview_url(
        self,
        source: Source,
        url: str,
        list_url: str | None,
    ) -> SourcePreviewItem:
        url_reject_reason = self._url_reject_reason(source, url)
        if url_reject_reason:
            return SourcePreviewItem(
                url=url,
                accepted=False,
                reason=url_reject_reason,
            )

        blocked_path = self._matched_fragment(
            url,
            source.config_json.get("blocked_path_fragments") or [],
        )
        if blocked_path:
            return SourcePreviewItem(
                url=url,
                accepted=False,
                reason=f"blocked path fragment: {blocked_path}",
            )

        try:
            item = self._fetch_detail(source, url)
        except httpx.HTTPError as exc:
            return SourcePreviewItem(
                url=url,
                accepted=False,
                reason=f"detail fetch failed: {exc}",
            )
        reject_reason = self._reject_reason(source, item, list_url)
        accepted = reject_reason is None
        return SourcePreviewItem(
            url=url,
            accepted=accepted,
            reason="accepted" if accepted else reject_reason,
            title=item.title,
            text_chars=len(item.extracted_text),
            attachment_count=len(item.attachments_json),
            item=item if accepted else None,
        )

    def _reject_reason(
        self,
        source: Source,
        item: RawSourceItem,
        list_url: str | None,
    ) -> str | None:
        if list_url and item.canonical_url == self._canonicalize_url(list_url):
            return "canonical URL resolves to list page"

        blocked_title = self._matched_fragment(
            item.title,
            source.config_json.get("blocked_title_fragments") or [],
        )
        if blocked_title:
            return f"blocked title fragment: {blocked_title}"

        source_name = source.name.strip().lower()
        title = item.title.strip().lower()
        if title and title == source_name:
            return "generic source title"

        min_text_chars = int(source.config_json.get("min_text_chars", 0))
        text_chars = len(item.extracted_text)
        if text_chars < min_text_chars:
            return f"text below min_text_chars: {text_chars} < {min_text_chars}"

        required_fragments = source.config_json.get("required_text_fragments") or []
        if required_fragments and not self._matched_fragment(
            f"{item.title}\n{item.extracted_text}",
            required_fragments,
        ):
            return "missing required text fragments"

        return None

    def _fetch_detail(self, source: Source, url: str) -> RawSourceItem:
        response = self.client.get(url, headers=self._request_headers(source))
        response.raise_for_status()
        if self._uses_legislatie_just_extractor(source):
            return build_raw_source_item_from_detail_html(
                source_id=source.source_id,
                url=self._canonicalize_url(url),
                html=response.text,
            )

        parser = _ReadableHtmlParser()
        parser.feed(response.text)
        text = parser.text
        title = parser.title or (text.splitlines()[0] if text else url)
        canonical_url = self._canonicalize_url(url)
        if parser.canonical_href:
            parsed_canonical = self._canonicalize_url(
                urljoin(url, parser.canonical_href)
            )
            if self._host(parsed_canonical) == self._host(url):
                canonical_url = parsed_canonical
        now = datetime.now(UTC)
        return RawSourceItem(
            source_id=source.source_id,
            original_url=url,
            canonical_url=canonical_url,
            fetched_at=now,
            title=title[:300],
            raw_html=response.text,
            extracted_text=text,
            attachments_json=[
                {
                    "url": urljoin(url, href),
                    "filename": href.rsplit("/", 1)[-1],
                    "content_type": "application/pdf",
                    "fetch_status": "pending",
                }
                for href in parser.links
                if href.lower().split("?", 1)[0].endswith(".pdf")
            ],
            content_hash=sha256(response.text.encode("utf-8")).hexdigest(),
            created_at=now,
        )

    def _uses_legislatie_just_extractor(self, source: Source) -> bool:
        return (
            source.config_json.get("extractor_id") == "legislatie_just"
            or source.config_json.get("parser_id") == "ro_portal_legislativ"
        )

    def _request_headers(self, source: Source) -> dict[str, str]:
        user_agent = source.config_json.get("user_agent") or (
            "UnderwrightLegalIngestion/0.1 "
            "(bounded legal source monitoring; contact: local-dev)"
        )
        return {
            "User-Agent": str(user_agent),
            "Accept": "text/html,application/xhtml+xml",
        }

    def _allowed_detail_hosts(self, source: Source, list_url: str) -> set[str]:
        configured_hosts = source.config_json.get("allowed_detail_hosts") or []
        hosts = {self._normalize_host(host) for host in configured_hosts}
        hosts.add(self._host(list_url))
        return {host for host in hosts if host}

    def _canonicalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        query = urlencode(
            [
                (key, value)
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                if not key.lower().startswith("utm_")
            ],
            doseq=True,
        )
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path or "/",
                "",
                query,
                "",
            )
        )

    def _is_http_url(self, url: str) -> bool:
        return urlparse(url).scheme in {"http", "https"}

    def _url_reject_reason(self, source: Source, url: str) -> str | None:
        blocked_pattern = self._matched_url_pattern(
            url,
            source.config_json.get("blocked_url_patterns") or [],
        )
        if blocked_pattern:
            return f"blocked URL pattern: {blocked_pattern}"

        allowed_patterns = source.config_json.get("allowed_url_patterns") or []
        if allowed_patterns and not self._matched_url_pattern(url, allowed_patterns):
            return "missing allowed URL pattern"
        return None

    def _matched_url_pattern(self, url: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            if re.search(pattern, url):
                return pattern
        return None

    def _matched_fragment(self, value: str, fragments: list[str]) -> str | None:
        normalized = value.lower()
        for fragment in fragments:
            if fragment.lower() in normalized:
                return fragment
        return None

    def _host(self, url: str) -> str:
        return self._normalize_host(urlparse(url).netloc)

    def _normalize_host(self, host: str) -> str:
        return host.lower().split("@")[-1].split(":")[0]
