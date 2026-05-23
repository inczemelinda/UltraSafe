from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from underwright.domain.claim_request import ClaimRequest
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.contract_request import ContractRequest
from underwright.domain.case_context_base import BaseCaseContext
from underwright.domain.contract_case_context import ContractCaseContext
from underwright.domain.email_message import (
    CustomerEmailMessage,
    EmailAttachment,
    EmailMessage,
)
from underwright.domain.module_result import ModuleResult
from underwright.domain.models import (
    ContractContextSource,
    GeneratedDocument,
    InsurerContextSource,
    Template,
)
from underwright.domain.contract_lifecycle import (
    ContractCreationData,
    ContractReadModel,
)
from underwright.domain.contract_decline import ContractDecline, ContractDeclineCreate
from underwright.domain.generated_document_lifecycle import GeneratedDocumentReadModel
from underwright.domain.quote_acceptance import QuoteAcceptance, QuoteAcceptanceCreate
from underwright.domain.quote_decision_audit import (
    QuoteDecisionAuditCreate,
    QuoteDecisionAuditRecord,
)
from underwright.domain.quote_document import QuoteDocument
from underwright.domain.quote_request import QuoteRequest
from underwright.domain.wording import (
    WordingDocument,
    WordingDocumentCreate,
    WordingDocumentVersion,
    WordingDocumentVersionCreate,
)


class ContractSourceQuoteConflictError(RuntimeError):
    """Raised when another request already created a contract for a quote."""

    def __init__(self, quote_request_id: UUID) -> None:
        self.quote_request_id = quote_request_id
        super().__init__(
            f"Contract already exists for source quote {quote_request_id}"
        )


# infrastructure/postgres.py
class ContractRepository(Protocol):
    def get_contract_context_source(
        self, contract_id: UUID
    ) -> ContractContextSource: ...

    def list_contracts(self) -> list[ContractReadModel]: ...

    def get_contract_by_id(self, contract_id: UUID) -> ContractReadModel: ...

    def list_claimable_contracts_by_client_id(
        self,
        client_id: int | str | UUID,
        claimable_statuses: set[str],
    ) -> list[ContractReadModel]: ...

    def list_contracts_by_client_id(
        self,
        client_id: int | str | UUID,
    ) -> list[ContractReadModel]: ...

    def get_contract_by_id_for_client(
        self,
        contract_id: UUID,
        client_id: int | str | UUID,
    ) -> ContractReadModel: ...

    def get_claimable_contract_by_id_for_client(
        self,
        contract_id: UUID,
        client_id: int | str | UUID,
        claimable_statuses: set[str],
    ) -> ContractReadModel: ...

    def get_contract_by_source_quote_request_id(
        self, quote_request_id: UUID
    ) -> ContractReadModel | None: ...

    def mark_contract_issued_for_quote_acceptance(
        self,
        quote_request_id: UUID,
        quote_acceptance_id: int,
    ) -> ContractReadModel | None: ...

    def mark_contract_declined(
        self,
        contract_id: UUID,
    ) -> ContractReadModel | None: ...

    def create_contract_from_quote_data(
        self, creation_data: ContractCreationData
    ) -> ContractReadModel: ...

    def has_default_insurer(self) -> bool: ...

    def get_default_insurer_context_source(self) -> InsurerContextSource: ...


class DefaultInsurerProvider(Protocol):
    def get_default_insurer_context_source(self) -> InsurerContextSource: ...


# infrastructure/postgres.py
class TemplateRepository(Protocol):
    def get_active_template(self, template_code: str) -> Template: ...


class WordingDocumentRepository(Protocol):
    def list_wording_documents(self) -> list[WordingDocument]: ...

    def get_wording_document(self, wording_document_id: int) -> WordingDocument: ...

    def get_wording_document_by_code(self, code: str) -> WordingDocument: ...

    def create_wording_document(
        self,
        document: WordingDocumentCreate,
    ) -> WordingDocument: ...

    def list_wording_versions(
        self,
        wording_document_id: int,
    ) -> list[WordingDocumentVersion]: ...

    def get_wording_version(self, wording_version_id: int) -> WordingDocumentVersion: ...

    def get_current_published_version(
        self,
        wording_document_id: int,
    ) -> WordingDocumentVersion | None: ...

    def create_wording_version(
        self,
        version: WordingDocumentVersionCreate,
        *,
        content_hash: str,
    ) -> WordingDocumentVersion: ...

    def publish_wording_version(
        self,
        wording_version_id: int,
        *,
        published_at: datetime,
    ) -> WordingDocumentVersion: ...

    def update_wording_version_full_text(
        self,
        wording_version_id: int,
        *,
        full_text: str,
        content_hash: str,
    ) -> WordingDocumentVersion: ...


# infrastructure/postgres.py
class GeneratedDocumentRepository(Protocol):
    def save(self, document: GeneratedDocument) -> GeneratedDocument: ...

    def get_latest_by_contract_id(
        self, contract_id: UUID
    ) -> GeneratedDocumentReadModel | None: ...

    def get_by_id(self, document_id: int) -> GeneratedDocumentReadModel: ...

    def update_pdf_metadata(
        self,
        *,
        document_id: int,
        pdf_storage_key: str,
        pdf_filename: str,
        pdf_content_hash: str,
        pdf_source_content_hash: str,
        pdf_generated_at,
        pdf_generation_metadata: dict[str, Any],
    ) -> GeneratedDocumentReadModel: ...


class ContractRequestRepository(Protocol):
    def create_request(self, request: ContractRequest) -> ContractRequest: ...

    def get_request_by_id(self, request_id: int) -> ContractRequest: ...

    def list_requests_by_client_id(self, client_id: int) -> list[ContractRequest]: ...

    def list_requests_by_status(self, request_status: str) -> list[ContractRequest]: ...

    def update_request_status(
        self,
        request_id: int,
        request_status: str,
    ) -> ContractRequest: ...


class EmailProvider(Protocol):
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
        reply_to: str | None = None,
        attachments: list[EmailAttachment] | None = None,
    ) -> str:
        ...


class EmailMessageRepository(Protocol):
    def save(self, email: EmailMessage) -> EmailMessage:
        ...

    def list_by_case_id(self, case_id: UUID) -> list[EmailMessage]:
        ...

    def list_by_customer_id(self, customer_id: int) -> list[CustomerEmailMessage]:
        ...

    def get_by_provider_message_id(
        self, provider_message_id: str
    ) -> EmailMessage | None:
        ...


class ClaimRequestRepository(Protocol):
    def create_request(self, request: ClaimRequest) -> ClaimRequest: ...

    def get_request_by_id(self, request_id: UUID) -> ClaimRequest: ...

    def list_requests_by_client_id(
        self,
        client_id: int | str | UUID,
    ) -> list[ClaimRequest]: ...

    def list_requests_by_status(self, request_status: str) -> list[ClaimRequest]: ...

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> ClaimRequest: ...

    def update_request_attachments(
        self,
        request_id: UUID,
        attachments: list,
    ) -> ClaimRequest: ...

    def update_request_claim_data(
        self,
        request_id: UUID,
        claim_data: dict[str, Any],
        request_status: str | None = None,
    ) -> ClaimRequest: ...

    def count_client_claims_since(
        self,
        client_id: int | str | UUID,
        since: datetime,
    ) -> int: ...


class ClaimAttachmentTextExtractor(Protocol):
    def extract_texts(
        self,
        claim_request: ClaimRequest,
        storage: Any,
    ) -> list[dict[str, Any]]: ...


class ClaimAttachmentSummaryGenerator(Protocol):
    def summarize(
        self,
        extraction_results: list[dict[str, Any]],
        *,
        claim_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class QuoteRequestRepository(Protocol):
    def create_request(self, request: QuoteRequest) -> QuoteRequest: ...

    def update_request(self, request: QuoteRequest) -> QuoteRequest: ...

    def get_request_by_id(self, request_id: UUID) -> QuoteRequest: ...

    def list_requests_by_client_id(
        self,
        client_id: int | str | UUID,
    ) -> list[QuoteRequest]: ...

    def list_requests_by_status(self, request_status: str) -> list[QuoteRequest]: ...

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> QuoteRequest: ...

    def create_decision_audit(
        self,
        record: QuoteDecisionAuditCreate,
    ) -> QuoteDecisionAuditRecord: ...

    def list_decision_audit(
        self,
        request_id: UUID,
    ) -> list[QuoteDecisionAuditRecord]: ...


class QuoteDocumentRepository(Protocol):
    def save(self, document: QuoteDocument) -> QuoteDocument: ...

    def get_by_id(self, document_id: int) -> QuoteDocument: ...

    def get_latest_successful_by_quote_request_id(
        self, quote_request_id: UUID
    ) -> QuoteDocument | None: ...


class QuoteAcceptanceRepository(Protocol):
    def create(self, acceptance: QuoteAcceptanceCreate) -> QuoteAcceptance: ...

    def get_by_quote_request_id(
        self, quote_request_id: UUID
    ) -> QuoteAcceptance | None: ...

    def get_by_id(self, acceptance_id: int) -> QuoteAcceptance: ...


class ContractDeclineRepository(Protocol):
    def create(self, decline: ContractDeclineCreate) -> ContractDecline: ...

    def get_by_contract_id(self, contract_id: UUID) -> ContractDecline | None: ...

    def get_by_id(self, decline_id: int) -> ContractDecline: ...


# application/modules/contract_payload_builder.py
class ContractPayloadBuilderPort(Protocol):
    def build(
        self, case_context: ContractCaseContext
    ) -> ModuleResult: ...


# infrastructure/templates/renderer.py
class TemplateRenderer(Protocol):
    def render(self, template: str, context: dict[str, Any]) -> str: ...


# infrastructure/llm/openai_compatible.py
class SupplementaryTextGenerator(Protocol):
    def generate(self, context: dict[str, Any], rendered_template: str) -> str: ...

#infrastructure/postgres/case_context_repository.py
class CaseContextRepository(Protocol):
    def save_case_context(self, context: BaseCaseContext) -> BaseCaseContext: ...
    def get_case_context_by_case_id(self, case_id: UUID | str) -> BaseCaseContext: ...
    def get_latest_claim_case_context_by_request_id(
        self, request_id: UUID | str
    ) -> ClaimCaseContext: ...
    def get_latest_claim_case_context_by_evidence_reply_token(
        self, reply_token: str
    ) -> ClaimCaseContext: ...
