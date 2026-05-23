from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
import hashlib
import os
from uuid import UUID

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


SUPPORTED_DATASETS = {"law_change_pipeline_demo_v1"}
COMMAND_NAME = "seed-legal-demo-data"

DATASET = "law_change_pipeline_demo_v1"
SOURCE_ID = "demo_ro_portal_legislativ"
RAW_ITEM_ID = UUID("91000000-0000-0000-0000-000000000001")
LEGAL_DOCUMENT_ID = UUID("92000000-0000-0000-0000-000000000001")
NORMALIZATION_RESULT_ID = UUID("95000000-0000-0000-0000-000000000001")
EVENT_ID = UUID("94000000-0000-0000-0000-000000000001")
CANDIDATE_ID = UUID("93000000-0000-0000-0000-000000000001")
TITLE = "DEMO - Legea nr. 99/2026 pentru modificarea Legii nr. 260/2008"
TEMPLATE_CODE = "DEMO_PAD_POLICY_WORDING_RO"
TEMPLATE_NAME = "DEMO - PAD Policy Wording Romania"
CANONICAL_URL = f"demo://{DATASET}/ro/lege-99-2026"
CREATED_AT = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
PUBLICATION_DATE = date(2026, 5, 15)
EFFECTIVE_DATE = date(2026, 6, 15)
LEGAL_FULL_TEXT = (
    "DEMO - Legea nr. 99/2026 pentru modificarea Legii nr. 260/2008.\n\n"
    "Legea nr. 99/2026 modifica Legea nr. 260/2008 privind asigurarea "
    "obligatorie a locuintelor.\n\n"
    "DEMO: termenul de notificare a daunei se modifica de la 10 zile "
    "calendaristice la 5 zile calendaristice de la producerea evenimentului.\n\n"
    "Publicata in DEMO - Monitorul Oficial nr. 500/2026. Prezenta lege intra "
    "in vigoare la data de 15 iunie 2026."
)
TEMPLATE_CONTENT = (
    "DEMO - PAD Policy Wording Romania\n\n"
    "Prezenta poliță este emisă în conformitate cu Legea nr. 260/2008. "
    "Asiguratul trebuie să notifice dauna în termen de 10 zile calendaristice "
    "de la producerea evenimentului."
)


@dataclass(frozen=True)
class LegalDemoSeedResult:
    dataset: str
    reset: bool
    sources: int
    raw_items: int
    legal_documents: int
    events: int
    templates: int
    review_candidates: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=COMMAND_NAME)
    parser.add_argument("--dataset", default=DATASET)
    parser.add_argument("--reset", action="store_true")
    return parser


def print_result(result: LegalDemoSeedResult) -> None:
    print(
        f"dataset={result.dataset} "
        f"reset={str(result.reset).lower()} "
        f"sources={result.sources} "
        f"raw_items={result.raw_items} "
        f"legal_documents={result.legal_documents} "
        f"events={result.events} "
        f"templates={result.templates} "
        f"review_candidates={result.review_candidates}"
    )


def seed_legal_demo_data(
    connection_factory,
    *,
    dataset: str,
    reset: bool = False,
) -> LegalDemoSeedResult:
    if dataset not in SUPPORTED_DATASETS:
        known = ", ".join(sorted(SUPPORTED_DATASETS))
        raise ValueError(f"Unsupported legal demo dataset: {dataset}. Known: {known}.")

    with connection_factory() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if reset:
                _reset_dataset(cur, dataset)
            _upsert_source(cur, dataset)
            _upsert_raw_item(cur, dataset)
            _upsert_normalized_legal_document(cur, dataset)
            _upsert_external_event_projection(cur, dataset)
            template_id = _upsert_template(cur, dataset)
            _upsert_template_review_candidate(cur, dataset, template_id)
        conn.commit()

    return LegalDemoSeedResult(
        dataset=dataset,
        reset=reset,
        sources=1,
        raw_items=1,
        legal_documents=1,
        events=1,
        templates=1,
        review_candidates=1,
    )


def _reset_dataset(cur, dataset: str) -> None:
    cur.execute(
        """
        DELETE FROM template_draft_revision
        WHERE source_metadata->>'demo_dataset' = %s
           OR suggestion_id IN (
            SELECT id
            FROM template_change_suggestion
            WHERE candidate_id IN (
                SELECT candidate_id
                FROM legal_document_template_review_candidate
                WHERE source_metadata->>'demo_dataset' = %s
                   OR normalized_legal_document_id IN (
                    SELECT id
                    FROM normalized_legal_document
                    WHERE source_metadata->>'demo_dataset' = %s
                )
                   OR template_id IN (
                    SELECT id
                    FROM template
                    WHERE metadata_json->>'demo_dataset' = %s
                )
            )
        )
        """,
        (dataset, dataset, dataset, dataset),
    )
    cur.execute(
        """
        DELETE FROM template_change_suggestion
        WHERE candidate_id IN (
            SELECT candidate_id
            FROM legal_document_template_review_candidate
            WHERE source_metadata->>'demo_dataset' = %s
               OR normalized_legal_document_id IN (
                SELECT id
                FROM normalized_legal_document
                WHERE source_metadata->>'demo_dataset' = %s
            )
               OR template_id IN (
                SELECT id
                FROM template
                WHERE metadata_json->>'demo_dataset' = %s
            )
        )
        """,
        (dataset, dataset, dataset),
    )
    cur.execute(
        """
        DELETE FROM legal_document_template_review_candidate
        WHERE source_metadata->>'demo_dataset' = %s
           OR normalized_legal_document_id IN (
            SELECT id
            FROM normalized_legal_document
            WHERE source_metadata->>'demo_dataset' = %s
        )
           OR template_id IN (
            SELECT id
            FROM template
            WHERE metadata_json->>'demo_dataset' = %s
        )
        """,
        (dataset, dataset, dataset),
    )
    cur.execute(
        """
        DELETE FROM intelligence_template_review_candidate
        WHERE metadata_json->>'demo_dataset' = %s
           OR event_id IN (
            SELECT event_id
            FROM external_event
            WHERE classification_json->>'demo_dataset' = %s
        )
        """,
        (dataset, dataset),
    )
    cur.execute(
        """
        DELETE FROM external_event
        WHERE classification_json->>'demo_dataset' = %s
        """,
        (dataset,),
    )
    cur.execute(
        """
        DELETE FROM template
        WHERE metadata_json->>'demo_dataset' = %s
        """,
        (dataset,),
    )
    cur.execute(
        """
        DELETE FROM legal_document_normalization_result
        WHERE source_metadata->>'demo_dataset' = %s
        """,
        (dataset,),
    )
    cur.execute(
        """
        DELETE FROM normalized_legal_document
        WHERE source_metadata->>'demo_dataset' = %s
        """,
        (dataset,),
    )
    cur.execute(
        """
        DELETE FROM raw_source_item
        WHERE canonical_url LIKE %s
        """,
        (f"demo://{dataset}/%",),
    )
    cur.execute(
        """
        DELETE FROM intelligence_source
        WHERE config_json->>'demo_dataset' = %s
        """,
        (dataset,),
    )


def _upsert_source(cur, dataset: str) -> None:
    cur.execute(
        """
        INSERT INTO intelligence_source (
            source_id,
            name,
            country,
            source_type,
            trust_tier,
            connector_type,
            language,
            enabled,
            config_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id) DO UPDATE SET
            name = EXCLUDED.name,
            country = EXCLUDED.country,
            source_type = EXCLUDED.source_type,
            trust_tier = EXCLUDED.trust_tier,
            connector_type = EXCLUDED.connector_type,
            language = EXCLUDED.language,
            enabled = EXCLUDED.enabled,
            config_json = EXCLUDED.config_json,
            updated_at = EXCLUDED.updated_at
        """,
        (
            SOURCE_ID,
            "DEMO - Portal Legislativ Romania",
            "RO",
            "legal_portal",
            "authoritative",
            "manual",
            "ro",
            False,
            Jsonb(
                {
                    "pipeline_domain": "legal_documents",
                    "parser_id": "ro_portal_legislativ",
                    "jurisdiction": "RO",
                    "demo_dataset": dataset,
                    "is_synthetic": True,
                    "seed_command": COMMAND_NAME,
                }
            ),
            CREATED_AT,
            CREATED_AT,
        ),
    )


def _upsert_raw_item(cur, dataset: str) -> None:
    content_hash = _sha256(LEGAL_FULL_TEXT)
    cur.execute(
        """
        INSERT INTO raw_source_item (
            raw_item_id,
            source_id,
            original_url,
            canonical_url,
            published_at,
            fetched_at,
            title,
            raw_html,
            extracted_text,
            attachments_json,
            content_hash,
            fetch_status,
            parse_status,
            error_message,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (raw_item_id) DO UPDATE SET
            title = EXCLUDED.title,
            raw_html = EXCLUDED.raw_html,
            extracted_text = EXCLUDED.extracted_text,
            content_hash = EXCLUDED.content_hash,
            fetched_at = EXCLUDED.fetched_at
        """,
        (
            RAW_ITEM_ID,
            SOURCE_ID,
            CANONICAL_URL,
            CANONICAL_URL,
            PUBLICATION_DATE,
            CREATED_AT,
            TITLE,
            f"<html><body><pre>{LEGAL_FULL_TEXT}</pre></body></html>",
            LEGAL_FULL_TEXT,
            Jsonb([]),
            content_hash,
            "success",
            "success",
            None,
            CREATED_AT,
        ),
    )


def _upsert_normalized_legal_document(cur, dataset: str) -> None:
    document_hash = _sha256(LEGAL_FULL_TEXT)
    cur.execute(
        """
        INSERT INTO normalized_legal_document (
            id,
            raw_source_item_id,
            source_id,
            source_key,
            jurisdiction,
            parser_id,
            canonical_url,
            source_url,
            external_identifier,
            title,
            language,
            issuer,
            instrument_type,
            instrument_number,
            instrument_year,
            publication_reference,
            publication_date,
            effective_date,
            status,
            legal_references,
            amends,
            repeals,
            full_text,
            summary,
            document_hash,
            extraction_confidence,
            parser_warnings,
            source_metadata,
            created_at,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            publication_reference = EXCLUDED.publication_reference,
            publication_date = EXCLUDED.publication_date,
            effective_date = EXCLUDED.effective_date,
            legal_references = EXCLUDED.legal_references,
            amends = EXCLUDED.amends,
            full_text = EXCLUDED.full_text,
            document_hash = EXCLUDED.document_hash,
            extraction_confidence = EXCLUDED.extraction_confidence,
            source_metadata = EXCLUDED.source_metadata,
            updated_at = EXCLUDED.updated_at
        """,
        (
            LEGAL_DOCUMENT_ID,
            RAW_ITEM_ID,
            SOURCE_ID,
            SOURCE_ID,
            "RO",
            "ro_portal_legislativ",
            CANONICAL_URL,
            CANONICAL_URL,
            "demo:ro:lege:99:2026",
            TITLE,
            "ro",
            "DEMO - Parlamentul României",
            "lege",
            "99",
            2026,
            "DEMO - Monitorul Oficial nr. 500/2026",
            PUBLICATION_DATE,
            EFFECTIVE_DATE,
            "in_force",
            Jsonb(["ro:lege:99:2026"]),
            Jsonb(["ro:lege:260:2008"]),
            Jsonb([]),
            LEGAL_FULL_TEXT,
            "DEMO - Legea nr. 99/2026 modifies claim notification timing for PAD wording.",
            document_hash,
            0.95,
            Jsonb([]),
            Jsonb(
                {
                    "is_synthetic": True,
                    "demo_dataset": dataset,
                    "seed_command": COMMAND_NAME,
                }
            ),
            CREATED_AT,
            CREATED_AT,
        ),
    )
    cur.execute(
        """
        INSERT INTO legal_document_normalization_result (
            id,
            raw_source_item_id,
            source_id,
            parser_id,
            normalized_legal_document_id,
            status,
            reason,
            parser_warnings,
            source_metadata,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (raw_source_item_id) DO UPDATE SET
            normalized_legal_document_id = EXCLUDED.normalized_legal_document_id,
            status = EXCLUDED.status,
            reason = EXCLUDED.reason,
            source_metadata = EXCLUDED.source_metadata,
            updated_at = EXCLUDED.updated_at
        """,
        (
            NORMALIZATION_RESULT_ID,
            RAW_ITEM_ID,
            SOURCE_ID,
            "ro_portal_legislativ",
            LEGAL_DOCUMENT_ID,
            "normalized",
            None,
            Jsonb([]),
            Jsonb(
                {
                    "is_synthetic": True,
                    "demo_dataset": dataset,
                    "seed_command": COMMAND_NAME,
                }
            ),
            CREATED_AT,
            CREATED_AT,
        ),
    )


def _upsert_external_event_projection(cur, dataset: str) -> None:
    cur.execute(
        """
        INSERT INTO external_event (
            event_id,
            raw_item_id,
            source_id,
            source_type,
            trust_tier,
            original_url,
            published_at,
            ingested_at,
            title,
            body_text_ref,
            body_text,
            original_language,
            country,
            jurisdiction,
            event_type,
            line_of_business,
            product,
            topics_json,
            perils_json,
            severity,
            confidence,
            underwriter_summary,
            recommended_action,
            evidence_json,
            classification_json,
            status,
            created_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (raw_item_id) DO UPDATE SET
            title = EXCLUDED.title,
            body_text = EXCLUDED.body_text,
            topics_json = EXCLUDED.topics_json,
            severity = EXCLUDED.severity,
            confidence = EXCLUDED.confidence,
            underwriter_summary = EXCLUDED.underwriter_summary,
            recommended_action = EXCLUDED.recommended_action,
            evidence_json = EXCLUDED.evidence_json,
            classification_json = EXCLUDED.classification_json,
            status = EXCLUDED.status
        """,
        (
            EVENT_ID,
            RAW_ITEM_ID,
            SOURCE_ID,
            "legal_portal",
            "authoritative",
            CANONICAL_URL,
            PUBLICATION_DATE,
            CREATED_AT,
            TITLE,
            f"raw_source_item:{RAW_ITEM_ID}:extracted_text",
            LEGAL_FULL_TEXT,
            "ro",
            "RO",
            "RO",
            "regulatory_update",
            "property",
            "residential_property",
            Jsonb(["PAD / compulsory home insurance", "claim notification deadline"]),
            Jsonb([]),
            "high",
            0.95,
            (
                "DEMO - Legea nr. 99/2026 amends Legea nr. 260/2008 and changes "
                "the claim notification deadline from 10 days to 5 days."
            ),
            (
                "Review PAD Policy Wording Romania and update the claim "
                "notification deadline clause."
            ),
            Jsonb(
                [
                    {
                        "snippet": (
                            "Termenul de notificare a daunei se modifica de la "
                            "10 zile calendaristice la 5 zile calendaristice."
                        ),
                        "reason": "The law changes a deadline that appears in the template.",
                    }
                ]
            ),
            Jsonb(
                {
                    "is_synthetic": True,
                    "demo_dataset": dataset,
                    "normalized_legal_document_id": str(LEGAL_DOCUMENT_ID),
                    "classification_mode": "deterministic_demo_seed",
                }
            ),
            "classified",
            CREATED_AT,
        ),
    )


def _upsert_template(cur, dataset: str) -> int:
    cur.execute(
        """
        INSERT INTO template (
            template_code,
            name,
            version,
            document_type,
            is_active,
            content,
            jurisdiction,
            product_line,
            legal_references_json,
            metadata_json,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (template_code) DO UPDATE SET
            name = EXCLUDED.name,
            version = EXCLUDED.version,
            document_type = EXCLUDED.document_type,
            is_active = EXCLUDED.is_active,
            content = EXCLUDED.content,
            jurisdiction = EXCLUDED.jurisdiction,
            product_line = EXCLUDED.product_line,
            legal_references_json = EXCLUDED.legal_references_json,
            metadata_json = EXCLUDED.metadata_json
        RETURNING id
        """,
        (
            TEMPLATE_CODE,
            TEMPLATE_NAME,
            "demo-v1",
            "insurance_contract",
            True,
            TEMPLATE_CONTENT,
            "RO",
            "property",
            Jsonb(["ro:lege:260:2008"]),
            Jsonb(
                {
                    "is_synthetic": True,
                    "demo_dataset": dataset,
                    "seed_command": COMMAND_NAME,
                }
            ),
            CREATED_AT,
        ),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError("Demo template was not saved.")
    return int(row["id"])


def _upsert_template_review_candidate(
    cur,
    dataset: str,
    template_id: int,
) -> None:
    template_version_hash = _sha256(f"{TEMPLATE_CODE}\ndemo-v1\n{TEMPLATE_CONTENT}")
    cur.execute(
        """
        INSERT INTO legal_document_template_review_candidate (
            candidate_id,
            normalized_legal_document_id,
            template_id,
            template_code,
            template_name,
            template_version,
            template_version_hash,
            match_type,
            matched_reference,
            review_reason,
            confidence,
            status,
            source_metadata,
            created_at,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
        ON CONFLICT (
            normalized_legal_document_id,
            template_id,
            template_version_hash,
            match_type,
            matched_reference
        ) DO UPDATE SET
            template_code = EXCLUDED.template_code,
            template_name = EXCLUDED.template_name,
            template_version = EXCLUDED.template_version,
            review_reason = EXCLUDED.review_reason,
            confidence = EXCLUDED.confidence,
            status = EXCLUDED.status,
            source_metadata = EXCLUDED.source_metadata,
            updated_at = EXCLUDED.updated_at
        """,
        (
            CANDIDATE_ID,
            LEGAL_DOCUMENT_ID,
            template_id,
            TEMPLATE_CODE,
            TEMPLATE_NAME,
            "demo-v1",
            template_version_hash,
            "amended_reference",
            "ro:lege:260:2008",
            (
                "DEMO - Legea nr. 99/2026 amends Legea nr. 260/2008, which "
                "is referenced by DEMO - PAD Policy Wording Romania. Review "
                "the claim notification deadline clause."
            ),
            0.95,
            "needs_review",
            Jsonb(
                {
                    "is_synthetic": True,
                    "demo_dataset": dataset,
                    "seed_command": COMMAND_NAME,
                }
            ),
            CREATED_AT,
            CREATED_AT,
        ),
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


load_dotenv()


def connection_factory():
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ.get("POSTGRES_PORT", 5432),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = seed_legal_demo_data(
            connection_factory,
            dataset=args.dataset,
            reset=args.reset,
        )
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
