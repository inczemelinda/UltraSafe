from __future__ import annotations

from datetime import datetime, timezone
import unittest
from uuid import UUID

from underwright.application.modules.quote_approval_module import QuoteApprovalModule
from underwright.application.modules.quote_data_completion_module import (
    QuoteDataCompletionModule,
)
from underwright.application.modules.quote_document_generation_module import (
    QuoteDocumentGenerationModule,
)
from underwright.application.modules.quote_payload_builder import QuotePayloadBuilder
from underwright.application.modules.policy_rules_module import PolicyRulesModule
from underwright.application.modules.pricing_calculation_module import (
    PricingCalculationModule,
)
from underwright.application.services.audit_service import AuditService
from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.quote_data_service import QuoteDataService
from underwright.application.services.quote_request_service import QuoteRequestService
from underwright.application.services.template_service import TemplateService
from underwright.application.workflows.quote_workflow import QuoteWorkflow
from underwright.domain.models import Address, Insurer, InsurerContextSource, Template
from underwright.domain.quote_decision_audit import (
    QuoteDecisionAuditCreate,
    QuoteDecisionAuditRecord,
)
from underwright.domain.quote_document import QuoteDocument
from underwright.domain.quote_request import QuoteRequest
from underwright.infrastructure.templates.renderer import PadTemplateRenderer

REQUEST_ID = UUID("80000000-0000-0000-0000-000000000001")


class FakeQuoteRequestRepository:
    def __init__(self, quote_request: QuoteRequest) -> None:
        self.quote_request = quote_request
        self.saved_request: QuoteRequest | None = None
        self.failed_request_id: UUID | None = None
        self.decision_audits: list[QuoteDecisionAuditRecord] = []

    def create_request(self, request: QuoteRequest) -> QuoteRequest:
        self.quote_request = request
        return request

    def update_request(self, request: QuoteRequest) -> QuoteRequest:
        self.saved_request = request
        self.quote_request = request
        return request

    def get_request_by_id(self, request_id: UUID) -> QuoteRequest:
        if request_id != self.quote_request.request_id:
            raise ValueError("QuoteRequest not found")
        return self.quote_request

    def list_requests_by_client_id(self, client_id) -> list[QuoteRequest]:
        return [self.quote_request]

    def list_requests_by_status(self, request_status: str) -> list[QuoteRequest]:
        return [self.quote_request]

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> QuoteRequest:
        self.failed_request_id = request_id
        self.quote_request.request_status = request_status
        return self.quote_request

    def create_decision_audit(
        self,
        record: QuoteDecisionAuditCreate,
    ) -> QuoteDecisionAuditRecord:
        saved = QuoteDecisionAuditRecord(
            id=len(self.decision_audits) + 1,
            **record.model_dump(),
        )
        self.decision_audits.insert(0, saved)
        return saved


class FakeTemplateRepository:
    def get_active_template(self, template_code: str) -> Template:
        return Template(
            id=7,
            template_code=template_code,
            name="Quote Template",
            version="1.0",
            document_type="insurance_quote",
            is_active=True,
            content=(
                "Quote {{ quote_meta.quote_id }} for "
                "{{ parties.insured.full_name }}: {{ pricing.estimated_premium }}"
            ),
            created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )


class FakeQuoteDocumentRepository:
    def __init__(self) -> None:
        self.saved_document: QuoteDocument | None = None

    def save(self, document: QuoteDocument) -> QuoteDocument:
        self.saved_document = document.model_copy(update={"id": 501})
        return self.saved_document


class FakeCaseContextRepository:
    def __init__(self) -> None:
        self.saved_context = None

    def save_case_context(self, context):
        self.saved_context = context
        return context

    def get_case_context_by_case_id(self, case_id):
        return self.saved_context


class FakeDefaultInsurerProvider:
    def get_default_insurer_context_source(self) -> InsurerContextSource:
        return InsurerContextSource(
            insurer=Insurer(
                id=42,
                name="Backend Mutual SA",
                company_id="RO-BACKEND",
                representative_name="Elena Backend",
                representative_role="Chief Underwriter",
                address_id=9,
            ),
            insurer_address=Address(
                id=9,
                country="Romania",
                county="Bucuresti",
                city="Bucuresti",
                street="Bd. Backend",
                number="10",
                postal_code="010010",
                full_text="Bd. Backend 10, Bucuresti",
            ),
        )


def complete_quote_request() -> QuoteRequest:
    return QuoteRequest(
        request_id=REQUEST_ID,
        client_id=1001,
        client_data={
            "full_name": "Ion Popescu",
            "email": "ion@example.test",
            "phone": "+40700000000",
        },
        asset_data={
            "asset_type": "apartment",
            "usage_type": "residential",
            "construction_type": "concrete",
            "year_built": 1998,
            "area_sqm": 70,
            "declared_value": 300000,
            "occupancy": "owner",
        },
        pricing_preview={"currency": "RON", "estimated_premium": 1200},
    )


def build_workflow(
    quote_request: QuoteRequest,
) -> tuple[QuoteWorkflow, FakeQuoteRequestRepository, FakeQuoteDocumentRepository]:
    quote_repository = FakeQuoteRequestRepository(quote_request)
    quote_request_service = QuoteRequestService(quote_repository)
    template_service = TemplateService(
        template_repository=FakeTemplateRepository(),
        template_renderer=PadTemplateRenderer(),
    )
    quote_document_repository = FakeQuoteDocumentRepository()
    case_context_repository = FakeCaseContextRepository()
    audit_service = AuditService()
    workflow = QuoteWorkflow(
        quote_request_service=quote_request_service,
        quote_data_service=QuoteDataService(quote_request_service),
        template_service=template_service,
        quote_document_repository=quote_document_repository,
        quote_data_completion_module=QuoteDataCompletionModule(),
        policy_rules_module=PolicyRulesModule(),
        pricing_calculation_module=PricingCalculationModule(),
        quote_approval_module=QuoteApprovalModule(),
        quote_payload_builder=QuotePayloadBuilder(),
        quote_document_generation_module=QuoteDocumentGenerationModule(
            template_service=template_service,
            audit_service=audit_service,
        ),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(case_context_repository),
        audit_service=audit_service,
    )
    return workflow, quote_repository, quote_document_repository


class QuoteWorkflowTestCase(unittest.TestCase):
    def test_quote_payload_uses_default_insurer_from_backend_provider(self) -> None:
        quote_request = complete_quote_request()
        context = CaseContextFactory().create_quote_case_context_from_request_id(
            REQUEST_ID,
            client_id=quote_request.client_id,
        )
        quote_request_service = QuoteRequestService(
            FakeQuoteRequestRepository(quote_request)
        )
        QuoteDataService(quote_request_service).attach_quote_request(
            context,
            quote_request,
        )

        result = QuotePayloadBuilder(
            default_insurer_provider=FakeDefaultInsurerProvider(),
        ).build(context)

        self.assertEqual(result.status, "success")
        insurer = context.domain_payload.quote_generation_payload["parties"][
            "insurer"
        ]
        self.assertEqual(insurer["name"], "Backend Mutual SA")
        self.assertEqual(insurer["company_id"], "RO-BACKEND")
        self.assertEqual(insurer["address"], "Bd. Backend 10, Bucuresti")
        self.assertEqual(insurer["representative"]["name"], "Elena Backend")

    def test_generates_unsigned_quote_document_and_auto_accepts_standard_quote(self) -> None:
        workflow, quote_repository, quote_document_repository = build_workflow(
            complete_quote_request()
        )

        result = workflow.run(REQUEST_ID, "QUOTE_STANDARD_RO")

        self.assertEqual(result.status, "auto_accepted")
        self.assertIsNotNone(result.quote_document)
        self.assertIs(result.quote_document, quote_document_repository.saved_document)
        self.assertEqual(quote_repository.saved_request.request_status, "auto_accepted")
        self.assertEqual(result.quote_document.quote_request_id, REQUEST_ID)
        self.assertIn("Ion Popescu", result.quote_document.rendered_text)
        self.assertEqual(
            result.case_context.generated_outputs.quote_document.quote_document_reference[
                "id"
            ],
            501,
        )
        self.assertIn(
            "quote_generation_payload",
            result.quote_document.rendered_json,
        )
        self.assertEqual(
            result.quote_document.rendered_json["quote_generation_payload"][
                "coverage"
            ],
            {
                "building_sum_insured": 300000.0,
                "contents_sum_insured": 300000.0,
                "total_sum_insured": 300000.0,
            },
        )
        self.assertEqual(
            result.case_context.domain_payload.approval_decision["decision_source"],
            "policy_rules_module",
        )
        self.assertEqual(
            result.case_context.domain_payload.rule_outcomes["recommended_actions"],
            ["auto_accept"],
        )
        self.assertIn("pricing_result", quote_repository.saved_request.pricing_preview)

    def test_nonstandard_quote_routes_to_underwriter_review(self) -> None:
        quote_request = complete_quote_request()
        quote_request.asset_data.update(
            {
                "usage_type": "Vacant",
                "construction_type": "Wood",
                "year_built": 1965,
                "previous_claims_count": 6,
            }
        )
        workflow, quote_repository, _quote_document_repository = build_workflow(
            quote_request
        )

        result = workflow.run(REQUEST_ID, "QUOTE_STANDARD_RO")

        self.assertEqual(result.status, "underwriter_review")
        self.assertEqual(
            quote_repository.saved_request.request_status,
            "underwriter_review",
        )
        rule_ids = {
            rule["policy_rule_id"]
            for rule in result.case_context.domain_payload.rule_outcomes[
                "nonstandard_rules"
            ]
        }
        self.assertIn("vacant_property_use", rule_ids)
        self.assertIn("wood_construction", rule_ids)
        self.assertEqual(quote_repository.saved_request.risk["score"], 25)
        self.assertEqual(quote_repository.saved_request.risk["level"], "High")
        self.assertTrue(
            quote_repository.saved_request.risk["requires_manual_review"]
        )

    def test_hard_rule_quote_is_disapproved_and_audited(self) -> None:
        quote_request = complete_quote_request()
        quote_request.client_data["address"] = {
            "country": "Bulgaria",
            "county": "Sofia",
            "city": "Sofia",
            "street": "Test",
            "number": "1",
            "postal_code": "1000",
            "full_text": "Test 1, Sofia, Bulgaria",
        }
        quote_request.asset_data["address"] = quote_request.client_data["address"]
        workflow, quote_repository, _quote_document_repository = build_workflow(
            quote_request
        )

        result = workflow.run(REQUEST_ID, "QUOTE_STANDARD_RO")

        self.assertEqual(result.status, "disapproved")
        self.assertEqual(quote_repository.saved_request.request_status, "disapproved")
        self.assertEqual(len(quote_repository.decision_audits), 1)
        self.assertEqual(
            quote_repository.decision_audits[0].decision_status,
            "disapproved",
        )
        self.assertIn(
            "unsupported_property_country",
            quote_repository.decision_audits[0].reason,
        )

    def test_underwriter_approved_quote_stays_approved_during_generation(self) -> None:
        quote_request = complete_quote_request()
        quote_request.request_status = "approved"
        quote_request.asset_data.update(
            {
                "usage_type": "Vacant",
                "construction_type": "Wood",
                "previous_claims_count": 6,
            }
        )
        workflow, quote_repository, _quote_document_repository = build_workflow(
            quote_request
        )

        result = workflow.run(REQUEST_ID, "QUOTE_STANDARD_RO")

        self.assertEqual(result.status, "approved")
        self.assertEqual(quote_repository.saved_request.request_status, "approved")
        self.assertEqual(
            result.case_context.domain_payload.approval_decision["decision_source"],
            "underwriter_decision",
        )


if __name__ == "__main__":
    unittest.main()
