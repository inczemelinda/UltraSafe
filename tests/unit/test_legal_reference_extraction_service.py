from __future__ import annotations

import pytest

from underwright.application.services.legal_reference_extraction_service import (
    LegalReferenceExtractionService,
)


def test_extracts_and_normalizes_romanian_legal_references() -> None:
    service = LegalReferenceExtractionService()
    examples = {
        "Legea nr. 260/2008": "ro:lege:260:2008",
        "Legea 260 din 2008": "ro:lege:260:2008",
        "legea nr.260/2008": "ro:lege:260:2008",
        "Legii nr. 260/2008": "ro:lege:260:2008",
        "Legea260/2008": "ro:lege:260:2008",
        "OUG nr. 50/2010": "ro:oug:50:2010",
        "OUG nr.50/2010": "ro:oug:50:2010",
        "Ordonanta de urgenta nr. 50/2010": "ro:oug:50:2010",
        "Ordonanța de urgență nr. 50/2010": "ro:oug:50:2010",
        "OG nr. 21/1992": "ro:og:21:1992",
        "Ordonanta nr. 21/1992": "ro:og:21:1992",
        "Ordinul nr. 10/2024": "ro:ordin:10:2024",
        "Ordinul ASF nr. 10/2024": "ro:ordin-asf:10:2024",
        "Norma ASF nr. 20/2017": "ro:norma-asf:20:2017",
        "Decizia nr. 123/2024": "ro:decizie:123:2024",
        "Decizia nr. 1.074 din 4 septembrie 2018": "ro:decizie:1074:2018",
    }

    for raw_reference, canonical in examples.items():
        assert service.normalize_reference(raw_reference) == canonical


def test_extracts_and_normalizes_eu_legal_references() -> None:
    service = LegalReferenceExtractionService()
    examples = {
        "Regulamentul (UE) 2024/1234": "eu:regulation:2024:1234",
        "Regulamentul(UE)2024/1234": "eu:regulation:2024:1234",
        "Regulation (EU) 2024/1234": "eu:regulation:2024:1234",
        "Regulation(EU)2024/1234": "eu:regulation:2024:1234",
        "Directiva (UE) 2023/1234": "eu:directive:2023:1234",
        "Directive (EU) 2023/1234": "eu:directive:2023:1234",
        "Decizia (UE) 2024/1234": "eu:decision:2024:1234",
        "Decision (EU) 2024/1234": "eu:decision:2024:1234",
    }

    for raw_reference, canonical in examples.items():
        assert service.normalize_reference(raw_reference) == canonical


def test_extract_references_returns_stable_unique_canonical_references() -> None:
    service = LegalReferenceExtractionService()

    references = service.extract_references(
        "Legea nr.260/2008 modifica Regulation (EU) 2024/1234. "
        "Legea 260 din 2008 este mentionata din nou."
    )

    assert references == [
        "ro:lege:260:2008",
        "eu:regulation:2024:1234",
    ]


def test_extracts_legislatie_detail_title_reference_before_body_references() -> None:
    service = LegalReferenceExtractionService()

    references = service.extract_references(
        "DECIZIE nr. 1.074 din 4 septembrie 2018 referitoare la "
        "excepția de neconstituționalitate a dispozițiilor art. 16 "
        "alin. (1) din Legea nr. 47/1992"
    )

    assert references == [
        "ro:decizie:1074:2018",
        "ro:lege:47:1992",
    ]


def test_extracts_romanian_amendment_and_repeal_relationships() -> None:
    service = LegalReferenceExtractionService()

    relationships = service.extract_amendment_relationships(
        "Actul modifica Legea nr. 260/2008. "
        "Se emite pentru modificarea Legii nr. 132/2017. "
        "Totodata, abroga Legea nr. 10/1995."
    )

    assert relationships == {
        "amends": ["ro:lege:260:2008", "ro:lege:132:2017"],
        "repeals": ["ro:lege:10:1995"],
    }


def test_relationship_extraction_ignores_nr_abbreviation_boundaries() -> None:
    service = LegalReferenceExtractionService()

    relationships = service.extract_amendment_relationships(
        "Actul modifica Legea nr. 132/2017 si OUG nr. 50/2010."
    )

    assert relationships == {
        "amends": ["ro:lege:132:2017", "ro:oug:50:2010"],
        "repeals": [],
    }


def test_extracts_eu_amendment_and_repeal_relationships() -> None:
    service = LegalReferenceExtractionService()

    relationships = service.extract_amendment_relationships(
        "This act amending Regulation (EU) 2024/1234 and "
        "repealing Directive (EU) 2023/1234."
    )

    assert relationships == {
        "amends": ["eu:regulation:2024:1234"],
        "repeals": ["eu:directive:2023:1234"],
    }


def test_normalize_reference_rejects_unsupported_references() -> None:
    service = LegalReferenceExtractionService()

    with pytest.raises(ValueError, match="Unsupported legal reference"):
        service.normalize_reference("some unrelated contract clause")
