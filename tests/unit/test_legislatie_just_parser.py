from __future__ import annotations

from datetime import date
from pathlib import Path

from underwright.infrastructure.source_connectors.legislatie_just import (
    parse_detail_html,
    parse_listing_html,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "legislatie_just"
SOURCE_URL = "https://legislatie.just.ro/Public/DetaliiDocument/207887"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_listing_extraction_returns_search_result_metadata() -> None:
    items = parse_listing_html(
        _fixture("listing_decizie_1074.html"),
        base_url="https://legislatie.just.ro",
    )

    assert len(items) == 1
    item = items[0]
    assert item.title == "DECIZIE 1074 04/09/2018"
    assert "excepția de neconstituționalitate" in item.heading
    assert item.issuer == "CURTEA CONSTITUȚIONALĂ"
    assert (
        item.publication_metadata
        == "Publicat în MONITORUL OFICIAL nr. 144 din 22 februarie 2019"
    )
    assert item.effective_date == date(2019, 2, 22)
    assert item.detail_url == SOURCE_URL


def test_detail_extraction_returns_document_metadata_and_source_url() -> None:
    document = parse_detail_html(
        _fixture("detail_decizie_1074.html"),
        source_url=SOURCE_URL,
    )

    assert document.title.startswith("DECIZIE nr. 1.074 din 4 septembrie 2018")
    assert document.act_type == "DECIZIE"
    assert document.act_number == "1074"
    assert document.act_date == date(2018, 9, 4)
    assert document.issuer == "CURTEA CONSTITUȚIONALĂ"
    assert (
        document.publication_details
        == "Publicat în MONITORUL OFICIAL nr. 144 din 22 februarie 2019"
    )
    assert document.effective_date == date(2019, 2, 22)
    assert document.source_url == SOURCE_URL
    assert "ro:lege:47:1992" in document.legal_references


def test_detail_full_text_is_clean_legal_body_not_raw_html() -> None:
    document = parse_detail_html(
        _fixture("detail_decizie_1074.html"),
        source_url=SOURCE_URL,
    )

    assert "<html" not in document.full_text.lower()
    assert "<section" not in document.full_text.lower()
    assert "Se admite excepția de neconstituționalitate" in document.full_text
    assert "Curtea Constituțională" in document.full_text


def test_detail_extracts_ordered_articles_and_preserves_diacritics() -> None:
    document = parse_detail_html(
        _fixture("detail_decizie_1074.html"),
        source_url=SOURCE_URL,
    )

    assert [article.article_id for article in document.articles] == [
        "Articolul 1",
        "Articolul 2",
    ]
    assert [article.order for article in document.articles] == [1, 2]
    assert "neconstituționalitate" in document.articles[0].text
    assert "României" in document.articles[1].text
    assert document.full_text.index("Articolul 1") < document.full_text.index(
        "Articolul 2"
    )


def test_detail_excludes_navigation_button_and_page_chrome_text() -> None:
    document = parse_detail_html(
        _fixture("detail_decizie_1074.html"),
        source_url=SOURCE_URL,
    )

    assert "Căutare" not in document.full_text
    assert "Meniul principal" not in document.full_text
    assert "Vizualizează" not in document.full_text
    assert "Print" not in document.full_text
    assert "Legislatie.just.ro" not in document.full_text


def test_detail_ignores_invalid_effective_date_without_failing() -> None:
    html = _fixture("detail_decizie_1074.html").replace(
        "Data intrării în vigoare: 22 februarie 2019",
        "Data intrării în vigoare: 31 februarie 2019",
    )

    document = parse_detail_html(html, source_url=SOURCE_URL)

    assert document.effective_date is None
    assert document.title.startswith("DECIZIE nr. 1.074")


def test_detail_extracts_live_span_based_legal_body_without_page_controls() -> None:
    html = """
    <html><body>
      <div>Cuprins Versiune Beta A fost lansata versiunea Beta</div>
      <div class="document_info">
        <span class="S_DEN">LEGE nr. 236 din 5 octombrie 2018</span>
        <span class="S_HDR">privind distribuția de asigurări</span>
        <span>EMITENT</span><span>PARLAMENTUL ROMÂNIEI</span>
        <span>Publicat în </span><span class="S_PUB_BDY">MONITORUL OFICIAL nr. 853 din 8 octombrie 2018</span>
        <span class="S_PAR">Parlamentul României adoptă prezenta lege.</span>
        <span class="S_ART">
          <span class="TAG_COLLAPSED"> + </span>
          <span class="S_ART_TTL">Articolul 1</span>
          <span class="S_ART_DEN">Domeniul de aplicare</span>
          <span class="S_ART_BDY">
            <span class="S_ALN_TTL">(1)</span>
            <span class="S_ALN_BDY">Prezenta lege reglementează distribuția produselor de asigurare.</span>
          </span>
        </span>
        <span class="S_ART">
          <span class="S_ART_TTL">Articolul 2</span>
          <span class="S_ART_BDY">Autoritatea competentă este Autoritatea de Supraveghere Financiară.</span>
        </span>
      </div>
      <span>Reveniti in topul paginii</span>
      <span>Forma printabilă</span>
      <span style="display:none">text ascuns de navigație</span>
    </body></html>
    """

    document = parse_detail_html(
        html,
        source_url="https://legislatie.just.ro/Public/DetaliiDocument/257093",
    )

    assert document.title == (
        "LEGE nr. 236 din 5 octombrie 2018 privind distribuția de asigurări"
    )
    assert document.issuer == "PARLAMENTUL ROMÂNIEI"
    assert (
        document.publication_details
        == "Publicat în MONITORUL OFICIAL nr. 853 din 8 octombrie 2018"
    )
    assert [article.article_id for article in document.articles] == [
        "Articolul 1",
        "Articolul 2",
    ]
    assert "distribuția produselor de asigurare" in document.full_text
    assert "Autoritatea de Supraveghere Financiară" in document.full_text
    assert "Reveniti in topul paginii" not in document.full_text
    assert "Forma printabilă" not in document.full_text
    assert "text ascuns" not in document.full_text
