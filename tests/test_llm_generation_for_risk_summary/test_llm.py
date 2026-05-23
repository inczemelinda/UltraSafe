#!/usr/bin/env python3
"""
Script de testare pentru OpenAICompatibleSupplementaryTextGenerator
Testează clientul OpenAI-compatible fără să depindă de mediul local.
"""

import json
import sys
import os
from types import SimpleNamespace

import pytest

#directorul src trebuie adaugat în PYTHONPATH pentru importuri
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from underwright.infrastructure.llm.openai_compatible import OpenAICompatibleSupplementaryTextGenerator  # noqa: E402


def load_test_data():
    """Încarcă datele de test din contract-template.json"""
    template_path = os.path.join(project_root, 'docs', 'contract-template.json')

    with open(template_path, 'r', encoding='utf-8') as f:
        context = json.load(f)

    return context


def create_rendered_template():
    """Creează un rendered_template simplu pentru test"""
    return """CONTRACT DE ASIGURARE A LOCUINȚEI
                Seria și numărul poliței: PAD-RISK-2026-000145
                Încheiat astăzi, la data de 2026-04-20, între societatea de asigurare Asigurator SA...
                Art. 5 - Profilul de risc        
                5.1. În baza informațiilor consolidate la momentul subscrierii, nivelul de risc asociat bunului asigurat este evaluat ca fiind mediu-ridicat.
                5.2. Rezumatul evaluării de risc este următorul: [AICI VA FI GENERAT DE LLM]
                5.3. Starea validării datelor utilizate în evaluarea prezentului contract este validat_complet.
            """

def test_prompt_generation():
    """Testează generarea prompt-ului"""
    print("=== TEST GENERARE PROMPT ===")

    context = load_test_data()
    generator = OpenAICompatibleSupplementaryTextGenerator(api_key="test-key")

    # Extrage date pentru prompt
    risk_profile = context.get("risk_profile", {})
    overall_level = risk_profile.get("overall_risk_level", "necunoscut")
    risk_score = risk_profile.get("risk_score", 0)
    factors = risk_profile.get("factors", [])

    prompt = generator._build_prompt(overall_level, risk_score, factors)

    print("Prompt generat pentru OpenAI:")
    print("=" * 50)
    print(prompt)
    print("=" * 50)
    print()


def test_generate_uses_openai_response(monkeypatch):
    """Testează generarea folosind un răspuns fake de la API."""
    context = load_test_data()
    rendered_template = create_rendered_template()
    expected_text = "Rezumat generat pentru test."

    def fake_post(url, headers, json, timeout):
        assert url == "https://api.openai.com/v1/chat/completions"
        assert headers["Authorization"] == "Bearer test-key"
        assert json["messages"][0]["role"] == "user"
        assert timeout == 30.0
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": f"  {expected_text}  "}}]
            },
        )

    monkeypatch.setattr("underwright.infrastructure.llm.openai_compatible.httpx.post", fake_post)

    generator = OpenAICompatibleSupplementaryTextGenerator(api_key="test-key")

    assert generator.generate(context, rendered_template) == expected_text


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is required for the optional live OpenAI smoke test.",
)
def test_real_openai_call():
    """Testează cu OpenAI API real folosind cheia din variabile de mediu"""
    print("=== TEST CU OPENAI API REAL ===")

    # Încarcă datele reale
    context = load_test_data()
    rendered_template = create_rendered_template()

    print("Context încărcat:", " Da" if context else " Nu")
    print("Template pregătit:", " Da" if rendered_template else " Nu")
    print()

    try:
        # Inițializează cu cheia din variabile de mediu
        generator = OpenAICompatibleSupplementaryTextGenerator()

        print("Apelare OpenAI API...")
        print()

        result = generator.generate(context, rendered_template)

        print("✅ Răspuns primit de la OpenAI!")
        print()

        print("Rezumat suplimentar de risc generat:")
        print("=" * 50)
        print(result)
        print("=" * 50)

    except Exception as e:
        print(f"❌ Eroare la apel OpenAI: {e}")
        print("Verifică că OPENAI_API_KEY este setată corect în variabile de mediu")

    print()


def main():
    """Funcția principală"""
    print("Testare Client OpenAI - Generator rezumat suplimentar de risc")

    print()

    try:
        test_prompt_generation()
        test_real_openai_call()
        print("✅ Testele au trecut!")

    except Exception as e:
        print(f"❌ Eroare în testare: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
