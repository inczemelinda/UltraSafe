from __future__ import annotations

from underwright.infrastructure.pdf.local_storage import LocalPdfArtifactStorage
from underwright.infrastructure.pdf.simple_text_renderer import SimpleTextPdfRenderer


def _utf16_hex(value: str) -> bytes:
    return value.encode("utf-16-be").hex().upper().encode("ascii")


def test_simple_text_pdf_renderer_creates_non_empty_pdf_bytes() -> None:
    pdf_bytes = SimpleTextPdfRenderer().render_text_pdf(
        title="Contract",
        text="First paragraph.\n\nSecond paragraph.",
        metadata={"Template": "PAD_PROPERTY_RO"},
    )

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 500
    assert b"/CIDFontType2" in pdf_bytes
    assert b"/ToUnicode" in pdf_bytes
    assert _utf16_hex("First paragraph.") in pdf_bytes


def test_simple_text_pdf_renderer_normalizes_markdown_list_markers() -> None:
    pdf_bytes = SimpleTextPdfRenderer().render_text_pdf(
        title="Contract",
        text="Lista:\n* risc acoperit",
    )

    assert b"* risc acoperit" not in pdf_bytes
    assert _utf16_hex("\N{BULLET} risc acoperit") in pdf_bytes


def test_simple_text_pdf_renderer_normalizes_old_coverage_ascii_table() -> None:
    pdf_bytes = SimpleTextPdfRenderer().render_text_pdf(
        title="Contract",
        text=(
            "| Categoria     | Suma Asigurata                                         |\r\n"
            "| ------------- | ------------------------------------------------------ |\r\n"
            "| Locuinta      | 350000.0 RON |\r\n"
            "| Bunuri mobile | 350000.0 RON |\r\n"
            "| Total         | 350000.0 RON |"
        ),
    )

    assert b"| Categoria" not in pdf_bytes
    assert _utf16_hex("Suma asigurată totală este de 350000.0 RON.") in pdf_bytes
    assert _utf16_hex(
        "\N{BULLET} suma asigurată pentru locuință: 350000.0 RON;"
    ) in pdf_bytes


def test_simple_text_pdf_renderer_preserves_romanian_diacritics_with_unicode_font() -> None:
    pdf_bytes = SimpleTextPdfRenderer().render_text_pdf(
        title="Poliță",
        text="Asigurătorul plătește locuință și bunuri mobile.",
    )

    assert b"/CIDFontType2" in pdf_bytes
    assert b"/ToUnicode" in pdf_bytes
    assert _utf16_hex("plătește locuință și") in pdf_bytes


def test_local_pdf_artifact_storage_writes_and_reads_configured_root(tmp_path) -> None:
    storage = LocalPdfArtifactStorage(tmp_path)

    key = storage.write("../contract.pdf", b"%PDF-1.4\n")

    assert key == "contract.pdf"
    assert storage.exists(key)
    assert storage.read(key) == b"%PDF-1.4\n"
    assert storage.path_for(key) == tmp_path / "contract.pdf"
