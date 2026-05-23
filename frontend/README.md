# UltraSafe Frontend

React + Vite frontend prototype for UltraSafe.

The app uses the backend API by default. Mock data, local state, and localStorage services are available only when mock mode is explicitly enabled.

## Requirements

- Node.js 18 or newer
- npm 9 or newer

## Run Locally

```bash
npm install
npm run dev
```

Open the URL printed by Vite, usually:

```text
http://127.0.0.1:5173
```

## Build

```bash
npm run build
```

## Data Source Switch

The frontend can run in two modes:

- Mock mode: current clickable demo using localStorage.
- Backend mode: calls the FastAPI backend.

Backend mode is the default. To run against the backend, create `frontend/.env`:

```bash
cp .env.example .env
```

Then set:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_USE_MOCK_API=false
```

To run a frontend-only local demo without backend API calls, explicitly enable mock mode:

```text
VITE_USE_MOCK_API=true
```

When mock mode is enabled during development, the app shows a "Mock data mode" indicator and logs a console warning.

The backend adapters live in:

```text
src/services/backend/
```

Pages should keep importing from the shared service facades:

```text
src/services/authService.ts
src/services/quoteService.ts
src/services/contractService.ts
src/services/claimService.ts
src/services/customerProfileService.ts
src/services/customerAdminService.ts
src/services/authUserAdminService.ts
src/services/emailService.ts
src/services/newsService.ts
```

## Mock Demo Accounts

These accounts work only when `VITE_USE_MOCK_API=true`.

Client:

```text
ana.popescu@client.com
client123
```

Empty client:

```text
mihai.ionescu@client.com
client123
```

Employee:

```text
ioana.polita@ultrasafe.ro
employee123
```

## Mock Data

Mock users, quotes, contracts, claims, profiles, email history, news, and underwriting rules live in:

```text
src/data/
```

Mock service functions live in:

```text
src/services/mock/
```

Backend mode currently connects:

```text
POST /auth/login
POST /auth/client/register
GET /me/quotes
GET /quotes/{request_id}
POST /me/quotes
POST /quotes/{request_id}/generate
GET /underwriter/quotes
PATCH /underwriter/quotes/{request_id}/decision
GET /me/contracts
GET /contracts
GET /underwriter/claims
POST /underwriter/claims/{request_id}/decision
GET /intelligence/events
```

The shared service facades live directly in `src/services/` and choose mock or backend based on `VITE_USE_MOCK_API`.

## Legal Review Backend Demo

Legal Review uses backend data by default. To force Legal Review back to mock data, set:

```text
VITE_USE_MOCK_LEGAL_REVIEW_API=true
```

From the repo root, apply the normal database migrations with `DATABASE_URL` set. The Legal Review flow needs the legal document/template review tables and hunk context migration:

```text
sql/013_legal_document_template_review_candidates.sql
sql/014_template_change_suggestions.sql
sql/015_template_draft_revisions.sql
sql/020_template_change_suggestion_hunk_context.sql
```

The migration script runs them in order:

```bash
scripts/db_migrate.sh
```

Seed the legal review demo data:

```bash
uv run seed-legal-demo-data --reset
```

Start the backend:

```bash
uv run uvicorn underwright.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Start the frontend with Legal Review using the backend:

```bash
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Default local URLs:

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8000
```

Draft creation creates an unpublished draft revision only. It does not publish or modify the current template.