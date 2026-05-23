from __future__ import annotations

import json
from datetime import UTC, date, datetime
from uuid import UUID

import httpx

from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewCandidate,
    NormalizedLegalDocument,
)
from underwright.domain.models import Template
from underwright.infrastructure.llm.template_change_suggestion_generator import (
    DeterministicDemoTemplateChangeSuggestionGenerator,
    OpenAICompatibleTemplateChangeSuggestionGenerator,
)


def test_openai_template_change_suggestion_generator_requests_strict_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["temperature"] == 0
        assert payload["response_format"] == {"type": "json_object"}
        user_payload = json.loads(payload["messages"][1]["content"])
        assert user_payload["legal_document"]["title"].startswith("DEMO - Legea")
        assert user_payload["candidate"]["match_type"] == "amended_reference"
        assert "10 zile calendaristice" in user_payload["template"]["template_content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "overall_summary": "Draft deadline update.",
                                    "hunks": [
                                        {
                                            "change_type": "replace",
                                            "old_text": "10 zile calendaristice",
                                            "new_text": "5 zile calendaristice",
                                            "rationale": (
                                                "The legal document changes the "
                                                "notification deadline."
                                            ),
                                            "source_reference": (
                                                "DEMO - Legea nr. 99/2026"
                                            ),
                                            "confidence": 0.91,
                                        }
                                    ],
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.openai.test",
    )
    generator = OpenAICompatibleTemplateChangeSuggestionGenerator(
        api_key="test-key",
        model="test-model",
        api_base="https://api.openai.test/v1",
        client=client,
    )

    generated = generator.generate(
        legal_document=make_legal_document(),
        template=make_template(),
        candidate=make_candidate(),
        relevant_template_content=make_template().content,
    )

    assert generated["overall_summary"] == "Draft deadline update."
    assert generated["hunks"][0]["old_text"] == "10 zile calendaristice"
    assert generated["hunks"][0]["new_text"] == "5 zile calendaristice"


def test_deterministic_demo_template_change_suggestion_generator_outputs_pad_hunk() -> None:
    generator = DeterministicDemoTemplateChangeSuggestionGenerator()

    generated = generator.generate(
        legal_document=make_legal_document(),
        template=make_template(),
        candidate=make_candidate(),
        relevant_template_content=make_template().content,
    )

    assert generated["hunks"][0]["change_type"] == "replace"
    assert generated["hunks"][0]["old_text"] == (
        "Asiguratul trebuie sa notifice dauna in termen de "
        "10 zile calendaristice de la producerea evenimentului."
    )
    assert generated["hunks"][0]["new_text"] == (
        "Asiguratul trebuie sa notifice dauna in termen de "
        "5 zile calendaristice de la producerea evenimentului."
    )


def test_deterministic_generator_uses_legislatie_document_as_source_reference() -> None:
    generator = DeterministicDemoTemplateChangeSuggestionGenerator()
    legal_document = make_legislatie_legal_document()

    generated = generator.generate(
        legal_document=legal_document,
        template=make_template(),
        candidate=make_candidate(),
        relevant_template_content=make_template().content,
    )

    assert generated["hunks"][0]["old_text"].startswith("Asiguratul trebuie")
    assert generated["hunks"][0]["new_text"].startswith("Asiguratul trebuie")
    assert generated["hunks"][0]["source_reference"] == legal_document.title
    assert "legal document states" in generated["hunks"][0]["rationale"]


def test_deterministic_demo_generator_outputs_fire_exclusion_scenario() -> None:
    generator = DeterministicDemoTemplateChangeSuggestionGenerator()
    legal_document = make_legal_document().model_copy(
        update={
            "title": "DEMO - Fire coverage exclusion clause wording change",
            "full_text": (
                "Excluderile pentru incendiu trebuie sa distinga intre daune "
                "accidentale si daune provocate intentionat."
            ),
        }
    )
    candidate = make_candidate().model_copy(
        update={
            "matched_reference": "fire_exclusion",
            "review_reason": "Template fire exclusion wording needs review.",
        }
    )

    generated = generator.generate(
        legal_document=legal_document,
        template=make_full_wording_template(),
        candidate=candidate,
        relevant_template_content=make_full_wording_template().content,
    )

    hunk = generated["hunks"][0]
    assert hunk["section_label"] == "Fire exclusion wording"
    assert "Incendiul este arderea" in hunk["old_text"]
    assert "incendiilor accidentale" in hunk["new_text"]
    assert "10 zile calendaristice" not in hunk["old_text"]


def test_deterministic_demo_generator_outputs_storm_deductible_scenario() -> None:
    generator = DeterministicDemoTemplateChangeSuggestionGenerator()
    legal_document = make_legal_document().model_copy(
        update={
            "title": "DEMO - Storm damage deductible disclosure clarification",
            "full_text": (
                "Fransizele pentru furtuna si grindina trebuie prezentate langa "
                "descrierea riscurilor acoperite."
            ),
        }
    )
    candidate = make_candidate().model_copy(
        update={
            "matched_reference": "storm_deductible",
            "review_reason": "Storm peril wording should include deductible disclosure.",
        }
    )

    generated = generator.generate(
        legal_document=legal_document,
        template=make_full_wording_template(),
        candidate=candidate,
        relevant_template_content=make_full_wording_template().content,
    )

    hunk = generated["hunks"][0]
    assert hunk["section_label"] == "Storm deductible disclosure"
    assert "Furtuna si grindina" in hunk["old_text"]
    assert "Fransiza aplicabila" in hunk["new_text"]
    assert hunk["new_text"] != hunk["old_text"]


def test_deterministic_demo_generator_outputs_claims_escalation_scenario() -> None:
    generator = DeterministicDemoTemplateChangeSuggestionGenerator()
    legal_document = make_legal_document().model_copy(
        update={
            "title": "DEMO - Contract template review required for claims escalation wording",
            "full_text": (
                "Contractele trebuie sa indice termenul de raspuns al "
                "asiguratorului si canalul pentru contestarea deciziei de dauna."
            ),
        }
    )
    candidate = make_candidate().model_copy(
        update={
            "matched_reference": "claims_escalation",
            "review_reason": "Claims handling obligations need escalation wording.",
        }
    )

    generated = generator.generate(
        legal_document=legal_document,
        template=make_full_wording_template(),
        candidate=candidate,
        relevant_template_content=make_full_wording_template().content,
    )

    hunk = generated["hunks"][0]
    assert hunk["section_label"] == "Claims escalation wording"
    assert "respingerii" in hunk["old_text"]
    assert "canalul disponibil pentru contestarea deciziei" in hunk["new_text"]


def make_legal_document() -> NormalizedLegalDocument:
    now = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
    return NormalizedLegalDocument(
        id=UUID("92000000-0000-0000-0000-000000000001"),
        raw_source_item_id=UUID("91000000-0000-0000-0000-000000000001"),
        source_id="demo_ro_portal_legislativ",
        source_key="demo_ro_portal_legislativ",
        jurisdiction="RO",
        parser_id="ro_portal_legislativ",
        canonical_url="demo://law_change_pipeline_demo_v1/ro/lege-99-2026",
        source_url="demo://law_change_pipeline_demo_v1/ro/lege-99-2026",
        external_identifier="demo:ro:lege:99:2026",
        title="DEMO - Legea nr. 99/2026 pentru modificarea Legii nr. 260/2008",
        language="ro",
        issuer="DEMO - Parlamentul Romaniei",
        instrument_type="lege",
        instrument_number="99",
        instrument_year=2026,
        publication_reference="DEMO - Monitorul Oficial nr. 500/2026",
        publication_date=date(2026, 5, 15),
        effective_date=date(2026, 6, 15),
        status="in_force",
        legal_references=["ro:lege:99:2026"],
        amends=["ro:lege:260:2008"],
        repeals=[],
        full_text=(
            "Termenul de notificare a daunei se modifica de la "
            "10 zile la 5 zile."
        ),
        document_hash="demo-hash",
        extraction_confidence=0.95,
        source_metadata={"is_synthetic": True},
        created_at=now,
        updated_at=now,
    )


def make_legislatie_legal_document() -> NormalizedLegalDocument:
    return make_legal_document().model_copy(
        update={
            "source_id": "ro_portal_legislativ",
            "source_key": "ro:lege:120:2026",
            "canonical_url": (
                "https://legislatie.just.ro/Public/DetaliiDocument/1202026"
            ),
            "source_url": (
                "https://legislatie.just.ro/Public/DetaliiDocument/1202026"
            ),
            "external_identifier": "ro:lege:120:2026",
            "title": "LEGE nr. 120/2026 privind notificarea daunelor PAD",
            "issuer": "Parlamentul României",
            "legal_references": ["ro:lege:120:2026"],
            "amends": ["ro:lege:260:2008"],
            "source_metadata": {"extractor_id": "legislatie_just"},
        }
    )


def make_template() -> Template:
    return Template(
        id=42,
        template_code="DEMO_PAD_POLICY_WORDING_RO",
        name="DEMO - PAD Policy Wording Romania",
        version="demo-v1",
        document_type="insurance_contract",
        is_active=True,
        content=(
            "Asiguratul trebuie sa notifice dauna in termen de "
            "10 zile calendaristice de la producerea evenimentului."
        ),
        jurisdiction="RO",
        product_line="property",
        legal_references_json=["ro:lege:260:2008"],
        metadata_json={"is_synthetic": True},
        created_at=datetime(2026, 5, 15, 10, 0, tzinfo=UTC),
    )


def make_full_wording_template() -> Template:
    return make_template().model_copy(
        update={
            "content": (
                "Asiguratul trebuie sa notifice dauna in termen de "
                "10 zile calendaristice de la producerea evenimentului. "
                "Incendiul este arderea cu flacara deschisa, produsa accidental, "
                "care se poate extinde prin propria forta. "
                "Furtuna si grindina sunt fenomene atmosferice cu intensitate "
                "suficienta pentru a provoca avarii directe acoperisului. "
                "Reinnoirea contractului nu este automata decat daca polita "
                "prevede expres acest lucru. "
                "Datele pot fi comunicate prestatorilor, evaluatorilor, "
                "reasiguratorilor, consultantilor, autoritatilor sau altor "
                "destinatari. "
                "In cazul respingerii totale sau partiale, Asiguratorul va "
                "indica motivele principale ale deciziei. "
                "Reclamatiile privind administrarea contractului sau solutionarea "
                "unei daune trebuie sa indice polita si dosarul de dauna. "
                "Contractul poate inceta inainte de termen daca riscul inceteaza "
                "sa existe."
            )
        }
    )


def make_candidate() -> LegalDocumentTemplateReviewCandidate:
    now = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
    return LegalDocumentTemplateReviewCandidate(
        candidate_id=UUID("93000000-0000-0000-0000-000000000001"),
        normalized_legal_document_id=make_legal_document().id,
        template_id=42,
        template_code="DEMO_PAD_POLICY_WORDING_RO",
        template_name="DEMO - PAD Policy Wording Romania",
        template_version="demo-v1",
        template_version_hash="template-version-hash",
        match_type="amended_reference",
        matched_reference="ro:lege:260:2008",
        review_reason=(
            "DEMO - Legea nr. 99/2026 amends ro:lege:260:2008, "
            "which is referenced by template DEMO_PAD_POLICY_WORDING_RO."
        ),
        confidence=0.95,
        status="needs_review",
        source_metadata={"is_synthetic": True},
        created_at=now,
        updated_at=now,
    )
