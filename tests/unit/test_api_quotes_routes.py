from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from underwright.api.dependencies import (
    get_contract_document_generation_service,
    get_current_auth_user,
    get_current_client_user,
    get_current_employee_user,
    get_customer_profile_service,
    get_generated_document_pdf_service,
    get_generated_document_query_service,
    get_quote_acceptance_service,
    get_quote_request_service,
    get_quote_to_contract_conversion_service,
    get_quote_workflow,
)
from underwright.api.main import create_app
from underwright.application.services.customer_profile_service import (
    CustomerProfileIncompleteError,
)
from underwright.application.services.quote_acceptance_service import (
    QuoteAcceptanceNotFoundError,
)
from underwright.domain.auth_user import AuthUser
from underwright.domain.customer_profile import (
    CustomerAddressProfile,
    CustomerProfileReadModel,
)
from underwright.domain.module_result import ModuleResult
from underwright.domain.quote_acceptance import QuoteAcceptance, QuoteAcceptanceInput
from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.quote_decision_audit import QuoteDecisionAuditRecord
from underwright.domain.quote_document import QuoteDocument
from underwright.domain.quote_request import QuoteRequest

REQUEST_ID = UUID("80000000-0000-0000-0000-000000000001")
CASE_ID = UUID("90000000-0000-0000-0000-000000000001")


class _FakeQuoteRequestService:
    def __init__(self) -> None:
        self.created_request: QuoteRequest | None = None
        self.updated_status: tuple[UUID, str] | None = None
        self.decision_update: dict[str, object] | None = None
        self.audit_records: list[QuoteDecisionAuditRecord] = []
        self.current_status = "underwriter_review"

    def create_quote_request(self, request: QuoteRequest) -> QuoteRequest:
        self.created_request = request
        return request

    def save_step_updates(self, request: QuoteRequest) -> QuoteRequest:
        return request

    def list_client_quote_requests(
        self,
        client_id: int | str | UUID,
    ) -> list[QuoteRequest]:
        return [
            QuoteRequest(
                request_id=REQUEST_ID,
                client_id=client_id,
                request_status="draft",
            )
        ]

    def list_quote_requests_by_status(self, request_status: str) -> list[QuoteRequest]:
        return [
            QuoteRequest(
                request_id=REQUEST_ID,
                client_id=1001,
                request_status=request_status,
            )
        ]

    def get_quote_request_detail(self, request_id: UUID) -> QuoteRequest:
        return QuoteRequest(
            request_id=request_id,
            client_id=1001,
            request_status=self.current_status,
            client_data={"full_name": "Ion Popescu"},
            asset_data={"asset_type": "apartment"},
        )

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> QuoteRequest:
        self.updated_status = (request_id, request_status)
        self.current_status = request_status
        return QuoteRequest(
            request_id=request_id,
            client_id=1001,
            request_status=request_status,
        )

    def update_underwriter_decision(
        self,
        request_id: UUID,
        request_status: str,
        *,
        reason: str | None,
        user: AuthUser,
    ) -> QuoteRequest:
        self.updated_status = (request_id, request_status)
        self.current_status = request_status
        self.decision_update = {
            "request_id": request_id,
            "request_status": request_status,
            "reason": reason,
            "user": user,
        }
        record = QuoteDecisionAuditRecord(
            id=len(self.audit_records) + 1,
            quote_request_id=request_id,
            previous_status="underwriter_review",
            decision_status=request_status,
            reason=reason,
            decided_by_auth_user_id=user.id,
            decided_by_name=user.full_name,
            decided_by_email=user.email,
        )
        self.audit_records.insert(0, record)
        return QuoteRequest(
            request_id=request_id,
            client_id=1001,
            request_status=request_status,
        )

    def list_decision_audit(
        self,
        request_id: UUID,
    ) -> list[QuoteDecisionAuditRecord]:
        return [
            record
            for record in self.audit_records
            if record.quote_request_id == request_id
        ]


class _FakePricingQuoteRequestService(_FakeQuoteRequestService):
    def create_quote_request(self, request: QuoteRequest) -> QuoteRequest:
        self.created_request = request
        request.pricing_preview.update(
            {
                "pricing": {
                    "source": "backend",
                    "finalPremium": 513,
                },
                "risk_assessment": {
                    "source": "backend",
                    "score": 100,
                    "level": "Low",
                },
            }
        )
        return request


class _FakeQuoteWorkflowSuccess:
    def run(self, request_id: UUID, template_code: str):
        context = QuoteCaseContext()
        context.case_metadata.case_id = CASE_ID
        return SimpleNamespace(
            case_context=context,
            quote_document=QuoteDocument(
                id=77,
                quote_request_id=request_id,
                template_id=1,
                generation_status="success",
                rendered_text="Unsigned quote",
            ),
            module_results=[
                ModuleResult(
                    module_name="QuotePayloadBuilder",
                    status="success",
                    summary="Built payload.",
                )
            ],
            status="underwriter_review",
        )


class _FakeQuoteWorkflowFailed:
    def run(self, request_id: UUID, template_code: str):
        context = QuoteCaseContext()
        context.case_metadata.case_id = CASE_ID
        return SimpleNamespace(
            case_context=context,
            quote_document=None,
            module_results=[
                ModuleResult(
                    module_name="QuoteDocumentGenerationModule",
                    status="failed",
                    summary="Generation failed.",
                )
            ],
            status="failed",
        )


class _FakeClientQuoteSubmissionWorkflow:
    def __init__(self, service: _FakeQuoteRequestService, status: str) -> None:
        self.service = service
        self.status = status
        self.ran: tuple[UUID, str] | None = None

    def run(self, request_id: UUID, template_code: str):
        self.ran = (request_id, template_code)
        self.service.update_request_status(request_id, self.status)
        context = QuoteCaseContext()
        context.case_metadata.case_id = CASE_ID
        return SimpleNamespace(
            case_context=context,
            quote_document=(
                QuoteDocument(
                    id=77,
                    quote_request_id=request_id,
                    template_id=1,
                    generation_status="success",
                    rendered_text="Unsigned quote",
                )
                if self.status == "auto_accepted"
                else None
            ),
            module_results=[],
            status=self.status,
        )


class _FakeContractConversionService:
    def __init__(self) -> None:
        self.published_quote_id: UUID | None = None
        self.published_document: QuoteDocument | None = None

    def latest_successful_quote_document(self, quote_id: UUID) -> QuoteDocument | None:
        return None

    def publish_approved_quote(
        self,
        quote_id: UUID,
        *,
        quote_document: QuoteDocument | None = None,
    ):
        self.published_quote_id = quote_id
        self.published_document = quote_document
        return SimpleNamespace(
            result="created",
            contract_id=REQUEST_ID,
            contract=SimpleNamespace(id=REQUEST_ID),
        )


class _FakeGeneratedDocumentQueryService:
    def get_latest_for_contract(self, contract_id: UUID):
        return None


class _FakeContractDocumentGenerationService:
    def __init__(self) -> None:
        self.generated_contract_id: UUID | None = None
        self.generated_template_code: str | None = None

    def generate(self, contract_id: UUID, template_code: str | None = None):
        self.generated_contract_id = contract_id
        self.generated_template_code = template_code
        return SimpleNamespace(
            status="success",
            document=SimpleNamespace(id=1),
            validation=SimpleNamespace(model_dump=lambda mode: {}),
            module_results=[],
        )


class _FakeGeneratedDocumentPdfService:
    def __init__(self) -> None:
        self.created_document_ids: list[int] = []

    def create_pdf(self, document_id: int):
        self.created_document_ids.append(document_id)
        return SimpleNamespace(
            status="ready",
            artifact=SimpleNamespace(document_id=document_id),
            blocking_errors=[],
        )


class _CompleteProfileService:
    def ensure_complete_profile(self, user: AuthUser):
        return CustomerProfileReadModel(
            customer_id=user.client_id,
            status="complete",
            requires_customer_profile_completion=False,
            type="individual",
            full_name="Backend Profile",
            national_id="1800101223344",
            company_id=None,
            email="backend.profile@example.test",
            phone="+40700000123",
            address=CustomerAddressProfile(
                country="Romania",
                county="Bucuresti",
                city="Bucuresti",
                street="Calea Backend",
                number="12",
                postal_code="010101",
            ),
        )


class _IncompleteProfileService:
    def ensure_complete_profile(self, user: AuthUser):
        raise CustomerProfileIncompleteError(
            missing_fields=["national_id"],
            status="pending_customer_link",
        )


class _FakeQuoteAcceptanceService:
    def __init__(self, acceptance: QuoteAcceptance | None = None) -> None:
        self.acceptance = acceptance or _quote_acceptance()
        self.accepted_input: QuoteAcceptanceInput | None = None
        self.accepted_user: AuthUser | None = None

    def get_acceptance(self, quote_id: UUID) -> QuoteAcceptance:
        if self.acceptance.quote_request_id != quote_id:
            raise QuoteAcceptanceNotFoundError("Quote acceptance not found.")
        return self.acceptance

    def get_acceptance_for_client(
        self,
        *,
        quote_id: UUID,
        user: AuthUser,
    ) -> QuoteAcceptance:
        if self.acceptance.quote_request_id != quote_id:
            raise QuoteAcceptanceNotFoundError("Quote acceptance not found.")
        return self.acceptance

    def accept_quote_for_client(
        self,
        *,
        quote_id: UUID,
        user: AuthUser,
        signer_input: QuoteAcceptanceInput,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> QuoteAcceptance:
        self.accepted_input = signer_input
        self.accepted_user = user
        self.acceptance = _quote_acceptance(
            quote_id=quote_id,
            signer_name=signer_input.signer_name,
            signer_email=signer_input.signer_email,
            signer_role=signer_input.signer_role,
            acceptance_statement=signer_input.acceptance_statement,
        )
        return self.acceptance


def _client_user(client_id: int | None = 1001) -> AuthUser:
    return AuthUser(
        id=1,
        email="client@example.com",
        password_hash="hash",
        role="client",
        full_name="Ion Popescu",
        phone="0712345678",
        client_id=client_id,
    )


def _employee_user() -> AuthUser:
    return AuthUser(
        id=2,
        email="underwriter@example.test",
        password_hash="hash",
        role="underwriter",
        full_name="Under Writer",
    )


def _employee_client(app) -> TestClient:
    app.dependency_overrides[get_current_employee_user] = lambda: _employee_user()
    return TestClient(app)


def _client_role_client(app) -> TestClient:
    app.dependency_overrides[get_current_auth_user] = lambda: _client_user()
    return TestClient(app)


class QuoteRoutesTestCase(unittest.TestCase):
    def test_global_quote_routes_require_employee_role(self) -> None:
        app = create_app()
        app.dependency_overrides[get_quote_request_service] = lambda: (
            _FakeQuoteRequestService()
        )

        assert TestClient(app).get(f"/quotes/{REQUEST_ID}").status_code == 401
        assert _client_role_client(app).get(f"/quotes/{REQUEST_ID}").status_code == 403
        assert _employee_client(app).get(f"/quotes/{REQUEST_ID}").status_code == 200

    def test_create_quote_request_uses_service(self) -> None:
        app = create_app()
        service = _FakeQuoteRequestService()
        app.dependency_overrides[get_quote_request_service] = lambda: service
        client = _employee_client(app)

        response = client.post(
            "/quotes",
            json={
                "request_id": str(REQUEST_ID),
                "client_id": 1001,
                "client_data": {"full_name": "Ion Popescu"},
                "asset_data": {"asset_type": "apartment"},
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(service.created_request)
        self.assertEqual(response.json()["request_id"], str(REQUEST_ID))

    def test_create_quote_response_exposes_backend_pricing_and_risk(self) -> None:
        app = create_app()
        service = _FakePricingQuoteRequestService()
        app.dependency_overrides[get_quote_request_service] = lambda: service
        client = _employee_client(app)

        response = client.post(
            "/quotes",
            json={
                "request_id": str(REQUEST_ID),
                "client_id": 1001,
                "client_data": {"full_name": "Ion Popescu"},
                "asset_data": {"asset_type": "apartment"},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pricing"]["source"], "backend")
        self.assertEqual(payload["pricing"]["finalPremium"], 513)
        self.assertEqual(payload["risk"]["source"], "backend")

    def test_list_client_quote_requests_uses_service(self) -> None:
        app = create_app()
        service = _FakeQuoteRequestService()
        app.dependency_overrides[get_quote_request_service] = lambda: service
        client = _employee_client(app)

        response = client.get("/quotes/client", params={"client_id": 1001})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["request_id"], str(REQUEST_ID))

    def test_create_my_quote_requires_complete_customer_profile(self) -> None:
        app = create_app()
        service = _FakeQuoteRequestService()
        app.dependency_overrides[get_quote_request_service] = lambda: service
        app.dependency_overrides[get_current_client_user] = lambda: _client_user(None)
        app.dependency_overrides[get_customer_profile_service] = lambda: (
            _IncompleteProfileService()
        )
        client = _employee_client(app)

        response = client.post(
            "/me/quotes",
            json={
                "client_data": {"full_name": "Ion Popescu"},
                "asset_data": {"asset_type": "apartment"},
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["code"], "CUSTOMER_PROFILE_INCOMPLETE"
        )
        self.assertIsNone(service.created_request)

    def test_create_my_quote_uses_authenticated_client_id(self) -> None:
        app = create_app()
        service = _FakeQuoteRequestService()
        workflow = _FakeClientQuoteSubmissionWorkflow(service, "auto_accepted")
        conversion_service = _FakeContractConversionService()
        document_service = _FakeContractDocumentGenerationService()
        pdf_service = _FakeGeneratedDocumentPdfService()
        app.dependency_overrides[get_quote_request_service] = lambda: service
        app.dependency_overrides[get_quote_workflow] = lambda: workflow
        app.dependency_overrides[get_quote_to_contract_conversion_service] = lambda: (
            conversion_service
        )
        app.dependency_overrides[get_generated_document_query_service] = lambda: (
            _FakeGeneratedDocumentQueryService()
        )
        app.dependency_overrides[get_contract_document_generation_service] = lambda: (
            document_service
        )
        app.dependency_overrides[get_generated_document_pdf_service] = lambda: (
            pdf_service
        )
        app.dependency_overrides[get_current_client_user] = lambda: _client_user(1001)
        app.dependency_overrides[get_customer_profile_service] = lambda: (
            _CompleteProfileService()
        )
        client = _employee_client(app)

        response = client.post(
            "/me/quotes",
            json={
                "client_data": {
                    "full_name": "Submitted Override",
                    "email": "submitted@example.test",
                    "phone": "+40000000000",
                    "national_id": "submitted-national-id",
                    "address": "Submitted address",
                },
                "asset_data": {"asset_type": "apartment"},
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(service.created_request)
        self.assertEqual(service.created_request.client_id, 1001)
        self.assertEqual(
            service.created_request.client_data["full_name"],
            "Backend Profile",
        )
        self.assertEqual(
            service.created_request.client_data["email"],
            "backend.profile@example.test",
        )
        self.assertEqual(
            service.created_request.client_data["national_id"],
            "1800101223344",
        )
        self.assertEqual(
            service.created_request.client_data["address"]["full_text"],
            "Calea Backend 12, Bucuresti, Bucuresti, Romania, 010101",
        )
        self.assertEqual(
            workflow.ran,
            (service.created_request.request_id, "PAD_STANDARD_RO"),
        )
        self.assertEqual(
            conversion_service.published_quote_id,
            service.created_request.request_id,
        )
        self.assertEqual(document_service.generated_contract_id, REQUEST_ID)
        self.assertEqual(document_service.generated_template_code, "PAD_PROPERTY_RO")
        self.assertEqual(pdf_service.created_document_ids, [1])
        self.assertEqual(response.json()["request_status"], "auto_accepted")

    def test_generate_quote_document_success_response_shape(self) -> None:
        app = create_app()
        app.dependency_overrides[get_quote_workflow] = lambda: (
            _FakeQuoteWorkflowSuccess()
        )
        client = _employee_client(app)

        response = client.post(
            f"/quotes/{REQUEST_ID}/generate",
            json={"template_code": "PAD_STANDARD_RO"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["case_id"], str(CASE_ID))
        self.assertEqual(payload["status"], "underwriter_review")
        self.assertEqual(payload["quote_document_id"], 77)
        self.assertEqual(
            payload["module_results"][0]["module_name"], "QuotePayloadBuilder"
        )

    def test_generate_quote_document_failure_response_shape(self) -> None:
        app = create_app()
        app.dependency_overrides[get_quote_workflow] = lambda: (
            _FakeQuoteWorkflowFailed()
        )
        client = _employee_client(app)

        response = client.post(
            f"/quotes/{REQUEST_ID}/generate",
            json={"template_code": "PAD_STANDARD_RO"},
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "QUOTE_WORKFLOW_FAILED")
        self.assertEqual(payload["status"], "failed")

    def test_underwriter_decision_updates_quote_status_and_audit(self) -> None:
        app = create_app()
        service = _FakeQuoteRequestService()
        conversion_service = _FakeContractConversionService()
        document_service = _FakeContractDocumentGenerationService()
        pdf_service = _FakeGeneratedDocumentPdfService()
        app.dependency_overrides[get_quote_request_service] = lambda: service
        app.dependency_overrides[get_quote_workflow] = lambda: (
            _FakeQuoteWorkflowSuccess()
        )
        app.dependency_overrides[get_quote_to_contract_conversion_service] = lambda: (
            conversion_service
        )
        app.dependency_overrides[get_generated_document_query_service] = lambda: (
            _FakeGeneratedDocumentQueryService()
        )
        app.dependency_overrides[get_contract_document_generation_service] = lambda: (
            document_service
        )
        app.dependency_overrides[get_generated_document_pdf_service] = lambda: (
            pdf_service
        )
        client = _employee_client(app)

        response = client.patch(
            f"/underwriter/quotes/{REQUEST_ID}/decision",
            json={"status": "approved", "reason": "Risk is acceptable."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.updated_status, (REQUEST_ID, "approved"))
        assert service.decision_update is not None
        self.assertEqual(service.decision_update["reason"], "Risk is acceptable.")
        self.assertEqual(
            service.decision_update["user"],
            _employee_user(),
        )
        self.assertEqual(conversion_service.published_quote_id, REQUEST_ID)
        self.assertIsNotNone(conversion_service.published_document)
        self.assertEqual(document_service.generated_contract_id, REQUEST_ID)
        self.assertEqual(document_service.generated_template_code, "PAD_PROPERTY_RO")
        self.assertEqual(pdf_service.created_document_ids, [1])
        self.assertEqual(response.json()["request_status"], "approved")

    def test_employee_can_read_underwriter_decision_audit(self) -> None:
        app = create_app()
        service = _FakeQuoteRequestService()
        service.audit_records = [
            QuoteDecisionAuditRecord(
                id=1,
                quote_request_id=REQUEST_ID,
                previous_status="underwriter_review",
                decision_status="disapproved",
                reason="Roof condition is outside appetite.",
                decided_by_auth_user_id=2,
                decided_by_name="Under Writer",
                decided_by_email="underwriter@example.test",
            )
        ]
        app.dependency_overrides[get_quote_request_service] = lambda: service
        client = _employee_client(app)

        response = client.get(f"/underwriter/quotes/{REQUEST_ID}/decision-audit")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["decision_status"], "disapproved")
        self.assertEqual(
            response.json()[0]["reason"], "Roof condition is outside appetite."
        )

    def test_client_cannot_read_underwriter_decision_audit(self) -> None:
        app = create_app()
        app.dependency_overrides[get_quote_request_service] = lambda: (
            _FakeQuoteRequestService()
        )

        response = _client_role_client(app).get(
            f"/underwriter/quotes/{REQUEST_ID}/decision-audit"
        )

        self.assertEqual(response.status_code, 403)

    def test_client_quote_acceptance_records_signer_provenance(self) -> None:
        app = create_app()
        service = _FakeQuoteAcceptanceService()
        app.dependency_overrides[get_current_client_user] = lambda: _client_user(1001)
        app.dependency_overrides[get_quote_acceptance_service] = lambda: service
        client = TestClient(app)

        response = client.post(
            f"/me/quotes/{REQUEST_ID}/acceptance",
            json={
                "signer_name": "Ion Popescu",
                "signer_email": "ion@example.test",
                "signer_role": "policyholder",
                "acceptance_statement": "I accept this quote.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(service.accepted_input)
        self.assertEqual(service.accepted_input.signer_name, "Ion Popescu")
        self.assertEqual(response.json()["quote_document_id"], 77)

    def test_client_quote_acceptance_requires_client_role(self) -> None:
        app = create_app()
        app.dependency_overrides[get_quote_acceptance_service] = lambda: (
            _FakeQuoteAcceptanceService()
        )

        unauthenticated = TestClient(app).post(
            f"/me/quotes/{REQUEST_ID}/acceptance",
            json={
                "signer_name": "Ion Popescu",
                "signer_email": "ion@example.test",
                "acceptance_statement": "I accept this quote.",
            },
        )
        self.assertEqual(unauthenticated.status_code, 401)

        app.dependency_overrides[get_current_auth_user] = lambda: _employee_user()
        forbidden = TestClient(app).post(
            f"/me/quotes/{REQUEST_ID}/acceptance",
            json={
                "signer_name": "Ion Popescu",
                "signer_email": "ion@example.test",
                "acceptance_statement": "I accept this quote.",
            },
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_client_can_read_own_quote_acceptance(self) -> None:
        app = create_app()
        app.dependency_overrides[get_current_client_user] = lambda: _client_user(1001)
        app.dependency_overrides[get_quote_acceptance_service] = lambda: (
            _FakeQuoteAcceptanceService()
        )
        client = TestClient(app)

        response = client.get(f"/me/quotes/{REQUEST_ID}/acceptance")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["signer_name"], "Ion Popescu")

    def test_client_patch_cannot_fake_quote_acceptance_status(self) -> None:
        app = create_app()
        service = _FakeQuoteRequestService()
        app.dependency_overrides[get_quote_request_service] = lambda: service
        app.dependency_overrides[get_current_client_user] = lambda: _client_user(1001)
        app.dependency_overrides[get_customer_profile_service] = lambda: (
            _CompleteProfileService()
        )
        client = TestClient(app)

        response = client.patch(
            f"/me/quotes/{REQUEST_ID}",
            json={"request_status": "auto_accepted"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"],
            "QUOTE_ACCEPTANCE_ENDPOINT_REQUIRED",
        )

    def test_employee_can_read_quote_acceptance(self) -> None:
        app = create_app()
        app.dependency_overrides[get_quote_acceptance_service] = lambda: (
            _FakeQuoteAcceptanceService()
        )
        client = _employee_client(app)

        response = client.get(f"/quotes/{REQUEST_ID}/acceptance")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["quote_content_hash"], "quote-hash")

    def test_client_cannot_read_global_quote_acceptance(self) -> None:
        app = create_app()
        app.dependency_overrides[get_quote_acceptance_service] = lambda: (
            _FakeQuoteAcceptanceService()
        )

        response = _client_role_client(app).get(f"/quotes/{REQUEST_ID}/acceptance")

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()


def _quote_acceptance(
    *,
    quote_id: UUID = REQUEST_ID,
    signer_name: str = "Ion Popescu",
    signer_email: str = "ion@example.test",
    signer_role: str | None = "policyholder",
    acceptance_statement: str = "I accept this quote.",
) -> QuoteAcceptance:
    return QuoteAcceptance(
        id=1,
        quote_request_id=quote_id,
        quote_document_id=77,
        accepted_by_auth_user_id=1,
        accepted_by_customer_id=1001,
        signer_name=signer_name,
        signer_email=signer_email,
        signer_role=signer_role,
        accepted_at="2026-05-14T10:00:00Z",
        acceptance_method="client_portal",
        acceptance_statement=acceptance_statement,
        quote_content_hash="quote-hash",
        created_at="2026-05-14T10:00:00Z",
    )
