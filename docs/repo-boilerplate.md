# Underwright Repo Boilerplate

Recommended repository shape for the Underwright backend.

## Recommended Repo Shape

```text
.
|-- README.md
|-- docs/
|   |-- architecture.md
|   |-- backend-refactor-runthrough.md
|   |-- domain-model.md
|   |-- quote-context.md
|   |-- contract-context.md
|   |-- llm-generation.md
|   `-- demo-checklist.md
|-- sql/
|   |-- 001_init_schema.sql
|   |-- 004_quote_requests.sql
|   `-- 005_quote_documents.sql
|-- src/
|   `-- underwright/
|       |-- api/
|       |-- application/
|       |-- domain/
|       |-- infrastructure/
|       |-- composition.py
|       `-- cli.py
|-- templates/
`-- tests/
```

## What Each Area Is For

### `docs/`

Planning, architecture, and handoff records.

- `architecture.md`: high-level quote-first flow and boundaries
- `backend-refactor-runthrough.md`: what changed and where things are now
- `domain-model.md`: entity fields and relationships
- `quote-context.md`: active quote generation payload
- `contract-context.md`: legacy/post-signing contract payload
- `llm-generation.md`: prompt inputs, output rules, failure handling
- `demo-checklist.md`: stakeholder verification steps

### `sql/`

Schema files only.

Quote tables should stay separate from legacy contract document tables:

- `quote_request`
- `quote_document`

### `src/underwright/api/`

FastAPI adapters.
The active public generation API is quote-based.

### `src/underwright/application/`

Use cases, services, modules, ports, and orchestration.

The active backend entry point is `QuoteWorkflow`.

### `src/underwright/domain/`

Core business entities and workflow state.

Boilerplate preference:

- use `pydantic` models for domain and DTO-like shapes
- split lifecycle-specific context into focused files
- keep quote and contract models distinct

### `src/underwright/infrastructure/`

Replaceable technical adapters.

- database repositories
- template rendering
- LLM provider
- file storage later

Postgres repositories should stay split by aggregate instead of being merged back into one large repository file.

### `src/underwright/composition.py`

Composition root.
Wire concrete adapters, services, modules, and workflows here.

### `templates/`

Template assets.
Quote-native templates should use the quote payload from `docs/quote-context.md`.

### `tests/`

Focused unit and smoke tests for routes, services, modules, workflows, and adapters.

## Run commands (pyproject.toml)

`pyproject.toml` is the source of truth for the project's run scripts and console commands. The backend exposes one FastAPI app plus console scripts defined under `[project.scripts]`. Run commands from the repository root.

Examples:

```bash
# sync tasks
uv sync
uv sync --group dev

# Run the backend API
uv run uvicorn underwright.api.main:app --reload

# Run quote-generation CLI
uv run cli run --quote-request-id <uuid> --template-code <template_code>

# Seed legal demo data
uv run seed-legal-demo-data
uv run seed-legal-demo-data --reset
uv run seed-legal-demo-data --dataset law_change_pipeline_demo_v1

# Ingestion jobs
uv run underwright-ingest preview --source-id asf_ro --limit 10
uv run underwright-ingest once --source-id asf_ro
uv run underwright-ingest process --source-id asf_ro --limit 50
uv run underwright-ingest correlate-templates --source-id asf_ro --limit 50
uv run underwright-ingest correlate-legal-templates --source-id asf_ro --limit 50

# Checks and tests
uv run ruff check src tests
uv run pytest
uv run python -m compileall -q src tests

# Known passing targeted test command (from repo docs)
uv run pytest tests/unit tests/test_cli.py tests/smoke/test_api_dependencies.py --ignore=tests/unit/test_postgres_claim_request_repository.py --ignore=tests/unit/test_postgres_quote_request_repository.py
```

Notes:

- DB-backed commands require environment variables like `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` and optionally `POSTGRES_PORT`.
- The frontend is separate and uses npm (the `frontend/` folder); use `npm install` / `npm ci` and `npm run dev` there.
