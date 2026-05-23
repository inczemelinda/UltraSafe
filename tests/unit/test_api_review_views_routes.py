"""Tests for the review_views API routes.

Verifies that GET /review-views/{case_id} retrieves the persisted review view
for a drafted contract case with appropriate error handling.
"""
from __future__ import annotations

import unittest
from uuid import UUID

from fastapi.testclient import TestClient

from underwright.api.dependencies import get_case_context_service
from underwright.api.main import create_app
from underwright.domain.contract_case_context import (
    ContractCaseContext,
    ContractReviewState,
)
from underwright.domain.review_models import (
    ContractReviewView,
    GeneratedOutputPanel,
    ReviewHeader,
    SourceInputPanel,
    TemplatePanel,
)

CASE_ID_1 = UUID("00000000-0000-0000-0000-000000000001")
CASE_ID_2 = UUID("00000000-0000-0000-0000-000000000002")
CASE_ID_3 = UUID("00000000-0000-0000-0000-000000000003")
CASE_ID_4 = UUID("00000000-0000-0000-0000-000000000004")
CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000001")


def _make_review_view() -> ContractReviewView:
    """Create a sample review view for testing."""
    return ContractReviewView(
        header=ReviewHeader(
            case_id=CASE_ID_1,
            contract_id=CONTRACT_ID,
            domain="contracts",
            workflow_status="success",
        ),
        source_input_panel=SourceInputPanel(
            contract_id=CONTRACT_ID,
        ),
        generated_output_panel=GeneratedOutputPanel(draft_contract_text="Test draft"),
        template_panel=TemplatePanel(
            template_id=1, template_code="PAD_STANDARD_RO", template_name="PAD Standard"
        ),
    )


class FakeCaseContextService:
    """Fake implementation for testing."""

    def __init__(self, case_context=None, raise_not_found=False):
        self.case_context = case_context
        self.raise_not_found = raise_not_found

    def get_case_context(self, case_id: str):
        if self.raise_not_found:
            raise ValueError(f"CaseContext with case_id {case_id} not found")
        return self.case_context


class ReviewViewsRoutesTestCase(unittest.TestCase):
    """Tests for review_views routes."""

    def test_get_review_view_returns_persisted_data(self) -> None:
        """Verify GET /review-views/{case_id} returns the persisted review view."""
        context = ContractCaseContext()
        context.case_metadata.case_id = CASE_ID_1
        context.case_metadata.status = "success"
        context.review_state = ContractReviewState(
            contract_review_view=_make_review_view()
        )

        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: FakeCaseContextService(
            context
        )
        client = TestClient(app)

        response = client.get(f"/review-views/{CASE_ID_1}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["case_id"], str(CASE_ID_1))
        self.assertEqual(payload["workflow_status"], "success")
        self.assertIn("review_view", payload)
        self.assertEqual(payload["review_view"]["header"]["case_id"], str(CASE_ID_1))
        self.assertEqual(payload["review_view"]["header"]["contract_id"], str(CONTRACT_ID))

    def test_get_review_view_not_found_returns_404(self) -> None:
        """Verify 404 when case context does not exist."""
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: FakeCaseContextService(
            raise_not_found=True
        )
        client = TestClient(app)

        response = client.get("/review-views/nonexistent-case")

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "CASE_CONTEXT_NOT_FOUND")
        self.assertIn("not found", payload["error"]["message"].lower())

    def test_get_review_view_missing_returns_400(self) -> None:
        """Verify 400 when review view is missing for completed workflow."""
        context = ContractCaseContext()
        context.case_metadata.case_id = CASE_ID_2
        context.case_metadata.status = "completed"
        # Simulate completed workflow without review view
        context.review_state = ContractReviewState(contract_review_view=None)

        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: FakeCaseContextService(
            context
        )
        client = TestClient(app)

        response = client.get(f"/review-views/{CASE_ID_2}")

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "MISSING_REVIEW_VIEW")
        self.assertIn("not available", payload["error"]["message"].lower())

    def test_get_review_view_draft_status_allows_missing_view(self) -> None:
        """Verify 200 when case is in draft status, even if review view missing."""
        context = ContractCaseContext()
        context.case_metadata.case_id = CASE_ID_3
        context.case_metadata.status = "draft"
        context.review_state = ContractReviewState(contract_review_view=None)

        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: FakeCaseContextService(
            context
        )
        client = TestClient(app)

        response = client.get(f"/review-views/{CASE_ID_3}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["case_id"], str(CASE_ID_3))
        self.assertEqual(payload["workflow_status"], "draft")
        self.assertIsNone(payload["review_view"])

    def test_get_review_view_no_rebuild_logic(self) -> None:
        """Verify endpoint does not rebuild business logic, only fetches and serializes."""
        # This test verifies that the review view is directly serialized
        # from the persisted state, without any reconstruction or processing.
        review_view = _make_review_view()
        context = ContractCaseContext()
        context.case_metadata.case_id = CASE_ID_4
        context.case_metadata.status = "success"
        context.review_state = ContractReviewState(contract_review_view=review_view)

        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: FakeCaseContextService(
            context
        )
        client = TestClient(app)

        response = client.get(f"/review-views/{CASE_ID_4}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        # Verify the returned review_view matches what was stored
        self.assertEqual(
            payload["review_view"]["header"]["case_id"],
            str(review_view.header.case_id),
        )
        self.assertEqual(
            payload["review_view"]["header"]["contract_id"],
            str(review_view.header.contract_id),
        )
        self.assertEqual(
            payload["review_view"]["source_input_panel"]["contract_id"],
            str(review_view.source_input_panel.contract_id),
        )


if __name__ == "__main__":
    unittest.main()
