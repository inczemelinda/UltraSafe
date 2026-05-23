from __future__ import annotations

import unittest
from uuid import UUID

from psycopg.types.json import Jsonb

from underwright.domain.case_context_base import BaseCaseContext
from underwright.domain.claim_analysis import CoverageAssessmentResult, EvidenceRequestDraft
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_review_models import (
    ClaimAttachmentsPanel,
    ClaimClientPanel,
    ClaimDetailPanel,
    ClaimReviewHeader,
    ClaimReviewView,
)
from underwright.infrastructure.postgres.case_context_repository import (
    CaseContextRepository,
)

CASE_ID = UUID("00000000-0000-0000-0000-000000000001")
CASE_ID_2 = UUID("00000000-0000-0000-0000-000000000002")
CLAIM_REQUEST_ID = UUID("00000000-0000-0000-0000-000000000003")


class FakeCursor:
    def __init__(self, fetchone_rows: list[tuple | dict] | None = None) -> None:
        self.fetchone_rows = list(fetchone_rows or [])
        self.executed: list[tuple[str, object]] = []
        self.rowcount = 0

    def execute(self, sql: str, params) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        if not self.fetchone_rows:
            return None
        return self.fetchone_rows.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False

    def cursor(self):
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


class CaseContextRepositoryTestCase(unittest.TestCase):
    def test_save_inserts_when_case_id_missing(self) -> None:
        cursor = FakeCursor(fetchone_rows=[(CASE_ID,)])
        repo = CaseContextRepository(make_connection_factory(cursor))
        context = BaseCaseContext()
        context.case_metadata.status = "started"

        repo.save_case_context(context)

        self.assertIsInstance(context.case_metadata.case_id, UUID)
        sql, params = cursor.executed[0]
        self.assertIn("INSERT INTO case_context", sql)
        self.assertIsInstance(params[0], UUID)
        self.assertEqual(params[1], "started")
        self.assertIsInstance(params[2], Jsonb)

    def test_save_updates_when_case_id_exists(self) -> None:
        cursor = FakeCursor(fetchone_rows=[(CASE_ID,)])
        cursor.rowcount = 1
        connection = FakeConnection(cursor)

        def connection_factory():
            return connection

        repo = CaseContextRepository(connection_factory)
        context = BaseCaseContext()
        context.case_metadata.case_id = CASE_ID
        context.case_metadata.status = "payload_ready"

        repo.save_case_context(context)

        sql, params = cursor.executed[0]
        self.assertIn("INSERT INTO case_context", sql)
        self.assertIn("ON CONFLICT (case_id)", sql)
        self.assertEqual(params[0], CASE_ID)
        self.assertEqual(params[1], "payload_ready")
        self.assertIsInstance(params[2], Jsonb)
        self.assertTrue(connection.committed)

    def test_save_raises_when_no_row_returned(self) -> None:
        cursor = FakeCursor()
        cursor.rowcount = 0
        repo = CaseContextRepository(make_connection_factory(cursor))
        context = BaseCaseContext()
        context.case_metadata.case_id = CASE_ID_2

        with self.assertRaises(RuntimeError):
            repo.save_case_context(context)

    def test_get_case_context_by_case_id_returns_model(self) -> None:
        payload = BaseCaseContext().model_dump(mode="json")
        cursor = FakeCursor(fetchone_rows=[(payload,)])
        repo = CaseContextRepository(make_connection_factory(cursor))

        result = repo.get_case_context_by_case_id(CASE_ID)

        self.assertIsInstance(result, BaseCaseContext)
        self.assertEqual(result.case_metadata.status, "draft")

    def test_get_case_context_by_case_id_returns_claim_review_findings(
        self,
    ) -> None:
        context = make_claim_context_with_review_findings()
        cursor = FakeCursor(fetchone_rows=[(context.model_dump(mode="json"),)])
        repo = CaseContextRepository(make_connection_factory(cursor))

        result = repo.get_case_context_by_case_id(CASE_ID)

        self.assertIsInstance(result, ClaimCaseContext)
        self.assertIsNotNone(result.generated_outputs.coverage_assessment)
        self.assertEqual(
            result.generated_outputs.coverage_assessment.coverage_status,
            "potentially_covered",
        )
        self.assertEqual(
            result.generated_outputs.coverage_assessment.wording_section_ids,
            ["coverage.fire_damage"],
        )
        self.assertIsNotNone(
            result.generated_outputs.coverage_assessment.assessed_at
        )
        self.assertIsNotNone(result.review_state.claim_review_view)
        self.assertEqual(
            result.review_state.claim_review_view["coverage_assessment"][
                "coverage_status"
            ],
            "potentially_covered",
        )

    def test_get_case_context_by_case_id_raises_when_missing(self) -> None:
        cursor = FakeCursor(fetchone_rows=[])
        repo = CaseContextRepository(make_connection_factory(cursor))

        with self.assertRaises(ValueError):
            repo.get_case_context_by_case_id(CASE_ID)

    def test_get_latest_claim_context_by_request_id_returns_claim_context(self) -> None:
        context = ClaimCaseContext(source_inputs={"request_id": CLAIM_REQUEST_ID})
        context.case_metadata.case_id = CASE_ID
        context.case_metadata.status = "in_review"
        cursor = FakeCursor(fetchone_rows=[(context.model_dump(mode="json"),)])
        repo = CaseContextRepository(make_connection_factory(cursor))

        result = repo.get_latest_claim_case_context_by_request_id(CLAIM_REQUEST_ID)

        sql, params = cursor.executed[0]
        self.assertIn("context_json -> 'case_metadata' ->> 'domain'", sql)
        self.assertIn("context_json -> 'source_inputs' ->> 'request_id'", sql)
        self.assertEqual(params, (str(CLAIM_REQUEST_ID),))
        self.assertIsInstance(result, ClaimCaseContext)
        self.assertEqual(result.source_inputs.request_id, CLAIM_REQUEST_ID)

    def test_get_latest_claim_context_by_request_id_returns_precheck_coverage(
        self,
    ) -> None:
        context = make_claim_context_with_review_findings()
        context.review_state.claim_review_view = None
        cursor = FakeCursor(fetchone_rows=[(context.model_dump(mode="json"),)])
        repo = CaseContextRepository(make_connection_factory(cursor))

        result = repo.get_latest_claim_case_context_by_request_id(CLAIM_REQUEST_ID)

        self.assertIsNotNone(result.generated_outputs.coverage_assessment)
        self.assertEqual(
            result.generated_outputs.coverage_assessment.coverage_status,
            "potentially_covered",
        )
        self.assertEqual(
            result.generated_outputs.coverage_assessment.matched_wording_sections,
            ["coverage.fire_damage"],
        )

    def test_get_latest_claim_context_by_request_id_raises_when_missing(self) -> None:
        cursor = FakeCursor(fetchone_rows=[])
        repo = CaseContextRepository(make_connection_factory(cursor))

        with self.assertRaises(ValueError):
            repo.get_latest_claim_case_context_by_request_id(CLAIM_REQUEST_ID)

    def test_get_latest_claim_context_by_evidence_reply_token_returns_claim_context(
        self,
    ) -> None:
        context = ClaimCaseContext(source_inputs={"request_id": CLAIM_REQUEST_ID})
        context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
            claim_request_id=CLAIM_REQUEST_ID,
            subject="Additional evidence required",
            body="Please send evidence.",
            recipients=["client@example.test"],
            required_documents=["fire report"],
            reply_token="reply-token-123",
        )
        cursor = FakeCursor(fetchone_rows=[(context.model_dump(mode="json"),)])
        repo = CaseContextRepository(make_connection_factory(cursor))

        result = repo.get_latest_claim_case_context_by_evidence_reply_token(
            "reply-token-123"
        )

        sql, params = cursor.executed[0]
        self.assertIn("->> 'reply_token'", sql)
        self.assertEqual(params, ("reply-token-123",))
        self.assertIsInstance(result, ClaimCaseContext)
        self.assertEqual(
            result.generated_outputs.evidence_request_draft.reply_token,
            "reply-token-123",
        )


def make_claim_context_with_review_findings() -> ClaimCaseContext:
    context = ClaimCaseContext(source_inputs={"request_id": CLAIM_REQUEST_ID})
    context.case_metadata.case_id = CASE_ID
    context.case_metadata.status = "needs_underwriter_review"
    context.generated_outputs.coverage_assessment = CoverageAssessmentResult(
        coverage_status="potentially_covered",
        matched_wording_sections=["coverage.fire_damage"],
        wording_section_ids=["coverage.fire_damage"],
        possible_exclusions=[],
        rationale="Fire wording may apply to the described incident.",
        confidence="high",
    )
    context.review_state.claim_review_view = ClaimReviewView(
        header=ClaimReviewHeader(
            case_id=CASE_ID,
            request_id=CLAIM_REQUEST_ID,
            domain="claims",
            workflow_status="needs_underwriter_review",
        ),
        client_panel=ClaimClientPanel(client_id=1001, client_data={}),
        claim_detail_panel=ClaimDetailPanel(claim_data={}),
        attachments_panel=ClaimAttachmentsPanel(),
        coverage_precheck=(
            context.generated_outputs.coverage_assessment.model_dump(mode="json")
        ),
        coverage_assessment=(
            context.generated_outputs.coverage_assessment.model_dump(mode="json")
        ),
    )
    return context


if __name__ == "__main__":
    unittest.main()
