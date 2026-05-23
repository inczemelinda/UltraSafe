# Frontend Source-of-Truth Audit

This audit tracks the remaining browser-local and mock-data state that touches
auth, profile, email, news, contracts, quotes, and claims. The rule is: backend
mode must never let browser state masquerade as backend truth. Mock/localStorage
state is only acceptable when it is explicit demo mode or clearly temporary UI
state.

## Fixed In This Slice

- Backend quote detail readers now treat only API `404` responses as missing
  records. Other backend/API failures are rethrown so backend mode does not turn
  an outage or auth problem into an empty quote.
- Backend claim detail readers now treat only API `404` responses as missing
  records. The underwriter claim fallback also rethrows non-404 failures.
- Frontend boundary tests now guard that mock storage helpers stay in
  `frontend/src/services/mock/*`, mock fixtures are not imported by pages or
  backend services, and backend readers do not hide non-404 failures.

## Explicit Mock/Demo-Only State

- `frontend/src/services/mock/*` uses `frontend/src/services/storage.ts` for
  local demo persistence. This includes mock auth/users, customer profile,
  profile documents, quotes, claims, contracts, underwriting rules, email, and
  news flows.
- `frontend/src/data/mock*.ts` fixtures are used by mock services only.
- `frontend/src/pages/PublicPages.tsx` pre-fills demo credentials only when
  `VITE_USE_MOCK_API=true`.
- `frontend/src/config/dataSource.ts` keeps backend mode as the default and
  shows/warns when mock mode is explicitly enabled.

## Acceptable Temporary UI/Cache State

- `frontend/src/services/authSession.ts` stores the current backend-issued auth
  session locally so route guards and API calls can attach the role token after a
  reload. This cache is not a replacement for backend-owned identity.
- `frontend/src/pages/ClientPages.tsx` stores quote and claim form drafts locally
  before submission. These are labelled as local/unsubmitted drafts in the UI and
  are cleared after successful backend creation.
- `frontend/src/pages/ClientPages.tsx` removes a legacy account-document storage
  key as cleanup only.

## Remaining Backendization Work

- Add a backend session validation/refresh step on app boot so cached auth
  sessions are verified before the UI treats them as current identity.
- Move quote and claim draft autosave backend-side if drafts need cross-device
  continuity, employee visibility, or regulatory auditability. Until then, keep
  local drafts clearly labelled as local and unsubmitted.
- Keep mock services available for demos, but continue enforcing that mock
  fixtures and mock localStorage helpers are only reachable through
  `VITE_USE_MOCK_API=true`.
