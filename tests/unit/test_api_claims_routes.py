from __future__ import annotations

import unittest
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from underwright.api.dependencies import (
    get_case_context_service,
    get_claim_attachment_processing_service,
    get_claim_attachment_storage_service,
    get_claim_decision_email_send_service,
    get_claim_decision_rewording_service,
    get_claim_evidence_ingestion_service,
    get_contract_query_service,
    get_claim_request_service,
    get_claim_review_query_service,
    get_claim_workflow,
    get_coverage_precheck_workflow,
    get_current_auth_user,
    get_current_client_user,
    get_current_employee_user,
    get_customer_profile_document_service,
    get_customer_profile_service,
    get_evidence_request_email_send_service,
    get_evidence_refresh_workflow,
    get_evidence_request_draft_service,
)
from underwright.api.main import create_app
from underwright.application.services.customer_profile_service import (
    CustomerProfileIncompleteError,
)
from underwright.application.services.claim_decision_rewording_service import (
    ClaimDecisionRewordingNotConfiguredError,
    ClaimDecisionRewordingProviderError,
)
from underwright.application.services.evidence_request_draft_service import (
    EvidenceRequestDraftService,
)
from underwright.application.services.claim_review_query_service import (
    ClaimReviewQueryService,
)
from underwright.application.workflows.claim_workflow import ClaimWorkflowResult
from underwright.domain.claim_analysis import (
    CoverageAssessmentResult,
    DocumentConsistencyResult,
    EvidenceRequirement,
    EvidenceRequirementResult,
    EvidenceRequestDraft,
)
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_request import ClaimAttachmentMetadata, ClaimRequest
from underwright.domain.customer_profile_document import CustomerProfileDocument
from underwright.domain.email_message import EmailAttachment, EmailMessage
from underwright.infrastructure.email.local_email_provider import LocalEmailProvider
from underwright.domain.claim_review_models import (
    ClaimAttachmentsPanel,
    ClaimClientPanel,
    ClaimDetailPanel,
    ClaimReviewHeader,
    ClaimReviewView,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.contract_lifecycle import (
    AddressSnapshot,
    ContractAssetSummary,
    ContractCustomerSummary,
    ContractPricingSummary,
    ContractReadModel,
)
from underwright.domain.module_result import ModuleResult
from underwright.infrastructure.storage.local_claim_attachment_storage import (
    LocalClaimAttachmentStorageService,
)

REQUEST_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
CASE_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000041")
OTHER_CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000042")
PROFILE_DOCUMENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def make_claim_request(status: str = "submitted") -> ClaimRequest:
    return ClaimRequest(
        request_id=REQUEST_ID,
        client_id=1001,
        request_status=status,
        client_data={"full_name": "Ion Popescu"},
        claim_data={
            "claim_type": "Fire",
            "description": "Kitchen fire with smoke damage.",
            "estimated_damage": 12000,
            "policy_number": "PAD-001",
            "property_address": "Bucharest",
        },
        attachments=[],
    )


def make_review_view() -> ClaimReviewView:
    return ClaimReviewView(
        header=ClaimReviewHeader(
            case_id=CASE_ID,
            request_id=REQUEST_ID,
            domain="claims",
            workflow_status="in_review",
        ),
        client_panel=ClaimClientPanel(client_id=1001, client_data={}),
        claim_detail_panel=ClaimDetailPanel(claim_data={}),
        attachments_panel=ClaimAttachmentsPanel(),
        coverage_precheck={
            "coverage_status": "potentially_covered",
            "matched_wording_sections": ["coverage.fire_damage"],
            "wording_section_ids": ["coverage.fire_damage"],
            "possible_exclusions": [],
            "rationale": "Fire wording may apply.",
            "confidence": "high",
            "assessed_at": "2026-05-11T00:00:00Z",
        },
        coverage_assessment={
            "coverage_status": "potentially_covered",
            "matched_wording_sections": ["coverage.fire_damage"],
            "wording_section_ids": ["coverage.fire_damage"],
            "possible_exclusions": [],
            "rationale": "Fire wording may apply.",
            "confidence": "high",
            "assessed_at": "2026-05-11T00:00:00Z",
        },
        document_consistency={
            "status": "no_discrepancies",
            "supporting_fact_count": 1,
            "discrepancy_count": 0,
        },
        supporting_facts=[
            {
                "field": "policy_number",
                "claim_value": "PAD-001",
                "document_value": "PAD-001",
                "source_document": "existing-policy-document.pdf",
                "severity": "info",
                "message": "Claim policy number matches the policy document.",
            }
        ],
        required_evidence=[],
        missing_evidence=[],
        suggested_next_action="underwriter_review",
        human_readable_summary="Ready for underwriter review.",
        confidence_panel={
            "score": None,
            "legacy_internal_signal": True,
            "not_decisioning": True,
        },
    )


class FakeClaimRequestService:
    def __init__(self) -> None:
        self.claim_request = make_claim_request()
        self.created_request = None

    def create_client_claim_request(self, request: ClaimRequest) -> ClaimRequest:
        self.created_request = request
        self.claim_request = request
        return request

    def list_client_claim_requests(self, client_id):
        return [self.claim_request]

    def list_underwriter_claim_queue_requests(self, request_status: str = "submitted"):
        return [make_claim_request(request_status)]

    def get_claim_request_detail(self, request_id):
        if request_id != REQUEST_ID:
            raise ValueError("ClaimRequest not found")
        return self.claim_request

    def start_underwriter_review(self, request_id):
        if request_id != REQUEST_ID:
            raise ValueError("ClaimRequest not found")
        if self.claim_request.request_status != "submitted":
            return self.claim_request
        self.claim_request = self.claim_request.model_copy(
            update={"request_status": "in_review"}
        )
        return self.claim_request

    def evaluate_precheck_for_request(self, request: ClaimRequest) -> dict:
        return {
            "status": "pass",
            "reasons": [],
            "claims_last_3y": 0,
        }

    def update_request_attachments(self, request_id, attachments):
        if request_id != REQUEST_ID:
            raise ValueError("ClaimRequest not found")
        self.claim_request = self.claim_request.model_copy(
            update={
                "attachments": [
                    ClaimAttachmentMetadata.model_validate(attachment)
                    for attachment in attachments
                ],
                "updated_at": datetime(2026, 5, 13, 11, 0, tzinfo=timezone.utc),
            }
        )
        return self.claim_request

    def submit_claim_decision(
        self,
        request_id,
        *,
        decision,
        justification,
        decided_by_auth_user_id,
        decided_by_email,
    ):
        if request_id != REQUEST_ID:
            raise ValueError("ClaimRequest not found")
        now = datetime(2026, 5, 15, 9, 30, tzinfo=timezone.utc)
        claim_data = {
            **self.claim_request.claim_data,
            "decision": decision,
            "decision_status": "submitted",
            "decision_justification": justification,
            "decided_by": decided_by_auth_user_id,
            "decided_by_email": decided_by_email,
            "decided_at": now.isoformat(),
        }
        request_status = (
            "needs_underwriter_review"
            if decision == "inspection_requested"
            else "completed"
        )
        self.claim_request = self.claim_request.model_copy(
            update={
                "claim_data": claim_data,
                "request_status": request_status,
                "updated_at": now,
            }
        )
        return self.claim_request

    def mark_decision_email_sent(self, request_id, *, email_message_id, sent_at):
        if request_id != REQUEST_ID:
            raise ValueError("ClaimRequest not found")
        claim_data = {
            **self.claim_request.claim_data,
            "decision_email_message_id": str(email_message_id),
            "decision_email_sent_at": sent_at.isoformat(),
        }
        self.claim_request = self.claim_request.model_copy(update={"claim_data": claim_data})
        return self.claim_request


class FakeClaimAttachmentProcessingService:
    def __init__(self, claim_request: ClaimRequest | None = None) -> None:
        self.claim_request = claim_request
        self.processed_request_ids: list[UUID] = []

    def process_request_attachments(self, request_id: UUID):
        self.processed_request_ids.append(request_id)
        return self.claim_request


class FakeEmailSendService:
    def __init__(
        self,
        *,
        status: str = "SENT",
        error_message: str | None = None,
    ) -> None:
        self.sent: list[dict] = []
        self.case_emails: list[EmailMessage] = []
        self.status = status
        self.error_message = error_message

    def send_case_email(
        self,
        *,
        case_id,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
        request_id=None,
        reply_to: str | None = None,
        attachments: list[EmailAttachment] | None = None,
    ) -> EmailMessage:
        message = {
            "case_id": case_id,
            "to_email": to_email,
            "subject": subject,
            "body": body,
            "html_body": html_body,
        }
        if request_id is not None:
            message["request_id"] = request_id
        if reply_to:
            message["reply_to"] = reply_to
        if attachments is not None:
            message["attachments"] = attachments
        self.sent.append(message)
        sent_at = (
            datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc)
            if self.status == "SENT"
            else None
        )
        return EmailMessage(
            id=uuid4(),
            case_id=case_id,
            request_id=request_id,
            direction="OUTBOUND",
            from_email="maria.tiuca@ultrasafe.ro",
            to_email=to_email,
            subject=subject,
            body=body,
            status=self.status,
            provider_message_id="message-id" if self.status == "SENT" else None,
            error_message=self.error_message,
            created_at=datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc),
            sent_at=sent_at,
        )

    def list_case_emails(self, case_id):
        return [email for email in self.case_emails if email.case_id == case_id]


class FakeClaimDecisionRewordingService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    def reword_decision_justification(self, *, justification, decision=None):
        self.calls.append({"justification": justification, "decision": decision})
        if self.error is not None:
            raise self.error
        return "A professionally worded version of the same reasoning."


class FakeContractQueryService:
    def __init__(self, contracts: list[ContractReadModel] | None = None) -> None:
        self.contracts = contracts or [make_contract()]

    def list_claimable_contracts_for_client(self, client_id):
        return [
            contract
            for contract in self.contracts
            if _is_claimable_for_client(contract, client_id)
        ]

    def get_claimable_contract_for_client(self, contract_id, client_id):
        for contract in self.list_claimable_contracts_for_client(client_id):
            if contract.id == contract_id:
                return contract
        raise ValueError("Claimable contract not found")


class FakeClaimWorkflowSuccess:
    def run(self, request_id):
        context = ClaimCaseContext()
        context.case_metadata.case_id = CASE_ID
        context.case_metadata.status = "in_review"
        context.review_state.claim_review_view = make_review_view()
        return ClaimWorkflowResult(
            case_context=context,
            review_view=context.review_state.claim_review_view,
            module_results=[
                ModuleResult(
                    module_name="ClaimValidationModule",
                    status="success",
                    summary="Valid.",
                )
            ],
            status="in_review",
        )


class FakeCoveragePrecheckWorkflowSuccess:
    def __init__(self, claim_request: ClaimRequest | None = None) -> None:
        self.claim_request = claim_request or make_claim_request(
            "needs_underwriter_review"
        )
        self.request_id = None

    def run(self, request_id):
        self.request_id = request_id
        return type(
            "CoveragePrecheckResult",
            (),
            {"claim_request": self.claim_request},
        )()


class FakeCoveragePrecheckWorkflowFailure:
    def __init__(self) -> None:
        self.request_id = None

    def run(self, request_id):
        self.request_id = request_id
        raise RuntimeError("precheck failed")


class FakeCoveragePrecheckWorkflowFromService:
    def __init__(self, service: FakeClaimRequestService) -> None:
        self.service = service
        self.request_id = None

    def run(self, request_id):
        self.request_id = request_id
        return type(
            "CoveragePrecheckResult",
            (),
            {"claim_request": self.service.claim_request},
        )()


class FakeCompleteProfileService:
    def ensure_complete_profile(self, user: AuthUser):
        return None


class FakeIncompleteProfileService:
    def ensure_complete_profile(self, user: AuthUser):
        raise CustomerProfileIncompleteError(
            missing_fields=["national_id"],
            status="pending_customer_link",
        )


def make_client_user(client_id: int | None = 1001) -> AuthUser:
    return AuthUser(
        id=1,
        email="client@example.com",
        password_hash="hash",
        role="client",
        full_name="Ion Popescu",
        phone="0712345678",
        client_id=client_id,
    )


def make_employee_user() -> AuthUser:
    return AuthUser(
        id=2,
        email="underwriter@example.test",
        password_hash="hash",
        role="underwriter",
        full_name="Under Writer",
    )


def _employee_client(app) -> TestClient:
    employee = make_employee_user()
    app.dependency_overrides[get_current_auth_user] = lambda: employee
    app.dependency_overrides[get_current_employee_user] = lambda: employee
    app.dependency_overrides.setdefault(
        get_claim_attachment_processing_service,
        lambda: FakeClaimAttachmentProcessingService(),
    )
    return TestClient(app)


def _client_auth_client(app, client_id: int | None = 1001) -> TestClient:
    user = make_client_user(client_id)
    app.dependency_overrides[get_current_auth_user] = lambda: user
    app.dependency_overrides[get_current_client_user] = lambda: user
    app.dependency_overrides.setdefault(
        get_claim_attachment_processing_service,
        lambda: FakeClaimAttachmentProcessingService(),
    )
    return TestClient(app)


def _internal_headers() -> dict[str, str]:
    os.environ["UNDERWRIGHT_INTERNAL_API_KEY"] = "test-internal-key"
    return {"X-Underwright-Internal-Key": "test-internal-key"}


def make_contract(
    *,
    contract_id: UUID = CONTRACT_ID,
    customer_id: int = 1001,
    status: str = "issued",
    expiration_date: date = date(2027, 5, 12),
) -> ContractReadModel:
    now = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
    address = AddressSnapshot(
        country="Romania",
        county="Bucuresti",
        city="Bucuresti",
        street="Str. Mihai Eminescu",
        number="12",
        postal_code="010123",
        full_text="Str. Mihai Eminescu 12, Bucuresti, 010123",
    )
    return ContractReadModel(
        id=contract_id,
        contract_number="POL-123456",
        document_type="insurance_contract",
        document_version="1.0",
        status=status,
        issue_date=date(2026, 5, 13),
        effective_date=date(2026, 5, 13),
        expiration_date=expiration_date,
        jurisdiction="Romania",
        governing_law="Legea 260/2008",
        currency="RON",
        created_at=now,
        updated_at=now,
        customer=ContractCustomerSummary(
            id=customer_id,
            type="individual",
            full_name="Ion Popescu",
            email="ion@example.test",
            phone="+40700000000",
            address=address,
        ),
        asset=ContractAssetSummary(
            id=55,
            asset_type="Apartment",
            usage_type="Owner occupied",
            construction_type="Concrete",
            year_built=1998,
            area_sqm=Decimal("70"),
            declared_value=Decimal("300000"),
            occupancy="Owner occupied",
            previous_claims_count=0,
            address=address,
        ),
        pricing=ContractPricingSummary(
            base_premium_ron=Decimal("600"),
            final_premium_ron=Decimal("513"),
            currency="RON",
            payment_plan_type="annual",
            installments=1,
        ),
    )


def _is_claimable_for_client(contract: ContractReadModel, client_id) -> bool:
    return (
        str(contract.customer.id if contract.customer else "") == str(client_id)
        and contract.status == "issued"
        and contract.expiration_date >= date(2026, 5, 13)
    )


class FakeEvidenceRefreshWorkflowSuccess:
    def __init__(self, context: ClaimCaseContext) -> None:
        self.context = context
        self.request_id = None
        self.claim_fact_updates = None

    def run(self, request_id, *, claim_fact_updates=None):
        self.request_id = request_id
        self.claim_fact_updates = claim_fact_updates
        return type(
            "EvidenceRefreshResult",
            (),
            {
                "case_context": self.context,
                "status": "completed",
                "refresh_pending_reason": None,
                "coverage_assessment_reran": False,
            },
        )()


class FakeCaseContextService:
    def __init__(self, context=None, raise_not_found: bool = False):
        self.context = context
        self.raise_not_found = raise_not_found
        self.saved_context = None

    def get_case_context(self, case_id):
        return self.context

    def get_latest_claim_case_context_by_request_id(self, request_id):
        if self.raise_not_found:
            raise ValueError("ClaimCaseContext not found")
        if request_id != REQUEST_ID:
            raise ValueError("ClaimCaseContext not found")
        return self.context

    def save_case_context(self, context):
        self.saved_context = context
        self.context = context
        return context


class FakeCustomerProfileDocumentService:
    def __init__(self, storage_key: str) -> None:
        self.storage_key = storage_key

    def get_for_customer_id(self, *, customer_id: int, document_id: UUID):
        assert customer_id == 1001
        assert document_id == PROFILE_DOCUMENT_ID
        return CustomerProfileDocument(
            id=document_id,
            customer_id=customer_id,
            label="ID document",
            document_type="ID document",
            file_name="buletin.png",
            content_type="image/png",
            size_bytes=7,
            storage_key=self.storage_key,
            file_url=f"/me/customer-profile/documents/{document_id}/download",
        )


class ClaimRoutesTestCase(unittest.TestCase):
    def test_underwriter_claim_routes_require_employee_role(self) -> None:
        app = create_app()
        app.dependency_overrides[get_claim_request_service] = (
            lambda: FakeClaimRequestService()
        )

        assert TestClient(app).get(f"/underwriter/claims/{REQUEST_ID}").status_code == 401
        assert _client_auth_client(app).get(f"/underwriter/claims/{REQUEST_ID}").status_code == 403
        assert _employee_client(app).get(f"/underwriter/claims/{REQUEST_ID}").status_code == 200

    def test_legacy_claim_attachment_upload_requires_auth(self) -> None:
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/claims/attachments",
            files=[("files", ("proof.pdf", b"%PDF-1.4\n", "application/pdf"))],
        )

        assert response.status_code == 401

    def test_legacy_claim_attachment_download_requires_auth(self) -> None:
        app = create_app()
        client = TestClient(app)

        response = client.get("/claims/attachments/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        assert response.status_code == 401

    def test_upload_claim_attachment_returns_metadata(self) -> None:
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            service = FakeClaimRequestService()
            app.dependency_overrides[get_claim_request_service] = lambda: service
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: LocalClaimAttachmentStorageService(Path(upload_dir))
            )
            client = _client_auth_client(app)
            content = b"%PDF-1.4\nclaim proof"

            response = client.post(
                f"/claims/{REQUEST_ID}/attachments",
                data={"document_roles": "identity_document"},
                files=[
                    (
                        "files",
                        ("../proof document.pdf", content, "application/pdf"),
                    )
                ],
            )

            payload = response.json()
            assert response.status_code == 200
            assert len(payload) == 1
            attachment = payload[0]
            assert attachment["file_name"] == "proof-document.pdf"
            assert attachment["content_type"] == "application/pdf"
            assert attachment["size_bytes"] == len(content)
            assert attachment["file_url"].startswith(f"/claims/{REQUEST_ID}/attachments/")
            assert attachment["metadata"]["attachment_id"]
            assert attachment["metadata"]["claim_id"] == str(REQUEST_ID)
            assert attachment["metadata"]["storage_key"]
            assert attachment["metadata"]["document_role"] == "identity_document"
            assert "/" not in attachment["metadata"]["storage_key"]
            assert str(upload_dir) not in attachment["file_url"]
            assert len(service.claim_request.attachments) == 1

    def test_upload_claim_attachment_rejects_document_role_count_mismatch(self) -> None:
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            app.dependency_overrides[get_claim_request_service] = (
                lambda: FakeClaimRequestService()
            )
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: LocalClaimAttachmentStorageService(Path(upload_dir))
            )
            client = _client_auth_client(app)

            response = client.post(
                f"/claims/{REQUEST_ID}/attachments",
                data={"document_roles": "identity_document"},
                files=[
                    ("files", ("proof.pdf", b"%PDF-1.4\n", "application/pdf")),
                    ("files", ("photo.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")),
                ],
            )

            assert response.status_code == 400
            assert response.json()["detail"] == (
                "document_roles must contain one value for each uploaded file."
            )

    def test_upload_claim_attachment_accepts_supported_image_and_docx_types(
        self,
    ) -> None:
        supported_files = [
            ("damage.png", b"\x89PNG\r\n", "image/png"),
            ("damage.jpg", b"\xff\xd8\xff\xe0", "image/jpeg"),
            (
                "report.docx",
                b"PK\x03\x04docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        ]
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            app.dependency_overrides[get_claim_request_service] = (
                lambda: FakeClaimRequestService()
            )
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: LocalClaimAttachmentStorageService(Path(upload_dir))
            )
            client = _client_auth_client(app)

            response = client.post(
                f"/claims/{REQUEST_ID}/attachments",
                files=[
                    ("files", (file_name, content, content_type))
                    for file_name, content, content_type in supported_files
                ],
            )

            payload = response.json()
            assert response.status_code == 200
            assert [item["content_type"] for item in payload] == [
                content_type for _, _, content_type in supported_files
            ]
            assert [item["size_bytes"] for item in payload] == [
                len(content) for _, content, _ in supported_files
            ]

    def test_upload_claim_attachment_rejects_empty_file(self) -> None:
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            app.dependency_overrides[get_claim_request_service] = (
                lambda: FakeClaimRequestService()
            )
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: LocalClaimAttachmentStorageService(Path(upload_dir))
            )
            client = _client_auth_client(app)

            response = client.post(
                f"/claims/{REQUEST_ID}/attachments",
                files=[("files", ("empty.pdf", b"", "application/pdf"))],
            )

            assert response.status_code == 400

    def test_upload_claim_attachment_rejects_unsupported_content_type(self) -> None:
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            app.dependency_overrides[get_claim_request_service] = (
                lambda: FakeClaimRequestService()
            )
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: LocalClaimAttachmentStorageService(Path(upload_dir))
            )
            client = _client_auth_client(app)

            response = client.post(
                f"/claims/{REQUEST_ID}/attachments",
                files=[("files", ("script.txt", b"hello", "text/plain"))],
            )

            assert response.status_code == 415

    def test_upload_claim_attachment_rejects_oversized_file(self) -> None:
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            app.dependency_overrides[get_claim_request_service] = (
                lambda: FakeClaimRequestService()
            )
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: LocalClaimAttachmentStorageService(
                    Path(upload_dir),
                    max_bytes=4,
                )
            )
            client = _client_auth_client(app)

            response = client.post(
                f"/claims/{REQUEST_ID}/attachments",
                files=[("files", ("large.pdf", b"12345", "application/pdf"))],
            )

            assert response.status_code == 413

    def test_download_claim_attachment_returns_file(self) -> None:
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            service = FakeClaimRequestService()
            storage_service = LocalClaimAttachmentStorageService(Path(upload_dir))
            app.dependency_overrides[get_claim_request_service] = lambda: service
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: storage_service
            )
            client = _client_auth_client(app)
            content = b"%PDF-1.4\nclaim proof"
            upload_response = client.post(
                f"/claims/{REQUEST_ID}/attachments",
                files=[("files", ("proof.pdf", content, "application/pdf"))],
            )
            attachment = upload_response.json()[0]

            response = client.get(attachment["file_url"])

            assert response.status_code == 200
            assert response.content == content
            assert response.headers["content-type"].startswith("application/pdf")
            assert "proof.pdf" in response.headers["content-disposition"]

    def test_download_claim_profile_document_returns_file_for_underwriter(self) -> None:
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            service = FakeClaimRequestService()
            storage_service = LocalClaimAttachmentStorageService(Path(upload_dir))
            content = b"\x89PNG\r\nclaim-id"
            stored = storage_service.save_attachment(
                file_name="buletin.png",
                content_type="image/png",
                content=BytesIO(content),
            )
            service.claim_request = service.claim_request.model_copy(
                update={
                    "attachments": [
                        ClaimAttachmentMetadata(
                            file_name="buletin.png",
                            content_type="image/png",
                            size_bytes=len(content),
                            file_url=f"/me/customer-profile/documents/{PROFILE_DOCUMENT_ID}/download",
                            metadata={
                                "label": "ID document",
                                "profile_document_id": str(PROFILE_DOCUMENT_ID),
                                "source": "client_profile",
                            },
                        )
                    ]
                }
            )
            app.dependency_overrides[get_claim_request_service] = lambda: service
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: storage_service
            )
            app.dependency_overrides[get_customer_profile_document_service] = (
                lambda: FakeCustomerProfileDocumentService(
                    str(stored.metadata["storage_key"])
                )
            )
            client = _employee_client(app)

            response = client.get(
                f"/claims/{REQUEST_ID}/profile-documents/{PROFILE_DOCUMENT_ID}"
            )

            assert response.status_code == 200
            assert response.content == content
            assert response.headers["content-type"].startswith("image/png")
            assert "buletin.png" in response.headers["content-disposition"]

    def test_client_cannot_upload_attachment_to_another_clients_claim(self) -> None:
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            app.dependency_overrides[get_claim_request_service] = (
                lambda: FakeClaimRequestService()
            )
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: LocalClaimAttachmentStorageService(Path(upload_dir))
            )
            client = _client_auth_client(app, client_id=2002)

            response = client.post(
                f"/claims/{REQUEST_ID}/attachments",
                files=[("files", ("proof.pdf", b"%PDF-1.4\n", "application/pdf"))],
            )

            assert response.status_code == 404

    def test_download_claim_attachment_returns_404_for_missing_id(self) -> None:
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            app.dependency_overrides[get_claim_request_service] = (
                lambda: FakeClaimRequestService()
            )
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: LocalClaimAttachmentStorageService(Path(upload_dir))
            )
            client = _client_auth_client(app)

            response = client.get(
                f"/claims/{REQUEST_ID}/attachments/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            )

            assert response.status_code == 404

    def test_deleted_claim_attachment_cannot_be_downloaded(self) -> None:
        with TemporaryDirectory() as upload_dir:
            app = create_app()
            service = FakeClaimRequestService()
            app.dependency_overrides[get_claim_request_service] = lambda: service
            app.dependency_overrides[get_claim_attachment_storage_service] = (
                lambda: LocalClaimAttachmentStorageService(Path(upload_dir))
            )
            client = _client_auth_client(app)
            upload_response = client.post(
                f"/claims/{REQUEST_ID}/attachments",
                files=[("files", ("proof.pdf", b"%PDF-1.4\n", "application/pdf"))],
            )
            attachment_id = upload_response.json()[0]["metadata"]["attachment_id"]

            delete_response = client.delete(
                f"/claims/{REQUEST_ID}/attachments/{attachment_id}"
            )
            download_response = client.get(
                f"/claims/{REQUEST_ID}/attachments/{attachment_id}"
            )

            assert delete_response.status_code == 204
            assert download_response.status_code == 404

    def test_create_claim_request_uses_service(self) -> None:
        app = create_app()
        service = FakeClaimRequestService()
        precheck_workflow = FakeCoveragePrecheckWorkflowSuccess()
        app.dependency_overrides[get_claim_request_service] = lambda: service
        app.dependency_overrides[get_coverage_precheck_workflow] = (
            lambda: precheck_workflow
        )
        client = _employee_client(app)

        response = client.post(
            "/claims",
            json={
                "request_id": str(REQUEST_ID),
                "client_id": 1001,
                "client_data": {"full_name": "Ion Popescu"},
                "claim_data": {"claim_type": "Fire"},
            },
        )

        assert response.status_code == 200
        assert service.created_request is not None
        assert precheck_workflow.request_id == REQUEST_ID
        assert response.json()["request_id"] == str(REQUEST_ID)
        assert response.json()["request_status"] == "needs_underwriter_review"

    def test_create_claim_request_preserves_uploaded_attachment_metadata(
        self,
    ) -> None:
        app = create_app()
        service = FakeClaimRequestService()
        precheck_workflow = FakeCoveragePrecheckWorkflowFailure()
        app.dependency_overrides[get_claim_request_service] = lambda: service
        app.dependency_overrides[get_coverage_precheck_workflow] = (
            lambda: precheck_workflow
        )
        client = _employee_client(app)

        response = client.post(
            "/claims",
            json={
                "request_id": str(REQUEST_ID),
                "client_id": 1001,
                "client_data": {"full_name": "Ion Popescu"},
                "claim_data": {"claim_type": "Fire"},
                "attachments": [
                    {
                        "file_name": "proof.pdf",
                        "content_type": "application/pdf",
                        "size_bytes": 123,
                        "file_url": "/claims/attachments/abc123",
                        "metadata": {"storage_key": "abc123"},
                    }
                ],
            },
        )

        payload = response.json()
        assert response.status_code == 200
        assert service.created_request is not None
        assert service.created_request.attachments[0].file_url == (
            "/claims/attachments/abc123"
        )
        assert service.created_request.attachments[0].metadata["storage_key"] == (
            "abc123"
        )
        assert payload["attachments"][0]["file_url"] == "/claims/attachments/abc123"
        assert payload["attachments"][0]["metadata"]["storage_key"] == "abc123"

    def test_create_claim_request_returns_created_claim_if_precheck_fails(
        self,
    ) -> None:
        app = create_app()
        service = FakeClaimRequestService()
        precheck_workflow = FakeCoveragePrecheckWorkflowFailure()
        app.dependency_overrides[get_claim_request_service] = lambda: service
        app.dependency_overrides[get_coverage_precheck_workflow] = (
            lambda: precheck_workflow
        )
        client = _employee_client(app)

        response = client.post(
            "/claims",
            json={
                "request_id": str(REQUEST_ID),
                "client_id": 1001,
                "client_data": {"full_name": "Ion Popescu"},
                "claim_data": {"claim_type": "Fire"},
            },
        )

        assert response.status_code == 200
        assert service.created_request is not None
        assert precheck_workflow.request_id == REQUEST_ID
        assert response.json()["request_status"] == "submitted"

    def test_create_my_claim_requires_complete_customer_profile(self) -> None:
        app = create_app()
        service = FakeClaimRequestService()
        app.dependency_overrides[get_claim_request_service] = lambda: service
        app.dependency_overrides[get_current_client_user] = lambda: make_client_user(None)
        app.dependency_overrides[get_customer_profile_service] = (
            lambda: FakeIncompleteProfileService()
        )
        client = _employee_client(app)

        response = client.post(
            "/me/claims",
            json={
                "claim_data": {"claim_type": "Fire"},
            },
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CUSTOMER_PROFILE_INCOMPLETE"
        assert service.created_request is None

    def test_create_my_claim_rejects_missing_contract_id(self) -> None:
        app = create_app()
        service = FakeClaimRequestService()
        app.dependency_overrides[get_claim_request_service] = lambda: service
        app.dependency_overrides[get_current_client_user] = lambda: make_client_user(1001)
        app.dependency_overrides[get_customer_profile_service] = (
            lambda: FakeCompleteProfileService()
        )
        client = _employee_client(app)

        response = client.post(
            "/me/claims",
            json={
                "claim_data": {"claim_type": "Fire"},
            },
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CLAIM_CONTRACT_REQUIRED"
        assert service.created_request is None

    def test_create_my_claim_rejects_other_client_contract(self) -> None:
        app = create_app()
        service = FakeClaimRequestService()
        app.dependency_overrides[get_claim_request_service] = lambda: service
        app.dependency_overrides[get_current_client_user] = lambda: make_client_user(1001)
        app.dependency_overrides[get_customer_profile_service] = (
            lambda: FakeCompleteProfileService()
        )
        app.dependency_overrides[get_contract_query_service] = lambda: FakeContractQueryService(
            [make_contract(contract_id=OTHER_CONTRACT_ID, customer_id=2002)]
        )
        client = _employee_client(app)

        response = client.post(
            "/me/claims",
            json={"claim_data": {"contract_id": str(OTHER_CONTRACT_ID)}},
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CLAIM_CONTRACT_NOT_CLAIMABLE"
        assert service.created_request is None

    def test_create_my_claim_rejects_non_claimable_contract(self) -> None:
        app = create_app()
        service = FakeClaimRequestService()
        app.dependency_overrides[get_claim_request_service] = lambda: service
        app.dependency_overrides[get_current_client_user] = lambda: make_client_user(1001)
        app.dependency_overrides[get_customer_profile_service] = (
            lambda: FakeCompleteProfileService()
        )
        app.dependency_overrides[get_contract_query_service] = lambda: FakeContractQueryService(
            [make_contract(status="draft")]
        )
        client = _employee_client(app)

        response = client.post(
            "/me/claims",
            json={"claim_data": {"contract_id": str(CONTRACT_ID)}},
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CLAIM_CONTRACT_NOT_CLAIMABLE"
        assert service.created_request is None

    def test_create_my_claim_rejects_expired_contract(self) -> None:
        app = create_app()
        service = FakeClaimRequestService()
        app.dependency_overrides[get_claim_request_service] = lambda: service
        app.dependency_overrides[get_current_client_user] = lambda: make_client_user(1001)
        app.dependency_overrides[get_customer_profile_service] = (
            lambda: FakeCompleteProfileService()
        )
        app.dependency_overrides[get_contract_query_service] = lambda: FakeContractQueryService(
            [make_contract(expiration_date=date(2026, 5, 12))]
        )
        client = _employee_client(app)

        response = client.post(
            "/me/claims",
            json={"claim_data": {"contract_id": str(CONTRACT_ID)}},
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CLAIM_CONTRACT_NOT_CLAIMABLE"
        assert service.created_request is None

    def test_create_my_claim_uses_authenticated_client_id(self) -> None:
        app = create_app()
        service = FakeClaimRequestService()
        precheck_workflow = FakeCoveragePrecheckWorkflowFromService(service)
        app.dependency_overrides[get_claim_request_service] = lambda: service
        app.dependency_overrides[get_coverage_precheck_workflow] = (
            lambda: precheck_workflow
        )
        app.dependency_overrides[get_current_client_user] = lambda: make_client_user(1001)
        app.dependency_overrides[get_customer_profile_service] = (
            lambda: FakeCompleteProfileService()
        )
        app.dependency_overrides[get_contract_query_service] = lambda: FakeContractQueryService()
        client = _employee_client(app)

        response = client.post(
            "/me/claims",
            json={
                "claim_data": {"claim_type": "Fire", "contract_id": str(CONTRACT_ID)},
            },
        )

        assert response.status_code == 200
        assert service.created_request is not None
        assert service.created_request.client_id == 1001

    def test_create_my_claim_derives_canonical_contract_fields(self) -> None:
        app = create_app()
        service = FakeClaimRequestService()
        precheck_workflow = FakeCoveragePrecheckWorkflowFromService(service)
        app.dependency_overrides[get_claim_request_service] = lambda: service
        app.dependency_overrides[get_coverage_precheck_workflow] = (
            lambda: precheck_workflow
        )
        app.dependency_overrides[get_current_client_user] = lambda: make_client_user(1001)
        app.dependency_overrides[get_customer_profile_service] = (
            lambda: FakeCompleteProfileService()
        )
        app.dependency_overrides[get_contract_query_service] = lambda: FakeContractQueryService()
        client = _employee_client(app)

        response = client.post(
            "/me/claims",
            json={
                "claim_data": {
                    "claim_id": "22222222-2222-4222-8222-000000000009",
                    "contract_id": str(CONTRACT_ID),
                    "policy_number": "TAMPERED-POLICY",
                    "property_address": "Tampered address",
                    "claim_type": "Fire",
                },
            },
        )

        assert response.status_code == 200
        assert service.created_request is not None
        claim_data = service.created_request.claim_data
        assert claim_data["claim_id"] == "22222222-2222-4222-8222-000000000009"
        assert claim_data["display_claim_id"] == "CLM-2026-000009"
        assert claim_data["contract_id"] == str(CONTRACT_ID)
        assert claim_data["policy_number"] == "POL-123456"
        assert claim_data["contract_display_id"] == "POL-Ion_Popescu-123456"
        assert claim_data["property_address"] == (
            "Str. Mihai Eminescu 12, Bucuresti, 010123"
        )
        assert claim_data["insured_asset_id"] == 55
        assert claim_data["coverage_amount"] == 300000.0

    def test_list_underwriter_claims_uses_status_filter(self) -> None:
        app = create_app()
        app.dependency_overrides[get_claim_request_service] = (
            lambda: FakeClaimRequestService()
        )
        client = _employee_client(app)

        response = client.get("/underwriter/claims", params={"status": "in_review"})

        assert response.status_code == 200
        assert response.json()[0]["request_status"] == "in_review"

    def test_start_underwriter_review_marks_submitted_claim_in_review(self) -> None:
        service = FakeClaimRequestService()
        app = create_app()
        app.dependency_overrides[get_claim_request_service] = lambda: service
        client = _employee_client(app)

        response = client.post(f"/underwriter/claims/{REQUEST_ID}/start-review")

        assert response.status_code == 200
        assert response.json()["request_status"] == "in_review"
        assert service.claim_request.request_status == "in_review"

    def test_submit_claim_decision_persists_denied_decision(self) -> None:
        claim_service = FakeClaimRequestService()
        app = create_app()
        app.dependency_overrides[get_claim_request_service] = lambda: claim_service

        response = _employee_client(app).post(
            f"/underwriter/claims/{REQUEST_ID}/decision",
            json={
                "decision": "denied",
                "justification": "This is not a good claim.",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["request_status"] == "completed"
        assert payload["claim_data"]["decision"] == "denied"
        assert payload["claim_data"]["decision_status"] == "submitted"
        assert payload["claim_data"]["decision_justification"] == (
            "This is not a good claim."
        )
        assert payload["claim_data"]["decided_by"] == 2
        assert payload["claim_data"]["decided_by_email"] == "underwriter@example.test"
        assert payload["claim_data"]["decided_at"]

    def test_submit_claim_decision_requires_employee_role(self) -> None:
        app = create_app()
        app.dependency_overrides[get_claim_request_service] = (
            lambda: FakeClaimRequestService()
        )

        assert (
            TestClient(app)
            .post(
                f"/underwriter/claims/{REQUEST_ID}/decision",
                json={"decision": "approved", "justification": "Covered loss."},
            )
            .status_code
            == 401
        )
        assert (
            _client_auth_client(app)
            .post(
                f"/underwriter/claims/{REQUEST_ID}/decision",
                json={"decision": "approved", "justification": "Covered loss."},
            )
            .status_code
            == 403
        )

    def test_send_claim_decision_email_requires_persisted_decision(self) -> None:
        claim_service = FakeClaimRequestService()
        email_service = FakeEmailSendService()
        app = create_app()
        app.dependency_overrides[get_claim_request_service] = lambda: claim_service
        app.dependency_overrides[get_claim_decision_email_send_service] = lambda: email_service

        response = _employee_client(app).post(
            f"/underwriter/claims/{REQUEST_ID}/decision-email"
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CLAIM_DECISION_REQUIRED"
        assert email_service.sent == []

    def test_send_claim_decision_email_uses_persisted_denied_decision(self) -> None:
        claim_service = FakeClaimRequestService()
        claim_service.claim_request = make_claim_request("completed").model_copy(
            update={
                "client_data": {
                    "full_name": "Alex Vulcu",
                    "email": "alex.vulcu@ultrasafe.ro",
                },
                "claim_data": {
                    "display_claim_id": "CLM-DEMO-ALEX-001",
                    "decision": "denied",
                    "decision_status": "submitted",
                    "decision_justification": "This is not a good claim.",
                    "decided_by": 2,
                    "decided_at": "2026-05-15T09:30:00+00:00",
                },
            }
        )
        email_service = FakeEmailSendService()
        app = create_app()
        app.dependency_overrides[get_claim_request_service] = lambda: claim_service
        app.dependency_overrides[get_claim_decision_email_send_service] = lambda: email_service

        with patch.dict(
            os.environ,
            {"EMAIL_DEMO_CLAIM_DECISION_TO": "alex.vulcu@ultrasafe.ro"},
            clear=False,
        ):
            response = _employee_client(app).post(
                f"/underwriter/claims/{REQUEST_ID}/decision-email"
            )

        assert response.status_code == 200
        assert response.json()["status"] == "SENT"
        assert email_service.sent == [
            {
                "case_id": REQUEST_ID,
                "to_email": "alex.vulcu@ultrasafe.ro",
                "subject": "Your Underwright claim decision",
                "body": (
                    "Hello Alex,\n\n"
                    "We have completed the review of your claim CLM-DEMO-ALEX-001.\n\n"
                    "Decision: Denied\n\n"
                    "Decision justification:\n"
                    "This is not a good claim.\n\n"
                    "This is a demo claim decision email sent from Underwright.\n\n"
                    "Regards,\n"
                    "Underwright Claims Team"
                ),
                "html_body": (
                    "<!doctype html><html><body><p>Hello Alex,</p>"
                    "<p>We have completed the review of your claim "
                    "<strong>CLM-DEMO-ALEX-001</strong>.</p>"
                    "<p><strong>Decision:</strong> Denied</p>"
                    "<p><strong>Decision justification:</strong><br>"
                    "This is not a good claim.</p>"
                    "<p>This is a demo claim decision email sent from Underwright.</p>"
                    "<p>Regards,<br>Underwright Claims Team</p></body></html>"
                ),
            }
        ]
        assert "Approved" not in email_service.sent[0]["body"]
        assert claim_service.claim_request.claim_data["decision_email_sent_at"]

    def test_send_claim_decision_email_blocks_duplicate_send(self) -> None:
        claim_service = FakeClaimRequestService()
        claim_service.claim_request = make_claim_request("completed").model_copy(
            update={
                "claim_data": {
                    "display_claim_id": "CLM-DEMO-ALEX-001",
                    "decision": "approved",
                    "decision_status": "submitted",
                    "decision_justification": "Covered loss.",
                    "decided_at": "2026-05-15T09:30:00+00:00",
                    "decision_email_sent_at": "2026-05-15T10:00:00+00:00",
                }
            }
        )
        email_service = FakeEmailSendService()
        app = create_app()
        app.dependency_overrides[get_claim_request_service] = lambda: claim_service
        app.dependency_overrides[get_claim_decision_email_send_service] = lambda: email_service

        response = _employee_client(app).post(
            f"/underwriter/claims/{REQUEST_ID}/decision-email"
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CLAIM_DECISION_EMAIL_ALREADY_SENT"
        assert email_service.sent == []

    def test_send_claim_decision_email_requires_employee_role(self) -> None:
        app = create_app()
        app.dependency_overrides[get_claim_request_service] = (
            lambda: FakeClaimRequestService()
        )
        app.dependency_overrides[get_claim_decision_email_send_service] = lambda: FakeEmailSendService()

        assert (
            TestClient(app)
            .post(f"/underwriter/claims/{REQUEST_ID}/decision-email")
            .status_code
            == 401
        )
        assert (
            _client_auth_client(app)
            .post(f"/underwriter/claims/{REQUEST_ID}/decision-email")
            .status_code
            == 403
        )

    def test_claim_decision_email_dependency_allows_local_demo_without_smtp(
        self,
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "POSTMARK_SERVER_TOKEN": "",
                "EMAIL_SMTP_HOST": "",
                "EMAIL_USERNAME": "",
                "EMAIL_PASSWORD": "",
                "EMAIL_FROM": "",
            },
            clear=False,
        ):
            service = get_claim_decision_email_send_service()

        assert isinstance(service.provider, LocalEmailProvider)
        assert service.from_email == "claims@underwright.local"

    def test_reword_claim_decision_justification_requires_employee_role(self) -> None:
        app = create_app()
        app.dependency_overrides[get_claim_decision_rewording_service] = (
            lambda: FakeClaimDecisionRewordingService()
        )

        body = {"decision": "denied", "justification": "The loss is not covered."}

        assert (
            TestClient(app)
            .post("/claims/decision-justification/reword", json=body)
            .status_code
            == 401
        )
        assert (
            _client_auth_client(app)
            .post("/claims/decision-justification/reword", json=body)
            .status_code
            == 403
        )

    def test_reword_claim_decision_justification_returns_suggestion(self) -> None:
        service = FakeClaimDecisionRewordingService()
        app = create_app()
        app.dependency_overrides[get_claim_decision_rewording_service] = lambda: service

        response = _employee_client(app).post(
            "/claims/decision-justification/reword",
            json={
                "decision": "denied",
                "justification": "The receipts do not match the claimed loss.",
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "suggestion": "A professionally worded version of the same reasoning."
        }
        assert service.calls == [
            {
                "decision": "denied",
                "justification": "The receipts do not match the claimed loss.",
            }
        ]

    def test_reword_claim_decision_justification_rejects_empty_text(self) -> None:
        service = FakeClaimDecisionRewordingService(error=ValueError("required"))
        app = create_app()
        app.dependency_overrides[get_claim_decision_rewording_service] = lambda: service

        response = _employee_client(app).post(
            "/claims/decision-justification/reword",
            json={"decision": "denied", "justification": "   "},
        )

        assert response.status_code == 400

    def test_reword_claim_decision_justification_returns_503_when_not_configured(
        self,
    ) -> None:
        service = FakeClaimDecisionRewordingService(
            error=ClaimDecisionRewordingNotConfiguredError()
        )
        app = create_app()
        app.dependency_overrides[get_claim_decision_rewording_service] = lambda: service

        response = _employee_client(app).post(
            "/claims/decision-justification/reword",
            json={"decision": "approved", "justification": "Covered loss."},
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "AI rewording is not configured."

    def test_reword_claim_decision_justification_hides_provider_error(self) -> None:
        service = FakeClaimDecisionRewordingService(
            error=ClaimDecisionRewordingProviderError("secret raw provider failure")
        )
        app = create_app()
        app.dependency_overrides[get_claim_decision_rewording_service] = lambda: service

        response = _employee_client(app).post(
            "/claims/decision-justification/reword",
            json={"decision": "approved", "justification": "Covered loss."},
        )

        assert response.status_code == 502
        assert response.json()["detail"] == "AI suggestion could not be generated."
        assert "secret" not in response.text

    def test_start_analysis_returns_review_view(self) -> None:
        app = create_app()
        app.dependency_overrides[get_claim_request_service] = (
            lambda: FakeClaimRequestService()
        )
        app.dependency_overrides[get_claim_workflow] = lambda: FakeClaimWorkflowSuccess()
        client = _employee_client(app)

        response = client.post(f"/underwriter/claims/{REQUEST_ID}/start-analysis")

        assert response.status_code == 200
        payload = response.json()
        assert payload["case_id"] == str(CASE_ID)
        assert payload["review_view"]["suggested_next_action"] == "underwriter_review"
        assert payload["review_view"]["supporting_facts"][0]["field"] == (
            "policy_number"
        )
        assert payload["module_results"][0]["module_name"] == "ClaimValidationModule"

    def test_refresh_claim_attachment_analysis_reprocesses_and_returns_review(
        self,
    ) -> None:
        context = ClaimCaseContext()
        context.case_metadata.case_id = CASE_ID
        context.case_metadata.status = "in_review"
        context.review_state.claim_review_view = make_review_view()
        processing_service = FakeClaimAttachmentProcessingService()
        app = create_app()
        app.dependency_overrides[get_claim_attachment_processing_service] = (
            lambda: processing_service
        )
        app.dependency_overrides[get_claim_review_query_service] = lambda: (
            make_claim_review_query_service(context)
        )
        client = _employee_client(app)

        response = client.post(
            f"/underwriter/claims/{REQUEST_ID}/attachments/refresh-analysis"
        )

        payload = response.json()
        assert response.status_code == 200
        assert processing_service.processed_request_ids == [REQUEST_ID]
        assert payload["case_id"] == str(CASE_ID)
        assert payload["review_view"]["suggested_next_action"] == (
            "underwriter_review"
        )

    def test_get_claim_review_view_returns_persisted_view(self) -> None:
        context = ClaimCaseContext()
        context.case_metadata.case_id = CASE_ID
        context.case_metadata.status = "in_review"
        context.review_state.claim_review_view = make_review_view()
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: FakeCaseContextService(
            context
        )
        client = _employee_client(app)

        response = client.get(f"/claim-review-views/{CASE_ID}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["review_view"]["header"]["case_id"] == str(CASE_ID)
        assert payload["review_view"]["coverage_assessment"]["coverage_status"] == (
            "potentially_covered"
        )
        assert payload["review_view"]["coverage_assessment"]["wording_section_ids"] == [
            "coverage.fire_damage"
        ]

    def test_get_latest_claim_review_returns_full_review(self) -> None:
        context = ClaimCaseContext()
        context.case_metadata.case_id = CASE_ID
        context.case_metadata.status = "in_review"
        context.review_state.claim_review_view = make_review_view()
        context.review_state.available_actions = [
            "view_details",
            "start_analysis",
            "request_evidence",
        ]
        context.generated_outputs.document_consistency = DocumentConsistencyResult(
            status="no_discrepancies"
        )
        context.generated_outputs.evidence_requirements = EvidenceRequirementResult(
            required_evidence=[],
            suggested_next_action="underwriter_review",
        )
        context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
            claim_request_id=REQUEST_ID,
            subject="Additional evidence required",
            body="Please provide supporting documents.",
            required_documents=["fire service report"],
        )
        app = create_app()
        app.dependency_overrides[get_claim_review_query_service] = lambda: (
            make_claim_review_query_service(context)
        )
        client = _employee_client(app)

        response = client.get(f"/underwriter/claims/{REQUEST_ID}/review")

        payload = response.json()
        assert response.status_code == 200
        assert payload["case_id"] == str(CASE_ID)
        assert payload["status"] == "in_review"
        assert payload["review_state"] == "full_review"
        assert payload["review_view"]["supporting_facts"][0]["field"] == (
            "policy_number"
        )
        assert payload["review_view"]["coverage_assessment"]["coverage_status"] == (
            "potentially_covered"
        )
        assert payload["evidence_request_draft"]["status"] == "draft"
        assert payload["review_view"]["evidence_request_draft"]["subject"] == (
            "Additional evidence required"
        )
        assert "start_analysis" not in payload["review_view"]["available_actions"]
        assert "request_evidence" in payload["review_view"]["available_actions"]

    def test_get_latest_claim_review_returns_coverage_precheck_only(self) -> None:
        context = ClaimCaseContext(source_inputs={"request_id": REQUEST_ID})
        context.case_metadata.case_id = CASE_ID
        context.case_metadata.status = "needs_underwriter_review"
        context.generated_outputs.coverage_assessment = CoverageAssessmentResult(
            coverage_status="potentially_covered",
            matched_wording_sections=["coverage.fire_damage"],
            wording_section_ids=["coverage.fire_damage"],
            possible_exclusions=[],
            rationale="Fire wording may apply.",
            confidence="high",
        )
        app = create_app()
        app.dependency_overrides[get_claim_review_query_service] = lambda: (
            make_claim_review_query_service(context)
        )
        client = _employee_client(app)

        response = client.get(f"/underwriter/claims/{REQUEST_ID}/review")

        payload = response.json()
        assert response.status_code == 200
        assert payload["review_state"] == "coverage_precheck_only"
        assert payload["review_view"]["coverage_assessment"]["coverage_status"] == (
            "potentially_covered"
        )
        assert payload["review_view"]["document_consistency"]["status"] == (
            "not_started"
        )
        assert "start_analysis" in payload["review_view"]["available_actions"]

    def test_get_latest_claim_review_returns_not_started_when_no_review_exists(
        self,
    ) -> None:
        app = create_app()
        app.dependency_overrides[get_claim_review_query_service] = lambda: (
            make_claim_review_query_service(None, raise_context_not_found=True)
        )
        client = _employee_client(app)

        response = client.get(f"/underwriter/claims/{REQUEST_ID}/review")

        payload = response.json()
        assert response.status_code == 200
        assert payload["case_id"] is None
        assert payload["status"] == "not_started"
        assert payload["review_state"] == "not_started"
        assert payload["review_view"]["document_consistency"]["status"] == (
            "not_started"
        )
        assert payload["review_view"]["coverage_assessment"] is None
        assert payload["review_view"]["available_actions"] == ["start_analysis"]

    def test_get_latest_claim_review_includes_attachment_summary_as_ai_finding(
        self,
    ) -> None:
        claim_service = FakeClaimRequestService()
        claim_data = dict(claim_service.claim_request.claim_data)
        claim_data["attachment_extraction_summary"] = {
            "claim_request_id": str(REQUEST_ID),
            "attachment_keys": ["damage-photo-1"],
            "attachment_count": 1,
            "summary": (
                "## Extracted fields / AI interpretation\n"
                "* Invoice and ownership proof are consistent with the claim details.\n"
                "* **Damage amount:** 12000 RON"
            ),
            "error": None,
            "source": "global_summary",
        }
        claim_service.claim_request = claim_service.claim_request.model_copy(
            update={
                "claim_data": claim_data,
                "attachments": [
                    ClaimAttachmentMetadata(
                        file_name="damage-photo.jpg",
                        content_type="image/jpeg",
                        size_bytes=12,
                        file_url="/claims/damage-photo.jpg",
                        metadata={"attachment_id": "damage-photo-1"},
                    )
                ],
            }
        )

        app = create_app()
        app.dependency_overrides[get_claim_review_query_service] = lambda: (
            ClaimReviewQueryService(
                claim_request_service=claim_service,
                case_context_service=FakeCaseContextService(
                    None,
                    raise_not_found=True,
                ),
            )
        )
        client = _employee_client(app)

        response = client.get(f"/underwriter/claims/{REQUEST_ID}/review")

        payload = response.json()
        assert response.status_code == 200
        assert payload["review_state"] == "not_started"
        findings = payload["review_view"].get("ai_review_findings")
        assert isinstance(findings, list)
        assert findings
        assert findings[0]["finding_type"] == "document_summary"
        assert findings[0]["description"] == (
            "Document interpretation:\n"
            "- Invoice and ownership proof are consistent with the claim details.\n"
            "- Damage amount: 12000 RON"
        )

    def test_get_latest_claim_review_ignores_stale_attachment_summary(
        self,
    ) -> None:
        claim_service = FakeClaimRequestService()
        claim_data = dict(claim_service.claim_request.claim_data)
        claim_data["attachment_extraction_summary"] = {
            "claim_request_id": str(REQUEST_ID),
            "attachment_keys": ["other-attachment"],
            "attachment_count": 1,
            "summary": "This summary was generated from another claim.",
            "error": None,
            "source": "global_summary",
        }
        claim_service.claim_request = claim_service.claim_request.model_copy(
            update={
                "claim_data": claim_data,
                "attachments": [
                    ClaimAttachmentMetadata(
                        file_name="damage-photo.jpg",
                        content_type="image/jpeg",
                        size_bytes=12,
                        file_url="/claims/damage-photo.jpg",
                        metadata={"attachment_id": "damage-photo-1"},
                    )
                ],
            }
        )

        app = create_app()
        app.dependency_overrides[get_claim_review_query_service] = lambda: (
            ClaimReviewQueryService(
                claim_request_service=claim_service,
                case_context_service=FakeCaseContextService(
                    None,
                    raise_not_found=True,
                ),
            )
        )
        client = _employee_client(app)

        response = client.get(f"/underwriter/claims/{REQUEST_ID}/review")

        payload = response.json()
        assert response.status_code == 200
        assert "ai_review_findings" not in payload["review_view"]

    def test_get_latest_claim_review_unknown_claim_returns_404(self) -> None:
        app = create_app()
        app.dependency_overrides[get_claim_review_query_service] = lambda: (
            make_claim_review_query_service(ClaimCaseContext())
        )
        client = _employee_client(app)

        response = client.get(
            "/underwriter/claims/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/review"
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CLAIM_REQUEST_NOT_FOUND"

    def test_create_evidence_request_draft_returns_fire_draft(self) -> None:
        context = make_context_with_evidence_requirements(
            [
                EvidenceRequirement(
                    requirement_type="official_fire_incident_confirmation",
                    reason="Fire incident needs official confirmation.",
                    acceptable_documents=[
                        "fire_service_report",
                        "emergency_report",
                        "official_incident_confirmation",
                    ],
                    severity="high",
                    status="missing",
                    suggested_next_action="request_evidence",
                )
            ]
        )
        service = FakeCaseContextService(context)
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        client = _employee_client(app)

        response = client.post(
            f"/underwriter/claims/{REQUEST_ID}/evidence-request/draft"
        )

        payload = response.json()
        assert response.status_code == 200
        assert payload["needed"] is True
        assert payload["draft"]["status"] == "draft"
        assert payload["draft"]["subject"] == (
            "Additional evidence required for your fire claim"
        )
        assert "fire service report" in payload["draft"]["required_documents"]
        assert "incident reference number" in payload["draft"]["body"]
        assert service.saved_context is context

    def test_create_evidence_request_draft_reports_no_request_needed(self) -> None:
        context = make_context_with_evidence_requirements([])
        service = FakeCaseContextService(context)
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        client = _employee_client(app)

        response = client.post(
            f"/underwriter/claims/{REQUEST_ID}/evidence-request/draft"
        )

        payload = response.json()
        assert response.status_code == 200
        assert payload["needed"] is False
        assert payload["draft"] is None
        assert "No evidence request is needed" in payload["message"]
        assert service.saved_context is None

    def test_update_evidence_request_draft_persists_edits(self) -> None:
        context = make_context_with_evidence_requirements([])
        service = FakeCaseContextService(context)
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        client = _employee_client(app)

        response = client.patch(
            f"/underwriter/claims/{REQUEST_ID}/evidence-request/draft",
            json={
                "subject": "Edited evidence request",
                "body": "Please send the fire report.",
                "recipients": ["client@example.test"],
                "required_documents": ["fire service report"],
                "source_suggestion_id": "ai-follow-up-fire",
                "requested_document_type": "fire service report",
                "due_date": "2026-05-30",
            },
        )

        payload = response.json()
        assert response.status_code == 200
        assert payload["draft"]["subject"] == "Edited evidence request"
        assert payload["draft"]["recipients"] == ["client@example.test"]
        assert payload["draft"]["send_status"] == "not_sent"
        assert payload["draft"]["due_date"] == "2026-05-30"
        assert service.saved_context is context
        assert (
            context.generated_outputs.communication_suggestion_states[
                "ai-follow-up-fire"
            ].status
            == "draft_created"
        )

    def test_update_evidence_request_draft_after_sent_starts_new_request(
        self,
    ) -> None:
        context = make_context_with_evidence_requirements([])
        context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
            claim_request_id=REQUEST_ID,
            subject="Additional evidence required",
            body="Please send the fire report.",
            recipients=["client@example.test"],
            required_documents=["fire service report"],
            source_suggestion_id="ai-follow-up-fire",
            status="sent",
            send_status="sent",
            sent_to=["client@example.test"],
        )
        service = FakeCaseContextService(context)
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        client = _employee_client(app)

        response = client.patch(
            f"/underwriter/claims/{REQUEST_ID}/evidence-request/draft",
            json={
                "subject": "Claimant statement required",
                "body": "Please send a claimant statement.",
                "recipients": ["client@example.test"],
                "required_documents": ["claimant statement"],
                "source_suggestion_id": "ai-follow-up-claimant-statement",
                "requested_document_type": "claimant statement",
            },
        )

        payload = response.json()
        assert response.status_code == 200
        assert payload["draft"]["subject"] == "Claimant statement required"
        assert payload["draft"]["required_documents"] == ["claimant statement"]
        assert payload["draft"]["source_suggestion_id"] == (
            "ai-follow-up-claimant-statement"
        )
        assert payload["draft"]["send_status"] == "not_sent"
        assert payload["draft"]["sent_to"] == []
        assert service.saved_context is context

    def test_dismiss_ai_communication_suggestion_persists_state(self) -> None:
        context = make_context_with_evidence_requirements([])
        service = FakeCaseContextService(context)
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        client = _employee_client(app)

        response = client.post(
            f"/underwriter/claims/{REQUEST_ID}/communication-suggestions/ai-follow-up-fire/dismiss"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "dismissed"
        assert service.saved_context is context
        assert (
            context.generated_outputs.communication_suggestion_states[
                "ai-follow-up-fire"
            ].dismissed_at
            is not None
        )

    def test_send_evidence_request_draft_sends_email_and_blocks_duplicate(
        self,
    ) -> None:
        context = make_context_with_evidence_requirements([])
        context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
            claim_request_id=REQUEST_ID,
            subject="Additional evidence required",
            body="Please send the fire report.",
            recipients=["client@example.test"],
            required_documents=["fire service report"],
            source_suggestion_id="ai-follow-up-fire",
        )
        service = FakeCaseContextService(context)
        email_service = FakeEmailSendService()
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        app.dependency_overrides[get_evidence_request_email_send_service] = (
            lambda: email_service
        )
        client = _employee_client(app)

        with patch.dict(
            os.environ,
            {
                "CLAIM_INBOUND_EMAIL_ADDRESS": "",
                "CLAIM_INBOUND_EMAIL_DOMAIN": "underwright.local",
            },
            clear=False,
        ):
            response = client.post(
                f"/underwriter/claims/{REQUEST_ID}/evidence-request/draft/send"
            )

        payload = response.json()
        assert response.status_code == 200
        assert payload["draft"]["status"] == "sent"
        assert payload["draft"]["send_status"] == "sent"
        assert payload["draft"]["sent_to"] == ["client@example.test"]
        assert payload["draft"]["provider_message_id"] == "message-id"
        assert payload["draft"]["email_message_id"]
        assert email_service.sent == [
            {
                "case_id": REQUEST_ID,
                "request_id": REQUEST_ID,
                "to_email": "client@example.test",
                "subject": (
                    "[UW-CLAIM:"
                    f"{context.generated_outputs.evidence_request_draft.reply_token}] "
                    "Additional evidence required"
                ),
                "body": "Please send the fire report.",
                "html_body": None,
                "reply_to": (
                    "claims+"
                    f"{context.generated_outputs.evidence_request_draft.reply_token}"
                    "@underwright.local"
                ),
            }
        ]
        assert (
            context.generated_outputs.communication_suggestion_states[
                "ai-follow-up-fire"
            ].status
            == "sent"
        )

        duplicate_response = client.post(
            f"/underwriter/claims/{REQUEST_ID}/evidence-request/draft/send"
        )

        assert duplicate_response.status_code == 409
        assert (
            duplicate_response.json()["error"]["code"]
            == "EVIDENCE_REQUEST_DRAFT_ALREADY_SENT"
        )

    def test_send_evidence_request_draft_uses_configured_postmark_inbound_address(
        self,
    ) -> None:
        context = make_context_with_evidence_requirements([])
        context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
            claim_request_id=REQUEST_ID,
            subject="Additional evidence required",
            body="Please send the fire report.",
            recipients=["client@example.test"],
            required_documents=["fire service report"],
        )
        service = FakeCaseContextService(context)
        email_service = FakeEmailSendService()
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        app.dependency_overrides[get_evidence_request_email_send_service] = (
            lambda: email_service
        )
        client = _employee_client(app)

        with patch.dict(
            os.environ,
            {
                "CLAIM_INBOUND_EMAIL_ADDRESS": (
                    "377b592f8a5d0e147633e00e2d93f840"
                    "@inbound.postmarkapp.com"
                )
            },
            clear=False,
        ):
            response = client.post(
                f"/underwriter/claims/{REQUEST_ID}/evidence-request/draft/send"
            )

        draft = context.generated_outputs.evidence_request_draft
        assert response.status_code == 200
        assert draft is not None
        assert email_service.sent[0]["reply_to"] == (
            "377b592f8a5d0e147633e00e2d93f840"
            f"+{draft.reply_token}@inbound.postmarkapp.com"
        )

    def test_send_demo_inbound_email_sends_to_postmark_inbound_address(
        self,
    ) -> None:
        context = make_context_with_evidence_requirements([])
        context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
            claim_request_id=REQUEST_ID,
            subject="Additional evidence required",
            body="Please send the fire report.",
            recipients=["client@example.test"],
            required_documents=["fire service report"],
            status="sent",
            send_status="sent",
            sent_to=["client@example.test"],
            reply_token="reply-token-123",
        )
        service = FakeCaseContextService(context)
        email_service = FakeEmailSendService()
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        app.dependency_overrides[get_evidence_request_email_send_service] = (
            lambda: email_service
        )
        client = _employee_client(app)

        with patch.dict(
            os.environ,
            {
                "CLAIM_INBOUND_EMAIL_ADDRESS": (
                    "377b592f8a5d0e147633e00e2d93f840"
                    "@inbound.postmarkapp.com"
                )
            },
            clear=False,
        ):
            response = client.post(
                f"/underwriter/claims/{REQUEST_ID}/communication/demo-inbound-email"
            )

        payload = response.json()
        assert response.status_code == 200
        assert payload["message"] == "Demo inbound email sent through Postmark."
        assert payload["to_email"] == (
            "377b592f8a5d0e147633e00e2d93f840"
            "+reply-token-123@inbound.postmarkapp.com"
        )
        assert payload["reply_token"] == "reply-token-123"
        assert email_service.sent[0]["case_id"] == REQUEST_ID
        assert email_service.sent[0]["request_id"] == REQUEST_ID
        assert email_service.sent[0]["to_email"] == payload["to_email"]
        assert email_service.sent[0]["subject"] == (
            "[UW-CLAIM:reply-token-123] Re: Additional evidence required"
        )
        attachments = email_service.sent[0]["attachments"]
        assert len(attachments) == 1
        assert attachments[0].file_name == "demo-inbound-evidence.pdf"
        assert attachments[0].content_type == "application/pdf"

    def test_send_demo_inbound_email_requires_sent_request(self) -> None:
        context = make_context_with_evidence_requirements([])
        context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
            claim_request_id=REQUEST_ID,
            subject="Additional evidence required",
            body="Please send the fire report.",
            recipients=["client@example.test"],
            required_documents=["fire service report"],
        )
        service = FakeCaseContextService(context)
        email_service = FakeEmailSendService()
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        app.dependency_overrides[get_evidence_request_email_send_service] = (
            lambda: email_service
        )
        client = _employee_client(app)

        with patch.dict(
            os.environ,
            {
                "CLAIM_INBOUND_EMAIL_ADDRESS": (
                    "377b592f8a5d0e147633e00e2d93f840"
                    "@inbound.postmarkapp.com"
                )
            },
            clear=False,
        ):
            response = client.post(
                f"/underwriter/claims/{REQUEST_ID}/communication/demo-inbound-email"
            )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "EVIDENCE_REQUEST_DRAFT_INVALID"
        assert email_service.sent == []

    def test_send_demo_inbound_email_requires_configured_inbound_address(
        self,
    ) -> None:
        context = make_context_with_evidence_requirements([])
        context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
            claim_request_id=REQUEST_ID,
            subject="Additional evidence required",
            body="Please send the fire report.",
            recipients=["client@example.test"],
            required_documents=["fire service report"],
            status="sent",
            send_status="sent",
            sent_to=["client@example.test"],
            reply_token="reply-token-123",
        )
        service = FakeCaseContextService(context)
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        app.dependency_overrides[get_evidence_request_email_send_service] = (
            lambda: FakeEmailSendService()
        )
        client = _employee_client(app)

        with patch.dict(os.environ, {"CLAIM_INBOUND_EMAIL_ADDRESS": ""}, clear=False):
            response = client.post(
                f"/underwriter/claims/{REQUEST_ID}/communication/demo-inbound-email"
            )

        assert response.status_code == 409
        assert (
            response.json()["error"]["code"]
            == "CLAIM_INBOUND_EMAIL_ADDRESS_REQUIRED"
        )

    def test_send_evidence_request_draft_requires_recipient(self) -> None:
        context = make_context_with_evidence_requirements([])
        context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
            claim_request_id=REQUEST_ID,
            subject="Additional evidence required",
            body="Please send the fire report.",
            recipients=[],
            required_documents=["fire service report"],
        )
        service = FakeCaseContextService(context)
        email_service = FakeEmailSendService()
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        app.dependency_overrides[get_evidence_request_email_send_service] = (
            lambda: email_service
        )
        client = _employee_client(app)

        response = client.post(
            f"/underwriter/claims/{REQUEST_ID}/evidence-request/draft/send"
        )

        assert response.status_code == 400
        assert (
            response.json()["error"]["code"]
            == "EVIDENCE_REQUEST_DRAFT_INVALID"
        )
        assert email_service.sent == []

    def test_send_evidence_request_draft_persists_provider_failure(self) -> None:
        context = make_context_with_evidence_requirements([])
        context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
            claim_request_id=REQUEST_ID,
            subject="Additional evidence required",
            body="Please send the fire report.",
            recipients=["client@example.test"],
            required_documents=["fire service report"],
        )
        service = FakeCaseContextService(context)
        email_service = FakeEmailSendService(
            status="FAILED",
            error_message="SMTP failed",
        )
        app = create_app()
        app.dependency_overrides[get_case_context_service] = lambda: service
        app.dependency_overrides[get_evidence_request_draft_service] = (
            lambda: EvidenceRequestDraftService()
        )
        app.dependency_overrides[get_evidence_request_email_send_service] = (
            lambda: email_service
        )
        client = _employee_client(app)

        response = client.post(
            f"/underwriter/claims/{REQUEST_ID}/evidence-request/draft/send"
        )

        payload = response.json()
        draft = context.generated_outputs.evidence_request_draft
        assert response.status_code == 502
        assert payload["error"]["code"] == "EVIDENCE_REQUEST_EMAIL_FAILED"
        assert draft is not None
        assert draft.status == "draft"
        assert draft.send_status == "failed"
        assert draft.send_error_message == "SMTP failed"
        assert draft.email_message_id is not None

    def test_receive_claim_evidence_records_metadata_and_refreshes(self) -> None:
        context = make_context_with_evidence_requirements([])
        claim_service = FakeClaimRequestService()
        case_context_service = FakeCaseContextService(context)
        evidence_service = make_evidence_ingestion_service(
            claim_service,
            case_context_service,
        )
        refresh_workflow = FakeEvidenceRefreshWorkflowSuccess(context)
        app = create_app()
        app.dependency_overrides[get_claim_evidence_ingestion_service] = (
            lambda: evidence_service
        )
        app.dependency_overrides[get_evidence_refresh_workflow] = (
            lambda: refresh_workflow
        )
        client = _employee_client(app)

        response = client.post(
            f"/internal/claims/{REQUEST_ID}/evidence",
            headers=_internal_headers(),
            json={
                "evidence_request_id": "evidence-request-1",
                "sender_email": "client@example.test",
                "message_body": "Attached is the report.",
                "attachments": [
                    {
                        "filename": "fire-service-report.pdf",
                        "storage_key": "s3://claims/fire-service-report.pdf",
                        "content_type": "application/pdf",
                    }
                ],
            },
        )

        payload = response.json()
        assert response.status_code == 200
        assert payload["evidence_received"] is True
        assert payload["refresh_status"] == "completed"
        assert payload["coverage_assessment_reran"] is False
        assert payload["received_evidence_count"] == 1
        assert refresh_workflow.request_id == REQUEST_ID
        assert refresh_workflow.claim_fact_updates == {}
        evidence = context.reference_data.received_evidence[0]
        assert evidence.sender_email == "client@example.test"
        assert evidence.attachments[0].filename == "fire-service-report.pdf"
        assert (
            context.reference_data.external_reference_data[
                "evidence_request_events"
            ][0]["status"]
            == "evidence_received"
        )
        assert case_context_service.saved_context is context

    def test_receive_claim_evidence_rejects_missing_internal_key(self) -> None:
        os.environ["UNDERWRIGHT_INTERNAL_API_KEY"] = "test-internal-key"
        app = create_app()
        client = _employee_client(app)

        response = client.post(
            f"/internal/claims/{REQUEST_ID}/evidence",
            json={"sender_email": "client@example.test"},
        )

        assert response.status_code == 401

    def test_receive_claim_evidence_rejects_wrong_internal_key(self) -> None:
        os.environ["UNDERWRIGHT_INTERNAL_API_KEY"] = "test-internal-key"
        app = create_app()
        client = _employee_client(app)

        response = client.post(
            f"/internal/claims/{REQUEST_ID}/evidence",
            headers={"X-Underwright-Internal-Key": "wrong-key"},
            json={"sender_email": "client@example.test"},
        )

        assert response.status_code == 403

    def test_receive_claim_evidence_unknown_claim_returns_404(self) -> None:
        context = make_context_with_evidence_requirements([])
        claim_service = FakeClaimRequestService()
        case_context_service = FakeCaseContextService(context)
        evidence_service = make_evidence_ingestion_service(
            claim_service,
            case_context_service,
        )
        refresh_workflow = FakeEvidenceRefreshWorkflowSuccess(context)
        app = create_app()
        app.dependency_overrides[get_claim_evidence_ingestion_service] = (
            lambda: evidence_service
        )
        app.dependency_overrides[get_evidence_refresh_workflow] = (
            lambda: refresh_workflow
        )
        client = _employee_client(app)

        response = client.post(
            "/internal/claims/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/evidence",
            headers=_internal_headers(),
            json={
                "sender_email": "client@example.test",
                "attachments": [
                    {
                        "filename": "fire-service-report.pdf",
                        "storage_key": "s3://claims/fire-service-report.pdf",
                    }
                ],
            },
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CLAIM_REQUEST_NOT_FOUND"
        assert context.reference_data.received_evidence == []
        assert refresh_workflow.request_id is None


def make_context_with_evidence_requirements(
    required_evidence: list[EvidenceRequirement],
) -> ClaimCaseContext:
    context = ClaimCaseContext(source_inputs={"request_id": REQUEST_ID})
    context.case_metadata.case_id = CASE_ID
    context.case_metadata.status = "in_review"
    context.reference_data.claim_request = make_claim_request().model_dump(mode="json")
    context.generated_outputs.evidence_requirements = EvidenceRequirementResult(
        required_evidence=required_evidence,
        suggested_next_action=(
            "request_evidence" if required_evidence else "underwriter_review"
        ),
    )
    return context


def make_evidence_ingestion_service(
    claim_service: FakeClaimRequestService,
    case_context_service: FakeCaseContextService,
):
    from underwright.application.services.case_context_service import (
        CaseContextFactory,
    )
    from underwright.application.services.claim_data_service import ClaimDataService
    from underwright.application.services.claim_evidence_ingestion_service import (
        ClaimEvidenceIngestionService,
    )

    return ClaimEvidenceIngestionService(
        claim_request_service=claim_service,
        claim_data_service=ClaimDataService(claim_service),
        case_context_factory=CaseContextFactory(),
        case_context_service=case_context_service,
    )


def make_claim_review_query_service(
    context,
    *,
    raise_context_not_found: bool = False,
):
    return ClaimReviewQueryService(
        claim_request_service=FakeClaimRequestService(),
        case_context_service=FakeCaseContextService(
            context,
            raise_not_found=raise_context_not_found,
        ),
    )


if __name__ == "__main__":
    unittest.main()
