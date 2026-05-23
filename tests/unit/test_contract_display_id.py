from uuid import UUID

from underwright.domain.contract_lifecycle import build_contract_display_id


def test_contract_display_id_uses_template_legal_name_and_differentiator() -> None:
    assert (
        build_contract_display_id(
            contract_number="PAD-RISK-2026-000145",
            legal_name="Vasile Valoare",
            fallback_id=UUID("10000000-0000-0000-0000-000000000101"),
        )
        == "PAD-RISK-Vasile_Valoare-000145"
    )


def test_contract_display_id_removes_legacy_embedded_first_name() -> None:
    assert (
        build_contract_display_id(
            contract_number="PAD-MARIA-2026-000201",
            legal_name="Maria Ionescu",
            fallback_id=None,
        )
        == "PAD-Maria_Ionescu-000201"
    )


def test_contract_display_id_does_not_duplicate_full_legal_name_suffix() -> None:
    assert (
        build_contract_display_id(
            contract_number="PAD-Maria-Ionescu-000201",
            legal_name="Maria Ionescu",
            fallback_id=None,
        )
        == "PAD-Maria_Ionescu-000201"
    )


def test_contract_display_id_falls_back_when_display_parts_are_missing() -> None:
    assert (
        build_contract_display_id(
            contract_number=None,
            legal_name=None,
            fallback_id=UUID("10000000-0000-0000-0000-000000000101"),
        )
        == "10000000-0000-0000-0000-000000000101"
    )


def test_contract_display_id_does_not_build_template_from_uuid_text() -> None:
    assert (
        build_contract_display_id(
            contract_number="10000000-0000-0000-0000-000000000101",
            legal_name="Vasile Valoare",
            fallback_id=UUID("10000000-0000-0000-0000-000000000101"),
        )
        == "10000000-0000-0000-0000-000000000101"
    )
