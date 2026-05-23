# Backend Refactor Runthrough

This note summarizes what changed in the backend and where the system now sits.

## Core Concept

The backend now treats quote as the pre-signature aggregate and contract as the post-signature artifact.

That means a client does not ask the system to generate a contract directly.
The client fills intake data and requests a quote. The quote is generated from a template, can be preapproved later when rules exist, or can be sent to an underwriter. After signing, that quote can become a contract.

## What Changed

### API

The active API surface moved from contract drafting routes to quote routes.

Active routes now live in `src/underwright/api/routes/quotes.py`:

- client quote intake: `POST /quotes`, `PATCH /quotes/{request_id}`, `GET /quotes/client`, `GET /quotes/{request_id}`
- quote generation: `POST /quotes/{request_id}/generate`
- underwriter queue: `GET /underwriter/quotes`, `GET /underwriter/quotes/{request_id}`, `PATCH /underwriter/quotes/{request_id}/decision`

Old public contract drafting routes were removed from FastAPI registration and deleted.

### Workflow

The active orchestration point is now `QuoteWorkflow`.

It runs this sequence:

1. load `QuoteRequest`
2. create `QuoteCaseContext`
3. attach request data
4. evaluate mandatory data
5. run approval decision
6. build quote payload
7. render quote document
8. save `QuoteDocument`
9. save request and case-context state

If mandatory data is incomplete, the workflow saves state but does not create a quote document.

### Approval

Approval is intentionally stubbed.
Complete quote requests are routed to `underwriter_review` with an approval decision source of `stub`.

The expected future split is:

- normal rules can set `auto_accepted`
- unusual or risky cases can stay in `underwriter_review`
- underwriter decisions set `approved`, `disapproved`, or `field_review_required`

### Domain

The crowded case context file was split by lifecycle:

- `case_context_base.py`: shared case metadata, audit entries, and base envelope
- `quote_case_context.py`: active quote workflow state
- `contract_case_context.py`: legacy/post-signing contract state
- `claim_case_context.py`: claim workflow state

New quote domain models:

- `QuoteRequest`: client intake and request status
- `QuoteDocument`: unsigned generated quote artifact
- `QuoteCaseContext`: workflow state and generation payload

### Persistence

Quote persistence is now separate from contract persistence.

New tables:

- `quote_request`
- `quote_document`

New Postgres adapters:

- `quote_request_repository.py`
- `quote_document_repository.py`

The old large `infrastructure/postgres/repositories.py` file was split into focused repository modules.

### Composition

Runtime wiring now lives in `src/underwright/composition.py`.

This is the composition root: it builds concrete Postgres adapters, services, modules, and `QuoteWorkflow`.
The API dependency layer and CLI both use that wiring.

## Where It Is Now

| Area | Current owner | Notes |
| --- | --- | --- |
| Client intake | `QuoteRequest` | Source of truth for data entered by the client. |
| Workflow state | `QuoteCaseContext` | Carries payload, outputs, warnings, approval decision, and audit trail. |
| Generated pre-signature document | `QuoteDocument` | Unsigned quote tied to `quote_request_id`. |
| Active orchestration | `QuoteWorkflow` | Runs the quote lifecycle. |
| Public API | `quotes.py` | Quote routes replaced public contract drafting routes. |
| Runtime wiring | `composition.py` | Composition root for API and CLI. |
| Underwriter queue | `QuoteRequest.request_status` | Defaults to `underwriter_review` after complete quote generation. |
| Contract generation | legacy/post-signing | Not the active client request flow. |

## Legacy And Trim Map

Keep for now:

- claim request/domain code, because it is separate from the quote refactor
- contract domain/workflow code as legacy or post-signing groundwork
- `generated_document` persistence for old contract artifacts
- contract context examples as legacy reference material

Trim or avoid expanding:

- direct pre-signature contract generation behavior
- public contract request/drafting routes
- new code that writes quote output into `generated_document`
- new pre-signature payloads under `contract_generation_payload`

The general rule: if it happens before signing, it belongs to quote. If it happens after signing, it can belong to contract.

## Verification Snapshot

The refactor passed:

- `uv run ruff check src tests`
- `.venv/bin/python -m compileall -q src tests`
- `uv run pytest tests/unit tests/test_cli.py tests/smoke/test_api_dependencies.py --ignore=tests/unit/test_postgres_claim_request_repository.py --ignore=tests/unit/test_postgres_quote_request_repository.py`

Two DB-backed repository tests still depend on local Postgres credentials and were excluded from the passing suite because the local `uw` user authentication failed.
