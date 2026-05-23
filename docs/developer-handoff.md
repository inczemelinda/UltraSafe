# Underwright Developer Handoff

This is the quick handoff guide for backend work after the quote-first refactor.
Read this alongside `docs/architecture.md` before changing workflow code.

## Main Idea

The active backend lifecycle is quote-first.

`QuoteRequest -> QuoteCaseContext -> QuoteWorkflow -> QuoteDocument -> underwriting`

A quote is the pre-signature artifact. A contract is the post-signature artifact.
That distinction is the main boundary to protect.

## Current Flow

In practice:

1. `QuoteRequestService` creates or updates client intake.
2. `QuoteWorkflow` creates one `QuoteCaseContext` for the request.
3. `QuoteDataService` attaches the request to reference data.
4. `QuoteDataCompletionModule` decides whether mandatory client and asset data is complete.
5. `QuoteApprovalModule` sets the approval decision. Today this is a stub that routes complete quotes to underwriter review.
6. `QuotePayloadBuilder` builds the quote generation payload.
7. `TemplateService` loads the template.
8. `QuoteDocumentGenerationModule` renders the unsigned quote.
9. `QuoteDocumentRepository` saves the generated document.
10. `QuoteRequestService` persists updated quote request state.

## Source Of Truth

Use these locations:

- Intake data: `QuoteRequest.client_data`, `QuoteRequest.asset_data`, `QuoteRequest.quote_steps`
- Intake completeness: `QuoteRequest.mandatory_data_status`
- Workflow envelope: `QuoteCaseContext`
- Active payload: `quote_case_context.domain_payload.quote_generation_payload`
- Approval decision: `quote_case_context.domain_payload.approval_decision`
- Generated unsigned document: `QuoteDocument`
- Review queue state: `QuoteRequest.request_status`

Do not introduce another active payload shape for quote generation.
All active payload fields should use snake_case.

## Statuses

Use the existing quote request status set until the team intentionally expands it:

| Status | Meaning |
| --- | --- |
| `draft` | Client intake exists but is not complete. |
| `pricing_in_progress` | Required data is still missing after generation was attempted. |
| `quote_ready` | Required data is complete before approval evaluation. |
| `auto_accepted` | Reserved for future preapproval rules. |
| `underwriter_review` | Current default for complete quotes because approval rules are a stub. |
| `approved` | Underwriter approved the quote. |
| `disapproved` | Underwriter declined the quote. |
| `field_review_required` | Underwriter needs field review before approval. |
| `failed` | Workflow failed and should expose a safe error state. |

`case_metadata.status` should mirror the workflow/request status.
Avoid parallel status fields in modules.

## Command Vs Query Convention

Use this rule for new application code:

- Commands mutate `QuoteCaseContext` or request state and return the same context or a small result.
- Queries return data and should not mutate `QuoteCaseContext`.

Examples:

- `QuoteDataService.attach_quote_request(case_context, quote_request)` is a command.
- `QuotePayloadBuilder.build(case_context)` is a command that attaches the canonical quote payload.
- `TemplateService.get_template_metadata(template)` is a query.
- Underwriter list/detail routes are queries until they change request status.

The reusable rule: pass state through the case context inside a workflow; use direct return values for read-only lookups.

## Where Things Live

- Active API routes: `src/underwright/api/routes/quotes.py`
- Active composition root: `src/underwright/composition.py`
- Quote workflow: `src/underwright/application/workflows/quote_workflow.py`
- Quote modules: `src/underwright/application/modules/quote_*`
- Quote services: `src/underwright/application/services/quote_*`
- Quote domain: `src/underwright/domain/quote_request.py`, `quote_case_context.py`, `quote_document.py`
- Quote persistence: `sql/004_quote_requests.sql`, `sql/005_quote_documents.sql`
- Quote adapters: `src/underwright/infrastructure/postgres/quote_*_repository.py`

## Legacy Boundary

The old direct contract generation flow is no longer the active pre-signature path.
Keep it only as legacy/demo support or future post-signing groundwork.

Do not reintroduce public pre-signature contract drafting routes.
New intake, approval, and generated pre-signature documents belong to the quote flow.

## Handoff Rules

- Protect the quote/contract lifecycle boundary.
- Use ports for repository contracts and Postgres adapters for implementation.
- Keep repositories split by aggregate instead of recreating a large shared repository file.
- Keep modules repository-free.
- Keep workflows thin: orchestration only.
- Add a service only when behavior is shared across routes or workflows.
- Add an abstraction only when it removes real duplication or protects a real boundary.

## Reference Docs

- `docs/backend-refactor-runthrough.md`: what changed and where the backend is now
- `docs/claim-review-flow.md`: current finding-based claim review flow
- `docs/claim-document-extraction-handoff.md`: where to wire claim document extraction
- `docs/quote-context.md`: active quote payload shape
- `docs/contract-context.md`: legacy contract payload shape
- `docs/domain-model.md`: table and relationship map
