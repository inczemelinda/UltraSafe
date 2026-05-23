from __future__ import annotations
import os
import httpx
from typing import Dict, Any
from dotenv import load_dotenv

# Încarcă variabilele din fișierul .env dacă există
load_dotenv()


class OpenAICompatibleSupplementaryTextGenerator:
    def __init__(self, api_key: str | None, model: str = "gpt-3.5-turbo"):

        self.api_base = "https://api.openai.com/v1"

        # Cheia API din parametru sau variabile de mediu
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        self.model = model

        if not self.api_key:
            raise ValueError(
                "API key required. Set OPENAI_API_KEY in environment variables or .env file."
            )

    def generate(self, context: Dict[str, Any], rendered_template: str) -> str:
        """
        Generează rezumatul suplimentar de risc pentru Art. 5.2 din contractul PAD.
        Args:
            context: Datele complete ale contractului în format dict
            rendered_template: Contractul PAD cu Art. 1-9 populat
        Returns:
            Textul descriptiv al evaluării riscurilor
        """

        # Extragem datele de risc din context
        risk_profile = context.get("risk_profile", {})
        overall_level = risk_profile.get("overall_risk_level", "necunoscut")
        risk_score = risk_profile.get("risk_score", 0)
        factors = risk_profile.get("factors", [])

        # Construim prompt-ul
        prompt = self._build_prompt(overall_level, risk_score, factors)

        # Apelăm API-ul OpenAI
        response = self._call_openai_api(prompt)

        return response.strip()

    def _build_prompt(self, overall_level: str, risk_score: int, factors: list) -> str:
        """Construiește prompt-ul pentru LLM."""
        factors_text = "\n".join(
            [
                f"- {f['label']}: nivel {f['level']} (scor {f['score']}), motive: {', '.join(f['evidence'])}"
                for f in factors
            ]
        )

        return f"""
               # Rol
               Ești un expert în evaluarea riscurilor pentru asigurări.

               # Context proprietate
               Primești următoarele informații despre o proprietate:

               - **Nivel general de risc:** {overall_level}
               - **Scor total de risc:** {risk_score}
               - **Factori de risc:** {factors_text}

               # Sarcină
               Generează un rezumat descriptiv, profesional, în limba română, care explică evaluarea riscurilor acestei proprietăți.

               # Cerințe pentru rezumat
               Rezumatul trebuie să:

               - fie concis, de maximum **120 de cuvinte**
               - menționeze **factorii principali de risc** și scorul asociat fiecăruia  
                  - exemplu: „expunerea la inundații – nivel ridicat, scor X”
               - aibă un ton **formal, clar și justificativ**
               - fie redactat **integral în limba română**, indiferent de limba în care sunt primite datele
               - fie ușor de înțeles atât pentru client, cât și pentru persoana care emite contractul

               # Utilizare
               Rezumatul va fi inclus în draftul final al documentației de asigurare și va servi drept justificare profesională a evaluării riscului.

               # Output
               Returnează doar rezumatul final, fără explicații suplimentare.

               Rezumat:
               """

    def _call_openai_api(self, prompt: str) -> str:
        """Apel către OpenAI API."""
        try:
            response = httpx.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise Exception(
                    f"OpenAI API error: {response.status_code} - {response.text}"
                )

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except Exception:
            # Fallback simplu în caz de eroare
            return "Proprietatea prezintă risc conform evaluării automate."
