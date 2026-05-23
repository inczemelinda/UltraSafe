from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class _ReferencePattern:
    jurisdiction: str
    reference_type: str
    pattern: re.Pattern[str]
    canonical_groups: tuple[str, str]


@dataclass(frozen=True)
class _ReferenceMatch:
    canonical: str
    start: int
    end: int


class LegalReferenceExtractionService:
    _AMENDMENT_CONTEXT_CHARS = 90

    def __init__(self) -> None:
        self._patterns = [
            self._ro_pattern(
                "lege",
                r"(?:legea|legii|lege)",
            ),
            self._ro_pattern(
                "oug",
                r"(?:oug|ordonanta\s+de\s+urgenta|ordonantei\s+de\s+urgenta)",
            ),
            self._ro_pattern(
                "og",
                r"(?:og|ordonanta(?:\s+guvernului)?)",
            ),
            self._ro_pattern(
                "ordin-asf",
                r"(?:ordinul|ordin)\s+asf",
            ),
            self._ro_pattern(
                "ordin",
                r"(?:ordinul|ordin)",
            ),
            self._ro_pattern(
                "norma-asf",
                r"(?:norma|normei)\s+asf",
            ),
            self._ro_pattern(
                "decizie",
                r"(?:decizia|deciziei|decizie)",
            ),
            self._eu_pattern(
                "regulation",
                r"(?:regulamentul|regulation)",
            ),
            self._eu_pattern(
                "directive",
                r"(?:directiva|directive)",
            ),
            self._eu_pattern(
                "decision",
                r"(?:decizia|decision)",
            ),
        ]

    def extract_references(self, text: str) -> list[str]:
        return self._canonical_references(self._find_matches(text))

    def normalize_reference(self, raw_reference: str) -> str:
        matches = self._find_matches(raw_reference)
        if not matches:
            raise ValueError(f"Unsupported legal reference: {raw_reference}")
        return sorted(matches, key=lambda match: (match.start, match.end))[0].canonical

    def extract_amendment_relationships(self, text: str) -> dict[str, list[str]]:
        normalized_text = self._normalize_text(text)
        amends: list[str] = []
        repeals: list[str] = []

        for match in sorted(self._find_matches(text), key=lambda item: item.start):
            context = normalized_text[
                max(0, match.start - self._AMENDMENT_CONTEXT_CHARS) : match.start
            ]
            relationship_signal = self._relationship_signal(context)
            if relationship_signal == "amends":
                amends.append(match.canonical)
            if relationship_signal == "repeals":
                repeals.append(match.canonical)

        return {
            "amends": self._dedupe(amends),
            "repeals": self._dedupe(repeals),
        }

    def _find_matches(self, text: str) -> list[_ReferenceMatch]:
        normalized_text = self._normalize_text(text)
        matches: list[_ReferenceMatch] = []

        for reference_pattern in self._patterns:
            for match in reference_pattern.pattern.finditer(normalized_text):
                first = match.group(reference_pattern.canonical_groups[0]).replace(
                    ".",
                    "",
                )
                second = match.group(reference_pattern.canonical_groups[1])
                matches.append(
                    _ReferenceMatch(
                        canonical=(
                            f"{reference_pattern.jurisdiction}:"
                            f"{reference_pattern.reference_type}:"
                            f"{first}:{second}"
                        ),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        return matches

    def _canonical_references(self, matches: list[_ReferenceMatch]) -> list[str]:
        ordered = sorted(matches, key=lambda match: (match.start, match.end))
        return self._dedupe([match.canonical for match in ordered])

    def _dedupe(self, references: list[str]) -> list[str]:
        deduped = []
        seen = set()
        for reference in references:
            if reference in seen:
                continue
            seen.add(reference)
            deduped.append(reference)
        return deduped

    def _ro_pattern(
        self,
        reference_type: str,
        label_pattern: str,
    ) -> _ReferencePattern:
        return _ReferencePattern(
            jurisdiction="ro",
            reference_type=reference_type,
            pattern=re.compile(
                rf"\b{label_pattern}\s*(?:nr\.?\s*)?"
                rf"(?P<number>\d+(?:\.\d+)*)\s*"
                rf"(?:/|\s+din\s+(?:\d{{1,2}}\s+[a-z]+\s+)?)"
                rf"(?P<year>\d{{4}})\b",
                re.IGNORECASE,
            ),
            canonical_groups=("number", "year"),
        )

    def _eu_pattern(
        self,
        reference_type: str,
        label_pattern: str,
    ) -> _ReferencePattern:
        return _ReferencePattern(
            jurisdiction="eu",
            reference_type=reference_type,
            pattern=re.compile(
                rf"\b{label_pattern}\s*\(\s*(?:ue|eu)\s*\)\s*"
                rf"(?P<year>\d{{4}})\s*/\s*(?P<number>\d+)\b",
                re.IGNORECASE,
            ),
            canonical_groups=("year", "number"),
        )

    def _normalize_text(self, text: str) -> str:
        without_diacritics = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        return " ".join(without_diacritics.lower().split())

    def _relationship_signal(self, context: str) -> str | None:
        context_without_abbreviation_dots = re.sub(r"\bnr\.", "nr", context)
        sentence_context = context_without_abbreviation_dots[
            max(
                context_without_abbreviation_dots.rfind("."),
                context_without_abbreviation_dots.rfind(";"),
            )
            + 1 :
        ]
        amendment_position = self._last_keyword_position(
            sentence_context,
            r"\b("
            r"modifica|modificarea|modificare|modificari|"
            r"amending|amends|amended"
            r")\b",
        )
        repeal_position = self._last_keyword_position(
            sentence_context,
            r"\b("
            r"abroga|abrogarea|abrogare|"
            r"repealing|repeals|repealed"
            r")\b",
        )
        if amendment_position is None and repeal_position is None:
            return None
        if repeal_position is None:
            return "amends"
        if amendment_position is None:
            return "repeals"
        return "amends" if amendment_position > repeal_position else "repeals"

    def _last_keyword_position(self, text: str, pattern: str) -> int | None:
        matches = list(re.finditer(pattern, text))
        if not matches:
            return None
        return matches[-1].start()
