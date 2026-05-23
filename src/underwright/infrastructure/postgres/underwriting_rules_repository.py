from __future__ import annotations

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.domain.underwriting_rules import UnderwritingRulesDocument


DOCUMENT_KEY = "employee_underwriting_rules"


DEFAULT_RULES_CONTENT = {
    "key": DOCUMENT_KEY,
    "sections": [
        {
            "id": "quote_review_principles",
            "title": "Quote Review Principles",
            "blocks": [
                {
                    "id": "principles",
                    "kind": "list",
                    "items": [
                        "A Quote is the client's insurance request.",
                        "A Contract is generated only after a Quote is approved.",
                        "A Claim is separate and linked to an existing contract.",
                        "Clients cannot see the internal risk score.",
                        "Employees can see the risk score, triggered rules, and suggested next action.",
                        "Some questions are used for premium calculation; others support underwriting decisions.",
                    ],
                }
            ],
        },
        {
            "id": "premium_calculation_model",
            "title": "Premium Calculation Model",
            "blocks": [
                {
                    "id": "premium_formula",
                    "kind": "notice",
                    "text": "Annual Premium = (Coverage Amount x Base Rate) x Risk Multipliers - Security Discounts",
                },
                {
                    "id": "premium_factors",
                    "kind": "table",
                    "headers": ["Factor", "Option", "Multiplier"],
                    "rows": [
                        ["Property use", "Owner occupied", "1.00"],
                        ["Property use", "Rented", "1.10"],
                        ["Property use", "Holiday home", "1.10"],
                        ["Property use", "Vacant", "1.30"],
                        ["Property use", "Commercial use", "1.25"],
                        ["Construction", "Concrete", "0.95"],
                        ["Construction", "Brick", "0.95"],
                        ["Construction", "Steel", "1.00"],
                        ["Construction", "Wood", "1.20"],
                        ["Property age", "< 20 years", "0.95"],
                        ["Property age", "20-50 years", "1.00"],
                        ["Property age", "50+ years", "1.15"],
                        ["Claims history", "None", "1.00"],
                        ["Claims history", "1-5 claims", "1.25"],
                        ["Claims history", "> 5 claims", "Manual review"],
                    ],
                },
                {
                    "id": "security_discounts",
                    "kind": "table",
                    "headers": ["Security Feature", "Discount"],
                    "rows": [
                        ["Alarm system", "-5%"],
                        ["Smoke detector", "-3%"],
                        ["Sprinklers", "-5%"],
                        ["Security cameras", "-5%"],
                        ["Security door", "-3%"],
                        ["Security guard", "-5%"],
                        ["Multiple measures", "Maximum -10% total"],
                    ],
                },
            ],
        },
        {
            "id": "manual_review_rules",
            "title": "Manual Review Rules",
            "blocks": [
                {
                    "id": "manual_review_table",
                    "kind": "table",
                    "headers": ["Rule", "Impact"],
                    "rows": [
                        ["Property built before 1975", "Risk score -20"],
                        ["More than 5 claims in last 5 years", "Risk score -30"],
                        ["Vacant property", "Risk score -15"],
                        ["Wood construction", "Risk score -10"],
                        ["Security measures present", "Can improve score up to +10"],
                        ["Final score <= 70", "Send quote to underwriting review"],
                    ],
                }
            ],
        },
        {
            "id": "underwriting_questions",
            "title": "Questions Used for Underwriting",
            "blocks": [
                {
                    "id": "underwriting_questions_table",
                    "kind": "table",
                    "headers": ["Question", "Used for Premium?", "Used for Underwriting?"],
                    "rows": [
                        ["Property use", "Yes", "Yes"],
                        ["Rebuild/coverage value", "Yes", "Yes"],
                        ["Construction type", "Yes", "Yes"],
                        ["Year built", "Yes", "Yes"],
                        ["Claims history", "Yes", "Yes"],
                        ["Security measures", "Yes, as discount", "Yes"],
                        ["Location risk", "Optional/AI-derived", "Yes"],
                        ["High-value items", "Only if coverage extension exists", "Yes"],
                        ["Renovations/structural changes", "Usually no", "Yes"],
                        ["Occupancy/vacancy", "Yes", "Yes"],
                        ["Key systems update history", "Usually no", "Yes"],
                    ],
                }
            ],
        },
        {
            "id": "coverage_and_limits",
            "title": "Coverage and Limits",
            "blocks": [
                {
                    "id": "coverage_limits",
                    "kind": "list",
                    "items": [
                        "Overall policy limit equals declared rebuild/replacement value.",
                        "Fire and explosion: 100% of sum insured.",
                        "Storm/hail: 100%.",
                        "Water damage: 20-30%.",
                        "Theft structural damage: 10-20%.",
                        "Flood: 15-25%.",
                        "Earthquake: 20-30%.",
                    ],
                }
            ],
        },
        {
            "id": "claim_review_rules",
            "title": "Claim Review Rules",
            "blocks": [
                {
                    "id": "claim_review_table",
                    "kind": "table",
                    "headers": ["Claim Rule", "Score Impact"],
                    "rows": [
                        ["Missing photos", "-25"],
                        ["Missing documents", "-25"],
                        ["Damage over 50% of coverage", "-15"],
                        ["Description too short", "-15"],
                        ["Incident type Other", "-10"],
                        ["No emergency services for severe events", "-10"],
                    ],
                }
            ],
        },
    ],
}


class PostgresUnderwritingRulesRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def get_document(self) -> UnderwritingRulesDocument:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                self._ensure_table(cur)
                cur.execute(
                    """
                    SELECT document_key, content_json, updated_at, updated_by
                    FROM underwriting_rules_document
                    WHERE document_key = %s
                    """,
                    (DOCUMENT_KEY,),
                )
                row = cur.fetchone()
                if row is None:
                    row = self._insert_default(cur)
                conn.commit()
        return self._to_document(row)

    def update_document(
        self,
        document: UnderwritingRulesDocument,
        updated_by: str | None = None,
    ) -> UnderwritingRulesDocument:
        content = document.model_dump(mode="json", exclude={"updated_at", "updated_by"})
        content["key"] = DOCUMENT_KEY

        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                self._ensure_table(cur)
                cur.execute(
                    """
                    INSERT INTO underwriting_rules_document (
                        document_key,
                        content_json,
                        updated_by,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, NOW(), NOW())
                    ON CONFLICT (document_key)
                    DO UPDATE SET
                        content_json = EXCLUDED.content_json,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = NOW()
                    RETURNING document_key, content_json, updated_at, updated_by
                    """,
                    (DOCUMENT_KEY, Jsonb(content), updated_by),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("Underwriting rules were not saved")
        return self._to_document(row)

    def _ensure_table(self, cur) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS underwriting_rules_document (
                document_key TEXT PRIMARY KEY,
                content_json JSONB NOT NULL,
                updated_by TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

    def _insert_default(self, cur):
        cur.execute(
            """
            INSERT INTO underwriting_rules_document (
                document_key,
                content_json,
                updated_by,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, NOW(), NOW())
            RETURNING document_key, content_json, updated_at, updated_by
            """,
            (DOCUMENT_KEY, Jsonb(DEFAULT_RULES_CONTENT), None),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Default underwriting rules were not created")
        return row

    def _to_document(self, row) -> UnderwritingRulesDocument:
        content = dict(row["content_json"])
        content["key"] = row["document_key"]
        content["updated_at"] = row["updated_at"]
        content["updated_by"] = row["updated_by"]
        return UnderwritingRulesDocument.model_validate(content)


__all__ = [
    "DEFAULT_RULES_CONTENT",
    "DOCUMENT_KEY",
    "PostgresUnderwritingRulesRepository",
]
