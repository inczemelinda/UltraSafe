# Underwright Architecture

This is the short implementation guide for the current backend shape.
Read this before adding quote, contract, or underwriting behavior.
For the refactor runthrough, see `docs/backend-refactor-runthrough.md`.

## Current Backend Flow

`QuoteRequest -> QuoteCaseContext -> quote modules -> QuoteDocument -> underwriter queue`

The active pre-signature lifecycle is quote-first:

- A client creates or updates a `QuoteRequest`.
- `QuoteWorkflow` creates a `QuoteCaseContext` for that request.
- Quote modules check mandatory data, make an approval decision, build a quote payload, and generate an unsigned quote document.
- `QuoteDocumentRepository` persists the generated unsigned quote.
- If the approval rules cannot preapprove the quote, the request is visible through underwriter quote routes.

A quote is not a contract. A quote becomes a contract only after signing.
That post-signing contract conversion is not implemented yet.

## Layer Model

The backend uses layered architecture with ports and adapters where the boundary is useful.

- `domain`: business shapes and state envelopes, such as `QuoteRequest`, `QuoteDocument`, and `QuoteCaseContext`.
- `application/services`: shared use-case operations around repositories, case contexts, templates, and audit events.
- `application/modules`: focused business steps, such as data completion, approval, payload building, and document generation.
- `application/workflows`: orchestration. Workflows decide the sequence of services and modules.
- `application/ports.py`: repository and integration protocols used by application code.
- `infrastructure/postgres`: concrete Postgres adapters for those ports.
- `api/routes`: FastAPI route adapters.
- `composition.py`: composition root that wires concrete adapters into the active workflow.

The useful distinction is: workflows decide order, modules do focused business work, services coordinate shared application operations, adapters do concrete IO.

## Active Quote Flow

1. `POST /quotes` creates a quote request from client intake data.
2. `PATCH /quotes/{request_id}` updates the intake state as the client completes steps.
3. `POST /quotes/{request_id}/generate` runs `QuoteWorkflow`.
4. `QuoteDataCompletionModule` checks required client and asset fields.
5. Incomplete requests are saved without a quote document.
6. Complete requests move through `QuoteApprovalModule`.
7. The current approval module is a stub that routes complete quotes to `underwriter_review`.
8. `QuotePayloadBuilder` builds `quote_case_context.domain_payload.quote_generation_payload`.
9. `QuoteDocumentGenerationModule` renders the unsigned quote from the active template.
10. `quote_document` persists the generated artifact tied to `quote_request_id`.
11. `/underwriter/quotes` exposes review queues and decisions.

## Source Of Truth

Use these ownership rules:

- Client intake lives on `QuoteRequest`.
- Workflow state lives on `QuoteCaseContext`.
- The active generation payload lives at `quote_case_context.domain_payload.quote_generation_payload`.
- The generated unsigned artifact is `QuoteDocument`.
- Underwriter decision state belongs on the quote request status and the quote case context approval payload.
- Contract state begins only after quote signing.

Do not add new pre-signature behavior to the legacy contract workflow.

## API Surface

Active quote routes:

- `POST /quotes`
- `PATCH /quotes/{request_id}`
- `GET /quotes/client?client_id=...`
- `GET /quotes/{request_id}`
- `POST /quotes/{request_id}/generate`
- `GET /underwriter/quotes?status=underwriter_review`
- `GET /underwriter/quotes/{request_id}`
- `PATCH /underwriter/quotes/{request_id}/decision`

The previous public contract drafting routes were removed from app registration.
Contract drafting code that remains is legacy or post-signing groundwork.

## Persistence

Active quote tables:

- `quote_request` stores client intake, step state, mandatory data status, attachments, pricing preview, and request status.
- `quote_document` stores generated unsigned quote text and JSON metadata for a quote request.

Legacy contract tables still exist for older demo data and future post-signing contract work.
Do not use `generated_document` for new quote output.

## Rules To Avoid Spaghetti

- New pre-signature features belong in the quote flow.
- Contracts are post-signature artifacts.
- Modules do not call repositories directly.
- Services may wrap repositories and update case context.
- Workflows orchestrate, but they should not contain payload-mapping or rendering details.
- Case context carries workflow state, payloads, generated outputs, review state, warnings, and audit trail.
- Review views are read models built from case context or request state, not a second source of truth.
- Infrastructure adapters stay concrete and boring: DB, template renderer, LLM client.

## Current Limitations

- Approval is a stub; complete quotes are routed to underwriter review.
- Quote-to-contract conversion after signing is not implemented.
- Quote-native templates are still catching up; `QuotePayloadBuilder` keeps a compatibility `contract_meta.contract_id` key for older PAD templates.
- Claims remain separate and are not part of the quote refactor.
- DB-backed repository tests require a working local Postgres user/password setup.