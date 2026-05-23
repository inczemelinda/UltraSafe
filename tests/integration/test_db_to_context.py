from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
from uuid import UUID

import psycopg

from underwright.application.modules.contract_payload_builder import ContractPayloadBuilder
from underwright.application.services.case_context_service import CaseContextFactory
from underwright.domain.contract_lifecycle import build_contract_display_id
from underwright.infrastructure.postgres.contract_repository import (
    PostgresContractRepository,
)


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


class DbToContextIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")

        cls.connection_kwargs = {
            "dbname": os.environ.get("POSTGRES_DB", "underwright"),
            "user": os.environ.get("POSTGRES_USER", "postgres"),
            "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "host": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "port": os.environ.get("POSTGRES_PORT", "5432"),
        }
        cls.contract_number = os.environ.get(
            "TEST_CONTRACT_NUMBER",
            "PAD-RISK-2026-000145",
        )

        try:
            with psycopg.connect(**cls.connection_kwargs) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM contract WHERE contract_number = %s",
                        (cls.contract_number,),
                    )
                    row = cur.fetchone()
        except psycopg.Error as exc:
            raise unittest.SkipTest(
                "Docker Postgres is not reachable for integration tests. "
                f"Connection attempt failed: {exc}"
            ) from exc

        if row is None:
            raise unittest.SkipTest(
                "Seeded contract was not found. "
                "Start the Docker DB with schema + seed init first."
            )

        try:
            cls.contract_id = UUID(str(row[0]))
        except ValueError as exc:
            raise unittest.SkipTest(
                "Seeded contract id is not a UUID. "
                "Rebuild the Docker DB from the current schema and seed files."
            ) from exc

    @classmethod
    def connection_factory(cls):
        return psycopg.connect(**cls.connection_kwargs)

    def test_seeded_contract_builds_generation_json(self) -> None:
        repository = PostgresContractRepository(self.connection_factory)
        builder = ContractPayloadBuilder()

        source = repository.get_contract_context_source(self.contract_id)
        case_context = (
            CaseContextFactory().create_contract_case_context_from_contract_id(
                self.contract_id
            )
        )
        case_context.reference_data.contract_source = source
        result = builder.build(case_context)
        payload = case_context.domain_payload.contract_generation_payload
        rendered_json = json.dumps(payload, ensure_ascii=False, indent=2)
        output_path = Path(__file__).resolve().parents[2] / "generated" / "test_contract_context.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered_json, encoding="utf-8")
        print(f"Wrote contract context JSON to {output_path}")

        self.assertEqual(result.status, "success")
        self.assertEqual(payload["document_type"], "insurance_contract")
        self.assertEqual(
            payload["contract_meta"]["contract_id"],
            build_contract_display_id(
                contract_number=self.contract_number,
                legal_name=source.customer.full_name,
                fallback_id=source.contract.id,
            ),
        )
        self.assertEqual(
            payload["parties"]["insured"]["full_name"], source.customer.full_name
        )
        self.assertEqual(payload["pricing"]["final_premium_ron"], 1490.0)
        self.assertIsInstance(rendered_json, str)
        self.assertIn('"risk_profile"', rendered_json)
        self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
