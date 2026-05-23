# Claim Review Flow

This is the current developer map for finding-based claim review. The central
rule is: the system provides underwriter decision support, not final claim
decisioning.

## Lifecycle

`ClaimRequest -> ClaimCaseContext -> claim modules -> ClaimReviewView`

1. `ClaimRequest` is client intake. It stores the submitted claim facts,
   client data, attachment metadata, and request status.
2. `CoveragePrecheckWorkflow` can run immediately after submission. It checks
   incident description against policy wording and routes the request for human
   review.
3. `ClaimWorkflow` runs when the underwriter starts or reruns analysis.
4. Claim modules write structured findings into `ClaimCaseContext`.
5. `ClaimReviewScreenBuilderModule` builds `ClaimReviewView`, the
   underwriter-facing read model.
6. `GET /underwriter/claims/{request_id}/review` loads the latest persisted
   review view without rerunning analysis.

## Objects

`ClaimRequest`
: Intake source of truth. It is not workflow memory.

`ClaimCaseContext`
: Workflow memory. It carries reference data, generated outputs, warnings,
  review state, and the latest underwriter read model.

`ExtractedDocumentBundle`
: Already-extracted document facts. The current
  `ExtractedDocumentDataService` is a temporary static adapter and does not do
  OCR, PDF parsing, classification, or extraction.

`PolicyWordingRetrievalService`
: Retrieves relevant policy wording or rulebook sections. The MVP returns a
  static set of sections, but the service boundary is meant to be replaced by
  real wording retrieval.

`CoverageAssessmentLLMService`
: Performs the LLM assessment of incident description against retrieved wording.
  It returns structured JSON shaped like `CoverageAssessmentResult`.

`CoverageAssessmentModule`
: Orchestrates wording retrieval and the LLM-backed assessment. A
  `CoverageAssessmentResult` is a pre-check for human review, not a final
  coverage decision.

`DocumentConsistencyModule`
: Compares claim intake fields against `ExtractedDocumentBundle` facts and
  emits supporting facts and discrepancies.

`EvidenceRequirementModule`
: Decides what follow-up proof is missing before underwriter review can
  continue. It can suggest `request_evidence`, `manual_review`, or
  `underwriter_review`.

`EvidenceRequestDraftService`
: Builds an underwriter-editable draft when evidence is missing. It does not
  send email or approve delivery.

`ClaimReviewView`
: Read model for the underwriter UI. It contains coverage pre-check,
  document consistency, supporting facts, discrepancies, required evidence,
  suggested next action, and human-readable summary.

## Statuses

Claim statuses used by this slice:

| Status | Meaning |
| --- | --- |
| `submitted` | Claim intake exists. |
| `screening` | Initial coverage pre-check is running. |
| `needs_underwriter_review` | Claim should appear for normal human review. |
| `coverage_review_required` | Wording fit may not apply; human coverage review is required. This is not dismissal. |
| `in_review` | Underwriter analysis workflow has run or is being reviewed. |
| `failed` | Workflow failed and should expose a safe review state. |

No status in this flow means the claim was accepted, rejected, paid, or
dismissed.

## Current Demo Slice

For a fire claim:

1. Coverage pre-check compares the incident description against fire wording
   through `CoverageAssessmentLLMService`.
2. If the LLM returns `potentially_covered`, the claim routes to underwriter
   review.
3. `DocumentConsistencyModule` checks intake fields against already-extracted
   document facts.
4. If there is no official fire report or authority-verified incident proof,
   `EvidenceRequirementModule` requires official fire incident confirmation.
5. `ClaimReviewView.suggested_next_action` becomes `request_evidence`.
6. The UI can generate an editable evidence request draft, but it does not send
   anything.

## Limitations

- No document extraction is implemented yet.
- No OCR, PDF parsing, or document classification is implemented here.
- No actual email hook handling is implemented in this flow; the internal
  evidence endpoint only records metadata for future ingestion.
- No evidence request email is sent automatically.
- No final accept/reject decision is made.
- No auto-dismiss exists yet.
- Coverage assessment uses LLM reasoning and must be reviewed by a human in
  this MVP.
- `EvidenceRefreshWorkflow` preserves existing coverage assessment unless
  incoming evidence explicitly changes coverage-relevant claim facts such as
  claim type, incident type, description, or incident date.
