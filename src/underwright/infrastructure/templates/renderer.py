from __future__ import annotations

import re
from typing import Any


class PadTemplateRenderer:
    """
    Renders PAD contract templates by replacing {{ placeholders }}
    with values from a contract context.

    Supports dot notation paths, such as:
    {{ contract_meta.contract_id }}
    {{ parties.insurer.name }}
    """

    _PLACEHOLDER_PATTERN = re.compile(r"{{\s*([A-Za-z0-9_.]+)\s*}}")
    _MARKDOWN_BULLET_PATTERN = re.compile(r"(?m)^([ \t]*)\* ")
    _COVERAGE_TABLE_PATTERN = re.compile(
        r"(?m)^[ \t]*\|\s*Categoria\s*\|[^\r\n]*\|\s*\r?\n"
        r"^[ \t]*\|\s*-+\s*\|\s*-+\s*\|\s*\r?\n"
        r"^[ \t]*\|\s*Locuin[^|]*\|\s*([^|\r\n]+?)\s*\|\s*\r?\n"
        r"^[ \t]*\|\s*Bunuri mobile\s*\|\s*([^|\r\n]+?)\s*\|\s*\r?\n"
        r"^[ \t]*\|\s*Total\s*\|\s*([^|\r\n]+?)\s*\|"
    )

    def render(self, template: str, context: Any) -> str:
        def replace_match(match: re.Match[str]) -> str:
            placeholder = match.group(1)
            value = self._resolve_placeholder(context, placeholder)
            return self._stringify(value, placeholder)

        rendered = self._PLACEHOLDER_PATTERN.sub(replace_match, template)
        return self._normalize_document_text(rendered)

    def extract_placeholders(self, template: str) -> list[str]:
        return sorted(set(self._PLACEHOLDER_PATTERN.findall(template)))

    def _resolve_placeholder(self, context: Any, path: str) -> Any:
        current: Any = context

        for part in path.split("."):
            if isinstance(current, dict):
                if part not in current:
                    raise KeyError(f"Missing placeholder value for '{path}'.")
                current = current[part]
                continue

            if hasattr(current, part):
                current = getattr(current, part)
                continue

            raise KeyError(f"Missing placeholder value for '{path}'.")

        return current

    def _stringify(self, value: Any, placeholder: str) -> str:
        if value is None:
            raise ValueError(f"Placeholder '{placeholder}' resolved to None.")

        return str(value)

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
                f"Suma asigurată totală este de {total_amount}.\n\n"
                "Aceasta este compusă din:\n"
                f"\N{BULLET} suma asigurată pentru locuință: {building_amount};\n"
                f"\N{BULLET} suma asigurată pentru bunuri mobile: {contents_amount}."
            )

        return self._COVERAGE_TABLE_PATTERN.sub(replace_table, text)
