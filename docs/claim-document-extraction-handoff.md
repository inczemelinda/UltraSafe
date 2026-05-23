# Claim Document Extraction Handoff

This handoff explains where to wire a computer-vision document extraction
component into the finding-based claim review workflow.

No implementation has been done in this handoff. This is the wiring plan.

## Main Idea

The extractor belongs behind `ExtractedDocumentDataService`.

That service is the boundary between uploaded claim documents and structured
document facts. The review workflow should continue to consume
`ExtractedDocumentBundle`, not OCR, PDF, image, or computer-vision details.

Keep this responsibility split:

- Computer-vision extractor: turns a stored file into structured facts.
- `ExtractedDocumentDataService`: loads/provides extracted facts for a claim.
- `DocumentConsistencyModule`: compares claim intake fields to document facts.
- `EvidenceRequirementModule`: decides what follow-up proof is missing.
- `CoverageAssessmentModule`: compares incident description to policy wording.
  It must not inspect uploaded documents.

## Current Repo Map

### Claim Submission

Claim creation is handled by:

- `src/underwright/api/routes/claims.py`
- function: `create_claim_request`

Current behavior:

1. Accepts a JSON body.
2. Creates a `ClaimRequest`.
3. Persists it through `ClaimRequestService`.
4. Runs `CoveragePrecheckWorkflow`.

Important: `POST /claims` does not currently receive uploaded file bytes. It
receives attachment metadata only.

### Attachment Metadata

Claim attachments are represented in:

- `src/underwright/domain/claim_request.py`
- class: `ClaimAttachmentMetadata`

Fields:

- `file_name`
- `content_type`
- `size_bytes`
- `file_url`
- `metadata`

The attachment list lives on:

- `ClaimRequest.attachments`

### Attachment Persistence

Claim requests are persisted by:

- `src/underwright/infrastructure/postgres/claim_request_repository.py`

The SQL schema stores attachments as JSONB:

- `sql/003_claim_requests.sql`
- column: `claim_request.attachments`

There is no claim-specific document file table or extraction result table at
the moment.

### File Storage References

Current claim submission appears to store references only, not file content.

Potential document locators available to an extractor:

- `ClaimAttachmentMetadata.file_url`
- `ClaimAttachmentMetadata.metadata["storage_key"]`
- `ClaimAttachmentMetadata.metadata["document_id"]`
- filename-only demo records

The frontend currently builds claim attachment metadata in:

- `frontend/src/services/backend/claimService.ts`
- function: `buildAttachments`

The current client claim flow sends filenames and labels, not binary files.

### Existing Extracted Document Service

Current extracted document service:

- `src/underwright/application/services/extracted_document_data_service.py`
- class: `ExtractedDocumentDataService`
- public method: `get_extracted_documents`

Current behavior:

1. Loads the `ClaimRequest`.
2. Reads `ClaimRequest.attachments`.
3. Optionally merges additional evidence attachments.
4. Infers document type from filename.
5. Returns mocked/static `ExtractedClaimDocument` data.

Mock generation currently lives in the same file:

- `infer_document_type`
- `_document_from_attachment`
- `_mock_extracted_fields`
- `_mock_confidence`

### Where Claim Review Loads Extracted Documents

Main underwriter analysis workflow:

- `src/underwright/application/workflows/claim_workflow.py`
- class: `ClaimWorkflow`
- method: `run`

The workflow calls:

- `ClaimDataService.attach_extracted_documents`

That method lives in:

- `src/underwright/application/services/claim_data_service.py`

It writes the bundle to:

- `ClaimCaseContext.reference_data["extracted_documents"]`

That is the data consumed by:

- `DocumentConsistencyModule`
- `EvidenceRequirementModule`

### New Evidence Entry Point

Future email-hook evidence metadata enters through:

- `src/underwright/api/routes/claims.py`
- endpoint: `POST /internal/claims/{request_id}/evidence`

Evidence metadata is recorded by:

- `src/underwright/application/services/claim_evidence_ingestion_service.py`
- class: `ClaimEvidenceIngestionService`

Evidence refresh runs through:

- `src/underwright/application/workflows/evidence_refresh_workflow.py`
- class: `EvidenceRefreshWorkflow`

`EvidenceRefreshWorkflow` converts incoming evidence attachments into
`ClaimAttachmentMetadata` and calls:

- `ExtractedDocumentDataService.get_extracted_documents(..., additional_attachments=...)`

This is the second important extraction path.

## Computer-Vision Component Status

I did not find an existing claim-document computer-vision extraction component
in this repo.

Searches did not reveal project-owned OCR, PDF parsing, image extraction, or
claim document extraction code. If the extractor exists on another branch or in
another service, wrap it behind the boundary described below.

## Recommended MVP Wiring

### 1. Add Or Adapt An Extraction Port

Recommended file:

- `src/underwright/application/ports.py`

or, if the project wants the smallest change:

- `src/underwright/application/services/extracted_document_data_service.py`

Suggested responsibility:

```python
class ClaimDocumentExtractionService(Protocol):
    def extract_document(
        self,
        claim_request: ClaimRequest,
        attachment: ClaimAttachmentMetadata,
    ) -> ExtractedClaimDocument | None:
        ...
```

The port should hide:

- local file paths
- object storage
- signed URLs
- OCR/CV library calls
- external service calls
- raw extractor response shape

The rest of the workflow should only see `ExtractedClaimDocument`.

### 2. Add Infrastructure Adapter For The CV Component

Recommended new package:

- `src/underwright/infrastructure/document_extraction/`

Possible files:

- `src/underwright/infrastructure/document_extraction/__init__.py`
- `src/underwright/infrastructure/document_extraction/cv_document_extraction_service.py`

The adapter should:

1. Resolve the document locator from attachment metadata.
2. Call the CV component.
3. Map the result to `ExtractedClaimDocument`.
4. Normalize errors into safe failures.

Expected mapper output:

- `document_id`
- `filename`
- `document_type`
- `extracted_fields`
- `extraction_confidence`
- `source`

### 3. Wire Adapter Through `ExtractedDocumentDataService`

Modify:

- `src/underwright/application/services/extracted_document_data_service.py`

Change `ExtractedDocumentDataService` so it can receive an optional extraction
adapter.

`get_extracted_documents` should:

1. Load the claim.
2. Combine original claim attachments and additional evidence attachments.
3. For each attachment, try the real extractor if a document locator exists.
4. Fall back to the current mock/static behavior only for demo/sample records.
5. Return an `ExtractedDocumentBundle`.

Do not let extractor failures crash the claim workflow. Failed or missing
extraction should produce partial data or insufficient document data.

### 4. Wire Composition

Modify:

- `src/underwright/composition.py`

Relevant functions:

- `build_claim_workflow`
- `build_evidence_refresh_workflow`

Build the extraction adapter once in composition, then pass it into
`ExtractedDocumentDataService`, then into `ClaimDataService`.

This keeps routes and modules free of CV-specific code.

### 5. Keep Routes Thin

Do not call the CV component from:

- `src/underwright/api/routes/claims.py`

Routes should keep calling workflow/service boundaries.

## When Extraction Should Run

Recommended MVP: run extraction lazily inside `ExtractedDocumentDataService`.

That means extraction happens during:

1. underwriter Start Analysis
2. evidence refresh after incoming evidence metadata is recorded

Do not run document extraction during `POST /claims` for MVP.

Reasons:

- Current claim submission does not upload actual file bytes.
- Coverage precheck should not inspect documents.
- Claim creation should remain resilient even if extraction fails.
- Lazy extraction fits the existing workflow seam.

## Future Persistence Option

For MVP, it is acceptable to store extracted document facts in:

- `ClaimCaseContext.reference_data["extracted_documents"]`

Add dedicated persistence later if the team needs:

- extraction caching
- idempotency across reruns
- audit history
- async extraction status
- raw document processing metadata

Possible future files:

- `sql/0xx_claim_extracted_documents.sql`
- `src/underwright/infrastructure/postgres/claim_extracted_document_repository.py`

Do not add these tables unless they solve an immediate problem.

## Tests To Add

Backend tests should use fake extractor services. Do not call a real CV service
in unit tests.

Recommended tests:

- `tests/unit/test_extracted_document_data_service.py`
  - real extractor is called for attachments with `file_url` or `storage_key`
  - extractor result maps into `ExtractedDocumentBundle`
  - extractor failure does not crash and returns safe partial data
  - filename-only demo attachments can still use mock fallback

- `tests/unit/test_claim_workflow.py`
  - `ClaimWorkflow` attaches extracted documents before document consistency
  - `DocumentConsistencyModule` consumes real extracted facts

- `tests/unit/test_evidence_refresh_workflow.py`
  - incoming evidence attachments are passed to extraction
  - evidence refresh reruns document consistency and evidence requirements
  - coverage assessment is not rerun unless claim facts changed

## Risks And Unknowns

- The current claim submission flow does not upload binary files.
- Initial claim attachments may only have filenames.
- The CV component is not visible in this repo.
- The extractor API, sync/async behavior, error model, and output shape are
  unknown.
- A storage resolver may be needed before the extractor can read files.
- Re-running Start Analysis could repeatedly extract the same files unless
  caching or persistence is added later.
- Extracted field names must line up with what `DocumentConsistencyModule`
  expects, especially:
  - `policy_number`
  - `insured_address`
  - `property_address`
  - `owner_name`
  - `full_name`
  - `damage_type`
  - `coverage_limit`
  - `authority_verified`

## Non-Goals

Do not add these as part of the MVP wiring:

- document extraction inside `CoverageAssessmentModule`
- direct CV calls from routes
- final claim accept/reject decisions
- auto-dismiss
- email sending
- full document extraction persistence unless required for the demo

## Suggested First Implementation Step

Start by adding the extraction port and a fake adapter test around
`ExtractedDocumentDataService`.

Once that seam works, plug in the actual CV component adapter in
`composition.py`.
