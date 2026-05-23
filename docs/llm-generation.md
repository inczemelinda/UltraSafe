# Underwright LLM Generation

The active LLM path supports quote document generation.
It should add bounded supplementary text to an already-rendered template, not invent the quote lifecycle or replace the source payload.

## Provider Contract

- OpenAI-compatible chat client using `httpx`
- Environment variable: `OPENAI_API_KEY`
- Optional environment variable: `OPENAI_API_BASE`
- Model is configurable by the adapter

If no API key is configured, quote generation still runs without supplementary LLM text.

## LLM Input

The generator receives:

- `quote_case_context.domain_payload.quote_generation_payload`
- rendered template text
- risk and asset details already present in the payload

The input should come from the active quote payload, not from a loose ad hoc dict.

## LLM Output

The generator returns a plain text supplement for the quote document.

The output is stored in `QuoteCaseContext.generated_outputs.quote_document` and persisted in `quote_document.rendered_json`.
The unsigned quote text remains the generated artifact.

## Failure Handling

- API timeout should use a simple fallback instead of failing the whole quote where possible.
- Missing API key should disable supplementary generation.
- Invalid responses should be recorded in generation metadata or module result state.

## Boundary

The LLM does not decide approval.
Approval belongs to quote rules or the underwriter flow.

## Claim Decision Rewording

The employee claim decision UI can ask the backend to rewrite a draft decision
justification for clarity and professionalism.

- Endpoint: `POST /claims/decision-justification/reword`
- Backend-only environment variables:
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL` (defaults to `gpt-4.1-mini`)
  - `OPENAI_TIMEOUT_SECONDS` (defaults to `15`)
- API surface: OpenAI Responses API via the backend `httpx` provider.

The rewording prompt must not add facts, remove material reasoning, change the
decision outcome, or produce a full email. It must return only replacement
customer-facing decision justification text. If the original wording is
inappropriate or unusable, the model must replace it with neutral professional
wording rather than critiquing the input. The frontend never calls OpenAI
directly and never receives the API key.
