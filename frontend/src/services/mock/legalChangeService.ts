import type {
  LegalChangeReviewStatus,
  LegalChangeItem,
  TemplateChangeSuggestion,
  TemplateChangeSuggestionDetail,
  TemplateChangeSuggestionHunk,
  TemplateChangeSuggestionHunkStatus,
  TemplateDraftRevision
} from "../../types";
import { delay } from "../storage";

const now = "2026-05-15T10:00:00Z";

const legalDocument = {
  id: "92000000-0000-0000-0000-000000000001",
  source_id: "demo_ro_portal_legislativ",
  source_key: "demo_ro_portal_legislativ",
  jurisdiction: "RO",
  parser_id: "ro_portal_legislativ",
  canonical_url: "demo://law_change_pipeline_demo_v1/ro/lege-99-2026",
  source_url: "demo://law_change_pipeline_demo_v1/ro/lege-99-2026",
  external_identifier: "demo:ro:lege:99:2026",
  title: "DEMO - Legea nr. 99/2026 pentru modificarea Legii nr. 260/2008",
  language: "ro",
  issuer: "DEMO - Parlamentul României",
  instrument_type: "lege",
  instrument_number: "99",
  instrument_year: 2026,
  publication_reference: "DEMO - Monitorul Oficial nr. 500/2026",
  publication_date: "2026-05-15",
  effective_date: "2026-06-15",
  status: "in_force",
  legal_references: ["ro:lege:99:2026"],
  amends: ["ro:lege:260:2008"],
  repeals: [],
  full_text:
    "DEMO - Legea nr. 99/2026 pentru modificarea Legii nr. 260/2008. Publicată în Monitorul Oficial nr. 500/2026. Termenul de notificare a daunei se modifică de la 10 zile calendaristice la 5 zile calendaristice.",
  summary: "Demo legal act changes the PAD claim notification deadline from 10 days to 5 days.",
  extraction_confidence: 0.95,
  source_metadata: {
    is_synthetic: true,
    demo_dataset: "law_change_pipeline_demo_v1"
  }
};

const fireLegalDocument = {
  ...legalDocument,
  id: "92000000-0000-0000-0000-000000000002",
  source_key: "demo_ro_portal_fire_exclusion",
  canonical_url: "demo://law_change_pipeline_demo_v1/ro/fire-exclusion-2026",
  source_url: "demo://law_change_pipeline_demo_v1/ro/fire-exclusion-2026",
  external_identifier: "demo:ro:ordin:44:2026",
  title: "DEMO - Fire coverage exclusion clause wording change",
  issuer: "DEMO - Autoritatea de Supraveghere Financiară",
  instrument_type: "ordin",
  instrument_number: "44",
  publication_reference: "DEMO - Ordin ASF nr. 44/2026",
  effective_date: "2026-06-01",
  legal_references: ["ro:ordin:44:2026"],
  full_text:
    "DEMO - Ordin ASF nr. 44/2026 solicită ca excluderile pentru incendiu să distingă între daune accidentale și daune provocate intenționat.",
  summary: "Demo fire exclusion wording update requires clearer distinction between accidental and intentional fire damage.",
  extraction_confidence: 0.89
};

const stormLegalDocument = {
  ...legalDocument,
  id: "92000000-0000-0000-0000-000000000003",
  source_key: "demo_ro_portal_storm_deductible",
  canonical_url: "demo://law_change_pipeline_demo_v1/ro/storm-deductible-2026",
  source_url: "demo://law_change_pipeline_demo_v1/ro/storm-deductible-2026",
  external_identifier: "demo:ro:norma:27:2026",
  title: "DEMO - Storm damage deductible disclosure clarification",
  issuer: "DEMO - Autoritatea de Supraveghere Financiară",
  instrument_type: "norma",
  instrument_number: "27",
  publication_reference: "DEMO - Buletin ASF nr. 27/2026",
  effective_date: "2026-06-20",
  legal_references: ["ro:norma:27:2026"],
  full_text:
    "DEMO - Norma ASF nr. 27/2026 cere ca franșizele pentru furtună și grindină să fie prezentate lângă descrierea riscurilor acoperite.",
  summary: "Storm deductible disclosures must be visible beside covered peril descriptions.",
  extraction_confidence: 0.8
};

const candidate = {
  candidate_id: "93000000-0000-0000-0000-000000000001",
  normalized_legal_document_id: legalDocument.id,
  template_id: 42,
  template_code: "DEMO_PAD_POLICY_WORDING_RO",
  template_name: "DEMO - PAD Policy Wording Romania",
  template_version: "demo-v1",
  template_version_hash: "demo-template-version-hash",
  match_type: "amended_reference",
  matched_reference: "ro:lege:260:2008",
  review_reason:
    "DEMO - Legea nr. 99/2026 amends ro:lege:260:2008, which is referenced by template DEMO_PAD_POLICY_WORDING_RO.",
  confidence: 0.95,
  status: "needs_review",
  source_metadata: {
    is_synthetic: true,
    demo_dataset: "law_change_pipeline_demo_v1"
  }
};

const fireCandidate = {
  ...candidate,
  candidate_id: "93000000-0000-0000-0000-000000000002",
  normalized_legal_document_id: fireLegalDocument.id,
  matched_reference: "fire_exclusion",
  review_reason:
    "The template contains covered fire peril and exclusion wording that may need review.",
  confidence: 0.87
};

const stormCandidate = {
  ...candidate,
  candidate_id: "93000000-0000-0000-0000-000000000003",
  normalized_legal_document_id: stormLegalDocument.id,
  matched_reference: "storm_deductible",
  review_reason:
    "The demo policy template contains storm peril wording and should be checked for deductible disclosure.",
  confidence: 0.76
};

const template = {
  id: 42,
  template_code: "DEMO_PAD_POLICY_WORDING_RO",
  name: "DEMO - PAD Policy Wording Romania",
  version: "demo-v1",
  document_type: "insurance_contract",
  is_active: true,
  content:
    "Prezenta poliță este emisă în conformitate cu Legea nr. 260/2008. Asiguratul trebuie să notifice dauna în termen de 10 zile calendaristice de la producerea evenimentului. Această obligație se aplică de la data producerii evenimentului asigurat. Incendiul este arderea cu flacără deschisă, produsă accidental, care se poate extinde prin propria forță. Furtuna și grindina sunt fenomene atmosferice cu intensitate suficientă pentru a provoca avarii directe acoperișului.",
  jurisdiction: "RO",
  product_line: "property",
  legal_references_json: ["ro:lege:260:2008"],
  metadata_json: {
    is_synthetic: true,
    demo_dataset: "law_change_pipeline_demo_v1"
  },
  created_at: now
};

let suggestion: TemplateChangeSuggestion | undefined;
let draftRevision: TemplateDraftRevision | undefined;
const candidateStatuses = new Map<string, LegalChangeReviewStatus>();

const scenarios = [
  {
    legalDocument,
    candidate,
    hunk: {
      sectionLabel: "Claim notification",
      articleTitle: "Article 7 - Claim notification",
      oldText:
        "Asiguratul trebuie să notifice dauna în termen de 10 zile calendaristice de la producerea evenimentului.",
      newText:
        "Asiguratul trebuie să notifice dauna în termen de 5 zile calendaristice de la producerea evenimentului.",
      rationale: "The legal update changes the notification deadline from 10 days to 5 days."
    }
  },
  {
    legalDocument: fireLegalDocument,
    candidate: fireCandidate,
    hunk: {
      sectionLabel: "Fire exclusion wording",
      articleTitle: "Article 3 - Covered fire peril",
      oldText:
        "Incendiul este arderea cu flacără deschisă, produsă accidental, care se poate extinde prin propria forță.",
      newText:
        "Incendiul este arderea cu flacără deschisă, produsă accidental, care se poate extinde prin propria forță. Daunele provocate intenționat de Asigurat sunt tratate separat ca excluderi și nu limitează acoperirea incendiilor accidentale.",
      rationale:
        "The legal update requires clearer distinction between accidental fire damage and intentionally caused fire damage."
    }
  },
  {
    legalDocument: stormLegalDocument,
    candidate: stormCandidate,
    hunk: {
      sectionLabel: "Storm deductible disclosure",
      articleTitle: "Article 3 - Storm and hail peril",
      oldText:
        "Furtuna și grindina sunt fenomene atmosferice cu intensitate suficientă pentru a provoca avarii directe acoperișului.",
      newText:
        "Furtuna și grindina sunt fenomene atmosferice cu intensitate suficientă pentru a provoca avarii directe acoperișului. Franșiza aplicabilă pentru furtună și grindină trebuie indicată lângă descrierea riscului acoperit.",
      rationale:
        "The legal update requires storm and hail deductibles to be visible next to covered peril descriptions."
    }
  }
];

export type LegalChangeReviewFilter = LegalChangeReviewStatus | "processed";

export async function getLegalChanges(
  status: LegalChangeReviewFilter = "needs_review"
): Promise<LegalChangeItem[]> {
  const statuses =
    status === "processed"
      ? new Set<LegalChangeReviewStatus>(["accepted", "dismissed"])
      : new Set<LegalChangeReviewStatus>([status]);
  return delay(
    scenarios
      .map((scenario) => ({
        legal_document: scenario.legalDocument,
        candidates: [candidateWithStatus(scenario.candidate)],
        affected_template_count: 1,
        highest_confidence: scenario.candidate.confidence
      }))
      .filter((item) => statuses.has(candidateStatus(item.candidates[0])))
  );
}

export async function createTemplateChangeSuggestion(
  candidateId: string
): Promise<TemplateChangeSuggestion> {
  const scenario = requireScenarioForCandidate(candidateId);
  const startOffset = template.content.indexOf(scenario.hunk.oldText);
  suggestion = {
    id: `94000000-0000-0000-0000-${candidateId.slice(-12)}`,
    candidate_id: scenario.candidate.candidate_id,
    template_id: scenario.candidate.template_id,
    normalized_legal_document_id: scenario.legalDocument.id,
    template_version_hash: scenario.candidate.template_version_hash,
    status: "draft",
    overall_summary: `AI-generated draft update for ${scenario.hunk.sectionLabel}.`,
    validation_result: { valid: true, errors: [] },
    hunks: [
      {
        id: `95000000-0000-0000-0000-${candidateId.slice(-12)}`,
        suggestion_id: `94000000-0000-0000-0000-${candidateId.slice(-12)}`,
        section_id: "claims.notification",
        section_label: scenario.hunk.sectionLabel,
        templateSectionTitle: scenario.hunk.sectionLabel,
        templateArticleTitle: scenario.hunk.articleTitle,
        beforeContext:
          "Prezenta poliță este emisă în conformitate cu Legea nr. 260/2008.",
        afterContext:
          "Această obligație se aplică de la data producerii evenimentului asigurat.",
        fullContextExcerpt: scenario.hunk.oldText,
        startOffset,
        endOffset: startOffset + scenario.hunk.oldText.length,
        change_type: "replace",
        old_text: scenario.hunk.oldText,
        new_text: scenario.hunk.newText,
        rationale: scenario.hunk.rationale,
        source_reference: scenario.legalDocument.title,
        confidence: 0.86,
        status: "draft",
        reviewer_notes: ""
      }
    ],
    created_at: now,
    updated_at: now
  };
  draftRevision = undefined;
  setCandidateStatus(candidateId, "needs_review");
  return delay(structuredClone(suggestion));
}

export async function getTemplateChangeSuggestion(
  suggestionId: string
): Promise<TemplateChangeSuggestionDetail> {
  const current = requireSuggestion(suggestionId);
  const scenario = requireScenarioForCandidate(current.candidate_id);
  return delay({
    suggestion: structuredClone(current),
    candidate: scenario.candidate,
    normalized_legal_document: scenario.legalDocument,
    template,
    draft_revision: draftRevision ? structuredClone(draftRevision) : null
  });
}

export async function updateTemplateChangeSuggestionHunk(
  suggestionId: string,
  hunkId: string,
  patch: {
    new_text?: string;
    status?: TemplateChangeSuggestionHunkStatus;
    reviewer_notes?: string;
  }
): Promise<TemplateChangeSuggestion> {
  const current = requireSuggestion(suggestionId);
  current.hunks = current.hunks.map((hunk) => {
    if (hunk.id !== hunkId) return hunk;
    return {
      ...hunk,
      new_text: patch.new_text ?? hunk.new_text,
      reviewer_notes: patch.reviewer_notes ?? hunk.reviewer_notes,
      status: patch.status ?? (patch.new_text == null ? hunk.status : "edited")
    };
  });
  current.updated_at = new Date().toISOString();
  syncCandidateStatusFromSuggestion(current);
  return delay(structuredClone(current));
}

export async function acceptTemplateChangeSuggestionHunk(
  suggestionId: string,
  hunkId: string
): Promise<TemplateChangeSuggestion> {
  return updateHunkStatus(suggestionId, hunkId, "accepted");
}

export async function rejectTemplateChangeSuggestionHunk(
  suggestionId: string,
  hunkId: string
): Promise<TemplateChangeSuggestion> {
  return updateHunkStatus(suggestionId, hunkId, "rejected");
}

export async function createDraftRevisionFromSuggestion(
  suggestionId: string
): Promise<TemplateDraftRevision> {
  const current = requireSuggestion(suggestionId);
  const reviewedHunks = current.hunks.filter((hunk) => hunk.status === "accepted" || hunk.status === "rejected" || hunk.status === "edited");
  const appliedHunks = current.hunks.filter((hunk) => hunk.status === "accepted" || hunk.status === "edited");
  if (!reviewedHunks.length || reviewedHunks.length !== current.hunks.length) {
    throw new Error("Review every hunk before creating a draft revision.");
  }
  let revisedContent = template.content;
  for (const hunk of appliedHunks) {
    if (hunk.change_type === "replace") {
      revisedContent = revisedContent.replace(hunk.old_text, hunk.new_text);
    }
  }
  draftRevision = {
    id: `96000000-0000-0000-0000-${current.candidate_id.slice(-12)}`,
    suggestion_id: current.id,
    template_id: template.id,
    template_code: template.template_code,
    template_name: template.name,
    base_template_version: template.version,
    base_template_version_hash: current.template_version_hash,
    status: "draft",
    base_content: template.content,
    revised_content: revisedContent,
    applied_hunk_ids: appliedHunks.map((hunk) => hunk.id),
    validation_result: { valid: true, errors: [] },
    source_metadata: {
      is_synthetic: true,
      demo_dataset: "law_change_pipeline_demo_v1"
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  };
  current.status = "applied_to_draft";
  current.updated_at = draftRevision.updated_at;
  setCandidateStatus(
    current.candidate_id,
    draftRevision.applied_hunk_ids.length ? "accepted" : "dismissed"
  );
  return delay(structuredClone(draftRevision));
}

export async function submitDraftRevisionForApproval(
  draftRevisionId: string
): Promise<TemplateDraftRevision> {
  if (!draftRevision || draftRevision.id !== draftRevisionId) {
    throw new Error("Create a draft revision first.");
  }
  if (draftRevision.status === "submitted_for_approval") {
    return delay(structuredClone(draftRevision));
  }
  const submittedAt = new Date().toISOString();
  const scenario = requireScenarioForCandidate(suggestion?.candidate_id ?? candidate.candidate_id);
  draftRevision = {
    ...draftRevision,
    status: "submitted_for_approval",
    validation_result: {
      valid: true,
      errors: [],
      approval_submission: {
        recipient_institution: scenario.legalDocument.issuer,
        submitted_at: submittedAt
      }
    },
    source_metadata: {
      ...draftRevision.source_metadata,
      approval_request: {
        recipient_institution: scenario.legalDocument.issuer,
        submitted_at: submittedAt,
        submission_status: "sent",
        submission_channel: "legal_review_workflow",
        source_legal_document_id: scenario.legalDocument.id,
        source_legal_document_title: scenario.legalDocument.title,
        source_legal_update_url: scenario.legalDocument.canonical_url
      }
    },
    updated_at: submittedAt
  };
  return delay(structuredClone(draftRevision));
}

function requireScenarioForCandidate(candidateId: string) {
  const scenario = scenarios.find((item) => item.candidate.candidate_id === candidateId);
  if (!scenario) throw new Error("Review candidate not found.");
  return scenario;
}

function updateHunkStatus(
  suggestionId: string,
  hunkId: string,
  status: TemplateChangeSuggestionHunkStatus
): Promise<TemplateChangeSuggestion> {
  const current = requireSuggestion(suggestionId);
  current.hunks = current.hunks.map((hunk) =>
    hunk.id === hunkId ? { ...hunk, status } : hunk
  );
  current.updated_at = new Date().toISOString();
  syncCandidateStatusFromSuggestion(current);
  return delay(structuredClone(current));
}

function requireSuggestion(suggestionId: string) {
  if (!suggestion || suggestion.id !== suggestionId) {
    throw new Error("Create a suggestion first.");
  }
  return suggestion;
}

function candidateWithStatus<T extends { candidate_id: string; status: string }>(
  current: T
) {
  return {
    ...current,
    status: candidateStatus(current)
  };
}

function candidateStatus(current: { candidate_id: string; status: string }) {
  return candidateStatuses.get(current.candidate_id) ?? (current.status as LegalChangeReviewStatus);
}

function setCandidateStatus(candidateId: string, status: LegalChangeReviewStatus) {
  candidateStatuses.set(candidateId, status);
}

function syncCandidateStatusFromSuggestion(current: TemplateChangeSuggestion) {
  if (current.hunks.length && current.hunks.every((hunk) => hunk.status === "rejected")) {
    setCandidateStatus(current.candidate_id, "dismissed");
    return;
  }
  if (candidateStatuses.get(current.candidate_id) === "dismissed") {
    setCandidateStatus(current.candidate_id, "needs_review");
  }
}

void draftRevision;
