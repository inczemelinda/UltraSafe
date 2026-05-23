from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from underwright.application.services.raw_ingestion_service import RawIngestionService
from underwright.domain.intelligence import IngestionRun, RawSourceItem, Source
from underwright.infrastructure.source_connectors.configured_web import (
    ConfiguredWebSourceConnector,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "legislatie_just"


def _legislatie_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _legislatie_source(**config_overrides) -> Source:
    config = {
        "pipeline_domain": "legal_documents",
        "parser_id": "ro_portal_legislativ",
        "extractor_id": "legislatie_just",
        "list_url": "https://legislatie.just.ro/list",
        "allowed_path_fragments": ["/public/detaliidocument"],
        "allowed_url_patterns": [
            r"^https://legislatie\.just\.ro/(public|Public)/DetaliiDocument/\d+"
        ],
        "max_items": 1,
    }
    config.update(config_overrides)
    return Source(
        source_id="ro_portal_legislativ",
        name="Portal Legislativ Romania",
        country="RO",
        source_type="legal_portal",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json=config,
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )


def test_configured_web_connector_fetches_list_detail_items_and_pdf_links() -> None:
    seen_user_agents: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_user_agents.append(request.headers["User-Agent"])
        if str(request.url) == "https://asfromania.ro/list":
            return httpx.Response(
                200,
            text='<a href="/ro/a/1/comunicate/property-news">item</a>',
        )
        return httpx.Response(
            200,
            text=(
                '<html><head><link rel="canonical" href="/canonical/property-news?utm_source=x"></head>'
                "<body><h1>ASF comunicare locuinte</h1>"
                "<p>Text despre asigurari de locuinte si cutremur.</p>"
                '<a href="/files/document.pdf">PDF</a></body></html>'
            ),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={"list_url": "https://asfromania.ro/list", "max_items": 1},
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    items = connector.fetch_items(source)

    assert len(items) == 1
    assert items[0].canonical_url == "https://asfromania.ro/canonical/property-news"
    assert items[0].title == "ASF comunicare locuinte"
    assert "cutremur" in items[0].extracted_text
    assert items[0].attachments_json[0].url == "https://asfromania.ro/files/document.pdf"
    assert seen_user_agents == [
        "UnderwrightLegalIngestion/0.1 "
        "(bounded legal source monitoring; contact: local-dev)",
        "UnderwrightLegalIngestion/0.1 "
        "(bounded legal source monitoring; contact: local-dev)",
    ]


def test_configured_web_connector_fetches_direct_detail_urls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "<html><body><h1>PAID comunicat</h1>"
                "<p>Informatii despre PAD, inundatii si locuinte.</p>"
                "</body></html>"
            ),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="paid_ro",
        name="PAID Romania",
        country="RO",
        source_type="insurance_pool",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "detail_urls": ["https://www.paidromania.ro/comunicate/"],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    items = connector.fetch_items(source)

    assert len(items) == 1
    assert items[0].source_id == "paid_ro"
    assert items[0].canonical_url == "https://www.paidromania.ro/comunicate/"
    assert "PAD" in items[0].extracted_text


def test_configured_web_connector_uses_custom_allowed_fragments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text=(
                    '<a href="/ignore/one">ignore</a>'
                    '<a href="/alerts/weather">weather</a>'
                ),
            )
        return httpx.Response(
            200,
            text="<html><body><h1>ANM avertizare</h1><p>Cod galben de furtuna.</p></body></html>",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="anm_ro",
        name="ANM",
        country="RO",
        source_type="weather",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "list_url": "https://example.test/list",
            "allowed_path_fragments": ["alerts"],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    items = connector.fetch_items(source)

    assert len(items) == 1
    assert items[0].canonical_url == "https://example.test/alerts/weather"
    assert "furtuna" in items[0].extracted_text


def test_configured_web_connector_allows_matching_url_patterns() -> None:
    fetched_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched_paths.append(request.url.path)
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text='<a href="/Public/DetaliiDocument/2602008">legal act</a>',
            )
        return httpx.Response(
            200,
            text="<html><body><h1>Legea nr. 260/2008</h1><p>Text legal.</p></body></html>",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="ro_portal_legislativ",
        name="Portal Legislativ Romania",
        country="RO",
        source_type="legal_portal",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "list_url": "https://legislatie.just.ro/list",
            "allowed_path_fragments": ["/public/detaliidocument"],
            "allowed_url_patterns": [
                r"^https://legislatie\.just\.ro/(public|Public)/DetaliiDocument/\d+"
            ],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    items = connector.fetch_items(source)

    assert len(items) == 1
    assert items[0].canonical_url == (
        "https://legislatie.just.ro/Public/DetaliiDocument/2602008"
    )
    assert fetched_paths == ["/list", "/Public/DetaliiDocument/2602008"]


def test_configured_web_connector_rejects_non_matching_allowed_url_patterns_before_fetching() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Non-matching detail URL should not be fetched")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="ro_portal_legislativ",
        name="Portal Legislativ Romania",
        country="RO",
        source_type="legal_portal",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "detail_urls": ["https://legislatie.just.ro/Public/DetaliiDocument/not-a-number"],
            "allowed_url_patterns": [
                r"^https://legislatie\.just\.ro/(public|Public)/DetaliiDocument/\d+"
            ],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    preview = connector.preview_items(source)

    assert len(preview) == 1
    assert preview[0].accepted is False
    assert preview[0].reason == "missing allowed URL pattern"
    assert connector.fetch_items(source) == []


def test_configured_web_connector_rejects_discovered_non_matching_allowed_url_patterns_before_fetching() -> None:
    fetched_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched_paths.append(request.url.path)
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text='<a href="/Public/DetaliiDocument/not-a-number">bad legal act</a>',
            )
        raise AssertionError("Non-matching discovered URL should not be fetched")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="ro_portal_legislativ",
        name="Portal Legislativ Romania",
        country="RO",
        source_type="legal_portal",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "list_url": "https://legislatie.just.ro/list",
            "allowed_path_fragments": ["/public/detaliidocument"],
            "allowed_url_patterns": [
                r"^https://legislatie\.just\.ro/(public|Public)/DetaliiDocument/\d+"
            ],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    preview = connector.preview_items(source)

    assert len(preview) == 1
    assert preview[0].accepted is False
    assert preview[0].reason == "missing allowed URL pattern"
    assert fetched_paths == ["/list"]


def test_configured_web_connector_skips_failed_details_and_keeps_fetching() -> None:
    fetched_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched_paths.append(request.url.path)
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text=(
                    '<a href="/ro/a/1/comunicate/broken">broken</a>'
                    '<a href="/ro/a/1/comunicate/working">working</a>'
                ),
            )
        if request.url.path.endswith("/broken"):
            return httpx.Response(500, text="broken")
        return httpx.Response(
            200,
            text="<html><body><h1>ASF comunicare</h1><p>Asigurari PAD.</p></body></html>",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={"list_url": "https://asfromania.ro/list", "max_items": 1},
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    preview = connector.preview_items(source, limit=2)
    items = connector.fetch_items(source)

    assert preview[0].accepted is False
    assert preview[0].reason.startswith("detail fetch failed:")
    assert preview[1].accepted is True
    assert len(items) == 1
    assert items[0].canonical_url == "https://asfromania.ro/ro/a/1/comunicate/working"
    assert fetched_paths == [
        "/list",
        "/ro/a/1/comunicate/broken",
        "/ro/a/1/comunicate/working",
        "/list",
        "/ro/a/1/comunicate/broken",
        "/ro/a/1/comunicate/working",
    ]


def test_configured_web_connector_skips_external_list_links_by_default() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "linkedin.com":
            raise AssertionError("External social link should not be fetched")
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text=(
                    '<a href="https://linkedin.com/company/asf/comunicate">social</a>'
                    '<a href="/ro/a/1/comunicate/property-news">item</a>'
                ),
            )
        return httpx.Response(
            200,
            text="<html><body><h1>ASF comunicare</h1><p>Asigurari de locuinte.</p></body></html>",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={"list_url": "https://asfromania.ro/list", "max_items": 1},
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    items = connector.fetch_items(source)

    assert len(items) == 1
    assert items[0].original_url == "https://asfromania.ro/ro/a/1/comunicate/property-news"


def test_configured_web_connector_rejects_blocked_url_patterns_before_fetching() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text='<a href="/ro/a/1/comunicate/blocked-123">blocked</a>',
            )
        raise AssertionError("Blocked URL pattern should not be fetched")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "list_url": "https://asfromania.ro/list",
            "allowed_path_fragments": ["comunicate"],
            "blocked_url_patterns": [r"blocked-\d+"],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    preview = connector.preview_items(source)

    assert len(preview) == 1
    assert preview[0].accepted is False
    assert preview[0].reason == r"blocked URL pattern: blocked-\d+"
    assert connector.fetch_items(source) == []


def test_configured_web_connector_extracts_readable_text_without_page_chrome() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "<html><head><title>Browser title</title></head><body>"
                "<header>Header navigation</header>"
                "<nav>Menu item</nav>"
                "<form>Login form</form>"
                "<main><h1>ASF comunicare PAD</h1>"
                "<p>Informatii despre asigurari de locuinte si PAD.</p></main>"
                "<footer>Footer links</footer>"
                "</body></html>"
            ),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="paid_ro",
        name="PAID Romania",
        country="RO",
        source_type="insurance_pool",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={"detail_urls": ["https://www.paidromania.ro/comunicate/"]},
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    item = connector.fetch_items(source)[0]

    assert item.title == "ASF comunicare PAD"
    assert "Informatii despre asigurari" in item.extracted_text
    assert "Header navigation" not in item.extracted_text
    assert "Login form" not in item.extracted_text


def test_configured_web_connector_rejects_blocked_paths_before_fetching() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text='<a href="/blocked/comunicate/property-news">blocked</a>',
            )
        raise AssertionError("Blocked detail URL should not be fetched")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "list_url": "https://asfromania.ro/list",
            "allowed_path_fragments": ["comunicate"],
            "blocked_path_fragments": ["/blocked"],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    preview = connector.preview_items(source)

    assert len(preview) == 1
    assert preview[0].accepted is False
    assert preview[0].reason == "blocked path fragment: /blocked"
    assert connector.fetch_items(source) == []


def test_configured_web_connector_rejects_generic_title_from_config() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text='<a href="/ro/a/1/comunicate/consumatori">category</a>',
            )
        return httpx.Response(
            200,
            text=(
                "<html><body><h1>Autoritatea de Supraveghere Financiară - Consumatori</h1>"
                + ("<p>Text lung despre meniuri si navigare. " * 20)
                + "</p></body></html>"
            ),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "list_url": "https://asfromania.ro/list",
            "allowed_path_fragments": ["comunicate"],
            "blocked_title_fragments": ["Consumatori"],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    preview = connector.preview_items(source)

    assert preview[0].accepted is False
    assert preview[0].reason == "blocked title fragment: Consumatori"
    assert connector.fetch_items(source) == []


def test_configured_web_connector_rejects_short_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body><h1>ASF PAD</h1><p>Short.</p></body></html>",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "detail_urls": ["https://asfromania.ro/ro/a/1/comunicate/pad"],
            "min_text_chars": 80,
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    preview = connector.preview_items(source)

    assert preview[0].accepted is False
    assert preview[0].reason.startswith("text below min_text_chars:")
    assert connector.fetch_items(source) == []


def test_configured_web_connector_rejects_missing_required_text_fragments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "<html><body><h1>ASF piata generala</h1>"
                "<p>Informatii administrative fara tema de proprietate.</p>"
                "</body></html>"
            ),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "detail_urls": ["https://asfromania.ro/ro/a/1/comunicate/admin"],
            "required_text_fragments": ["pad", "locuinte"],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    preview = connector.preview_items(source)

    assert preview[0].accepted is False
    assert preview[0].reason == "missing required text fragments"
    assert connector.fetch_items(source) == []


def test_configured_web_connector_rejects_canonical_list_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text='<a href="/ro/a/1/comunicate/list-copy">category</a>',
            )
        return httpx.Response(
            200,
            text=(
                '<html><head><link rel="canonical" href="/list"></head>'
                "<body><h1>ASF comunicare</h1><p>Asigurari de locuinte si PAD.</p></body></html>"
            ),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "list_url": "https://asfromania.ro/list",
            "allowed_path_fragments": ["comunicate"],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    preview = connector.preview_items(source)

    assert preview[0].accepted is False
    assert preview[0].reason == "canonical URL resolves to list page"
    assert connector.fetch_items(source) == []


def test_configured_web_connector_respects_max_items_for_accepted_list_items() -> None:
    fetched_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched_paths.append(request.url.path)
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text=(
                    '<a href="/ro/a/1/comunicate/one">one</a>'
                    '<a href="/ro/a/1/comunicate/two">two</a>'
                ),
            )
        return httpx.Response(
            200,
            text="<html><body><h1>ASF comunicare</h1><p>Asigurari de locuinte.</p></body></html>",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "list_url": "https://asfromania.ro/list",
            "allowed_path_fragments": ["comunicate"],
            "max_items": 1,
        },
        created_at="2026-05-06T10:00:00+00:00",
        updated_at="2026-05-06T10:00:00+00:00",
    )

    items = connector.fetch_items(source)

    assert len(items) == 1
    assert items[0].original_url == "https://asfromania.ro/ro/a/1/comunicate/one"
    assert fetched_paths == ["/list", "/ro/a/1/comunicate/one"]


def test_configured_web_connector_emits_legislatie_raw_source_item() -> None:
    fetched_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched_paths.append(request.url.path)
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text=_legislatie_fixture("listing_decizie_1074.html"),
            )
        return httpx.Response(
            200,
            text=_legislatie_fixture("detail_decizie_1074.html"),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)

    items = connector.fetch_items(_legislatie_source())

    assert len(items) == 1
    item = items[0]
    assert item.source_id == "ro_portal_legislativ"
    assert item.canonical_url == (
        "https://legislatie.just.ro/Public/DetaliiDocument/207887"
    )
    assert item.title.startswith("DECIZIE nr. 1.074 din 4 septembrie 2018")
    assert "Articolul 1" in item.extracted_text
    assert "Se admite excepția de neconstituționalitate" in item.extracted_text
    assert "Print" not in item.extracted_text
    assert item.content_hash
    assert fetched_paths == ["/list", "/Public/DetaliiDocument/207887"]


def test_configured_web_connector_attaches_legislatie_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=_legislatie_fixture("detail_decizie_1074.html"),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ConfiguredWebSourceConnector(client)
    source = _legislatie_source(
        detail_urls=["https://legislatie.just.ro/Public/DetaliiDocument/207887"],
    )

    item = connector.fetch_items(source)[0]

    assert item.metadata_json["extractor_id"] == "legislatie_just"
    assert item.metadata_json["issuer"] == "CURTEA CONSTITUȚIONALĂ"
    assert item.metadata_json["publication_details"] == (
        "Publicat în MONITORUL OFICIAL nr. 144 din 22 februarie 2019"
    )
    assert item.metadata_json["effective_date"] == "2019-02-22"
    assert item.metadata_json["act_type"] == "DECIZIE"
    assert item.metadata_json["act_number"] == "1074"
    assert item.metadata_json["act_date"] == "2018-09-04"
    assert item.metadata_json["legal_references"] == [
        "ro:decizie:1074:2018",
        "ro:lege:47:1992",
    ]
    assert item.metadata_json["article_count"] == 2


def test_legislatie_duplicate_fetches_deduplicate_through_raw_ingestion_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=_legislatie_fixture("detail_decizie_1074.html"),
        )

    source = _legislatie_source(
        detail_urls=[
            "https://legislatie.just.ro/Public/DetaliiDocument/207887",
            "https://legislatie.just.ro/Public/DetaliiDocument/207887",
        ],
        max_items=2,
    )
    raw_repo = _DedupeRawItemRepository()
    service = RawIngestionService(
        source_repository=_SingleSourceRepository(source),
        raw_item_repository=raw_repo,
        ingestion_run_repository=_RecordingRunRepository(),
        connector_registry={
            "web_scrape": ConfiguredWebSourceConnector(
                httpx.Client(transport=httpx.MockTransport(handler))
            )
        },
    )

    run = service.run_once("ro_portal_legislativ")

    assert run.status == "success"
    assert run.raw_items_seen == 2
    assert run.raw_items_created == 1
    assert len(raw_repo.saved_items) == 2
    assert len(raw_repo.seen_urls) == 1
    assert len(raw_repo.seen_hashes) == 1


class _SingleSourceRepository:
    def __init__(self, source: Source) -> None:
        self.source = source

    def get_enabled(self, source_id: str) -> Source:
        if source_id != self.source.source_id:
            raise ValueError(f"Source not found: {source_id}")
        return self.source


class _DedupeRawItemRepository:
    def __init__(self) -> None:
        self.saved_items: list[RawSourceItem] = []
        self.seen_urls: set[tuple[str, str]] = set()
        self.seen_hashes: set[tuple[str, str]] = set()

    def save_if_new(self, item: RawSourceItem) -> bool:
        self.saved_items.append(item)
        url_key = (item.source_id, item.canonical_url)
        hash_key = (item.source_id, item.content_hash)
        if url_key in self.seen_urls or hash_key in self.seen_hashes:
            return False
        self.seen_urls.add(url_key)
        self.seen_hashes.add(hash_key)
        return True


class _RecordingRunRepository:
    def start(self, source_id: str) -> IngestionRun:
        return IngestionRun(
            run_id=uuid4(),
            source_id=source_id,
            status="started",
            started_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
        )

    def finish(
        self,
        run: IngestionRun,
        status: str,
        raw_items_seen: int,
        raw_items_created: int,
        errors: list[str],
    ) -> IngestionRun:
        run.status = status
        run.raw_items_seen = raw_items_seen
        run.raw_items_created = raw_items_created
        run.errors = errors
        run.finished_at = datetime(2026, 5, 7, 9, 1, tzinfo=UTC)
        return run
