from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import unittest
from uuid import UUID

from psycopg.types.json import Jsonb

from underwright.domain.contract_request import ContractRequest
from underwright.domain.email_message import EmailMessage
from underwright.domain.models import GeneratedDocument
from underwright.infrastructure.postgres.contract_repository import (
    PostgresContractRepository,
)
from underwright.infrastructure.postgres.contract_request_repository import (
    PostgresContractRequestRepository,
)
from underwright.infrastructure.postgres.email_repository import (
    PostgresEmailMessageRepository,
)
from underwright.infrastructure.postgres.generated_document_repository import (
    PostgresGeneratedDocumentRepository,
)
from underwright.infrastructure.postgres.template_repository import (
    PostgresTemplateRepository,
)


class FakeCursor:
    def __init__(self, fetchone_rows: list[dict] | None = None, fetchall_rows: list[list[dict]] | None = None) -> None:
        self.fetchone_rows = list(fetchone_rows or [])
        self.fetchall_rows = list(fetchall_rows or [])
        self.executed: list[tuple[str, object]] = []

    def execute(self, sql: str, params) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        if not self.fetchone_rows:
            return None
        return self.fetchone_rows.pop(0)

    def fetchall(self):
        if not self.fetchall_rows:
            return []
        return self.fetchall_rows.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False

    def cursor(self, row_factory=None):
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def make_connection_factory(cursor: FakeCursor):
    def factory():
        return FakeConnection(cursor)

    return factory


def _contract_read_row(
    *,
    contract_id: UUID = UUID("10000000-0000-0000-0000-000000000001"),
    customer_id: int = 1001,
    source_quote_request_id: UUID | None = UUID(
        "90000000-0000-0000-0000-000000000001"
    ),
    status: str = "generated",
) -> dict:
    now = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)
    return {
        "id": contract_id,
        "contract_number": "PAD-Q-2026-00000001",
        "document_type": "insurance_contract",
        "document_version": "1.0",
        "status": status,
        "source_quote_request_id": source_quote_request_id,
        "source_quote_document_id": 77,
        "source_quote_acceptance_id": None,
        "issue_date": date(2026, 4, 20),
        "effective_date": date(2026, 4, 20),
        "expiration_date": date(2027, 4, 19),
        "jurisdiction": "Romania",
        "governing_law": "Legea 260/2008",
        "currency": "RON",
        "created_at": now,
        "updated_at": now,
        "customer_id": customer_id,
        "customer_type": "individual",
        "customer_full_name": "Ion Popescu",
        "customer_national_id": "1800101223344",
        "customer_company_id": None,
        "customer_email": "ion.popescu@example.test",
        "customer_phone": "+40712345678",
        "customer_address_country": "Romania",
        "customer_address_county": "Bucuresti",
        "customer_address_city": "Bucuresti",
        "customer_address_street": "Str. Lalelelor",
        "customer_address_number": "12",
        "customer_address_postal_code": "031234",
        "customer_address_full_text": "Str. Lalelelor 12, Bucuresti",
        "asset_id": 1,
        "asset_type": "apartment",
        "usage_type": "owner occupied",
        "construction_type": "concrete",
        "year_built": 1986,
        "floor": 4,
        "area_sqm": Decimal("68.00"),
        "declared_value": Decimal("350000.00"),
        "occupancy": "owner occupied",
        "previous_claims_count": 0,
        "asset_address_country": "Romania",
        "asset_address_county": "Bucuresti",
        "asset_address_city": "Bucuresti",
        "asset_address_street": "Str. Lalelelor",
        "asset_address_number": "12",
        "asset_address_postal_code": "031234",
        "asset_address_full_text": "Str. Lalelelor 12, Bucuresti",
        "base_premium_ron": Decimal("600.00"),
        "final_premium_ron": Decimal("513.00"),
        "payment_plan_type": "annual",
        "installments": 1,
    }


class PostgresRepositoriesTestCase(unittest.TestCase):
    def test_email_repository_saves_request_id_for_inbound_messages(self) -> None:
        email_id = UUID("30000000-0000-0000-0000-000000000002")
        request_id = UUID("40000000-0000-0000-0000-000000000002")
        created_at = datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchone_rows=[
                (
                    email_id,
                    request_id,
                    request_id,
                    "INBOUND",
                    "client@example.com",
                    "claims@example.com",
                    "Re: Evidence request",
                    "Attached.",
                    "RECEIVED",
                    "postmark-message-id",
                    None,
                    created_at,
                    None,
                )
            ]
        )
        repo = PostgresEmailMessageRepository(make_connection_factory(cursor))

        saved = repo.save(
            EmailMessage(
                id=email_id,
                case_id=request_id,
                request_id=request_id,
                direction="INBOUND",
                from_email="client@example.com",
                to_email="claims@example.com",
                subject="Re: Evidence request",
                body="Attached.",
                status="RECEIVED",
                provider_message_id="postmark-message-id",
            )
        )

        sql, params = cursor.executed[0]
        assert "request_id" in sql
        assert params["request_id"] == request_id
        assert saved.request_id == request_id

    def test_email_repository_gets_by_provider_message_id(self) -> None:
        email_id = UUID("30000000-0000-0000-0000-000000000003")
        request_id = UUID("40000000-0000-0000-0000-000000000003")
        created_at = datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchone_rows=[
                (
                    email_id,
                    request_id,
                    request_id,
                    "INBOUND",
                    "client@example.com",
                    "claims@example.com",
                    "Re: Evidence request",
                    "Attached.",
                    "RECEIVED",
                    "postmark-message-id",
                    None,
                    created_at,
                    None,
                )
            ]
        )
        repo = PostgresEmailMessageRepository(make_connection_factory(cursor))

        email = repo.get_by_provider_message_id("postmark-message-id")

        sql, params = cursor.executed[0]
        assert "WHERE provider_message_id = %s" in sql
        assert params == ("postmark-message-id",)
        assert email is not None
        assert email.request_id == request_id
        assert email.provider_message_id == "postmark-message-id"

    def test_email_repository_lists_customer_emails_with_customer_case_scope(self) -> None:
        email_id = UUID("30000000-0000-0000-0000-000000000001")
        case_id = UUID("40000000-0000-0000-0000-000000000001")
        created_at = datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchall_rows=[
                [
                    (
                        email_id,
                        1001,
                        case_id,
                        "Claim 40000000",
                        "OUTBOUND",
                        "SENT",
                        "client@example.com",
                        "claims@example.com",
                        "Evidence request",
                        "Please send evidence.",
                        "Please send evidence.\n\nRegards,\nUnderwright Claims Team",
                        None,
                        "smtp",
                        "message-id",
                        None,
                        created_at,
                        created_at,
                        None,
                    )
                ]
            ]
        )
        repo = PostgresEmailMessageRepository(make_connection_factory(cursor))

        emails = repo.list_by_customer_id(1001)

        assert emails[0].id == email_id
        assert emails[0].customer_id == 1001
        assert emails[0].case_reference == "Claim 40000000"
        assert emails[0].body_preview == "Please send evidence."
        assert emails[0].body_text.endswith("Underwright Claims Team")
        sql, params = cursor.executed[0]
        assert "claim_request" in sql
        assert "quote_request" in sql
        assert "WHERE client_id = %(customer_id)s" in sql
        assert "ORDER BY e.created_at DESC" in sql
        assert params == {"customer_id": 1001}

    def test_contract_repository_builds_context_source(self) -> None:
        contract_id = UUID("10000000-0000-0000-0000-000000000001")
        cursor = FakeCursor(
            fetchone_rows=[
                {
                    "id": contract_id,
                    "contract_number": "PAD-RISK-2026-000145",
                    "document_type": "insurance_contract",
                    "document_version": "1.0",
                    "insurer_id": 1,
                    "customer_id": 1,
                    "insured_asset_id": 1,
                    "issue_date": date(2026, 4, 20),
                    "effective_date": date(2026, 5, 1),
                    "expiration_date": date(2027, 4, 30),
                    "jurisdiction": "Romania",
                    "governing_law": "Legea 260/2008",
                    "currency": "RON",
                    "status": "draft",
                    "created_at": datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
                    "updated_at": datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
                },
                {
                    "id": 1,
                    "type": "individual",
                    "full_name": "Ion Popescu",
                    "national_id": "1800101223344",
                    "company_id": None,
                    "email": "ion.popescu@example.test",
                    "phone": "+40712345678",
                    "address_id": 2,
                },
                {
                    "id": 2,
                    "country": "Romania",
                    "county": "Bucuresti",
                    "city": "Bucuresti",
                    "street": "Str. Lalelelor",
                    "number": "12",
                    "postal_code": "031234",
                    "full_text": "Str. Lalelelor 12, Sector 3, Bucuresti",
                },
                {
                    "id": 1,
                    "name": "Asigurator Demo SA",
                    "company_id": "RO12345678",
                    "representative_name": "Maria Ionescu",
                    "representative_role": "Director General",
                    "address_id": 1,
                },
                {
                    "id": 1,
                    "country": "Romania",
                    "county": "Bucuresti",
                    "city": "Bucuresti",
                    "street": "Bd. Exemplu",
                    "number": "100",
                    "postal_code": "010101",
                    "full_text": "Bd. Exemplu 100, Bucuresti",
                },
                {
                    "id": 1,
                    "customer_id": 1,
                    "asset_type": "apartment",
                    "usage_type": "residential",
                    "construction_type": "concrete",
                    "year_built": 1986,
                    "floor": 4,
                    "area_sqm": Decimal("68.00"),
                    "declared_value": Decimal("350000.00"),
                    "occupancy": "owner_occupied",
                    "previous_claims_count": 2,
                    "address_id": 2,
                    "created_at": datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
                    "updated_at": datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
                },
                {
                    "id": 2,
                    "country": "Romania",
                    "county": "Bucuresti",
                    "city": "Bucuresti",
                    "street": "Str. Lalelelor",
                    "number": "12",
                    "postal_code": "031234",
                    "full_text": "Str. Lalelelor 12, Sector 3, Bucuresti",
                },
                {
                    "id": 1,
                    "contract_id": contract_id,
                    "overall_risk_level": "medium_high",
                    "risk_score": 72,
                    "assessment_date": date(2026, 4, 20),
                    "created_at": datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
                },
                {
                    "id": 1,
                    "contract_id": contract_id,
                    "base_premium_ron": Decimal("1200.00"),
                    "adjustments_json": [
                        {
                            "source": "FLOOD_EXPOSURE",
                            "type": "percentage",
                            "value": "12.00",
                        },
                        {
                            "code": "property_type_multiplier",
                            "label": "Property type",
                            "adjustment_type": "multiplier",
                            "value": "1.08",
                            "amount": "48.00",
                            "explanation": "Property type multiplier: 1.08.",
                        },
                    ],
                    "final_premium_ron": Decimal("1490.00"),
                    "payment_plan_type": "annual",
                    "installments": 1,
                },
            ],
            fetchall_rows=[
                [
                    {
                        "id": 1,
                        "risk_profile_id": 1,
                        "code": "FLOOD_EXPOSURE",
                        "label": "Expunere la inundatii",
                        "level": "high",
                        "score": 85,
                        "evidence_json": [
                            "zona cu istoric de inundatii",
                            "proximitate fata de zona vulnerabila",
                        ],
                        "clause_tags_json": ["flood_specific", "inspection_recommended"],
                        "premium_adjustment_percent": Decimal("12.00"),
                        "deductible_adjustment_ron": Decimal("500.00"),
                        "created_at": datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
                    }
                ]
            ],
        )

        repo = PostgresContractRepository(make_connection_factory(cursor))
        result = repo.get_contract_context_source(contract_id)

        self.assertEqual(result.contract.contract_number, "PAD-RISK-2026-000145")
        self.assertEqual(result.customer.full_name, "Ion Popescu")
        self.assertEqual(result.insurer.company_id, "RO12345678")
        self.assertEqual(result.risk_profile.risk_score, 72)
        self.assertEqual(len(result.risk_factors), 1)
        first_adjustment = result.pricing.adjustments_json[0]
        self.assertEqual(first_adjustment.source, "FLOOD_EXPOSURE")
        quote_adjustment = result.pricing.adjustments_json[1]
        self.assertEqual(quote_adjustment.source, "property_type_multiplier")
        self.assertEqual(quote_adjustment.type, "multiplier")
        self.assertEqual(quote_adjustment.value, Decimal("1.08"))
        self.assertEqual(len(cursor.executed), 10)

    def test_contract_repository_lists_client_contracts_by_source_quote_owner(
        self,
    ) -> None:
        quote_id = UUID("90000000-0000-0000-0000-000000000031")
        cursor = FakeCursor(
            fetchall_rows=[
                [
                    _contract_read_row(
                        customer_id=9999,
                        source_quote_request_id=quote_id,
                    )
                ]
            ],
        )

        repo = PostgresContractRepository(make_connection_factory(cursor))
        result = repo.list_contracts_by_client_id(1001)

        sql, params = cursor.executed[0]
        self.assertIn("quote_request qr", sql)
        self.assertIn("qr.request_id = c.source_quote_request_id", sql)
        self.assertIn("qr.client_id = %s", sql)
        self.assertEqual(params, (1001, 1001))
        self.assertEqual(result[0].source_quote_request_id, quote_id)
        self.assertEqual(result[0].customer.id, 9999)

    def test_contract_repository_gets_client_contract_by_source_quote_owner(
        self,
    ) -> None:
        contract_id = UUID("10000000-0000-0000-0000-000000000031")
        quote_id = UUID("90000000-0000-0000-0000-000000000031")
        cursor = FakeCursor(
            fetchone_rows=[
                _contract_read_row(
                    contract_id=contract_id,
                    customer_id=9999,
                    source_quote_request_id=quote_id,
                )
            ],
        )

        repo = PostgresContractRepository(make_connection_factory(cursor))
        result = repo.get_contract_by_id_for_client(contract_id, 1001)

        sql, params = cursor.executed[0]
        self.assertIn("quote_request qr", sql)
        self.assertIn("qr.request_id = c.source_quote_request_id", sql)
        self.assertIn("qr.client_id = %s", sql)
        self.assertEqual(params, (contract_id, 1001, 1001))
        self.assertEqual(result.id, contract_id)
        self.assertEqual(result.customer.id, 9999)

    def test_template_repository_returns_active_template(self) -> None:
        cursor = FakeCursor(
            fetchone_rows=[
                {
                    "id": 1,
                    "template_code": "PAD_STANDARD_RO",
                    "name": "PAD Standard RO",
                    "version": "1.0",
                    "document_type": "insurance_contract",
                    "is_active": True,
                    "content": "template body",
                    "created_at": datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
                }
            ]
        )

        repo = PostgresTemplateRepository(make_connection_factory(cursor))
        result = repo.get_active_template("PAD_STANDARD_RO")

        self.assertEqual(result.template_code, "PAD_STANDARD_RO")
        self.assertTrue(result.is_active)

    def test_generated_document_repository_wraps_jsonb_and_commits(self) -> None:
        now = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)
        contract_id = UUID("10000000-0000-0000-0000-000000000001")
        cursor = FakeCursor(
            fetchone_rows=[
                {
                    "id": 7,
                    "contract_id": contract_id,
                    "template_id": 1,
                    "generation_status": "success",
                    "rendered_text": "rendered contract",
                    "rendered_json": {"payload": {"ok": True}},
                    "template_code": "PAD_PROPERTY_RO",
                    "template_version": "1.0",
                    "template_version_hash": "template-hash",
                    "payload_snapshot": {"document_type": "insurance_contract"},
                    "generation_metadata": {"generation_mode": "template"},
                    "content_hash": "content-hash",
                    "file_url": "/tmp/generated.txt",
                    "created_at": now,
                    "updated_at": now,
                }
            ]
        )
        connection = FakeConnection(cursor)

        def connection_factory():
            return connection

        repo = PostgresGeneratedDocumentRepository(connection_factory)
        document = GeneratedDocument(
            contract_id=contract_id,
            template_id=1,
            generation_status="success",
            rendered_text="rendered contract",
            rendered_json={"payload": {"ok": True}},
            template_code="PAD_PROPERTY_RO",
            template_version="1.0",
            template_version_hash="template-hash",
            payload_snapshot={"document_type": "insurance_contract"},
            generation_metadata={"generation_mode": "template"},
            content_hash="content-hash",
            file_url="/tmp/generated.txt",
            created_at=now,
            updated_at=now,
        )

        result = repo.save(document)

        self.assertEqual(result.id, 7)
        self.assertTrue(connection.committed)
        _, params = cursor.executed[0]
        self.assertIsInstance(params[4], Jsonb)
        self.assertIsInstance(params[8], Jsonb)
        self.assertIsInstance(params[9], Jsonb)
        self.assertEqual(params[10], "content-hash")

    def test_generated_document_repository_get_latest_returns_read_model(self) -> None:
        now = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)
        contract_id = UUID("10000000-0000-0000-0000-000000000001")
        cursor = FakeCursor(
            fetchone_rows=[
                {
                    "id": 8,
                    "contract_id": contract_id,
                    "template_id": 1,
                    "generation_status": "success",
                    "rendered_text": "latest rendered contract",
                    "rendered_json": {},
                    "template_code": "PAD_PROPERTY_RO",
                    "template_version": "1.0",
                    "template_version_hash": "template-hash",
                    "payload_snapshot": {"document_type": "insurance_contract"},
                    "generation_metadata": {"generation_mode": "template"},
                    "content_hash": "content-hash",
                    "file_url": None,
                    "created_at": now,
                    "updated_at": now,
                }
            ]
        )

        repo = PostgresGeneratedDocumentRepository(make_connection_factory(cursor))
        result = repo.get_latest_by_contract_id(contract_id)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, 8)
        self.assertEqual(result.document_type, "insurance_contract")
        self.assertEqual(result.template_code, "PAD_PROPERTY_RO")
        self.assertEqual(result.content_hash, "content-hash")

    def test_generated_document_repository_get_by_id_returns_read_model(self) -> None:
        now = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)
        contract_id = UUID("10000000-0000-0000-0000-000000000001")
        cursor = FakeCursor(
            fetchone_rows=[
                {
                    "id": 8,
                    "contract_id": contract_id,
                    "template_id": 1,
                    "generation_status": "success",
                    "rendered_text": "rendered contract",
                    "rendered_json": {
                        "contract_generation_payload": {
                            "document_type": "insurance_contract"
                        },
                        "template_used": {
                            "template_code": "PAD_PROPERTY_RO",
                            "template_version": "1.0",
                        },
                    },
                    "template_code": None,
                    "template_version": None,
                    "template_version_hash": None,
                    "payload_snapshot": {},
                    "generation_metadata": {},
                    "content_hash": None,
                    "file_url": None,
                    "created_at": now,
                    "updated_at": now,
                }
            ]
        )

        repo = PostgresGeneratedDocumentRepository(make_connection_factory(cursor))
        result = repo.get_by_id(8)

        self.assertEqual(result.id, 8)
        self.assertEqual(result.document_type, "insurance_contract")
        self.assertEqual(result.template_code, "PAD_PROPERTY_RO")

    def test_generated_document_repository_updates_pdf_metadata(self) -> None:
        now = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)
        generated_at = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
        contract_id = UUID("10000000-0000-0000-0000-000000000001")
        cursor = FakeCursor(
            fetchone_rows=[
                {
                    "id": 8,
                    "contract_id": contract_id,
                    "template_id": 1,
                    "generation_status": "success",
                    "rendered_text": "rendered contract",
                    "rendered_json": {},
                    "template_code": "PAD_PROPERTY_RO",
                    "template_version": "1.0",
                    "template_version_hash": "template-hash",
                    "payload_snapshot": {"document_type": "insurance_contract"},
                    "generation_metadata": {"generation_mode": "template"},
                    "content_hash": "source-hash",
                    "pdf_storage_key": "generated-document-8.pdf",
                    "pdf_filename": "generated-document-8.pdf",
                    "pdf_content_hash": "pdf-hash",
                    "pdf_source_content_hash": "source-hash",
                    "pdf_generated_at": generated_at,
                    "pdf_generation_metadata": {"renderer": "SimpleTextPdfRenderer"},
                    "file_url": None,
                    "created_at": now,
                    "updated_at": now,
                }
            ]
        )
        connection = FakeConnection(cursor)

        def connection_factory():
            return connection

        repo = PostgresGeneratedDocumentRepository(connection_factory)
        result = repo.update_pdf_metadata(
            document_id=8,
            pdf_storage_key="generated-document-8.pdf",
            pdf_filename="generated-document-8.pdf",
            pdf_content_hash="pdf-hash",
            pdf_source_content_hash="source-hash",
            pdf_generated_at=generated_at,
            pdf_generation_metadata={"renderer": "SimpleTextPdfRenderer"},
        )

        self.assertEqual(result.pdf_storage_key, "generated-document-8.pdf")
        self.assertEqual(result.pdf_content_hash, "pdf-hash")
        self.assertEqual(result.pdf_source_content_hash, "source-hash")
        self.assertTrue(connection.committed)
        _, params = cursor.executed[0]
        self.assertIsInstance(params[5], Jsonb)

    def test_contract_request_repository_create_wraps_jsonb_and_commits(self) -> None:
        now = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchone_rows=[
                {
                    "request_id": 101,
                    "client_id": 202,
                    "request_status": "created",
                    "client_data": {"name": "Ion Popescu"},
                    "insured_data": {"asset_type": "apartment"},
                    "request_details": {"channel": "web"},
                    "attachments": {"files": ["id_card.pdf"]},
                    "created_at": now,
                }
            ]
        )
        connection = FakeConnection(cursor)

        def connection_factory():
            return connection

        repo = PostgresContractRequestRepository(connection_factory)
        request = ContractRequest(
            request_id=101,
            client_id=202,
            client_data={"name": "Ion Popescu"},
            insured_data={"asset_type": "apartment"},
            request_details={"channel": "web"},
            attachments={"files": ["id_card.pdf"]},
            created_at=now,
        )

        result = repo.create_request(request)

        self.assertEqual(result.request_id, 101)
        self.assertTrue(connection.committed)
        _, params = cursor.executed[0]
        self.assertIsInstance(params[3], Jsonb)
        self.assertIsInstance(params[4], Jsonb)
        self.assertIsInstance(params[5], Jsonb)
        self.assertIsInstance(params[6], Jsonb)

    def test_contract_request_repository_get_by_id_returns_domain_model(self) -> None:
        now = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchone_rows=[
                {
                    "request_id": 101,
                    "client_id": 202,
                    "request_status": "pending",
                    "client_data": {},
                    "insured_data": {},
                    "request_details": {},
                    "attachments": {},
                    "created_at": now,
                }
            ]
        )

        repo = PostgresContractRequestRepository(make_connection_factory(cursor))
        result = repo.get_request_by_id(101)

        self.assertEqual(result.request_status, "pending")
        self.assertEqual(result.client_id, 202)

    def test_contract_request_repository_get_by_id_raises_when_missing(self) -> None:
        cursor = FakeCursor()

        repo = PostgresContractRequestRepository(make_connection_factory(cursor))

        with self.assertRaisesRegex(ValueError, "ContractRequest not found"):
            repo.get_request_by_id(999)

    def test_contract_request_repository_lists_by_client_id(self) -> None:
        now = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchall_rows=[
                [
                    {
                        "request_id": 101,
                        "client_id": 202,
                        "request_status": "created",
                        "client_data": {},
                        "insured_data": {},
                        "request_details": {},
                        "attachments": {},
                        "created_at": now,
                    },
                    {
                        "request_id": 102,
                        "client_id": 202,
                        "request_status": "in_review",
                        "client_data": {},
                        "insured_data": {},
                        "request_details": {},
                        "attachments": {},
                        "created_at": now,
                    },
                ]
            ]
        )

        repo = PostgresContractRequestRepository(make_connection_factory(cursor))
        result = repo.list_requests_by_client_id(202)

        self.assertEqual(len(result), 2)
        self.assertEqual([item.request_id for item in result], [101, 102])

    def test_contract_request_repository_lists_by_status(self) -> None:
        now = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchall_rows=[
                [
                    {
                        "request_id": 201,
                        "client_id": 301,
                        "request_status": "pending",
                        "client_data": {},
                        "insured_data": {},
                        "request_details": {},
                        "attachments": {},
                        "created_at": now,
                    },
                    {
                        "request_id": 202,
                        "client_id": 302,
                        "request_status": "pending",
                        "client_data": {},
                        "insured_data": {},
                        "request_details": {},
                        "attachments": {},
                        "created_at": now,
                    },
                ]
            ]
        )

        repo = PostgresContractRequestRepository(make_connection_factory(cursor))
        result = repo.list_requests_by_status("pending")

        self.assertEqual(len(result), 2)
        self.assertTrue(all(item.request_status == "pending" for item in result))

    def test_contract_request_repository_update_status_commits_and_returns_row(self) -> None:
        now = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchone_rows=[
                {
                    "request_id": 101,
                    "client_id": 202,
                    "request_status": "completed",
                    "client_data": {},
                    "insured_data": {},
                    "request_details": {},
                    "attachments": {},
                    "created_at": now,
                }
            ]
        )
        connection = FakeConnection(cursor)

        def connection_factory():
            return connection

        repo = PostgresContractRequestRepository(connection_factory)
        result = repo.update_request_status(101, "completed")

        self.assertEqual(result.request_status, "completed")
        self.assertTrue(connection.committed)
        _, params = cursor.executed[0]
        self.assertEqual(params, ("completed", 101))

    def test_contract_request_repository_update_status_raises_when_missing(self) -> None:
        connection = FakeConnection(FakeCursor())

        def connection_factory():
            return connection

        repo = PostgresContractRequestRepository(connection_factory)

        with self.assertRaisesRegex(ValueError, "ContractRequest not found"):
            repo.update_request_status(404, "rejected")


if __name__ == "__main__":
    unittest.main()
