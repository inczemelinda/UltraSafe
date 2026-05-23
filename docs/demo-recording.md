# Demo Recording

This demo automation records the short client quote flow:

Home page -> client login -> Get a Quote -> completed quote estimate form.

It uses explicit mock frontend data, so it does not require the backend. Set `VITE_USE_MOCK_API=true` before running the demo; the flow submits the mock quote and stops on the thank-you confirmation.

## Demo Account

```text
vasile.valoare@client.com
client123
```

## Run The Demo

From `frontend/`:

```bash
VITE_USE_MOCK_API=true npm run demo:quote
```

Or put `VITE_USE_MOCK_API=true` in `frontend/.env.local` for repeated demo runs.

```bash
npm run demo:quote
```

This starts the Vite dev server on `http://127.0.0.1:5173`, opens Chromium headed, and performs the paced demo flow. The Playwright config also sets `VITE_USE_MOCK_API=true` for its managed dev server; if you reuse an already-running server, start that server with mock mode explicitly enabled.

To slow the flow down for narration, add a Playwright delay:

```bash
VITE_USE_MOCK_API=true DEMO_SLOW_MO_MS=50 npm run demo:quote
```

## Record With Playwright Video

From `frontend/`:

```bash
npm run demo:quote:record
```

Videos are written under `frontend/test-results/demo/`. Playwright records the browser viewport; OBS can also capture the headed browser window if you prefer manual recording.

## Codegen

From `frontend/`:

```bash
npm run demo:codegen
```

## Notes

- The script clears localStorage/sessionStorage for the browser context before the flow so saved quote drafts do not change the starting step.
- The flow submits only when mock demo mode is explicitly enabled; it does not call the backend.
- Prefilled fields are left untouched. The script only fills empty inputs.
- The script adds an in-page cursor overlay because Playwright video does not reliably capture the OS cursor.
- The script uses accessible locators for labels, buttons, links, and visible option text. No product selectors were added.
- If browser launch fails in a restricted shell, run the npm script from a normal terminal session.
