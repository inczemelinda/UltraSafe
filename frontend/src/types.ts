export type UserRole = "client" | "employee";
export type QuoteDerivedValueSource = "backend" | "preview" | "unavailable";

export interface AppUser {
  id: string;
  role: UserRole;
  fullName: string;
  email: string;
  password: string;
  accessToken?: string;
  customerId?: string;
  customerProfileStatus?: CustomerProfileStatus | string | null;
  requiresCustomerProfileCompletion?: boolean;
  phone?: string;
  address?: string;
  nationalId?: string;
  title?: string;
}

export type PropertyType = "Apartment" | "House" | "Commercial";
export type ConstructionType = "Brick" | "Concrete" | "Wood" | "Steel";
export type UsageType =
  | "Owner occupied"
  | "Rented"
  | "Vacant"
  | "Holiday home"
  | "Commercial use";

export type SecurityFeature =
  | "Alarm"
  | "Smoke detector"
  | "Sprinklers"
  | "Security cameras"
  | "Security door"
  | "Security guard";

export type QuoteStatus =
  | "draft"
  | "submitted"
  | "in_review"
  | "approved"
  | "rejected"
  | "contract_generated"
  | "accepted_by_client"
  | "declined_by_client";

export type ContractStatus = "draft" | "generated" | "issued" | "active" | "expired" | "declined";

export type ClaimStatus =
  | "draft"
  | "submitted"
  | "in_review"
  | "accepted"
  | "rejected"
  | "inspection_requested"
  | "paid";

export type ClaimType = "Fire" | "Water damage" | "Theft" | "Storm" | "Other";

export interface AddressData {
  country: string;
  county: string;
  city: string;
  street: string;
  number: string;
  postal_code: string;
  full_text: string;
}

export interface CustomerData {
  type: "individual" | "company";
  full_name: string;
  national_id: string;
  company_id?: string;
  email: string;
  phone: string;
  address?: string;
}

export type CustomerProfileStatus =
  | "pending_customer_link"
  | "incomplete"
  | "complete";

export interface CustomerProfileAddress {
  country?: string | null;
  county?: string | null;
  city?: string | null;
  street?: string | null;
  number?: string | null;
  postal_code?: string | null;
  full_text?: string | null;
}

export interface CustomerProfile {
  customer_id?: number | null;
  status: CustomerProfileStatus;
  requires_customer_profile_completion: boolean;
  type?: "individual" | "company" | null;
  full_name?: string | null;
  national_id?: string | null;
  company_id?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: CustomerProfileAddress | null;
  missing_fields: string[];
  customer_profile_completed_at?: string | null;
  customer_profile_updated_at?: string | null;
  customer_profile_updated_by_auth_user_id?: number | null;
  customer_profile_completion_source?: string | null;
  profile_update_count?: number;
  linked_auth_user_count?: number | null;
  legal_documents?: CustomerLegalDocument[];
}

export interface CustomerLegalDocument {
  id: string;
  label: string;
  document_type: string;
  file_name: string;
  content_type?: string | null;
  size_bytes?: number | null;
  file_url?: string | null;
  source?: "client_profile" | "legal_document" | string;
  extracted_fields?: Record<string, unknown>;
  ai_interpretation?: string | null;
}

export interface CustomerProfileDocument {
  id: string;
  customer_id: number;
  label: string;
  document_type: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  storage_key: string;
  file_url?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CustomerAdminSummary extends CustomerProfile {
  id: string;
  profile_status: CustomerProfileStatus;
  legal_name?: string | null;
  customer_type?: "individual" | "company" | null;
}

export interface CustomerProfileDetail extends CustomerProfile {
  id: string;
  profile_status: CustomerProfileStatus;
}

export interface CustomerLinkedAuthUser {
  id: string;
  user_id?: number | null;
  auth_user_id?: number | null;
  email: string;
  role: string;
  full_name: string;
  client_id?: number | null;
  customer_profile_status?: string | null;
  requires_customer_profile_completion?: boolean;
  linked_at?: string | null;
  status?: string | null;
}

export interface CustomerAuthUserRelinkResult {
  auth_user_id: number;
  auth_user_email: string;
  old_customer_id?: number | null;
  old_customer_name?: string | null;
  new_customer_id: number;
  new_customer_name?: string | null;
  reason: string;
  changed_by_auth_user_id?: number | null;
  changed_at: string;
}

export interface CustomerEmailMessage {
  id: string;
  customer_id: number | string;
  case_id?: string | null;
  case_reference?: string | null;
  direction: "OUTBOUND" | "INBOUND" | string;
  status: "DRAFT" | "SENT" | "FAILED" | "RECEIVED" | string;
  to_email: string;
  from_email: string;
  subject: string;
  body_preview: string;
  body_text?: string | null;
  body_html?: string | null;
  provider?: string | null;
  provider_message_id?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  sent_at?: string | null;
  received_at?: string | null;
}

export interface SentEmailMessage {
  id: string;
  case_id?: string | null;
  direction: string;
  from_email: string;
  to_email: string;
  subject: string;
  body: string;
  status: string;
  provider_message_id?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  sent_at?: string | null;
}

export type AuthUserSearchRole = "client" | "employee" | "underwriter" | "admin";

export interface AuthUserSearchParams {
  query?: string;
  role?: AuthUserSearchRole;
  unlinkedOnly?: boolean;
  limit?: number;
}

export interface AuthUserSearchResult {
  id: number;
  email: string;
  role: AuthUserSearchRole;
  full_name: string;
  client_id?: number | null;
  customer_full_name?: string | null;
  is_active?: boolean;
  status?: string;
  created_at?: string | null;
}

export interface CustomerProfileUpdate {
  type?: "individual" | "company";
  full_name?: string;
  national_id?: string;
  company_id?: string;
  email?: string;
  phone?: string;
  address?: CustomerProfileAddress;
}

export interface InsuredAssetData {
  asset_type: PropertyType;
  usage_type: UsageType;
  construction_type: ConstructionType;
  year_built: number;
  floor?: string;
  area_sqm: number;
  declared_value: number;
  occupancy: UsageType;
  previous_claims_count: number;
  address: AddressData;
}

export interface RequestDetails {
  coverage_amount: number;
  security_features: SecurityFeature[];
  systems_updated?: string;
  location_risks?: string;
  high_value_items?: string;
  renovations?: string;
  long_vacancy?: string;
}

export interface PremiumPreviewAdjustment {
  code?: string;
  label: string;
  value: string;
  amountDelta: number;
}

export interface PricingBreakdown {
  basePremium: number;
  coverageAmount?: number;
  coverageRate?: number;
  propertyTypeMultiplier?: number;
  propertyUseMultiplier: number;
  sizeMultiplier?: number;
  constructionMultiplier: number;
  ageMultiplier: number;
  claimsMultiplier: number;
  securityDiscountPercent: number;
  manualReviewSurcharge: number;
  finalPremium: number;
  estimatedPremium?: number;
  adjustments?: PremiumPreviewAdjustment[];
  explanation: string[];
  currency?: string;
  ruleVersion?: string;
  source?: QuoteDerivedValueSource;
}

export interface RiskAssessment {
  riskScore: number;
  riskLevel: "Low" | "Medium" | "High";
  triggeredRules: string[];
  recommendation: string;
  requiresManualReview: boolean;
  ruleVersion?: string;
  source?: QuoteDerivedValueSource;
}

export interface Quote {
  id: string;
  requestId: string;
  clientId: string;
  clientName: string;
  propertyType: PropertyType;
  propertyAddress: string;
  yearBuilt: number;
  areaSqm: number;
  constructionType: ConstructionType;
  usageType: UsageType;
  coverageAmount: number;
  previousClaimsCount: number;
  securityFeatures: SecurityFeature[];
  premium: number;
  riskScore: number;
  riskReasons: string[];
  pricing: PricingBreakdown;
  pricingSource?: QuoteDerivedValueSource;
  riskSource?: QuoteDerivedValueSource;
  pricingRuleVersion?: string;
  riskRuleVersion?: string;
  riskLevel?: RiskAssessment["riskLevel"];
  requiresManualReview?: boolean;
  allowedActions?: string[];
  status: QuoteStatus;
  createdAt: string;
  updatedAt?: string;
  rejectionReason?: string;
  clientData: CustomerData;
  insuredData: InsuredAssetData;
  requestDetails: RequestDetails;
  attachments: MockDocument[];
}

export interface Contract {
  id: string;
  quoteId: string;
  clientId: string;
  clientName: string;
  propertyAddress: string;
  coverageAmount: number;
  premium: number;
  status: ContractStatus;
  generatedAt: string;
  policyPeriodStart: string;
  policyPeriodEnd: string;
  limits: Array<{ label: string; value: string }>;
  documentText: string;
}

export interface ContractAddressSnapshot {
  country: string;
  county: string;
  city: string;
  street: string;
  number: string;
  postal_code: string;
  full_text: string;
}

export interface ContractCustomerSummary {
  id?: number | null;
  type: string;
  full_name: string;
  national_id?: string | null;
  company_id?: string | null;
  email: string;
  phone: string;
  address?: ContractAddressSnapshot | null;
}

export interface ContractAssetSummary {
  id?: number | null;
  asset_type: string;
  usage_type: string;
  construction_type: string;
  year_built: number;
  floor?: number | null;
  area_sqm: number | string;
  declared_value: number | string;
  occupancy: string;
  previous_claims_count: number;
  address?: ContractAddressSnapshot | null;
}

export interface ContractPricingSummary {
  base_premium_ron: number | string;
  final_premium_ron: number | string;
  currency: string;
  payment_plan_type: string;
  installments: number;
}

export interface ContractDetail {
  id: string;
  contract_number: string;
  display_id?: string | null;
  displayId?: string | null;
  contractDisplayId?: string | null;
  document_type: string;
  document_version: string;
  status: ContractStatus | string;
  source_quote_request_id?: string | null;
  source_quote_id?: string | null;
  source_quote_document_id?: number | null;
  source_quote_acceptance_id?: number | null;
  issue_date: string;
  effective_date: string;
  expiration_date: string;
  jurisdiction: string;
  governing_law: string;
  currency: string;
  created_at: string;
  updated_at: string;
  customer?: ContractCustomerSummary | null;
  asset?: ContractAssetSummary | null;
  pricing?: ContractPricingSummary | null;
}

export type ContractSummary = ContractDetail;

export interface ClaimableContract {
  contract_id: string;
  contract_number: string;
  display_id?: string | null;
  displayId?: string | null;
  contractDisplayId?: string | null;
  policy_number: string;
  status: ContractStatus | string;
  effective_date: string;
  expiration_date?: string | null;
  insured_asset_id?: number | string | null;
  address?: ContractAddressSnapshot | null;
  coverage_amount?: number | string | null;
}

export interface ClaimableContractsResponse {
  items: ClaimableContract[];
}

export interface BackendValidationIssue {
  code: string;
  message: string;
  field?: string | null;
}

export interface ContractConversionValidation {
  can_convert: boolean;
  blocking_errors: BackendValidationIssue[];
  warnings: BackendValidationIssue[];
  model_gaps?: string[];
}

export interface QuoteContractResolution {
  quote_id: string;
  already_converted: boolean;
  conversion_status: "converted" | "eligible" | "blocked" | string;
  contract_id?: string | null;
  contract?: ContractDetail | null;
  validation: ContractConversionValidation;
}

export interface QuoteAcceptance {
  id: number;
  quote_request_id: string;
  quote_document_id: number;
  accepted_by_auth_user_id?: number | null;
  accepted_by_customer_id: number;
  signer_name: string;
  signer_email: string;
  signer_role?: string | null;
  accepted_at: string;
  acceptance_method: string;
  ip_address?: string | null;
  user_agent?: string | null;
  acceptance_statement: string;
  quote_content_hash: string;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
}

export interface QuoteAcceptanceInput {
  signer_name: string;
  signer_email: string;
  signer_role?: string | null;
  acceptance_statement: string;
}

export interface ContractDecline {
  id: number;
  contract_id: string;
  source_quote_request_id?: string | null;
  declined_by_auth_user_id?: number | null;
  declined_by_customer_id: number;
  reason?: string | null;
  declined_at: string;
  ip_address?: string | null;
  user_agent?: string | null;
  metadata?: Record<string, unknown>;
}

export interface QuoteDecisionAuditRecord {
  id: number;
  quote_request_id: string;
  previous_status: string;
  decision_status: string;
  reason?: string | null;
  decided_by_auth_user_id?: number | null;
  decided_by_name?: string | null;
  decided_by_email?: string | null;
  decided_at: string;
  metadata?: Record<string, unknown>;
}

export interface ContractConversionResult {
  quote_id: string;
  result: "created" | "already_exists" | "blocked" | string;
  contract_id?: string | null;
  contract?: ContractDetail | null;
  validation: ContractConversionValidation;
}

export interface GeneratedDocument {
  id: number;
  contract_id: string;
  document_type?: string | null;
  template_id: number;
  template_code?: string | null;
  template_version?: string | null;
  template_version_hash?: string | null;
  rendered_text: string;
  rendered_html?: string | null;
  payload_snapshot: Record<string, unknown>;
  generation_metadata: Record<string, unknown>;
  content_hash?: string | null;
  pdf_storage_key?: string | null;
  pdf_filename?: string | null;
  pdf_content_hash?: string | null;
  pdf_source_content_hash?: string | null;
  pdf_generated_at?: string | null;
  pdf_generation_metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  status: string;
}

export interface GeneratedDocumentPdfArtifact {
  document_id: number;
  contract_id: string;
  pdf_storage_key: string;
  pdf_content_hash: string;
  source_content_hash: string;
  pdf_generated_at: string;
  status: string;
  filename: string;
}

export interface MockDocument {
  id: string;
  label: string;
  fileName: string;
  type: "PDF" | "DOCX" | "JPG" | "PNG" | "ZIP";
  url?: string;
  fileUrl?: string;
  contentType?: string;
  sizeBytes?: number;
  storageKey?: string;
  metadata?: Record<string, unknown>;
}

export interface ClaimAttachmentMetadata {
  file_name: string;
  content_type: string;
  size_bytes: number;
  file_url?: string | null;
  metadata?: {
    storage_key?: string;
    [key: string]: unknown;
  };
}

export type ClaimReviewNextAction =
  | "request_evidence"
  | "manual_review"
  | "underwriter_review"
  | "coverage_review"
  | string;

export interface ClaimEvidenceRequirement {
  requirementType: string;
  reason: string;
  acceptableDocuments: string[];
  severity?: string;
  status?: string;
  suggestedNextAction?: string;
}

export interface EvidenceRequestDraft {
  draftId?: string;
  claimRequestId: string;
  subject: string;
  body: string;
  recipients?: string[];
  requiredDocuments: string[];
  status: "draft" | string;
  sourceSuggestionId?: string;
  requestedDocumentType?: string;
  dueDate?: string;
  sendStatus?: string;
  sentAt?: string;
  sentTo?: string[];
  providerMessageId?: string;
  emailMessageId?: string;
  replyToken?: string;
  sendErrorMessage?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface EvidenceRequestDraftResponse {
  needed: boolean;
  message: string;
  draft?: EvidenceRequestDraft | null;
}

export interface DemoInboundEmailResponse {
  message: string;
  to_email: string;
  subject: string;
  provider_message_id?: string | null;
  reply_token: string;
  attachment_file_name: string;
}

export interface EvidenceRequestDraftUpdate {
  subject: string;
  body: string;
  recipients?: string[];
  requiredDocuments?: string[];
  sourceSuggestionId?: string;
  requestedDocumentType?: string;
  dueDate?: string;
}

export interface ClaimCommunicationSuggestionState {
  suggestionId: string;
  status: string;
  source?: string;
  draftId?: string;
  dismissedAt?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface ClaimCoverageAssessment {
  coverageStatus: string;
  matchedWordingSections: string[];
  wordingSectionIds: string[];
  possibleExclusions: string[];
  rationale: string;
  confidence: string;
  assessedAt?: string;
}

export interface ClaimDocumentFinding {
  field: string;
  claimValue?: unknown;
  documentValue?: unknown;
  sourceDocument?: string;
  severity?: string;
  message: string;
}

export type AiReviewLifecycleStatus =
  | "not_started"
  | "processing"
  | "completed"
  | "failed"
  | "unavailable"
  | string;

export interface AiReviewFinding {
  id: string;
  claimId?: string;
  findingType: string;
  severity: string;
  description: string;
  relatedDocument?: string;
  relatedRequirement?: string;
  recommendation?: string;
  suggestedFollowUpAction?: string;
  confidence?: string;
  reviewStatus?: string;
  createdAt?: string;
  source?: string;
}

export interface SuggestedEmailDraft {
  subject: string;
  body: string;
  requestedDocumentType?: string;
  dueDate?: string;
}

export interface AiFollowUpSuggestion {
  id: string;
  claimId?: string;
  title: string;
  reason: string;
  recommendedRequest: string;
  priority: string;
  confidence: string;
  relatedRequirementId?: string;
  relatedDocumentId?: string;
  relatedRequirement?: string;
  relatedEvidenceIssue?: string;
  suggestedEmailSubject: string;
  suggestedEmailBody: string;
  suggestedEmailDraft?: SuggestedEmailDraft;
  status: string;
  createdAt?: string;
  warnings?: string[];
  fullReasoning?: string;
}

export interface ClaimDocumentConsistency {
  status: string;
  message?: string;
  supportingFactCount?: number;
  discrepancyCount?: number;
}

export interface Claim {
  id: string;
  displayClaimId?: string;
  contractId: string;
  contractDisplayId?: string;
  claimNumber?: string;
  claimReference?: string;
  publicId?: string;
  externalId?: string;
  clientId: string;
  clientName: string;
  policyNumber: string;
  propertyAddress: string;
  claimType: ClaimType;
  incidentDate: string;
  incidentTime: string;
  estimatedDamage: number;
  score: number;
  scoreReasons: string[];
  status: ClaimStatus;
  description: string;
  emergencyServices: boolean;
  hasPhotos: boolean;
  hasDocuments: boolean;
  contactPhone: string;
  contactEmail: string;
  evidence: MockDocument[];
  createdAt: string;
  rejectionReason?: string;
  internalNote?: string;
  decision?: "approved" | "denied" | "inspection_requested";
  decisionStatus?: "pending" | "submitted" | string;
  decisionJustification?: string;
  decidedBy?: string;
  decidedByEmail?: string;
  decidedAt?: string;
  decisionEmailSentAt?: string;
  decisionEmailMessageId?: string;
  reviewCaseId?: string;
  reviewState?: "not_started" | "coverage_precheck_only" | "full_review" | string;
  coverageAssessment?: ClaimCoverageAssessment;
  coveragePrecheck?: ClaimCoverageAssessment;
  documentConsistency?: ClaimDocumentConsistency;
  supportingFacts?: ClaimDocumentFinding[];
  discrepancies?: ClaimDocumentFinding[];
  suggestedNextAction?: ClaimReviewNextAction;
  requiredEvidence?: ClaimEvidenceRequirement[];
  aiReviewStatus?: AiReviewLifecycleStatus;
  aiReviewFindings?: AiReviewFinding[];
  aiFollowUpSuggestions?: AiFollowUpSuggestion[];
  communicationSuggestionStates?: Record<string, ClaimCommunicationSuggestionState>;
  humanReadableSummary?: string;
  evidenceRequestDraft?: EvidenceRequestDraft | null;
  availableActions?: string[];
}

export interface QuoteDraft {
  propertyType: PropertyType | "";
  address: AddressData;
  yearBuilt: string;
  areaSqm: string;
  constructionType: ConstructionType | "";
  usageType: UsageType | "";
  coverageAmount: string;
  hadClaims: "Yes" | "No" | "";
  previousClaimsCount: string;
  securityFeatures: SecurityFeature[];
  fullName: string;
  email: string;
  phone: string;
  nationalId: string;
  systemsUpdated: string;
  locationRisks: string;
  highValueItems: string;
  renovations: string;
  longVacancy: string;
}

export interface ClaimDraft {
  claimId?: string;
  contractId: string;
  policyNumber: string;
  fullName: string;
  propertyAddress: string;
  claimType: ClaimType | "";
  incidentDate: string;
  incidentTime: string;
  description: string;
  estimatedDamage: string;
  emergencyServices: "Yes" | "No" | "";
  photosFileName: string;
  documentsFileName: string;
  evidenceFiles?: Record<string, string>;
  attachments?: ClaimAttachmentMetadata[];
  phone: string;
  email: string;
}

export type UnderwritingRuleBlockKind = "list" | "notice" | "table";

export interface UnderwritingRuleBlock {
  id: string;
  kind: UnderwritingRuleBlockKind;
  text?: string;
  items?: string[];
  headers?: string[];
  rows?: string[][];
}

export interface UnderwritingRuleSection {
  id: string;
  title: string;
  blocks: UnderwritingRuleBlock[];
}

export interface UnderwritingRulesDocument {
  key: string;
  sections: UnderwritingRuleSection[];
  updated_at?: string | null;
  updated_by?: string | null;
}

export interface NewsStory {
  id: string;
  title: string;
  publishedAt: string;
  sourceCount: number;
  coverageLabel: string;
  rightCoverage: number;
  centerCoverage: number;
  leftCoverage: number;
  summary: string[];
  eventType?: string;
  severity?: string;
  relevance?: string;
  intelligenceStatus?: string;
  sourceName?: string;
  country?: string;
  lineOfBusiness?: string | null;
  topics?: string[];
  sourceLinks?: Array<{ label: string; url: string; contentType?: string | null }>;
}

export interface NewsStoryFilters {
  country?: string;
  lineOfBusiness?: string;
}

export type TemplateChangeSuggestionStatus =
  | "draft"
  | "accepted"
  | "rejected"
  | "superseded"
  | "applied_to_draft";

export type TemplateChangeSuggestionHunkStatus =
  | "draft"
  | "accepted"
  | "rejected"
  | "edited";

export type LegalChangeReviewStatus =
  | "needs_review"
  | "accepted"
  | "dismissed";

export type TemplateChangeType =
  | "replace"
  | "insert_before"
  | "insert_after"
  | "delete"
  | "manual_review";

export interface NormalizedLegalDocument {
  id: string;
  source_id: string;
  source_key: string;
  jurisdiction: string;
  parser_id: string;
  canonical_url: string;
  source_url: string;
  external_identifier?: string | null;
  title: string;
  language?: string | null;
  issuer?: string | null;
  instrument_type?: string | null;
  instrument_number?: string | null;
  instrument_year?: number | null;
  publication_reference?: string | null;
  publication_date?: string | null;
  effective_date?: string | null;
  status?: string | null;
  legal_references: Array<string | Record<string, unknown>>;
  amends: Array<string | Record<string, unknown>>;
  repeals: Array<string | Record<string, unknown>>;
  full_text: string;
  summary?: string | null;
  extraction_confidence: number;
  source_metadata: Record<string, unknown>;
}

export interface LegalTemplateReviewCandidate {
  candidate_id: string;
  normalized_legal_document_id: string;
  template_id: number;
  template_code: string;
  template_name: string;
  template_version: string;
  template_version_hash: string;
  match_type: string;
  matched_reference?: string | null;
  review_reason: string;
  confidence: number;
  status: LegalChangeReviewStatus | string;
  source_metadata: Record<string, unknown>;
}

export interface LegalChangeItem {
  legal_document: NormalizedLegalDocument;
  candidates: LegalTemplateReviewCandidate[];
  affected_template_count: number;
  highest_confidence: number;
}

export interface TemplateChangeSuggestionHunk {
  id: string;
  suggestion_id: string;
  section_id?: string | null;
  section_label?: string | null;
  templateSectionTitle?: string | null;
  templateArticleTitle?: string | null;
  beforeContext?: string | null;
  afterContext?: string | null;
  fullContextExcerpt?: string | null;
  startOffset?: number | null;
  endOffset?: number | null;
  template_section_title?: string | null;
  template_article_title?: string | null;
  before_context?: string | null;
  after_context?: string | null;
  full_context_excerpt?: string | null;
  start_offset?: number | null;
  end_offset?: number | null;
  change_type: TemplateChangeType;
  old_text: string;
  new_text: string;
  rationale: string;
  source_reference: string;
  confidence: number;
  status: TemplateChangeSuggestionHunkStatus;
  reviewer_notes?: string | null;
}

export interface TemplateChangeSuggestion {
  id: string;
  candidate_id: string;
  template_id: number;
  normalized_legal_document_id: string;
  template_version_hash: string;
  status: TemplateChangeSuggestionStatus;
  overall_summary: string;
  validation_result: Record<string, unknown>;
  hunks: TemplateChangeSuggestionHunk[];
  created_at: string;
  updated_at: string;
}

export interface TemplateChangeSuggestionDetail {
  suggestion: TemplateChangeSuggestion;
  candidate: LegalTemplateReviewCandidate;
  normalized_legal_document: NormalizedLegalDocument;
  template: {
    id?: number | null;
    template_code: string;
    name: string;
    version: string;
    document_type: string;
    is_active: boolean;
    content: string;
    jurisdiction?: string | null;
    product_line?: string | null;
    legal_references_json: string[];
    metadata_json: Record<string, unknown>;
    created_at: string;
  };
  draft_revision?: TemplateDraftRevision | null;
}

export interface TemplateDraftRevision {
  id: string;
  suggestion_id: string;
  template_id: number;
  template_code: string;
  template_name: string;
  base_template_version: string;
  base_template_version_hash: string;
  status: "draft" | "submitted_for_approval" | "accepted" | "rejected" | "superseded";
  base_content: string;
  revised_content: string;
  applied_hunk_ids: string[];
  validation_result: Record<string, unknown>;
  source_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

