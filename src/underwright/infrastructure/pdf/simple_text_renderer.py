from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import re
import struct
import textwrap
from typing import Literal
import unicodedata


Alignment = Literal["left", "center"]


@dataclass(frozen=True)
class _StyledLine:
    text: str
    font: str = "F1"
    size: float = 10.2
    leading: float = 14.5
    align: Alignment = "left"
    indent: float = 0
    before: float = 0
    after: float = 0
    color: str = "0.08 0.12 0.20"


@dataclass(frozen=True)
class _PlacedLine:
    line: _StyledLine
    y: float


@dataclass(frozen=True)
class _TrueTypeFont:
    name: str
    data: bytes
    units_per_em: int
    ascent: int
    descent: int
    bbox: tuple[int, int, int, int]
    advance_widths: tuple[int, ...]
    cmap: dict[int, int]

    def glyph_id(self, codepoint: int) -> int:
        return self.cmap.get(codepoint, 0)

    def width(self, codepoint: int) -> int:
        glyph_id = self.glyph_id(codepoint)
        if not self.advance_widths:
            return 500
        if glyph_id >= len(self.advance_widths):
            glyph_id = 0
        return max(1, round(self.advance_widths[glyph_id] * 1000 / self.units_per_em))


class SimpleTextPdfRenderer:
    """Dependency-free renderer for persisted contract text.

    The output stays intentionally small, but contract documents get the layout
    rules the UI was previously faking: centered policy titles, bold chapter and
    article headings, readable spacing, and normalized bullet lists.
    """

    renderer_version = "contract-document-v4-unicode"

    _PAGE_WIDTH = 595.0
    _PAGE_HEIGHT = 842.0
    _MARGIN_X = 54.0
    _TOP_Y = 790.0
    _BOTTOM_Y = 54.0
    _CONTENT_WIDTH = _PAGE_WIDTH - (_MARGIN_X * 2)
    _CUSTOM_CHAR_CODES = {
        "\u0102": 128,
        "\u0103": 129,
        "\u0218": 130,
        "\u0219": 131,
        "\u021a": 132,
        "\u021b": 133,
        "\u00c2": 134,
        "\u00e2": 135,
        "\u00ce": 136,
        "\u00ee": 137,
        "\N{BULLET}": 138,
        "\u201e": 139,
        "\u201d": 140,
        "\u015e": 141,
        "\u015f": 142,
        "\u0162": 143,
        "\u0163": 144,
    }
    _FONT_ENCODING_DIFFERENCES = (
        "[128 /Abreve /abreve /Scommaaccent /scommaaccent "
        "/Tcommaaccent /tcommaaccent /Acircumflex /acircumflex "
        "/Icircumflex /icircumflex /bullet /quotedblbase "
        "/quotedblright /Scedilla /scedilla /Tcedilla /tcedilla]"
    )

    _MARKDOWN_BULLET_PATTERN = re.compile(r"(?m)^([ \t]*)\* ")
    _COVERAGE_TABLE_PATTERN = re.compile(
        r"(?m)^[ \t]*\|\s*Categoria\s*\|[^\r\n]*\|\s*\r?\n"
        r"^[ \t]*\|\s*-+\s*\|\s*-+\s*\|\s*\r?\n"
        r"^[ \t]*\|\s*Locuin[^|]*\|\s*([^|\r\n]+?)\s*\|\s*\r?\n"
        r"^[ \t]*\|\s*Bunuri mobile\s*\|\s*([^|\r\n]+?)\s*\|\s*\r?\n"
        r"^[ \t]*\|\s*Total\s*\|\s*([^|\r\n]+?)\s*\|"
    )

    def render_text_pdf(
        self,
        *,
        title: str,
        text: str,
        metadata: dict | None = None,
    ) -> bytes:
        styled_lines = self._styled_lines(
            title=title,
            text=text,
            metadata=metadata or {},
        )
        pages = self._paginate(styled_lines)
        return self._build_pdf(pages)

    def _styled_lines(
        self,
        *,
        title: str,
        text: str,
        metadata: dict,
    ) -> list[_StyledLine]:
        lines: list[_StyledLine] = []

        if title.strip():
            lines.extend(
                self._wrapped_lines(
                    title.strip(),
                    font="F2",
                    size=14.0,
                    leading=17.0,
                    align="center",
                    color="0.05 0.18 0.52",
                    after=4.0,
                )
            )

        metadata_lines = [
            f"{key}: {value}"
            for key, value in metadata.items()
            if value is not None and value != ""
        ]
        for metadata_line in metadata_lines:
            lines.extend(
                self._wrapped_lines(
                    metadata_line,
                    size=8.4,
                    leading=11.0,
                    align="center",
                    color="0.38 0.46 0.58",
                )
            )
        if title.strip() or metadata_lines:
            lines.append(_StyledLine("", leading=12.0))

        normalized_text = self._normalize_document_text(text)
        for raw_line in normalized_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            trimmed = raw_line.strip()
            if not trimmed:
                lines.append(_StyledLine("", leading=8.0))
                continue

            if self._is_centered_contract_title(trimmed):
                lines.extend(
                    self._wrapped_lines(
                        trimmed,
                        font="F2",
                        size=15.0,
                        leading=18.0,
                        align="center",
                        before=4.0,
                        after=2.0,
                    )
                )
                continue

            if self._is_contract_chapter_heading(trimmed):
                lines.extend(
                    self._wrapped_lines(
                        trimmed,
                        font="F2",
                        size=12.2,
                        leading=15.5,
                        before=12.0,
                        after=3.0,
                    )
                )
                continue

            if self._is_contract_article_heading(trimmed):
                lines.extend(
                    self._wrapped_lines(
                        trimmed,
                        font="F2",
                        size=10.8,
                        leading=14.0,
                        before=7.0,
                        after=1.5,
                    )
                )
                continue

            if trimmed.startswith("\N{BULLET} "):
                lines.extend(self._bullet_lines(trimmed[2:]))
                continue

            lines.extend(self._wrapped_lines(raw_line.strip()))

        return lines or [_StyledLine("")]

    def _wrapped_lines(
        self,
        text: str,
        *,
        font: str = "F1",
        size: float = 10.2,
        leading: float = 14.5,
        align: Alignment = "left",
        indent: float = 0,
        before: float = 0,
        after: float = 0,
        color: str = "0.08 0.12 0.20",
    ) -> list[_StyledLine]:
        width = self._CONTENT_WIDTH - indent
        max_chars = max(24, int(width / (size * 0.48)))
        wrapped = textwrap.wrap(
            text,
            width=max_chars,
            break_long_words=False,
            replace_whitespace=False,
        ) or [text]

        return [
            _StyledLine(
                line,
                font=font,
                size=size,
                leading=leading,
                align=align,
                indent=indent,
                before=before if index == 0 else 0,
                after=after if index == len(wrapped) - 1 else 0,
                color=color,
            )
            for index, line in enumerate(wrapped)
        ]

    def _bullet_lines(self, text: str) -> list[_StyledLine]:
        width = self._CONTENT_WIDTH - 18
        max_chars = max(24, int(width / (10.2 * 0.48)))
        wrapped = textwrap.wrap(
            text,
            width=max_chars,
            break_long_words=False,
            replace_whitespace=False,
        ) or [text]
        lines: list[_StyledLine] = []
        for index, line in enumerate(wrapped):
            prefix = "\N{BULLET} " if index == 0 else "  "
            lines.append(
                _StyledLine(
                    f"{prefix}{line}",
                    indent=12,
                    leading=14.2,
                    before=1.5 if index == 0 else 0,
                )
            )
        return lines

    def _paginate(self, lines: list[_StyledLine]) -> list[list[_PlacedLine]]:
        pages: list[list[_PlacedLine]] = []
        current_page: list[_PlacedLine] = []
        y = self._TOP_Y

        for line in lines:
            required_height = line.before + line.leading + line.after
            if current_page and y - required_height < self._BOTTOM_Y:
                pages.append(current_page)
                current_page = []
                y = self._TOP_Y

            y -= line.before
            if line.text:
                current_page.append(_PlacedLine(line=line, y=y))
            y -= line.leading + line.after

        if current_page:
            pages.append(current_page)
        return pages or [[_PlacedLine(_StyledLine(""), self._TOP_Y)]]

    def _build_pdf(self, pages: list[list[_PlacedLine]]) -> bytes:
        font_pair = self._load_unicode_font_pair()
        if font_pair is not None:
            return self._build_unicode_pdf(pages, font_pair)
        return self._build_type1_pdf(pages)

    def _build_type1_pdf(self, pages: list[list[_PlacedLine]]) -> bytes:
        objects: list[bytes] = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"",
        ]
        page_object_ids: list[int] = []
        font_regular_object_id = 3 + len(pages) * 2
        font_bold_object_id = font_regular_object_id + 1

        for page_number, page_lines in enumerate(pages, start=1):
            page_object_id = len(objects) + 1
            content_object_id = page_object_id + 1
            page_object_ids.append(page_object_id)
            objects.append(
                (
                    "<< /Type /Page /Parent 2 0 R "
                    "/Resources << /Font << "
                    f"/F1 {font_regular_object_id} 0 R "
                    f"/F2 {font_bold_object_id} 0 R "
                    ">> >> "
                    "/MediaBox [0 0 595 842] "
                    f"/Contents {content_object_id} 0 R >>"
                ).encode("ascii")
            )
            content = self._page_content(
                page_lines,
                page_number=page_number,
                page_count=len(pages),
            )
            objects.append(
                f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
                + content
                + b"\nendstream"
            )

        objects.append(self._font_object("Helvetica"))
        objects.append(self._font_object("Helvetica-Bold"))
        kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
        objects[1] = (
            f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>"
        ).encode("ascii")

        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for object_id, body in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{object_id} 0 obj\n".encode("ascii"))
            output.extend(body)
            output.extend(b"\nendobj\n")

        xref_offset = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n"
            ).encode("ascii")
        )
        return bytes(output)

    def _build_unicode_pdf(
        self,
        pages: list[list[_PlacedLine]],
        fonts: tuple[_TrueTypeFont, _TrueTypeFont],
    ) -> bytes:
        regular_font, bold_font = fonts
        used_codepoints = self._used_codepoints(pages)
        objects: list[bytes] = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"",
        ]
        regular_font_object_id = 3
        regular_objects = self._unicode_font_objects(
            regular_font,
            object_id=regular_font_object_id,
            used_codepoints=used_codepoints,
        )
        bold_font_object_id = regular_font_object_id + len(regular_objects)
        bold_objects = self._unicode_font_objects(
            bold_font,
            object_id=bold_font_object_id,
            used_codepoints=used_codepoints,
        )
        objects.extend(regular_objects)
        objects.extend(bold_objects)

        page_object_ids: list[int] = []
        for page_number, page_lines in enumerate(pages, start=1):
            page_object_id = len(objects) + 1
            content_object_id = page_object_id + 1
            page_object_ids.append(page_object_id)
            objects.append(
                (
                    "<< /Type /Page /Parent 2 0 R "
                    "/Resources << /Font << "
                    f"/F1 {regular_font_object_id} 0 R "
                    f"/F2 {bold_font_object_id} 0 R "
                    ">> >> "
                    "/MediaBox [0 0 595 842] "
                    f"/Contents {content_object_id} 0 R >>"
                ).encode("ascii")
            )
            content = self._page_content(
                page_lines,
                page_number=page_number,
                page_count=len(pages),
                unicode_text=True,
            )
            objects.append(self._stream_object({}, content))

        kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
        objects[1] = (
            f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>"
        ).encode("ascii")
        return self._serialize_pdf(objects)

    def _serialize_pdf(self, objects: list[bytes]) -> bytes:
        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for object_id, body in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{object_id} 0 obj\n".encode("ascii"))
            output.extend(body)
            output.extend(b"\nendobj\n")

        xref_offset = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n"
            ).encode("ascii")
        )
        return bytes(output)

    def _page_content(
        self,
        page_lines: list[_PlacedLine],
        *,
        page_number: int,
        page_count: int,
        unicode_text: bool = False,
    ) -> bytes:
        commands: list[bytes] = [
            b"0.88 0.91 0.96 RG",
            f"{self._MARGIN_X:g} 812 m {self._PAGE_WIDTH - self._MARGIN_X:g} 812 l S".encode(
                "ascii"
            ),
        ]
        for placed in page_lines:
            line = placed.line
            x = self._x_for_line(line)
            commands.extend(
                [
                    b"BT",
                    f"/{line.font} {line.size:g} Tf".encode("ascii"),
                    f"{line.color} rg".encode("ascii"),
                    f"1 0 0 1 {x:.2f} {placed.y:.2f} Tm".encode("ascii"),
                    self._pdf_text(line.text, unicode_text=unicode_text) + b" Tj",
                    b"ET",
                ]
            )

        footer = f"Page {page_number} / {page_count}"
        commands.extend(
            [
                b"BT",
                b"/F1 8 Tf",
                b"0.55 0.61 0.70 rg",
                f"1 0 0 1 {self._center_x(footer, 8, False):.2f} 32 Tm".encode(
                    "ascii"
                ),
                self._pdf_text(footer, unicode_text=unicode_text) + b" Tj",
                b"ET",
            ]
        )
        return b"\n".join(commands)

    def _used_codepoints(self, pages: list[list[_PlacedLine]]) -> set[int]:
        codepoints: set[int] = set()
        page_count = len(pages)
        for page_number, page_lines in enumerate(pages, start=1):
            for placed in page_lines:
                codepoints.update(self._codepoints_for_pdf(placed.line.text))
            codepoints.update(self._codepoints_for_pdf(f"Page {page_number} / {page_count}"))
        return codepoints or {32}

    def _codepoints_for_pdf(self, value: str) -> set[int]:
        return {ord(char) if ord(char) <= 0xFFFF else ord("?") for char in value}

    def _unicode_font_objects(
        self,
        font: _TrueTypeFont,
        *,
        object_id: int,
        used_codepoints: set[int],
    ) -> list[bytes]:
        cidfont_id = object_id + 1
        descriptor_id = object_id + 2
        fontfile_id = object_id + 3
        cid_to_gid_id = object_id + 4
        to_unicode_id = object_id + 5
        font_name = self._pdf_name(font.name)
        x_min, y_min, x_max, y_max = font.bbox

        return [
            (
                "<< /Type /Font /Subtype /Type0 "
                f"/BaseFont /{font_name} /Encoding /Identity-H "
                f"/DescendantFonts [{cidfont_id} 0 R] "
                f"/ToUnicode {to_unicode_id} 0 R >>"
            ).encode("ascii"),
            (
                "<< /Type /Font /Subtype /CIDFontType2 "
                f"/BaseFont /{font_name} "
                "/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
                f"/FontDescriptor {descriptor_id} 0 R "
                f"/CIDToGIDMap {cid_to_gid_id} 0 R "
                f"/DW 500 /W [ {self._width_array(font, used_codepoints)} ] >>"
            ).encode("ascii"),
            (
                "<< /Type /FontDescriptor "
                f"/FontName /{font_name} /Flags 32 "
                f"/FontBBox [{x_min} {y_min} {x_max} {y_max}] "
                f"/ItalicAngle 0 /Ascent {font.ascent} /Descent {font.descent} "
                f"/CapHeight {font.ascent} /StemV 80 /FontFile2 {fontfile_id} 0 R >>"
            ).encode("ascii"),
            self._stream_object({"Length1": str(len(font.data))}, font.data),
            self._stream_object({}, self._cid_to_gid_map(font, used_codepoints)),
            self._stream_object({}, self._to_unicode_cmap(used_codepoints)),
        ]

    def _width_array(self, font: _TrueTypeFont, used_codepoints: set[int]) -> str:
        return " ".join(
            f"{codepoint} [{font.width(codepoint)}]"
            for codepoint in sorted(used_codepoints)
        )

    def _cid_to_gid_map(self, font: _TrueTypeFont, used_codepoints: set[int]) -> bytes:
        max_codepoint = max(used_codepoints) if used_codepoints else 32
        mapping = bytearray((max_codepoint + 1) * 2)
        for codepoint in used_codepoints:
            glyph_id = font.glyph_id(codepoint)
            mapping[codepoint * 2 : codepoint * 2 + 2] = glyph_id.to_bytes(2, "big")
        return bytes(mapping)

    def _to_unicode_cmap(self, used_codepoints: set[int]) -> bytes:
        entries = [
            f"<{codepoint:04X}> <{self._unicode_hex(codepoint)}>"
            for codepoint in sorted(used_codepoints)
        ]
        chunks: list[str] = []
        for index in range(0, len(entries), 100):
            group = entries[index : index + 100]
            chunks.append(f"{len(group)} beginbfchar")
            chunks.extend(group)
            chunks.append("endbfchar")

        cmap = "\n".join(
            [
                "/CIDInit /ProcSet findresource begin",
                "12 dict begin",
                "begincmap",
                "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
                "/CMapName /Adobe-Identity-UCS def",
                "/CMapType 2 def",
                "1 begincodespacerange",
                "<0000> <FFFF>",
                "endcodespacerange",
                *chunks,
                "endcmap",
                "CMapName currentdict /CMap defineresource pop",
                "end",
                "end",
            ]
        )
        return cmap.encode("ascii")

    def _unicode_hex(self, codepoint: int) -> str:
        if codepoint <= 0xFFFF:
            return f"{codepoint:04X}"
        codepoint -= 0x10000
        high = 0xD800 + (codepoint >> 10)
        low = 0xDC00 + (codepoint & 0x3FF)
        return f"{high:04X}{low:04X}"

    def _stream_object(self, entries: dict[str, str], data: bytes) -> bytes:
        extra = " ".join(f"/{key} {value}" for key, value in entries.items())
        dictionary = f"<< /Length {len(data)}"
        if extra:
            dictionary += f" {extra}"
        dictionary += " >>\nstream\n"
        return dictionary.encode("ascii") + data + b"\nendstream"

    def _pdf_name(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "", value)
        return cleaned or "UnderWrightUnicodeFont"

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_unicode_font_pair() -> tuple[_TrueTypeFont, _TrueTypeFont] | None:
        regular_path = SimpleTextPdfRenderer._first_existing_font(
            os.getenv("UNDERWRIGHT_PDF_FONT_REGULAR"),
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        )
        bold_path = SimpleTextPdfRenderer._first_existing_font(
            os.getenv("UNDERWRIGHT_PDF_FONT_BOLD"),
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        )
        if regular_path is None or bold_path is None:
            return None
        try:
            return (
                SimpleTextPdfRenderer._load_true_type_font(str(regular_path)),
                SimpleTextPdfRenderer._load_true_type_font(str(bold_path)),
            )
        except (OSError, ValueError, struct.error):
            return None

    @staticmethod
    def _first_existing_font(*candidates: str | None) -> Path | None:
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate)
            if path.is_file():
                return path
        return None

    @staticmethod
    @lru_cache(maxsize=8)
    def _load_true_type_font(path: str) -> _TrueTypeFont:
        data = Path(path).read_bytes()
        tables = SimpleTextPdfRenderer._ttf_tables(data)
        head = SimpleTextPdfRenderer._table(data, tables, "head")
        hhea = SimpleTextPdfRenderer._table(data, tables, "hhea")
        maxp = SimpleTextPdfRenderer._table(data, tables, "maxp")
        hmtx = SimpleTextPdfRenderer._table(data, tables, "hmtx")

        units_per_em = SimpleTextPdfRenderer._u16(head, 18)
        bbox = (
            SimpleTextPdfRenderer._i16(head, 36),
            SimpleTextPdfRenderer._i16(head, 38),
            SimpleTextPdfRenderer._i16(head, 40),
            SimpleTextPdfRenderer._i16(head, 42),
        )
        ascent = round(SimpleTextPdfRenderer._i16(hhea, 4) * 1000 / units_per_em)
        descent = round(SimpleTextPdfRenderer._i16(hhea, 6) * 1000 / units_per_em)
        metric_count = SimpleTextPdfRenderer._u16(hhea, 34)
        glyph_count = SimpleTextPdfRenderer._u16(maxp, 4)
        advance_widths = SimpleTextPdfRenderer._advance_widths(
            hmtx,
            glyph_count=glyph_count,
            metric_count=metric_count,
        )
        cmap = SimpleTextPdfRenderer._parse_cmap(
            SimpleTextPdfRenderer._table(data, tables, "cmap")
        )
        if not cmap:
            raise ValueError("TrueType font has no Unicode cmap.")

        return _TrueTypeFont(
            name=SimpleTextPdfRenderer._font_postscript_name(
                SimpleTextPdfRenderer._table(data, tables, "name")
                if "name" in tables
                else b"",
                fallback=Path(path).stem,
            ),
            data=data,
            units_per_em=units_per_em,
            ascent=ascent,
            descent=descent,
            bbox=tuple(round(value * 1000 / units_per_em) for value in bbox),
            advance_widths=tuple(advance_widths),
            cmap=cmap,
        )

    @staticmethod
    def _ttf_tables(data: bytes) -> dict[str, tuple[int, int]]:
        table_count = SimpleTextPdfRenderer._u16(data, 4)
        tables: dict[str, tuple[int, int]] = {}
        for index in range(table_count):
            offset = 12 + index * 16
            tag = data[offset : offset + 4].decode("ascii", errors="ignore")
            table_offset = SimpleTextPdfRenderer._u32(data, offset + 8)
            table_length = SimpleTextPdfRenderer._u32(data, offset + 12)
            tables[tag] = (table_offset, table_length)
        return tables

    @staticmethod
    def _table(data: bytes, tables: dict[str, tuple[int, int]], tag: str) -> bytes:
        if tag not in tables:
            raise ValueError(f"TrueType font is missing {tag} table.")
        offset, length = tables[tag]
        return data[offset : offset + length]

    @staticmethod
    def _advance_widths(
        hmtx: bytes,
        *,
        glyph_count: int,
        metric_count: int,
    ) -> list[int]:
        widths: list[int] = []
        last_width = 500
        for index in range(metric_count):
            last_width = SimpleTextPdfRenderer._u16(hmtx, index * 4)
            widths.append(last_width)
        while len(widths) < glyph_count:
            widths.append(last_width)
        return widths

    @staticmethod
    def _parse_cmap(cmap_table: bytes) -> dict[int, int]:
        subtable_count = SimpleTextPdfRenderer._u16(cmap_table, 2)
        candidates: list[tuple[int, dict[int, int]]] = []
        for index in range(subtable_count):
            record_offset = 4 + index * 8
            platform_id = SimpleTextPdfRenderer._u16(cmap_table, record_offset)
            encoding_id = SimpleTextPdfRenderer._u16(cmap_table, record_offset + 2)
            subtable_offset = SimpleTextPdfRenderer._u32(cmap_table, record_offset + 4)
            if subtable_offset >= len(cmap_table):
                continue
            fmt = SimpleTextPdfRenderer._u16(cmap_table, subtable_offset)
            parsed: dict[int, int] = {}
            if fmt == 4:
                parsed = SimpleTextPdfRenderer._parse_cmap_format4(
                    cmap_table,
                    subtable_offset,
                )
            elif fmt == 12:
                parsed = SimpleTextPdfRenderer._parse_cmap_format12(
                    cmap_table,
                    subtable_offset,
                )
            if parsed:
                priority = 0
                if platform_id == 3 and encoding_id == 10:
                    priority = 3
                elif platform_id == 3 and encoding_id in {1, 0}:
                    priority = 2
                elif platform_id == 0:
                    priority = 1
                candidates.append((priority, parsed))
        if not candidates:
            return {}
        return max(candidates, key=lambda item: item[0])[1]

    @staticmethod
    def _parse_cmap_format4(data: bytes, offset: int) -> dict[int, int]:
        length = SimpleTextPdfRenderer._u16(data, offset + 2)
        end = offset + length
        segment_count = SimpleTextPdfRenderer._u16(data, offset + 6) // 2
        end_codes_offset = offset + 14
        start_codes_offset = end_codes_offset + segment_count * 2 + 2
        deltas_offset = start_codes_offset + segment_count * 2
        range_offsets_offset = deltas_offset + segment_count * 2
        cmap: dict[int, int] = {}

        for index in range(segment_count):
            end_code = SimpleTextPdfRenderer._u16(data, end_codes_offset + index * 2)
            start_code = SimpleTextPdfRenderer._u16(data, start_codes_offset + index * 2)
            delta = SimpleTextPdfRenderer._i16(data, deltas_offset + index * 2)
            range_offset_position = range_offsets_offset + index * 2
            range_offset = SimpleTextPdfRenderer._u16(data, range_offset_position)
            if start_code == 0xFFFF and end_code == 0xFFFF:
                continue
            for codepoint in range(start_code, min(end_code, 0xFFFF) + 1):
                if range_offset == 0:
                    glyph_id = (codepoint + delta) & 0xFFFF
                else:
                    glyph_offset = (
                        range_offset_position
                        + range_offset
                        + (codepoint - start_code) * 2
                    )
                    if glyph_offset + 2 > end:
                        continue
                    glyph_id = SimpleTextPdfRenderer._u16(data, glyph_offset)
                    if glyph_id:
                        glyph_id = (glyph_id + delta) & 0xFFFF
                if glyph_id:
                    cmap[codepoint] = glyph_id
        return cmap

    @staticmethod
    def _parse_cmap_format12(data: bytes, offset: int) -> dict[int, int]:
        group_count = SimpleTextPdfRenderer._u32(data, offset + 12)
        cmap: dict[int, int] = {}
        groups_offset = offset + 16
        for index in range(group_count):
            group_offset = groups_offset + index * 12
            start_code = SimpleTextPdfRenderer._u32(data, group_offset)
            end_code = SimpleTextPdfRenderer._u32(data, group_offset + 4)
            start_glyph = SimpleTextPdfRenderer._u32(data, group_offset + 8)
            if start_code > 0xFFFF:
                continue
            for codepoint in range(start_code, min(end_code, 0xFFFF) + 1):
                cmap[codepoint] = start_glyph + codepoint - start_code
        return cmap

    @staticmethod
    def _font_postscript_name(name_table: bytes, *, fallback: str) -> str:
        if not name_table:
            return fallback
        count = SimpleTextPdfRenderer._u16(name_table, 2)
        string_offset = SimpleTextPdfRenderer._u16(name_table, 4)
        for index in range(count):
            record_offset = 6 + index * 12
            platform_id = SimpleTextPdfRenderer._u16(name_table, record_offset)
            name_id = SimpleTextPdfRenderer._u16(name_table, record_offset + 6)
            length = SimpleTextPdfRenderer._u16(name_table, record_offset + 8)
            offset = SimpleTextPdfRenderer._u16(name_table, record_offset + 10)
            if name_id != 6:
                continue
            raw = name_table[string_offset + offset : string_offset + offset + length]
            encoding = "utf-16-be" if platform_id in {0, 3} else "latin-1"
            decoded = raw.decode(encoding, errors="ignore").strip()
            if decoded:
                return decoded
        return fallback

    @staticmethod
    def _u16(data: bytes, offset: int) -> int:
        return struct.unpack_from(">H", data, offset)[0]

    @staticmethod
    def _i16(data: bytes, offset: int) -> int:
        return struct.unpack_from(">h", data, offset)[0]

    @staticmethod
    def _u32(data: bytes, offset: int) -> int:
        return struct.unpack_from(">I", data, offset)[0]

    def _font_object(self, base_font: str) -> bytes:
        return (
            "<< /Type /Font /Subtype /Type1 "
            f"/BaseFont /{base_font} "
            "/Encoding << /Type /Encoding /BaseEncoding /WinAnsiEncoding "
            f"/Differences {self._FONT_ENCODING_DIFFERENCES} >> >>"
        ).encode("ascii")

    def _x_for_line(self, line: _StyledLine) -> float:
        if line.align == "center":
            return self._center_x(line.text, line.size, line.font == "F2")
        return self._MARGIN_X + line.indent

    def _center_x(self, text: str, size: float, bold: bool) -> float:
        width = self._approx_text_width(text, size, bold)
        return max(self._MARGIN_X, (self._PAGE_WIDTH - width) / 2)

    def _approx_text_width(self, text: str, size: float, bold: bool) -> float:
        normalized = self._ascii_text(text)
        average_width = 0.55 if bold else 0.51
        return min(self._CONTENT_WIDTH, len(normalized) * size * average_width)

    def _pdf_text(self, value: str, *, unicode_text: bool) -> bytes:
        if unicode_text:
            return self._unicode_pdf_string(value)
        return self._pdf_string(value)

    def _unicode_pdf_string(self, value: str) -> bytes:
        encoded = bytearray()
        for char in value:
            codepoint = ord(char)
            if codepoint > 0xFFFF:
                codepoint = ord("?")
            encoded.extend(codepoint.to_bytes(2, "big"))
        return b"<" + bytes(encoded).hex().upper().encode("ascii") + b">"

    def _pdf_string(self, value: str) -> bytes:
        encoded = bytearray()
        for char in value:
            encoded.extend(self._pdf_char_bytes(char))

        escaped = bytearray(b"(")
        for byte in encoded:
            if byte in (0x28, 0x29, 0x5C):
                escaped.extend(b"\\")
                escaped.append(byte)
            elif byte < 32 or byte > 126:
                escaped.extend(f"\\{byte:03o}".encode("ascii"))
            else:
                escaped.append(byte)
        escaped.extend(b")")
        return bytes(escaped)

    def _pdf_char_bytes(self, char: str) -> bytes:
        custom_code = self._CUSTOM_CHAR_CODES.get(char)
        if custom_code is not None:
            return bytes([custom_code])

        if char == "\u2013" or char == "\u2014":
            return b"-"
        if char in {"\u2018", "\u2019"}:
            return b"'"

        try:
            return char.encode("cp1252")
        except UnicodeEncodeError:
            fallback = self._ascii_text(char)
            return fallback.encode("ascii") if fallback else b"?"

    def _ascii_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        return normalized.encode("ascii", "ignore").decode("ascii")

    def _normalize_list_bullets(self, text: str) -> str:
        return self._MARKDOWN_BULLET_PATTERN.sub(
            lambda match: f"{match.group(1)}\N{BULLET} ",
            text,
        )

    def _normalize_document_text(self, text: str) -> str:
        return self._normalize_coverage_table(self._normalize_list_bullets(text))

    def _normalize_coverage_table(self, text: str) -> str:
        def replace_table(match: re.Match[str]) -> str:
            building_amount = match.group(1).strip()
            contents_amount = match.group(2).strip()
            total_amount = match.group(3).strip()
            return (
                f"Suma asigurat\u0103 total\u0103 este de {total_amount}.\n\n"
                "Aceasta este compus\u0103 din:\n"
                f"\N{BULLET} suma asigurat\u0103 pentru locuin\u021b\u0103: {building_amount};\n"
                f"\N{BULLET} suma asigurat\u0103 pentru bunuri mobile: {contents_amount}."
            )

        return self._COVERAGE_TABLE_PATTERN.sub(replace_table, text)

    def _is_centered_contract_title(self, value: str) -> bool:
        normalized = self._normalize_heading(value)
        return normalized in {
            "POLITA DE ASIGURARE A LOCUINTEI SI BUNURILOR",
            "LOCUINTA SI BUNURI",
        }

    def _is_contract_chapter_heading(self, value: str) -> bool:
        return bool(re.match(r"^CAPITOLUL\s+[IVXLCDM]+\b", value.strip(), re.I))

    def _is_contract_article_heading(self, value: str) -> bool:
        return bool(re.match(r"^Art\.\s+\d+\b", value.strip(), re.I))

    def _normalize_heading(self, value: str) -> str:
        return self._ascii_text(value).upper()


__all__ = ["SimpleTextPdfRenderer"]
