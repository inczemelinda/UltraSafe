import { ChevronDown, Download, Pencil, Save } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Button,
  DataTable,
  DetailGrid,
  EmptyState,
  Modal,
  PageHeader,
  Panel,
  PremiumCounter,
  PrimaryLink,
  StatusBadge,
  UploadCard,
  formatCurrency,
  formatDate
} from "../components/ui";
import { WizardStepper } from "../components/client/WizardStepper";
import { GeneratedDocumentPdfViewer } from "../components/GeneratedDocumentPdfViewer";
import { AnimatedCardReveal, staggerCardDelay } from "../components/animations/AnimatedCardReveal";
import type { UploadCardFile } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import {
  createClaim,
  getClientClaims,
  getMyClaimById,
  uploadClaimAttachments
} from "../services/claimService";
import {
  downloadGeneratedDocumentPdf,
  convertQuoteToContract,
  declineMyContract,
  getClaimableContracts,
  getLatestMyContractDocument,
  getMyContract,
  getMyContracts,
  resolveQuoteContract
} from "../services/contractService";
import {
  getMyCustomerProfile,
  updateMyCustomerProfile
} from "../services/customerProfileService";
import {
  deleteMyProfileDocument,
  listMyProfileDocuments,
  uploadMyProfileDocument
} from "../services/profileDocumentService";
import {
  acceptQuote,
  createQuote,
  getClientQuotes,
  getMyQuoteAcceptance,
  getMyQuoteById
} from "../services/quoteService";
import type {
  Claim,
  ClaimAttachmentMetadata,
  ClaimableContract,
  ClaimDraft,
  ContractDetail,
  CustomerProfile,
  CustomerProfileDocument,
  CustomerProfileUpdate,
  GeneratedDocument,
  AppUser,
  MockDocument,
  Quote,
  QuoteAcceptance,
  QuoteDraft,
  SecurityFeature
} from "../types";
import { getPremiumPreviewBreakdown } from "../utils/pricing";
import {
  getQuotePremium,
  getQuotePricingSourceLabel,
  isQuotePricingUnavailable
} from "../utils/quotePricing";
import {
  getContractDisplayIdentifier,
  getContractLifecycleDisplayStatus,
  getContractLifecycleStatusLabel
} from "../utils/contractDisplay";
import { getClaimDisplayIdentifier } from "../utils/claimDisplay";

const quoteStepDefinitions = [
  { id: "propertyType", label: "Property" },
  { id: "address", label: "Address" },
  { id: "coverage", label: "Cover" },
  { id: "size", label: "Size" },
  { id: "age", label: "Year" },
  { id: "construction", label: "Structure" },
  { id: "use", label: "Use" },
  { id: "claims", label: "History" },
  { id: "security", label: "Safety" },
  { id: "contact", label: "Confirm" }
] as const;

type QuoteStepId = (typeof quoteStepDefinitions)[number]["id"];

const legacyQuoteStepIds: QuoteStepId[] = [
  "propertyType",
  "address",
  "age",
  "size",
  "construction",
  "use",
  "coverage",
  "claims",
  "security",
  "contact"
];

const quoteSteps = quoteStepDefinitions.map((step) => step.label);

const claimSteps = [
  "Claim",
  "Property",
  "Incident",
  "Damage",
  "Contact",
  "Documents"
];

const defaultClaimAddress = {
  country: "",
  county: "",
  city: "",
  street: "",
  number: "",
  postal_code: ""
};

const defaultQuoteDraft = (user?: AppUser | null): QuoteDraft => ({
  propertyType: "",
  address: {
    country: "Romania",
    county: "",
    city: "",
    street: "",
    number: "",
    postal_code: "",
    full_text: ""
  },
  yearBuilt: "",
  areaSqm: "",
  constructionType: "",
  usageType: "",
  coverageAmount: "",
  hadClaims: "",
  previousClaimsCount: "0",
  securityFeatures: [],
  fullName: user?.fullName ?? "",
  email: user?.email ?? "",
  phone: user?.phone ?? "",
  nationalId: user?.nationalId ?? "",
  systemsUpdated: "",
  locationRisks: "",
  highValueItems: "",
  renovations: "",
  longVacancy: ""
});

const accountDocumentLabels = [
  "ID document",
  "Property ownership document",
  "Land registry extract",
  "Existing policy document",
  "Bank document",
  "Property photos"
];

const requiredClaimDocumentLabels = ["Photos from incident"];
const claimDocumentLabels = [...requiredClaimDocumentLabels, ...accountDocumentLabels];
const listHeaderRevealDelay = 0;
const listTableRevealDelay = 0.16;

function ClientPageContent({
  children,
  className = ""
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`mx-auto w-full max-w-5xl ${className}`}>{children}</div>;
}

function ClientLoadingWait({
  title,
  description = "Please wait while we load the latest information.",
  className = ""
}: {
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div
      aria-busy="true"
      className={`flex min-h-[360px] w-full items-center justify-center px-5 py-8 text-center ${className}`}
      role="status"
    >
      <div>
        <span className="mx-auto block h-8 w-8 rounded-full border-2 border-white/35 border-t-white motion-safe:animate-spin" />
        <p className="mt-4 text-sm font-bold text-white drop-shadow-sm">{title}</p>
        <p className="mt-1 max-w-sm text-xs font-semibold text-white/75 drop-shadow-sm">{description}</p>
      </div>
    </div>
  );
}

function legacyAccountDocsKey(clientId?: string) {
  return `underwright_account_documents_${clientId ?? "client-001"}_v2`;
}

function clearLegacyAccountDocuments(clientId?: string) {
  try {
    window.localStorage.removeItem(legacyAccountDocsKey(clientId));
  } catch {
  }
}

type SavedQuoteDraft = {
  id: string;
  step: number;
  stepId?: QuoteStepId;
  draft: QuoteDraft;
  updatedAt: string;
};

type SavedClaimDraft = {
  id: string;
  step: number;
  draft: ClaimDraft;
  address: typeof defaultClaimAddress;
  evidenceFiles: Record<string, string>;
  evidenceFileMetadata?: Record<string, DraftUploadMetadata[]>;
  updatedAt: string;
};

type DraftUploadMetadata = {
  file_name: string;
  size_bytes?: number;
  content_type?: string;
  profile_document_id?: string;
  file_url?: string | null;
  label?: string;
};

type LocalDraftSummary = {
  id: string;
  title: string;
  description: string;
  statusLabel: string;
  updatedAt: string;
  href: string;
};

function quoteDraftKey(clientId?: string) {
  return `underwright_client_quote_draft_${clientId ?? "client-001"}_v1`;
}

function claimDraftKey(clientId?: string) {
  return `underwright_client_claim_draft_${clientId ?? "client-001"}_v1`;
}

function loadStoredDraft<T>(key: string): T | null {
  try {
    const stored = window.localStorage.getItem(key);
    return stored ? (JSON.parse(stored) as T) : null;
  } catch {
    return null;
  }
}

function saveStoredDraft<T>(key: string, draft: T) {
  try {
    window.localStorage.setItem(key, JSON.stringify(draft));
  } catch {}
}

function clearStoredDraft(key: string) {
  try {
    window.localStorage.removeItem(key);
  } catch {}
}

function loadQuoteFormDraft(clientId?: string) {
  return loadStoredDraft<SavedQuoteDraft>(quoteDraftKey(clientId));
}

function saveQuoteFormDraft(clientId: string | undefined, draft: SavedQuoteDraft) {
  saveStoredDraft(quoteDraftKey(clientId), draft);
}

function clearQuoteFormDraft(clientId?: string) {
  clearStoredDraft(quoteDraftKey(clientId));
}

function loadClaimFormDraft(clientId?: string) {
  return loadStoredDraft<SavedClaimDraft>(claimDraftKey(clientId));
}

function saveClaimFormDraft(clientId: string | undefined, draft: SavedClaimDraft) {
  saveStoredDraft(claimDraftKey(clientId), draft);
}

function clearClaimFormDraft(clientId?: string) {
  clearStoredDraft(claimDraftKey(clientId));
}

function makeGeneratedQuoteDraftId() {
  return `Q-DRAFT-${new Date().getFullYear()}-${String(Date.now()).slice(-5)}`;
}

function defaultClaimDraft(user: AppUser | null | undefined, claimId: string): ClaimDraft {
  return {
    claimId,
    contractId: "",
    policyNumber: "",
    fullName: user?.fullName ?? "",
    propertyAddress: "",
    claimType: "",
    incidentDate: "",
    incidentTime: "",
    description: "",
    estimatedDamage: "",
    emergencyServices: "",
    photosFileName: "",
    documentsFileName: "",
    phone: user?.phone ?? "",
    email: user?.email ?? ""
  };
}

function hydrateQuoteDraft(savedDraft: QuoteDraft, user?: AppUser | null) {
  const defaults = defaultQuoteDraft(user);
  return {
    ...defaults,
    ...savedDraft,
    fullName: defaults.fullName,
    email: defaults.email,
    phone: defaults.phone,
    nationalId: defaults.nationalId,
    address: {
      ...defaults.address,
      ...savedDraft.address
    }
  };
}

function hydrateClaimDraft(savedDraft: ClaimDraft, user: AppUser | null | undefined, claimId: string) {
  return {
    ...defaultClaimDraft(user, claimId),
    ...savedDraft,
    claimId: savedDraft.claimId ?? claimId
  };
}

function fieldFromCustomerProfile(
  currentValue: string,
  previousUserValue: string | undefined,
  profileValue: string | undefined
) {
  if (!currentValue.trim() || currentValue === (previousUserValue ?? "")) {
    return profileValue ?? "";
  }
  return currentValue;
}

function quoteDraftWithCustomerProfile(
  draft: QuoteDraft,
  profileForm: CustomerProfileFormState,
  profileUser: AppUser,
  previousUser?: AppUser | null
): QuoteDraft {
  return {
    ...draft,
    fullName: profileForm.fullName || profileUser.fullName || "",
    phone: profileForm.phone || profileUser.phone || "",
    email: profileForm.email || profileUser.email || "",
    nationalId: profileForm.nationalId || profileUser.nationalId || "",
    address: quoteAddressWithCustomerProfile(draft.address, profileForm, previousUser)
  };
}

function quoteAddressWithCustomerProfile(
  currentAddress: QuoteDraft["address"],
  profileForm: CustomerProfileFormState,
  previousUser?: AppUser | null
) {
  const previousDefaults = defaultQuoteDraft(previousUser).address;
  const profileAddress = {
    ...profileForm.address,
    full_text: formatClaimAddress(profileForm.address)
  };
  return (Object.keys(currentAddress) as Array<keyof QuoteDraft["address"]>).reduce(
    (nextAddress, field) => ({
      ...nextAddress,
      [field]: fieldFromCustomerProfile(
        currentAddress[field],
        previousDefaults[field],
        profileAddress[field]
      )
    }),
    currentAddress
  );
}

function claimDraftWithCustomerProfile(
  draft: ClaimDraft,
  profileUser: AppUser,
  previousUser?: AppUser | null
): ClaimDraft {
  return {
    ...draft,
    fullName: fieldFromCustomerProfile(draft.fullName, previousUser?.fullName, profileUser.fullName),
    phone: fieldFromCustomerProfile(draft.phone, previousUser?.phone, profileUser.phone),
    email: fieldFromCustomerProfile(draft.email, previousUser?.email, profileUser.email)
  };
}

function clampDraftStep(value: number | undefined, totalSteps: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(Math.max(Number(value), 0), totalSteps - 1);
}

function getQuoteStepIndex(stepId: QuoteStepId) {
  const index = quoteStepDefinitions.findIndex((step) => step.id === stepId);
  return index >= 0 ? index : 0;
}

function getQuoteStepId(stepIndex: number) {
  return quoteStepDefinitions[clampDraftStep(stepIndex, quoteStepDefinitions.length)].id;
}

function hasValidQuoteCoverageAmount(draft: QuoteDraft) {
  const coverageAmount = Number(draft.coverageAmount);
  return Number.isFinite(coverageAmount) && coverageAmount > 0;
}

function resolveSavedQuoteStep(saved?: SavedQuoteDraft | null) {
  if (!saved) return 0;
  if (saved.stepId) return getQuoteStepIndex(saved.stepId);
  const legacyStepId = legacyQuoteStepIds[clampDraftStep(saved.step, legacyQuoteStepIds.length)];
  return getQuoteStepIndex(legacyStepId);
}

function hasQuoteDraftContent(draft: QuoteDraft, user?: AppUser | null) {
  const defaults = defaultQuoteDraft(user);
  const addressChanged = (Object.keys(draft.address) as Array<keyof QuoteDraft["address"]>).some(
    (field) => draft.address[field] !== defaults.address[field]
  );
  const contactChanged = (["fullName", "email", "phone", "nationalId"] as const).some(
    (field) => draft[field] !== defaults[field]
  );

  return Boolean(
    addressChanged ||
      contactChanged ||
      draft.propertyType ||
      draft.yearBuilt ||
      draft.areaSqm ||
      draft.constructionType ||
      draft.usageType ||
      draft.coverageAmount ||
      draft.hadClaims ||
      (draft.previousClaimsCount && draft.previousClaimsCount !== "0") ||
      draft.securityFeatures.length ||
      draft.systemsUpdated ||
      draft.locationRisks ||
      draft.highValueItems ||
      draft.renovations ||
      draft.longVacancy
  );
}

function hasClaimDraftContent(
  draft: ClaimDraft,
  address: typeof defaultClaimAddress,
  evidenceFiles: Record<string, string>,
  user?: AppUser | null,
  prefilledEvidenceFiles: Record<string, string> = {}
) {
  const defaults = defaultClaimDraft(user, draft.claimId ?? "");
  const addressChanged = Boolean(draft.contractId);
  const contactChanged = (["fullName", "email", "phone"] as const).some(
    (field) => draft[field] !== defaults[field]
  );
  const evidenceChanged = claimDocumentLabels.some(
    (label) => Boolean(evidenceFiles[label]) && evidenceFiles[label] !== prefilledEvidenceFiles[label]
  );

  return Boolean(
    addressChanged ||
      contactChanged ||
      evidenceChanged ||
      draft.claimType ||
      draft.incidentDate ||
      draft.incidentTime ||
      draft.description ||
      draft.estimatedDamage ||
      draft.emergencyServices
  );
}

function fileMetadataFromFiles(files: File[]): DraftUploadMetadata[] {
  return files.map((file) => ({
    file_name: file.name,
    size_bytes: file.size,
    content_type: file.type || undefined
  }));
}

function metadataFromEvidenceFiles(evidenceFiles: Record<string, string>) {
  return Object.fromEntries(
    Object.entries(evidenceFiles)
      .map(([label, fileNames]) => [
        label,
        splitEvidenceFileNames(fileNames).map((fileName) => ({
          file_name: fileName
        }))
      ])
      .filter(([, files]) => files.length)
  ) as Record<string, DraftUploadMetadata[]>;
}

function evidenceFilesFromProfileDocuments(documents: CustomerProfileDocument[]) {
  return Object.fromEntries(
    documents
      .filter((document) => accountDocumentLabels.includes(document.label))
      .map((document) => [document.label, document.file_name])
  ) as Record<string, string>;
}

function metadataFromProfileDocuments(documents: CustomerProfileDocument[]) {
  return Object.fromEntries(
    documents
      .filter((document) => accountDocumentLabels.includes(document.label))
      .map((document) => [
        document.label,
        [
          {
            file_name: document.file_name,
            size_bytes: document.size_bytes,
            content_type: document.content_type,
            profile_document_id: document.id,
            file_url: document.file_url,
            label: document.label
          }
        ]
      ])
  ) as Record<string, DraftUploadMetadata[]>;
}

function documentsByLabel(documents: CustomerProfileDocument[]) {
  return Object.fromEntries(documents.map((document) => [document.label, document]));
}

function splitEvidenceFileNames(fileNames?: string) {
  return (fileNames ?? "")
    .split(",")
    .map((fileName) => fileName.trim())
    .filter(Boolean);
}

function joinedFileNames(files: File[]) {
  return files.map((file) => file.name).join(", ");
}

function displayFilesForLabel(
  label: string,
  evidenceFiles: Record<string, string>,
  evidenceFileMetadata: Record<string, DraftUploadMetadata[]>
): UploadCardFile[] {
  const metadata = evidenceFileMetadata[label];
  if (metadata?.length) {
    return metadata;
  }
  return splitEvidenceFileNames(evidenceFiles[label]).map((fileName) => ({
    file_name: fileName
  }));
}

function hasEvidenceForLabel(evidenceFiles: Record<string, string>, label: string) {
  return splitEvidenceFileNames(evidenceFiles[label]).length > 0;
}

function flattenSelectedEvidenceFiles(
  selectedFilesByLabel: Record<string, File[]>
) {
  return claimDocumentLabels.flatMap((label) =>
    (selectedFilesByLabel[label] ?? []).map((file) => ({ label, file }))
  );
}

function documentRoleForEvidenceLabel(label: string): string {
  switch (label) {
    case "ID document":
      return "identity_document";
    case "Property ownership document":
    case "Land registry extract":
      return "land_registry";
    case "Existing policy document":
      return "existing_policy";
    case "Bank document":
      return "bank_document";
    case "Property photos":
      return "property_photo_before";
    case "Photos from incident":
      return "property_photo_after";
    default:
      return "";
  }
}

function profileDocumentAttachmentsForClaim(
  evidenceFileMetadata: Record<string, DraftUploadMetadata[]>,
  selectedFilesByLabel: Record<string, File[]>
): ClaimAttachmentMetadata[] {
  return accountDocumentLabels.flatMap((label) => {
    if (selectedFilesByLabel[label]?.length) return [];
    return (evidenceFileMetadata[label] ?? [])
      .filter((file) => file.profile_document_id)
      .map((file) => ({
        file_name: file.file_name,
        content_type: file.content_type || "application/octet-stream",
        size_bytes: file.size_bytes ?? 0,
        file_url: file.file_url ?? `/me/customer-profile/documents/${file.profile_document_id}/download`,
        metadata: {
          label,
          document_role: documentRoleForEvidenceLabel(label),
          source: "client_profile",
          profile_document_id: file.profile_document_id
        }
      }));
  });
}

function labelUploadedAttachments(
  attachments: ClaimAttachmentMetadata[],
  selectedFiles: Array<{ label: string; file: File }>
): ClaimAttachmentMetadata[] {
  return attachments.map((attachment, index) => ({
    ...attachment,
    metadata: {
      ...(attachment.metadata ?? {}),
      label: selectedFiles[index]?.label
    }
  }));
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function isSavedQuoteDraftVisible(saved: SavedQuoteDraft, user?: AppUser | null) {
  return saved.step > 0 || hasQuoteDraftContent(hydrateQuoteDraft(saved.draft, user), user);
}

function isSavedClaimDraftVisible(saved: SavedClaimDraft, user?: AppUser | null) {
  const claimId = saved.id || saved.draft.claimId || "";
  return hasClaimDraftContent(
    hydrateClaimDraft(saved.draft, user, claimId),
    saved.address ?? defaultClaimAddress,
    saved.evidenceFiles ?? {},
    user
  );
}

function formatQuoteAddress(address: QuoteDraft["address"]) {
  return [
    `${address.street} ${address.number}`.trim(),
    address.city,
    address.county,
    address.country,
    address.postal_code
  ].filter(Boolean).join(", ");
}

function formatDraftQuoteAddress(address: QuoteDraft["address"]) {
  const hasEnteredAddress = Boolean(
    address.county ||
      address.city ||
      address.street ||
      address.number ||
      address.postal_code ||
      (address.country && address.country !== "Romania")
  );
  return hasEnteredAddress ? formatQuoteAddress(address) : "";
}

function buildLocalQuoteDraftSummary(saved: SavedQuoteDraft, user?: AppUser | null): LocalDraftSummary {
  const draft = hydrateQuoteDraft(saved.draft, user);
  const propertyAddress = formatDraftQuoteAddress(draft.address);
  const coverageAmount = Number(draft.coverageAmount);

  return {
    id: "local-quote-draft",
    title: propertyAddress || draft.propertyType || "Quote draft",
    description: Number.isFinite(coverageAmount) && coverageAmount > 0
      ? `Coverage ${formatCurrency(coverageAmount)}`
      : quoteStepDefinitions[resolveSavedQuoteStep(saved)]?.label ?? "Quote details",
    statusLabel: "Not submitted",
    updatedAt: saved.updatedAt,
    href: "/client/quote/new"
  };
}

function buildLocalClaimDraftSummary(saved: SavedClaimDraft, user?: AppUser | null): LocalDraftSummary {
  const draft = hydrateClaimDraft(saved.draft, user, saved.id);

  return {
    id: "local-claim-draft",
    title: draft.claimType || "Claim draft",
    description: draft.propertyAddress || "Claim details saved locally",
    statusLabel: "Not submitted",
    updatedAt: saved.updatedAt,
    href: "/client/claims/new"
  };
}

function loadVisibleQuoteDraftSummary(user?: AppUser | null) {
  const saved = loadQuoteFormDraft(user?.id);
  if (!saved || !isSavedQuoteDraftVisible(saved, user)) return null;
  return buildLocalQuoteDraftSummary(saved, user);
}

function loadVisibleClaimDraftSummary(user?: AppUser | null) {
  const saved = loadClaimFormDraft(user?.id);
  if (!saved || !isSavedClaimDraftVisible(saved, user)) return null;
  return buildLocalClaimDraftSummary(saved, user);
}

function getClientQuoteStatus(quote: Quote) {
  if (quote.status === "rejected" || quote.status === "declined_by_client") return "Rejected";
  if (quote.status === "draft") return "Draft";
  if (quote.status === "in_review" || quote.status === "submitted") return "In Review";
  return "Accepted";
}

function QuotePremiumValue({ quote }: { quote: Quote }) {
  const pricingUnavailable = isQuotePricingUnavailable(quote);
  return (
    <span className="inline-flex flex-col gap-0.5">
      <span>{pricingUnavailable ? "Pricing unavailable" : formatCurrency(getQuotePremium(quote))}</span>
      <span className="text-xs font-semibold text-slate-500">
        {getQuotePricingSourceLabel(quote)}
      </span>
    </span>
  );
}

function getClientClaimStatus(claim: Claim) {
  if (claim.status === "draft") return "Draft";
  if (claim.status === "inspection_requested") return "Inspection Request";
  if (claim.status === "rejected") return "Rejected";
  if (claim.status === "submitted" || claim.status === "in_review") return "Submitted";
  if (claim.status === "accepted" || claim.status === "paid") return "Approved";
  return "Declined";
}

function LocalDraftsSection({
  ariaLabel,
  drafts
}: {
  ariaLabel: string;
  drafts: LocalDraftSummary[];
}) {
  if (!drafts.length) return null;

  return (
    <Panel animated className="mb-4 shrink-0 border-amber-200 bg-amber-50/80" revealDelay={0.08}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-amber-700">Drafts</p>
          <h2 className="text-sm font-bold text-slate-950">Saved on this device</h2>
        </div>
        <span className="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800 ring-1 ring-inset ring-amber-200">
          Local draft
        </span>
      </div>
      <ul aria-label={ariaLabel} className="mt-3 divide-y divide-amber-200 overflow-hidden rounded-lg bg-white/80 ring-1 ring-amber-200">
        {drafts.map((draft) => (
          <li key={draft.id}>
            <Link
              className="grid gap-2 px-3 py-3 text-sm transition hover:bg-amber-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-amber-300 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
              to={draft.href}
            >
              <span className="min-w-0">
                <span className="block truncate font-bold text-slate-950">{draft.title}</span>
                <span className="mt-0.5 block truncate text-xs font-semibold text-slate-500">{draft.description}</span>
              </span>
              <span className="flex flex-wrap items-center gap-2 text-xs font-bold text-slate-500 sm:justify-end">
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-700">{draft.statusLabel}</span>
                <span>Updated {formatDate(draft.updatedAt)}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function numberValue(value: number | string | null | undefined) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function isLegacyContractRouteId(contractId: string) {
  return contractId.startsWith("C-");
}

function quoteIdFromLegacyContractRoute(contractId: string) {
  return contractId.slice(2);
}

async function getLinkedQuote(contract: ContractDetail) {
  const quoteId = contract.source_quote_request_id ?? contract.source_quote_id;
  if (!quoteId) return undefined;
  try {
    return await getMyQuoteById(quoteId);
  } catch {
    return undefined;
  }
}

function hasGeneratedDocumentPdf(document?: GeneratedDocument) {
  return Boolean(
    document?.pdf_storage_key ||
    document?.pdf_filename ||
    document?.pdf_content_hash ||
    document?.pdf_generated_at
  );
}

function GeneratedDocumentPdfLink({
  document,
  label = "Download PDF"
}: {
  document?: GeneratedDocument;
  label?: string;
}) {
  const { showToast } = useToast();
  const [downloading, setDownloading] = useState(false);
  if (!document || !hasGeneratedDocumentPdf(document)) return null;

  async function downloadPdf() {
    if (!document || downloading) return;
    setDownloading(true);
    try {
      const result = await downloadGeneratedDocumentPdf(document.id, { clientScoped: true });
      triggerBlobDownload(result.blob, result.filename ?? `contract-${document.contract_id}.pdf`);
    } catch (error) {
      showToast(errorMessage(error, "Could not download PDF."), "error");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <button
      className="inline-flex min-h-8 items-center justify-center gap-2 rounded-md bg-orange-600 px-3 py-1 text-xs font-semibold text-white transition hover:bg-orange-600 focus:outline-none focus:ring-4 focus:ring-orange-100"
      onClick={() => void downloadPdf()}
      type="button"
    >
      <Download className="h-4 w-4" />
      {downloading ? "Downloading" : label}
    </button>
  );
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}

function makeGeneratedClaimId() {
  return `CL-${new Date().getFullYear()}-${String(Date.now()).slice(-5)}`;
}

type CustomerProfileFormState = {
  type: "individual" | "company";
  fullName: string;
  nationalId: string;
  companyId: string;
  email: string;
  phone: string;
  address: {
    country: string;
    county: string;
    city: string;
    street: string;
    number: string;
    postal_code: string;
  };
};

function requiresProfileCompletion(user?: AppUser | null) {
  return Boolean(
    user?.role === "client" &&
    (user.requiresCustomerProfileCompletion ||
      user.customerProfileStatus !== "complete" ||
      !user.customerId)
  );
}

function CustomerProfileRequiredScreen({ context }: { context: "quote" | "claim" }) {
  return (
    <ClientPageContent>
      <PageHeader
        description={
          context === "quote"
            ? "Legal and address details are required before quote submission."
            : "Legal and address details are required before claim submission."
        }
        title="Complete Customer Profile"
      />
      <CustomerProfilePanel />
    </ClientPageContent>
  );
}

function CustomerProfilePanel() {
  const { user, setUser } = useAuth();
  const { showToast } = useToast();
  const [form, setForm] = useState<CustomerProfileFormState>(() =>
    customerProfileFormFromUser(user)
  );
  const [profile, setProfile] = useState<CustomerProfile>();
  const [editingProfile, setEditingProfile] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(Boolean(user));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!user) {
      setLoadingProfile(false);
      return;
    }
    let cancelled = false;
    setLoadingProfile(true);
    void getMyCustomerProfile()
      .then((loaded) => {
        if (cancelled) return;
        setProfile(loaded);
        setForm(customerProfileFormFromProfile(loaded, user));
        setEditingProfile(false);
        setError(undefined);
      })
      .catch((loadError) => {
        if (!cancelled) setError(errorMessage(loadError, "Could not load customer profile."));
      })
      .finally(() => {
        if (!cancelled) setLoadingProfile(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  async function saveProfile() {
    if (!user || saving) return;
    const missing = missingCustomerProfileFields(form);
    if (missing.length) {
      showToast(`Please complete: ${missing.join(", ")}.`, "error");
      return;
    }
    setSaving(true);
    setError(undefined);
    try {
      const updatedProfile = await updateMyCustomerProfile(customerProfilePayload(form));
      setProfile(updatedProfile);
      setUser(appUserWithCustomerProfile(user, updatedProfile, form));
      setEditingProfile(false);
      showToast("Customer profile saved.");
    } catch (saveError) {
      setError(errorMessage(saveError, "Could not save customer profile."));
    } finally {
      setSaving(false);
    }
  }

  function updateField(field: keyof Omit<CustomerProfileFormState, "address">, value: string) {
    if (!editingProfile) return;
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateAddress(field: keyof CustomerProfileFormState["address"], value: string) {
    if (!editingProfile) return;
    setForm((current) => ({
      ...current,
      address: { ...current.address, [field]: value }
    }));
  }

  function cancelProfileEdit() {
    setForm(profile ? customerProfileFormFromProfile(profile, user) : customerProfileFormFromUser(user));
    setEditingProfile(false);
    setError(undefined);
  }

  if (loadingProfile) {
    return <ClientLoadingWait className="h-full" title="Loading customer profile" />;
  }

  return (
    <Panel animated className="flex h-full flex-col">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-950">Customer Profile</h2>
        </div>
        <StatusBadge status={profile?.status === "complete" ? "Complete" : "Incomplete"} />
      </div>
      {error ? (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">
          {error}
        </p>
      ) : null}
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <SelectInput
          disabled={!editingProfile}
          label="Customer type"
          onChange={(value) => updateField("type", value as CustomerProfileFormState["type"])}
          options={[["individual", "Individual"], ["company", "Company"]]}
          value={form.type}
        />
        <TextInput
          disabled={!editingProfile}
          label={form.type === "company" ? "Legal company name" : "Legal full name"}
          onChange={(value) => updateField("fullName", value)}
          value={form.fullName}
        />
        {form.type === "company" ? (
          <TextInput disabled={!editingProfile} label="Company registration number" onChange={(value) => updateField("companyId", value)} value={form.companyId} />
        ) : (
          <TextInput disabled={!editingProfile} label="National ID" onChange={(value) => updateField("nationalId", value)} value={form.nationalId} />
        )}
        <TextInput disabled={!editingProfile} label="Email" onChange={(value) => updateField("email", value)} value={form.email} />
        <TextInput disabled={!editingProfile} label="Phone" onChange={(value) => updateField("phone", value)} value={form.phone} />
      </div>
      <div className="mt-5 grid gap-4 md:grid-cols-3">
        <TextInput disabled={!editingProfile} label="Country" onChange={(value) => updateAddress("country", value)} value={form.address.country} />
        <TextInput disabled={!editingProfile} label="County" onChange={(value) => updateAddress("county", value)} value={form.address.county} />
        <TextInput disabled={!editingProfile} label="City" onChange={(value) => updateAddress("city", value)} value={form.address.city} />
        <TextInput disabled={!editingProfile} label="Street" onChange={(value) => updateAddress("street", value)} value={form.address.street} />
        <TextInput disabled={!editingProfile} label="Number" onChange={(value) => updateAddress("number", value)} value={form.address.number} />
        <TextInput disabled={!editingProfile} label="Postal code" onChange={(value) => updateAddress("postal_code", value)} value={form.address.postal_code} />
      </div>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-4">
        <p className="text-xs font-semibold text-slate-500">
          {profile?.customer_profile_updated_at
            ? `Updated ${formatDate(profile.customer_profile_updated_at)}`
            : "Profile audit metadata will appear after save."}
        </p>
        <div className="flex flex-wrap justify-end gap-2">
          {editingProfile ? (
            <>
              <Button disabled={saving} onClick={cancelProfileEdit}>
                Cancel
              </Button>
              <Button disabled={saving} icon={Save} onClick={() => void saveProfile()} variant="primary">
                {saving ? "Saving..." : "Save Profile"}
              </Button>
            </>
          ) : (
            <Button icon={Pencil} onClick={() => setEditingProfile(true)} variant="primary">
              Edit
            </Button>
          )}
        </div>
      </div>
    </Panel>
  );
}

function customerProfilePayload(form: CustomerProfileFormState): CustomerProfileUpdate {
  return {
    type: form.type,
    full_name: form.fullName,
    national_id: form.type === "individual" ? form.nationalId : undefined,
    company_id: form.type === "company" ? form.companyId : undefined,
    email: form.email,
    phone: form.phone,
    address: {
      ...form.address,
      full_text: formatClaimAddress(form.address)
    }
  };
}

function customerProfileFormFromUser(user?: AppUser | null): CustomerProfileFormState {
  return {
    type: "individual",
    fullName: user?.fullName ?? "",
    nationalId: user?.nationalId ?? "",
    companyId: "",
    email: user?.email ?? "",
    phone: user?.phone ?? "",
    address: {
      country: "Romania",
      county: "",
      city: "",
      street: "",
      number: "",
      postal_code: ""
    }
  };
}

function customerProfileFormFromProfile(
  profile: CustomerProfile,
  user?: AppUser | null
): CustomerProfileFormState {
  const address = profile.address ?? {};
  return {
    type: profile.type ?? "individual",
    fullName: profile.full_name ?? user?.fullName ?? "",
    nationalId: profile.national_id ?? user?.nationalId ?? "",
    companyId: profile.company_id ?? "",
    email: profile.email ?? user?.email ?? "",
    phone: profile.phone ?? user?.phone ?? "",
    address: {
      country: address.country ?? "Romania",
      county: address.county ?? "",
      city: address.city ?? "",
      street: address.street ?? "",
      number: address.number ?? "",
      postal_code: address.postal_code ?? ""
    }
  };
}

function missingCustomerProfileFields(form: CustomerProfileFormState) {
  const missing: string[] = [];
  if (!form.fullName.trim()) missing.push("legal name");
  if (!form.email.trim()) missing.push("email");
  if (!form.phone.trim()) missing.push("phone");
  if (form.type === "individual" && !form.nationalId.trim()) missing.push("national ID");
  if (form.type === "company" && !form.companyId.trim()) missing.push("company registration number");
  if (!form.address.country.trim()) missing.push("country");
  if (!form.address.county.trim()) missing.push("county");
  if (!form.address.city.trim()) missing.push("city");
  if (!form.address.street.trim()) missing.push("street");
  if (!form.address.number.trim()) missing.push("number");
  if (!form.address.postal_code.trim()) missing.push("postal code");
  return missing;
}

function appUserWithCustomerProfile(
  user: AppUser,
  profile: CustomerProfile,
  form: CustomerProfileFormState
): AppUser {
  const customerId = profile.customer_id ? String(profile.customer_id) : user.customerId;
  return {
    ...user,
    id: customerId ?? user.id,
    customerId,
    customerProfileStatus: profile.status,
    requiresCustomerProfileCompletion: profile.requires_customer_profile_completion,
    fullName: profile.full_name ?? form.fullName,
    email: profile.email ?? form.email,
    phone: profile.phone ?? form.phone,
    nationalId: profile.national_id ?? form.nationalId,
    address: profile.address?.full_text ?? formatClaimAddress(form.address)
  };
}

export function ClientHomePage() {
  const { user } = useAuth();
  const [dashboard, setDashboard] = useState<{
    quotes: Quote[];
    contracts: ContractDetail[];
    claims: Claim[];
    loading: boolean;
  }>({ quotes: [], contracts: [], claims: [], loading: true });
  const firstName = clientFirstName(user);
  const activeContracts = dashboard.contracts.filter((contract) => String(contract.status).toLowerCase() === "active");
  const latestContract = activeContracts[0] ?? dashboard.contracts[0];
  const openClaims = dashboard.claims.filter((claim) =>
    !["paid", "accepted", "rejected"].includes(String(claim.status).toLowerCase())
  );
  const latestQuote = dashboard.quotes[0];
  const contractPremium = latestContract?.pricing?.final_premium_ron;
  const premiumValue = Number(contractPremium ?? (latestQuote ? getQuotePremium(latestQuote) : 0));
  const coverageValue = Number(latestContract?.asset?.declared_value ?? latestQuote?.coverageAmount ?? 0);
  const propertyAddress = latestContract?.asset?.address?.full_text ?? latestQuote?.propertyAddress ?? user?.address ?? "No property yet";
  const nextDate = latestContract?.expiration_date ? formatDate(latestContract.expiration_date) : "After contract issue";

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      try {
        const [quotes, contracts, claims] = await Promise.all([
          getClientQuotes(),
          getMyContracts(),
          getClientClaims()
        ]);
        if (!cancelled) {
          setDashboard({ quotes, contracts, claims, loading: false });
        }
      } catch {
        if (!cancelled) {
          setDashboard({ quotes: [], contracts: [], claims: [], loading: false });
        }
      }
    }

    loadDashboard();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto w-full max-w-7xl">
      {requiresProfileCompletion(user) ? (
        <div className="mb-5">
          <CustomerProfilePanel />
        </div>
      ) : null}

      <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-lg sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-orange-600">Client dashboard</p>
            <h1 className="mt-2 text-4xl font-extrabold leading-tight text-zinc-950 sm:text-5xl">
              Welcome back{firstName ? `, ${firstName}` : ""}.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-600">
              Your quotes, contracts, and claims are organized in one place and ready whenever you need them.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <PrimaryLink to="/client/quote/new">Start a quote</PrimaryLink>
            <PrimaryLink to="/client/claims/new">Report a claim</PrimaryLink>
          </div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <ClientDashboardStat
            label="Active contracts"
            value={dashboard.loading ? "..." : String(activeContracts.length || dashboard.contracts.length)}
            detail={latestContract ? getContractLifecycleStatusLabel(latestContract.status) : "No active contract"}
          />
          <ClientDashboardStat
            label="Premium"
            value={dashboard.loading ? "..." : formatCurrency(premiumValue)}
            detail={latestQuote ? getQuotePricingSourceLabel(latestQuote) : "Latest available pricing"}
          />
          <ClientDashboardStat
            label="Coverage"
            value={dashboard.loading ? "..." : formatCurrency(coverageValue)}
            detail={propertyAddress}
          />
          <ClientDashboardStat
            label="Open claims"
            value={dashboard.loading ? "..." : String(openClaims.length)}
            detail={openClaims[0] ? getClaimDisplayIdentifier(openClaims[0]) : "No claim needs action"}
          />
        </div>
      </section>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
        <Panel animated className="p-0" revealDelay={0.08}>
          <div className="border-b border-zinc-200 p-5">
            <h2 className="text-lg font-extrabold text-zinc-950">Current policy snapshot</h2>
            <p className="mt-1 text-sm leading-6 text-zinc-600">
              A readable summary of the latest contract or quote in your account.
            </p>
          </div>
          <div className="grid gap-4 p-5 md:grid-cols-3">
            <div className="rounded-xl bg-zinc-950 p-4 text-white">
              <div className="text-xs font-bold uppercase tracking-[0.12em] text-white/60">Next renewal</div>
              <div className="mt-4 text-2xl font-extrabold">{nextDate}</div>
              <div className="mt-2 text-sm text-white/60">{latestContract?.contract_number ?? latestQuote?.requestId ?? "Quote pending"}</div>
            </div>
            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 md:col-span-2">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="text-xs font-bold uppercase tracking-[0.12em] text-zinc-500">Insured property</div>
                  <div className="mt-2 text-lg font-extrabold text-zinc-950">{propertyAddress}</div>
                  <div className="mt-1 text-sm font-semibold text-zinc-500">
                    {latestContract?.asset?.asset_type ?? latestQuote?.propertyType ?? "Property details pending"}
                  </div>
                </div>
                <StatusBadge status={latestContract?.status ?? latestQuote?.status ?? "draft"} />
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <MiniFact label="Quotes" value={dashboard.loading ? "..." : String(dashboard.quotes.length)} />
                <MiniFact label="Contracts" value={dashboard.loading ? "..." : String(dashboard.contracts.length)} />
                <MiniFact label="Claims" value={dashboard.loading ? "..." : String(dashboard.claims.length)} />
              </div>
            </div>
          </div>
        </Panel>

        <Panel animated revealDelay={0.16}>
          <h2 className="text-lg font-extrabold text-zinc-950">Quick actions</h2>
          <div className="mt-4 grid gap-3">
            <Link className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 transition hover:border-zinc-300 hover:bg-white" to="/client/quotes">
              <span className="block text-sm font-extrabold text-zinc-950">Review quotes</span>
              <span className="mt-1 block text-sm text-zinc-600">Open submitted quotes and pricing explanations.</span>
            </Link>
            <Link className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 transition hover:border-zinc-300 hover:bg-white" to="/client/contracts">
              <span className="block text-sm font-extrabold text-zinc-950">View contracts</span>
              <span className="mt-1 block text-sm text-zinc-600">Download PDFs and check policy status.</span>
            </Link>
            <Link className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 transition hover:border-zinc-300 hover:bg-white" to="/client/claims">
              <span className="block text-sm font-extrabold text-zinc-950">Track claims</span>
              <span className="mt-1 block text-sm text-zinc-600">See decisions, evidence requests, and payouts.</span>
            </Link>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function ClientDashboardStat({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
      <div className="text-xs font-extrabold uppercase tracking-[0.12em] text-zinc-500">{label}</div>
      <div className="mt-3 truncate text-2xl font-extrabold text-zinc-950">{value}</div>
      <div className="mt-2 line-clamp-2 text-sm font-semibold leading-5 text-zinc-500">{detail}</div>
    </div>
  );
}

function MiniFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3">
      <div className="text-[11px] font-extrabold uppercase tracking-[0.1em] text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-extrabold text-zinc-950">{value}</div>
    </div>
  );
}

function clientFirstName(user?: AppUser | null) {
  return user?.fullName?.trim().split(/\s+/)[0] || undefined;
}

export function NewQuotePage() {
  const { user, setUser } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const savedQuoteForm = loadQuoteFormDraft(user?.id);
  const quoteDraftId = useRef(savedQuoteForm?.id ?? makeGeneratedQuoteDraftId());
  const [step, setStep] = useState(() => resolveSavedQuoteStep(savedQuoteForm));
  const [draft, setDraft] = useState<QuoteDraft>(() =>
    savedQuoteForm ? hydrateQuoteDraft(savedQuoteForm.draft, user) : defaultQuoteDraft(user)
  );
  const [reviewModal, setReviewModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const pricing = useMemo(
    () => getPremiumPreviewBreakdown(draft),
    [
      draft.propertyType,
      draft.yearBuilt,
      draft.areaSqm,
      draft.constructionType,
      draft.usageType,
      draft.coverageAmount,
      draft.hadClaims,
      draft.previousClaimsCount,
      draft.securityFeatures
    ]
  );
  const premium = pricing.estimatedPremium ?? pricing.finalPremium;

  useEffect(() => {
    const saved = loadQuoteFormDraft(user?.id);
    quoteDraftId.current = saved?.id ?? makeGeneratedQuoteDraftId();
    setStep(resolveSavedQuoteStep(saved));
    setDraft(saved ? hydrateQuoteDraft(saved.draft, user) : defaultQuoteDraft(user));
  }, [user?.id]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    void getMyCustomerProfile()
      .then((profile) => {
        if (cancelled) return;
        const profileForm = customerProfileFormFromProfile(profile, user);
        const profileUser = appUserWithCustomerProfile(user, profile, profileForm);
        setUser(profileUser);
        setDraft((current) => quoteDraftWithCustomerProfile(current, profileForm, profileUser, user));
      })
      .catch((error) => {
        if (!cancelled) {
          showToast(errorMessage(error, "Could not load customer profile."), "error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [showToast, user?.id]);

  useEffect(() => {
    if (!hasQuoteDraftContent(draft, user) && step === 0) {
      clearQuoteFormDraft(user?.id);
      return;
    }

    saveQuoteFormDraft(user?.id, {
      id: quoteDraftId.current,
      step,
      stepId: getQuoteStepId(step),
      draft,
      updatedAt: new Date().toISOString()
    });
  }, [draft, step, user?.id]);

  function update(field: keyof QuoteDraft, value: any) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function updateAddress(field: keyof QuoteDraft["address"], value: string) {
    setDraft((current) => ({
      ...current,
      address: { ...current.address, [field]: value }
    }));
  }

  function getStepValidationMessage() {
    const currentStepId = getQuoteStepId(step);
    const currentYear = new Date().getFullYear();
    const yearBuilt = Number(draft.yearBuilt);
    const areaSqm = Number(draft.areaSqm);
    const claimsCount = Number(draft.previousClaimsCount);

    if (currentStepId === "coverage" && !hasValidQuoteCoverageAmount(draft)) return "Add the amount you want protected. An estimate is fine for now.";
    if (currentStepId === "propertyType" && !draft.propertyType) return "Choose what kind of property you want to insure.";
    if (currentStepId === "address" && !(draft.address.country && draft.address.county && draft.address.city && draft.address.street && draft.address.number && draft.address.postal_code)) return "Add the property address so we can identify the home correctly.";
    if (currentStepId === "age" && (!Number.isFinite(yearBuilt) || yearBuilt <= 1700 || yearBuilt > currentYear)) return "Add the build year. If you are not sure, use an estimate.";
    if (currentStepId === "size" && (!Number.isFinite(areaSqm) || areaSqm <= 0)) return "Add the approximate size in square meters.";
    if (currentStepId === "construction" && !draft.constructionType) return "Choose the closest structure type. If you are not sure, use the recommended option.";
    if (currentStepId === "use" && !draft.usageType) return "Tell us how the property is usually used.";
    if (currentStepId === "claims" && (!draft.hadClaims || (draft.hadClaims === "Yes" && (!Number.isFinite(claimsCount) || claimsCount <= 0)))) return "Tell us whether there were previous property claims. An approximate count is enough.";
    if (currentStepId === "contact" && !(draft.fullName && draft.email && draft.phone && draft.nationalId)) return "Complete your contact details so we can issue the quote correctly.";
    return null;
  }

  function next() {
    const validationMessage = getStepValidationMessage();
    if (validationMessage) {
      showToast(validationMessage, "error");
      return;
    }
    setStep((current) => Math.min(current + 1, quoteSteps.length - 1));
  }

  async function submit() {
    if (submitting) return;
    const validationMessage = getStepValidationMessage();
    if (validationMessage) {
      showToast(validationMessage, "error");
      return;
    }
    setSubmitting(true);
    try {
      const quote = await createQuote(draft);
      clearQuoteFormDraft(user?.id);
      if (quote.status === "in_review") {
        setReviewModal(true);
        return;
      }
      navigate("/client/contracts");
    } catch (error) {
      showToast(errorMessage(error, "Quote submission failed. Please try again."), "error");
    } finally {
      setSubmitting(false);
    }
  }

  if (requiresProfileCompletion(user)) {
    return <CustomerProfileRequiredScreen context="quote" />;
  }

  const currentQuoteStepId = getQuoteStepId(step);

  return (
    <>
      <ClientPageContent>
        <PageHeader
          animated
          description="Tell us what you know. If you are not sure about a technical detail, choose the closest estimate and we will clearly mark what can be confirmed later."
          title="Start a quote"
        />
        <PremiumCounter animated breakdown={pricing} value={premium} />
        <div className="mt-4 grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Panel animated revealDelay={0.08}>
            <WizardStepper
              ariaLabel="Quote progress"
              className="mb-5"
              currentStep={step}
              steps={quoteStepDefinitions}
            />
            <QuoteStep draft={draft} stepId={currentQuoteStepId} update={update} updateAddress={updateAddress} />
            {step === quoteSteps.length - 1 ? (
              <details className="mt-4 rounded-xl border border-zinc-200 bg-zinc-50 p-3">
                <summary className="cursor-pointer text-sm font-extrabold text-zinc-900">
                  Optional details that can improve accuracy
                </summary>
                <p className="mt-2 text-sm leading-6 text-zinc-600">
                  Skip anything you do not know. These answers help us explain the price and reduce follow-up questions.
                </p>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <SelectInput
                    label="When were key systems last updated?"
                    onChange={(value) => update("systemsUpdated", value)}
                    options={["Last year", "Last 2 years", "Last 5 years", "More than 5 years ago", "Unknown"].map((item) => [item, item])}
                    value={draft.systemsUpdated}
                  />
                  <SelectInput label="Known risks in the area?" onChange={(value) => update("locationRisks", value)} options={[["Yes", "Yes"], ["No", "No"], ["Unknown", "I am not sure"]]} value={draft.locationRisks} />
                  <SelectInput label="High-value items inside?" onChange={(value) => update("highValueItems", value)} options={[["Yes", "Yes"], ["No", "No"], ["Unknown", "I am not sure"]]} value={draft.highValueItems} />
                  <SelectInput label="Renovated or structurally changed?" onChange={(value) => update("renovations", value)} options={[["Yes", "Yes"], ["No", "No"], ["Unknown", "I am not sure"]]} value={draft.renovations} />
                </div>
              </details>
            ) : null}
            <div className="mt-5 flex flex-wrap justify-end gap-3">
              <Button onClick={() => step === 0 ? navigate("/client") : setStep((current) => Math.max(current - 1, 0))}>
                Back
              </Button>
              {step === quoteSteps.length - 1 ? (
                <Button disabled={submitting} onClick={() => void submit()} variant="primary">
                  {submitting ? "Sending quote..." : "Send for quote"}
                </Button>
              ) : (
                <Button onClick={next} variant="primary">
                  Continue
                </Button>
              )}
            </div>
          </Panel>
          <QuoteFlowGuide draft={draft} pricing={pricing} stepId={currentQuoteStepId} />
        </div>
      </ClientPageContent>
      <Modal
        actions={<Button onClick={() => navigate("/client")} variant="primary">Close</Button>}
        onClose={() => navigate("/client")}
        open={reviewModal}
        title="Thank you for completing the quote."
      >
        Your request requires underwriting review. We will review it and get back to you soon.
      </Modal>
    </>
  );
}

export function ClientQuotesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [localQuoteDraft, setLocalQuoteDraft] = useState<LocalDraftSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }
    let cancelled = false;

    async function loadQuotes() {
      setLoading(true);
      setLoadError(undefined);
      try {
        const items = await getClientQuotes();
        if (!cancelled) {
          setQuotes(items);
          setLocalQuoteDraft(loadVisibleQuoteDraftSummary(user));
        }
      } catch (error) {
        if (!cancelled) setLoadError(errorMessage(error, "Could not load quotes."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadQuotes();
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (loading) {
    return (
      <ClientPageContent className="flex min-h-0 flex-1 flex-col">
        <ClientLoadingWait title="Loading quotes" />
      </ClientPageContent>
    );
  }

  if (loadError) {
    return (
      <ClientPageContent className="flex min-h-0 flex-1 flex-col">
        <EmptyState title={loadError} />
      </ClientPageContent>
    );
  }

  return (
    <ClientPageContent className="flex min-h-0 flex-1 flex-col">
      <Panel animated className="mb-4 shrink-0" revealDelay={listHeaderRevealDelay}>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <h1 className="text-xl font-bold tracking-normal text-slate-950">Quotes</h1>
          <div className="flex flex-wrap gap-2">
            <PrimaryLink to="/client/quote/new">Get a Quote</PrimaryLink>
            <Button className="min-h-8 px-3 py-1 text-xs" onClick={() => navigate("/client")} variant="primary">Back</Button>
          </div>
        </div>
      </Panel>
      <LocalDraftsSection
        ariaLabel="Local quote drafts"
        drafts={localQuoteDraft ? [localQuoteDraft] : []}
      />
      <DataTable
        animated
        revealDelay={listTableRevealDelay}
        className="flex min-h-[360px] flex-1 flex-col"
        columns={[
          { header: "Quote ID", render: (item) => item.id },
          { header: "Property Address", render: (item) => item.propertyAddress },
          { header: "Premium", render: (item) => item.status === "draft" ? "" : <QuotePremiumValue quote={item} /> },
          { header: "Status", render: (item) => <StatusBadge status={getClientQuoteStatus(item)} /> },
          { header: "Date", render: (item) => item.status === "draft" ? "" : formatDate(item.createdAt) }
        ]}
        data={quotes}
        emptyText="You do not have any submitted quotes yet."
        getRowHref={(item) => `/client/quotes/${item.id}`}
        scrollerClassName="min-h-0 flex-1 overflow-y-scroll"
      />
    </ClientPageContent>
  );
}

export function ClientQuoteDetailPage() {
  const { quoteId } = useParams();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [quote, setQuote] = useState<Quote>();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [contractOpening, setContractOpening] = useState(false);

  useEffect(() => {
    if (!quoteId) {
      setLoading(false);
      setLoadError("Quote not found");
      return;
    }
    let cancelled = false;

    async function loadQuote() {
      setLoading(true);
      setLoadError(undefined);
      setQuote(undefined);
      try {
        const found = await getMyQuoteById(quoteId);
        if (!cancelled) setQuote(found);
      } catch (error) {
        if (!cancelled) setLoadError(errorMessage(error, "Could not load quote."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadQuote();
    return () => {
      cancelled = true;
    };
  }, [quoteId]);

  if (loading) {
    return (
      <ClientPageContent>
        <ClientLoadingWait title="Loading quote" />
      </ClientPageContent>
    );
  }
  if (loadError || !quote) return <EmptyState title={loadError ?? "Quote not found"} />;

  const status = getClientQuoteStatus(quote);

  async function openAcceptedQuoteContract() {
    if (!quote || contractOpening) return;
    setContractOpening(true);
    try {
      const resolution = await resolveQuoteContract(quote.id, { clientScoped: true });
      const result = await convertQuoteToContract(quote.id, { clientScoped: true });
      const contractId = result.contract_id ?? result.contract?.id ?? resolution.contract_id ?? resolution.contract?.id;

      if (result.result === "blocked" || !contractId) {
        const issue = result.validation.blocking_errors[0] ?? resolution.validation.blocking_errors[0];
        showToast(issue?.message ?? "Contract is not available yet.", "error");
        return;
      }

      navigate(`/client/contracts/${contractId}`);
    } catch (error) {
      showToast(errorMessage(error, "Could not open contract."), "error");
    } finally {
      setContractOpening(false);
    }
  }

  return (
    <ClientPageContent>
      <PageHeader title={`Quote ${quote.id}`} />
      <Panel animated>
        <h2 className="mb-4 text-lg font-bold text-slate-950">Quote details</h2>
        <DetailGrid
          animated
          items={[
            ["Quote ID", quote.id],
            ["Status", <StatusBadge status={status} />],
            ["Premium", <QuotePremiumValue quote={quote} />],
            ["Date", formatDate(quote.createdAt)]
          ]}
        />
        <div className="mt-6">
          <h2 className="text-lg font-bold text-slate-950">Completed questions</h2>
          <QuoteAnswerList quote={quote} />
        </div>
      </Panel>
      {status === "In Review" ? (
        <Panel animated className="mt-4 bg-amber-50" revealDelay={0.16}>
          <p className="text-sm font-semibold text-amber-700">Your quote is currently under underwriting review.</p>
        </Panel>
      ) : null}
      {status === "Accepted" ? (
        <Panel animated className="mt-4 bg-emerald-50" revealDelay={0.16}>
          <p className="text-sm font-semibold text-emerald-700">Your quote has been accepted by underwriting. You can review the generated contract.</p>
        </Panel>
      ) : null}
      {status === "Rejected" ? (
        <Panel animated className="mt-4 bg-red-50/80" revealDelay={0.16}>
          <p className="text-sm font-semibold text-red-700">Your quote was rejected. {quote.rejectionReason ?? "This quote was rejected by underwriting."}</p>
        </Panel>
      ) : null}
      <div className="mt-6 flex flex-wrap justify-end gap-3">
        {status === "Accepted" ? (
          <Button className="min-h-8 px-3 py-1 text-xs" loading={contractOpening} onClick={() => void openAcceptedQuoteContract()} variant="success">
            {contractOpening ? "Opening" : "View Contract"}
          </Button>
        ) : null}
        <Button className="min-h-8 px-3 py-1 text-xs" onClick={() => navigate("/client/quotes")} variant="primary">Back</Button>
      </div>
    </ClientPageContent>
  );
}

function QuoteAnswerList({ quote }: { quote: Quote }) {
  const additionalItems = [
    ["Key systems last updated", quote.requestDetails.systems_updated],
    ["Known location risks", quote.requestDetails.location_risks],
    ["High-value items", quote.requestDetails.high_value_items],
    ["Renovations or structural changes", quote.requestDetails.renovations]
  ].filter(([, value]) => Boolean(value));

  const items: Array<[string, string | number]> = [
    ["What type of property is it?", quote.propertyType],
    ["What is the property address?", quote.propertyAddress],
    ["What year was the property built?", quote.yearBuilt],
    ["What is the approximate size of the property?", `${quote.areaSqm} m²`],
    ["What construction type is it?", quote.constructionType],
    ["How is the property used?", quote.usageType],
    ["What coverage amount do you want?", formatCurrency(quote.coverageAmount)],
    ["Have you had any property claims in the last 5 years?", quote.previousClaimsCount > 0 ? `Yes, ${quote.previousClaimsCount}` : "No"],
    ["Does the property have security protection?", quote.securityFeatures.length ? quote.securityFeatures.join(", ") : "No"],
    ["Contact information", `${quote.clientData.full_name}, ${quote.clientData.email}, ${quote.clientData.phone}`],
    ...(additionalItems as Array<[string, string]>)
  ];

  return (
    <dl className="mt-4 grid gap-3 md:grid-cols-2">
      {items.map(([label, value], index) => (
        <AnimatedCardReveal className="rounded-xl border border-slate-200 bg-white p-3" delay={staggerCardDelay(index)} key={label}>
          <dt className="text-sm font-semibold text-slate-600">{label}</dt>
          <dd className="mt-1 text-sm font-semibold text-slate-900">{value}</dd>
        </AnimatedCardReveal>
      ))}
    </dl>
  );
}

export function ClientContractsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [contracts, setContracts] = useState<ContractDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setLoadError(undefined);
      try {
        const contractRecords = await getMyContracts();
        if (cancelled) return;
        setContracts(contractRecords);
      } catch (error) {
        if (!cancelled) setLoadError(errorMessage(error, "Could not load contracts."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (loading) {
    return (
      <ClientPageContent className="flex min-h-0 flex-1 flex-col">
        <ClientLoadingWait title="Loading contracts" />
      </ClientPageContent>
    );
  }

  return (
    <ClientPageContent className="flex min-h-0 flex-1 flex-col">
      <Panel animated className="mb-4 shrink-0" revealDelay={listHeaderRevealDelay}>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <h1 className="text-xl font-bold tracking-normal text-slate-950">Contracts</h1>
          <div className="flex flex-wrap gap-2">
            <Button className="min-h-8 px-3 py-1 text-xs" onClick={() => navigate("/client")} variant="primary">Back</Button>
          </div>
        </div>
      </Panel>
      {loadError ? (
        <EmptyState title={loadError} />
      ) : (
        <DataTable
          animated
          revealDelay={listTableRevealDelay}
          className="flex min-h-[360px] flex-1 flex-col"
          columns={[
            { header: "Contract ID", render: (item) => getContractDisplayIdentifier(item) },
            { header: "Property Address", render: (item) => contractPropertyAddress(item) },
            { header: "Premium", render: (item) => formatCurrency(contractPremium(item)) },
            { header: "Status", render: (item) => <ClientContractStatusBadge status={item.status} /> },
            { header: "Date", render: (item) => formatDate(item.issue_date || item.created_at) }
          ]}
          data={contracts}
          emptyText="You do not have any contracts yet."
          getRowHref={(item) => `/client/contracts/${item.id}`}
          scrollerClassName="min-h-0 flex-1 overflow-y-scroll"
        />
      )}
    </ClientPageContent>
  );
}

function ContractView({
  contract,
  document,
  quote
}: {
  contract: ContractDetail;
  document?: GeneratedDocument;
  quote?: Quote;
}) {
  return (
    <div className="grid items-stretch gap-4 xl:grid-cols-[minmax(0,2.6fr)_minmax(280px,1fr)]">
      <ContractPdfPanel contract={contract} document={document} />
      <SelectedContractSummary contract={contract} document={document} quote={quote} />
    </div>
  );
}

function ContractPdfPanel({
  contract,
  document,
  className = ""
}: {
  contract: ContractDetail;
  document?: GeneratedDocument;
  className?: string;
}) {
  return (
    <GeneratedDocumentPdfViewer
      animated
      canCreatePdf
      clientScoped
      className={className}
      displayFilename={contractPdfFilenameLabel(contract, document)}
      document={document}
      emptyDescription="The policy PDF will appear here when it is available."
      ensureLatestPdf
      showEyebrow={false}
      title={contractDocumentName(contract, document)}
    />
  );
}

function SelectedContractSummary({
  contract,
  document,
  quote,
  className = ""
}: {
  contract: ContractDetail;
  document?: GeneratedDocument;
  quote?: Quote;
  className?: string;
}) {
  const linkedQuoteId = quote?.id ?? contract.source_quote_request_id ?? contract.source_quote_id ?? "-";
  return (
    <Panel animated className={`flex h-full flex-col text-sm ${className}`} revealDelay={0.08}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <h2 className="text-sm font-bold text-slate-950">Contract summary</h2>
      </div>
      <ClientContractSummaryDetails
        className="sm:grid-cols-2 xl:grid-cols-1"
        items={[
          ["Contract ID", getContractDisplayIdentifier(contract)],
          ["Type", contractTypeLabel(contract, document)],
          ["Insured name", contract.customer?.full_name ?? "-"],
          ["Premium", formatCurrency(contractPremium(contract))],
          ["Coverage amount", formatCurrency(contractCoverageAmount(contract))],
          ["Policy period", policyPeriodLabel(contract)],
          ["Status", <ClientContractStatusBadge status={contract.status} />],
          ["Linked quote ID", linkedQuoteId]
        ]}
      />
    </Panel>
  );
}

function ClientContractSummaryDetails({
  items,
  className = ""
}: {
  items: Array<[string, ReactNode]>;
  className?: string;
}) {
  return (
    <dl className={`grid gap-2 ${className}`}>
      {items.map(([label, value], index) => (
        <AnimatedCardReveal className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2 shadow-sm" delay={staggerCardDelay(index)} key={label}>
          <dt className="text-[10px] font-bold leading-3 text-slate-500">{label}</dt>
          <dd className="mt-1 break-words text-xs font-bold leading-4 text-slate-900">{value}</dd>
        </AnimatedCardReveal>
      ))}
    </dl>
  );
}

function contractDocumentName(contract: ContractDetail, document?: GeneratedDocument) {
  void document;
  return `${contractTypeLabel(contract)} ${getContractDisplayIdentifier(contract)}`;
}

function contractTypeLabel(contract: ContractDetail, document?: GeneratedDocument) {
  const rawType = document?.document_type ?? contract.document_type ?? "Contract";
  if (/generated/i.test(rawType)) return "Policy contract";
  return humanizeIdentifier(rawType);
}

function contractPdfFilenameLabel(contract: ContractDetail, document?: GeneratedDocument) {
  const fallback = `${getContractDisplayIdentifier(contract)}.pdf`;
  if (!document?.pdf_filename) return fallback;
  return document.pdf_filename
    .replace(/generated[-_ ]?document/gi, "policy-document")
    .replace(/generated[-_ ]?contract/gi, "policy-contract")
    .replace(/generated/gi, "policy");
}

function ClientContractStatusBadge({ status }: { status: string }) {
  const label = clientContractStatusLabel(status);
  const displayStatus = getContractLifecycleDisplayStatus(status);
  const statusClass =
    displayStatus === "declined"
      ? "bg-red-50 text-red-700 ring-red-200"
      : displayStatus === "awaiting_client_signing"
      ? "bg-purple-50 text-purple-700 ring-purple-200"
      : displayStatus === "issued"
      ? "bg-amber-50 text-amber-700 ring-amber-200"
      : "bg-emerald-50 text-emerald-700 ring-emerald-200";

  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-bold ring-1 ring-inset ${statusClass}`}>
      {label}
    </span>
  );
}

function clientContractStatusLabel(status: string) {
  return getContractLifecycleStatusLabel(status);
}

function contractPremium(contract: ContractDetail) {
  return numberValue(contract.pricing?.final_premium_ron);
}

function contractCoverageAmount(contract: ContractDetail) {
  return numberValue(contract.asset?.declared_value);
}

function contractPropertyAddress(contract: ContractDetail) {
  return contract.asset?.address?.full_text ?? "-";
}

function policyPeriodLabel(contract: ContractDetail) {
  const start = contract.effective_date || "-";
  const end = contract.expiration_date || "-";
  return `${start} to ${end}`;
}

function humanizeIdentifier(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ") || "Contract";
}

export function ClientContractDetailPage() {
  const { contractId } = useParams();
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [contract, setContract] = useState<ContractDetail>();
  const [document, setDocument] = useState<GeneratedDocument>();
  const [quote, setQuote] = useState<Quote>();
  const [acceptance, setAcceptance] = useState<QuoteAcceptance>();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [signOpen, setSignOpen] = useState(false);
  const [signing, setSigning] = useState(false);
  const [declineOpen, setDeclineOpen] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [declineReason, setDeclineReason] = useState("");
  const [signerName, setSignerName] = useState("");
  const [signerEmail, setSignerEmail] = useState("");
  const [signerRole, setSignerRole] = useState("policyholder");

  useEffect(() => {
    if (!contractId) return;
    let cancelled = false;

    async function loadContract() {
      setLoading(true);
      setLoadError(undefined);
      setContract(undefined);
      setDocument(undefined);
      setQuote(undefined);
      setAcceptance(undefined);

      try {
        if (isLegacyContractRouteId(contractId)) {
          void quoteIdFromLegacyContractRoute(contractId);
          setLoadError("Contract document is not available yet.");
          return;
        }

        const found = await getMyContract(contractId);
        if (cancelled) return;
        setContract(found);

        const linkedQuoteId = found.source_quote_request_id ?? found.source_quote_id;
        const [latestDocument, linkedQuote, linkedAcceptance] = await Promise.all([
          getLatestMyContractDocument(found.id),
          getLinkedQuote(found),
          linkedQuoteId ? getMyQuoteAcceptance(linkedQuoteId) : Promise.resolve(undefined)
        ]);
        if (cancelled) return;
        setDocument(latestDocument);
        setQuote(linkedQuote);
        setAcceptance(linkedAcceptance);
        setSignerName((current) => current || user?.fullName || found.customer?.full_name || "");
        setSignerEmail((current) => current || user?.email || found.customer?.email || "");
      } catch (error) {
        if (!cancelled) setLoadError(errorMessage(error, "Could not load contract."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadContract();
    return () => {
      cancelled = true;
    };
  }, [contractId, navigate, user]);

  const linkedQuoteId = contract?.source_quote_request_id ?? contract?.source_quote_id;
  const signed = Boolean(acceptance || contract?.source_quote_acceptance_id || contract?.status === "issued");
  const declined = contract?.status === "declined";
  const canSign = Boolean(contract && linkedQuoteId && contract.status === "generated" && !signed && !declining);
  const canDecline = Boolean(contract && contract.status === "generated" && !signed && !signing);

  async function submitContractSignature() {
    if (!linkedQuoteId || signing) return;
    if (!signerName.trim() || !signerEmail.trim()) {
      showToast("Signer name and email are required.", "error");
      return;
    }
    setSigning(true);
    try {
      await acceptQuote(linkedQuoteId, {
        signer_name: signerName.trim(),
        signer_email: signerEmail.trim(),
        signer_role: signerRole.trim() || undefined,
        acceptance_statement: `I accept contract ${contract ? getContractDisplayIdentifier(contract) : linkedQuoteId} and confirm the details are accurate.`
      });
      const recordedAcceptance = await getMyQuoteAcceptance(linkedQuoteId);
      setAcceptance(recordedAcceptance);
      setContract((current) =>
        current
          ? {
              ...current,
              status: "issued",
              source_quote_acceptance_id: recordedAcceptance?.id ?? current.source_quote_acceptance_id
            }
          : current
      );
      showToast("Contract signed.");
      setSignOpen(false);
    } catch (error) {
      showToast(errorMessage(error, "Could not sign contract."), "error");
    } finally {
      setSigning(false);
    }
  }

  async function submitContractDecline() {
    if (!contract || declining) return;
    setDeclining(true);
    try {
      await declineMyContract(contract.id, declineReason);
      setContract((current) =>
        current
          ? {
              ...current,
              status: "declined"
            }
          : current
      );
      showToast("Contract declined.");
      setDeclineOpen(false);
    } catch (error) {
      showToast(errorMessage(error, "Could not decline contract."), "error");
    } finally {
      setDeclining(false);
    }
  }

  function signContract(event: FormEvent) {
    event.preventDefault();
    void submitContractSignature();
  }

  function declineContract(event: FormEvent) {
    event.preventDefault();
    void submitContractDecline();
  }

  if (loading) {
    return (
      <ClientPageContent>
        <ClientLoadingWait title="Loading contract document" />
      </ClientPageContent>
    );
  }
  if (loadError || !contract) return <EmptyState title={loadError ?? "Contract not found"} />;

  return (
    <ClientPageContent>
      <PageHeader
        action={
          <div className="flex flex-wrap justify-end gap-2">
            {canSign ? (
              <Button className="min-h-8 px-3 py-1 text-xs" disabled={declining} loading={signing} onClick={() => setSignOpen(true)} variant="success">
                Sign contract
              </Button>
            ) : null}
            {canDecline ? (
              <Button className="min-h-8 px-3 py-1 text-xs" disabled={signing} loading={declining} onClick={() => setDeclineOpen(true)} variant="danger">
                Decline contract
              </Button>
            ) : null}
            <GeneratedDocumentPdfLink document={document} />
          </div>
        }
        title={`Contract ${getContractDisplayIdentifier(contract)}`}
      />
      {declined ? (
        <Panel animated className="mt-4 border-red-200 bg-red-50 text-sm font-semibold text-red-700" revealDelay={0.08}>
          This contract was declined.
        </Panel>
      ) : null}
      <ContractView contract={contract} document={document} quote={quote} />
      <div className="mt-6 flex flex-wrap justify-end gap-3">
        <PrimaryLink to="/client/contracts">Back to Contracts</PrimaryLink>
      </div>
      <Modal
        actions={
          <>
            <Button disabled={signing} onClick={() => setSignOpen(false)}>Cancel</Button>
            <Button disabled={signing} onClick={() => void submitContractSignature()} variant="success">
              {signing ? "Signing..." : "Sign contract"}
            </Button>
          </>
        }
        onClose={() => setSignOpen(false)}
        open={signOpen}
        title="Sign contract"
      >
        <form className="grid gap-3" onSubmit={signContract}>
          <label className="grid gap-1 text-xs font-bold text-slate-600">
            Signer name
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900" onChange={(event) => setSignerName(event.target.value)} value={signerName} />
          </label>
          <label className="grid gap-1 text-xs font-bold text-slate-600">
            Signer email
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900" onChange={(event) => setSignerEmail(event.target.value)} type="email" value={signerEmail} />
          </label>
          <label className="grid gap-1 text-xs font-bold text-slate-600">
            Role
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900" onChange={(event) => setSignerRole(event.target.value)} value={signerRole} />
          </label>
        </form>
      </Modal>
      <Modal
        actions={
          <>
            <Button disabled={declining} onClick={() => setDeclineOpen(false)}>Cancel</Button>
            <Button disabled={declining} onClick={() => void submitContractDecline()} variant="danger">
              {declining ? "Declining..." : "Decline contract"}
            </Button>
          </>
        }
        onClose={() => setDeclineOpen(false)}
        open={declineOpen}
        title="Decline contract"
      >
        <form className="grid gap-3" onSubmit={declineContract}>
          <label className="grid gap-1 text-xs font-bold text-slate-600">
            Reason
            <textarea
              className="min-h-24 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900"
              onChange={(event) => setDeclineReason(event.target.value)}
              value={declineReason}
            />
          </label>
        </form>
      </Modal>
    </ClientPageContent>
  );
}

export function ClientClaimsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [claims, setClaims] = useState<Claim[]>([]);
  const [localClaimDraft, setLocalClaimDraft] = useState<LocalDraftSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }
    let cancelled = false;

    async function loadClaims() {
      setLoading(true);
      setLoadError(undefined);
      try {
        const items = await getClientClaims();
        if (!cancelled) {
          setClaims(items);
          setLocalClaimDraft(loadVisibleClaimDraftSummary(user));
        }
      } catch (error) {
        if (!cancelled) setLoadError(errorMessage(error, "Could not load claims."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadClaims();
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (loading) {
    return (
      <ClientPageContent className="flex min-h-0 flex-1 flex-col">
        <ClientLoadingWait title="Loading claims" />
      </ClientPageContent>
    );
  }

  if (loadError) {
    return (
      <ClientPageContent className="flex min-h-0 flex-1 flex-col">
        <EmptyState title={loadError} />
      </ClientPageContent>
    );
  }

  return (
    <ClientPageContent className="flex min-h-0 flex-1 flex-col">
      <PageHeader
        action={
          <>
            <PrimaryLink to="/client/claims/new">File a Claim</PrimaryLink>
            <Button className="min-h-8 px-3 py-1 text-xs" onClick={() => navigate("/client")} variant="primary">Back</Button>
          </>
        }
        animated
        revealDelay={listHeaderRevealDelay}
        title="Claims"
      />
      <LocalDraftsSection
        ariaLabel="Local claim drafts"
        drafts={localClaimDraft ? [localClaimDraft] : []}
      />
      <DataTable
        animated
        revealDelay={listTableRevealDelay}
        className="flex min-h-[360px] flex-1 flex-col"
        columns={[
          { header: "Claim ID", render: (item) => getClaimDisplayIdentifier(item) },
          { header: "Property Address", render: (item) => item.propertyAddress },
          { header: "Incident Type", render: (item) => item.claimType },
          { header: "Status", render: (item) => <StatusBadge status={getClientClaimStatus(item)} /> },
          { header: "Date", render: (item) => item.status === "draft" ? "" : formatDate(item.incidentDate) }
        ]}
        data={claims}
        emptyText="You do not have any claims yet."
        getRowHref={(item) => `/client/claims/${item.id}`}
        scrollerClassName="min-h-0 flex-1 overflow-y-scroll"
      />
    </ClientPageContent>
  );
}

export function NewClaimPage() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [claimableContracts, setClaimableContracts] = useState<ClaimableContract[]>([]);
  const [claimableContractsStatus, setClaimableContractsStatus] = useState<"loading" | "loaded" | "error">("loading");
  const [claimableContractsError, setClaimableContractsError] = useState<string>();
  const [profileDocuments, setProfileDocuments] = useState<CustomerProfileDocument[]>([]);
  const [profileDocumentsStatus, setProfileDocumentsStatus] = useState<"loading" | "loaded" | "error">("loading");
  const [profileDocumentsError, setProfileDocumentsError] = useState<string>();
  const [done, setDone] = useState(false);
  const [submissionStatus, setSubmissionStatus] = useState<"idle" | "uploading" | "submitting">("idle");
  const savedClaimForm = loadClaimFormDraft(user?.id);
  const initialClaimId = savedClaimForm?.id ?? savedClaimForm?.draft.claimId ?? makeGeneratedClaimId();
  const [step, setStep] = useState(() => clampDraftStep(savedClaimForm?.step, claimSteps.length));
  const [claimId, setClaimId] = useState(initialClaimId);
  const [evidenceFiles, setEvidenceFiles] = useState<Record<string, string>>(() => savedClaimForm?.evidenceFiles ?? {});
  const [selectedEvidenceFiles, setSelectedEvidenceFiles] = useState<Record<string, File[]>>({});
  const [evidenceFileMetadata, setEvidenceFileMetadata] = useState<Record<string, DraftUploadMetadata[]>>(() => {
    return savedClaimForm?.evidenceFileMetadata ?? metadataFromEvidenceFiles(savedClaimForm?.evidenceFiles ?? {});
  });
  const [claimAddress, setClaimAddress] = useState(() => savedClaimForm?.address ?? { ...defaultClaimAddress });
  const [draft, setDraft] = useState<ClaimDraft>(() =>
    savedClaimForm
      ? hydrateClaimDraft(savedClaimForm.draft, user, initialClaimId)
      : defaultClaimDraft(user, initialClaimId)
  );

  useEffect(() => {
    const saved = loadClaimFormDraft(user?.id);
    const nextClaimId = saved?.id ?? saved?.draft.claimId ?? makeGeneratedClaimId();

    setClaimId(nextClaimId);
    setStep(clampDraftStep(saved?.step, claimSteps.length));
    setClaimAddress(saved?.address ?? { ...defaultClaimAddress });
    setDraft(saved ? hydrateClaimDraft(saved.draft, user, nextClaimId) : defaultClaimDraft(user, nextClaimId));
    setEvidenceFiles(saved?.evidenceFiles ?? {});
    setEvidenceFileMetadata(saved?.evidenceFileMetadata ?? metadataFromEvidenceFiles(saved?.evidenceFiles ?? {}));
    setSelectedEvidenceFiles({});
  }, [user?.id]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    void getMyCustomerProfile()
      .then((profile) => {
        if (cancelled) return;
        const profileForm = customerProfileFormFromProfile(profile, user);
        const profileUser = appUserWithCustomerProfile(user, profile, profileForm);
        setUser(profileUser);
        setDraft((current) => claimDraftWithCustomerProfile(current, profileUser, user));
      })
      .catch((error) => {
        if (!cancelled) {
          showToast(errorMessage(error, "Could not load customer profile."), "error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [showToast, user?.id]);

  useEffect(() => {
    if (!user) return;
    void loadClaimableContracts();
  }, [user]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setProfileDocumentsStatus("loading");
    setProfileDocumentsError(undefined);
    listMyProfileDocuments()
      .then((documents) => {
        if (cancelled) return;
        setProfileDocuments(documents);
        setProfileDocumentsStatus("loaded");
        const prefilledFiles = evidenceFilesFromProfileDocuments(documents);
        const prefilledMetadata = metadataFromProfileDocuments(documents);
        setEvidenceFiles((current) => ({ ...prefilledFiles, ...current }));
        setEvidenceFileMetadata((current) => ({ ...prefilledMetadata, ...current }));
        clearLegacyAccountDocuments(user.id);
      })
      .catch((error) => {
        if (!cancelled) {
          setProfileDocumentsStatus("error");
          setProfileDocumentsError(errorMessage(error, "Could not load account documents."));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    if (done) return;
    const currentDraft = { ...draft, claimId };
    const prefilledEvidenceFiles = evidenceFilesFromProfileDocuments(profileDocuments);
    if (!hasClaimDraftContent(currentDraft, claimAddress, evidenceFiles, user, prefilledEvidenceFiles) && step === 0) {
      clearClaimFormDraft(user?.id);
      return;
    }

    saveClaimFormDraft(user?.id, {
      id: claimId,
      step,
      draft: currentDraft,
      address: claimAddress,
      evidenceFiles,
      evidenceFileMetadata,
      updatedAt: new Date().toISOString()
    });
  }, [claimAddress, claimId, done, draft, evidenceFileMetadata, evidenceFiles, profileDocuments, step, user?.id]);

  async function loadClaimableContracts() {
    if (!user) return;
    setClaimableContractsStatus("loading");
    setClaimableContractsError(undefined);
    try {
      const items = await getClaimableContracts();
      setClaimableContracts(items);
      setClaimableContractsStatus("loaded");
      setDraft((current) => reconcileClaimDraftContract(current, items));
      setClaimAddress({ ...defaultClaimAddress });
    } catch (error) {
      setClaimableContracts([]);
      setClaimableContractsStatus("error");
      setClaimableContractsError(errorMessage(error, "Could not load insured properties."));
      setDraft((current) => clearClaimDraftContract(current));
    }
  }

  if (requiresProfileCompletion(user)) {
    return <CustomerProfileRequiredScreen context="claim" />;
  }

  function update(field: keyof ClaimDraft, value: string) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function selectClaimableContract(contractId: string) {
    const selected = claimableContracts.find((contract) => contract.contract_id === contractId);
    setDraft((current) => (
      selected ? applyClaimableContractToDraft(current, selected) : clearClaimDraftContract(current)
    ));
  }

  function updateEvidence(label: string, files: File[]) {
    setSelectedEvidenceFiles((current) => ({ ...current, [label]: files }));
    setEvidenceFileMetadata((current) => ({
      ...current,
      [label]: fileMetadataFromFiles(files)
    }));
    setEvidenceFiles((current) => ({ ...current, [label]: joinedFileNames(files) }));
  }

  function removeEvidenceFile(label: string, index: number) {
    const selectedFiles = selectedEvidenceFiles[label] ?? [];
    if (selectedFiles.length) {
      updateEvidence(label, selectedFiles.filter((_, currentIndex) => currentIndex !== index));
      return;
    }

    setEvidenceFileMetadata((current) => {
      const nextFiles = (current[label] ?? []).filter((_, currentIndex) => currentIndex !== index);
      const next = { ...current };
      if (nextFiles.length) next[label] = nextFiles;
      else delete next[label];
      return next;
    });
    setEvidenceFiles((current) => {
      const nextFiles = splitEvidenceFileNames(current[label]).filter((_, currentIndex) => currentIndex !== index);
      const next = { ...current };
      if (nextFiles.length) next[label] = nextFiles.join(", ");
      else delete next[label];
      return next;
    });
  }

  function getStepValidationMessage(currentStep = step) {
    const incidentDate = new Date(`${draft.incidentDate}T${draft.incidentTime || "00:00"}`);
    const missingDocument = requiredClaimDocumentLabels.find((label) => !hasEvidenceForLabel(evidenceFiles, label));
    const selectedContract = claimableContracts.find((contract) => contract.contract_id === draft.contractId);

    if (currentStep === 0 && !draft.claimType) return "Choose the closest category for what happened.";
    if (currentStep === 1) {
      if (claimableContractsStatus === "loading") return "Insured properties are still loading.";
      if (claimableContractsStatus === "error") return "Could not load insured properties.";
      if (!claimableContracts.length) return "No claimable insured properties are available.";
      if (!draft.contractId || !selectedContract) return "Choose the insured property connected to this claim.";
    }
    if (currentStep === 2) {
      if (!(draft.incidentDate && draft.incidentTime && draft.emergencyServices)) return "Add when it happened and whether emergency services were involved.";
      if (Number.isFinite(incidentDate.getTime()) && incidentDate > new Date()) return "Incident date cannot be in the future.";
    }
    if (currentStep === 3 && (!(draft.description && draft.estimatedDamage) || Number(draft.estimatedDamage) <= 0)) {
      return "Describe the damage and add an estimated amount. An estimate is fine.";
    }
    if (currentStep === 4 && !(draft.fullName && draft.phone && draft.email)) return "Add the best contact details for claim updates.";
    if (currentStep === 5 && missingDocument) return `Please attach ${missingDocument}. Photos are required so we can verify the damage.`;
    return null;
  }

  function next() {
    const message = getStepValidationMessage();
    if (message) {
      showToast(message, "error");
      return;
    }
    setStep((current) => Math.min(current + 1, claimSteps.length - 1));
  }

  function preventImplicitSubmit(event: FormEvent) {
    event.preventDefault();
  }

  async function submitClaim() {
    if (submissionStatus !== "idle") return;
    const messages = claimSteps
      .map((_, index) => getStepValidationMessage(index))
      .filter(Boolean);
    if (!draft.contractId || messages.length) {
      showToast(!draft.contractId ? "A generated contract is required before filing a claim." : messages[0]!, "error");
      return;
    }
    const selectedFiles = flattenSelectedEvidenceFiles(selectedEvidenceFiles);
    const profileDocumentAttachments = profileDocumentAttachmentsForClaim(
      evidenceFileMetadata,
      selectedEvidenceFiles
    );
    let currentPhase: "uploading" | "submitting" = "submitting";

    try {
      currentPhase = "submitting";
      setSubmissionStatus("submitting");
      const createdClaim = await createClaim({
        ...draft,
        claimId,
        photosFileName: evidenceFiles["Photos from incident"],
        documentsFileName: claimDocumentLabels.map((label) => evidenceFiles[label]).filter(Boolean).join(", "),
        evidenceFiles,
        attachments: profileDocumentAttachments
      });
      clearClaimFormDraft(user?.id);
      if (selectedFiles.length) {
        currentPhase = "uploading";
        setSubmissionStatus("uploading");
        await uploadClaimAttachments(
          createdClaim.id,
          selectedFiles.map(({ label, file }) => ({
            file,
            documentRole: documentRoleForEvidenceLabel(label)
          }))
        );
      }
      setSelectedEvidenceFiles({});
      setEvidenceFileMetadata({});
      setEvidenceFiles({});
      setDone(true);
    } catch (error) {
      showToast(
        errorMessage(
          error,
          currentPhase === "uploading"
            ? "Document upload failed. Please try again."
            : "Claim submission failed. Please try again."
        ),
        "error"
      );
    } finally {
      setSubmissionStatus("idle");
    }
  }

  return (
    <ClientPageContent>
      <PageHeader
        description="Tell us what happened in plain language. Upload what you have now; if something is missing, we will ask for it clearly."
        title="File a claim"
      />
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel animated>
          <WizardStepper ariaLabel="Claim progress" currentStep={step} steps={claimSteps} />
          <form className="mt-4" onSubmit={preventImplicitSubmit}>
            <ClaimStep
              claimableContracts={claimableContracts}
              claimableContractsError={claimableContractsError}
              claimableContractsStatus={claimableContractsStatus}
              draft={draft}
              evidenceFileMetadata={evidenceFileMetadata}
              evidenceFiles={evidenceFiles}
              profileDocumentsError={profileDocumentsError}
              profileDocumentsStatus={profileDocumentsStatus}
              removeEvidenceFile={removeEvidenceFile}
              retryClaimableContracts={() => void loadClaimableContracts()}
              selectClaimableContract={selectClaimableContract}
              selectedEvidenceFiles={selectedEvidenceFiles}
              step={step}
              update={update}
              updateEvidence={updateEvidence}
            />
            <div className="mt-5 flex flex-wrap justify-end gap-3">
              <Button disabled={step === 0} onClick={() => setStep((current) => Math.max(current - 1, 0))} type="button" variant="secondary">
                Back
              </Button>
              {step < claimSteps.length - 1 ? (
                <Button onClick={next} type="button" variant="primary">Continue</Button>
              ) : (
                <Button disabled={submissionStatus !== "idle"} onClick={() => void submitClaim()} type="button" variant="primary">
                  {submissionStatus === "uploading"
                    ? "Uploading documents..."
                    : submissionStatus === "submitting"
                      ? "Sending claim..."
                      : "Send claim"}
                </Button>
              )}
            </div>
          </form>
        </Panel>
        <ClaimFlowGuide
          claimableContracts={claimableContracts}
          draft={draft}
          evidenceFiles={evidenceFiles}
          step={step}
        />
      </div>
      <Modal
        actions={<Button onClick={() => navigate("/client/claims")} variant="primary">Close</Button>}
        onClose={() => navigate("/client/claims")}
        open={done}
        title="Your claim was sent."
      >
        We will review the information and tell you clearly if anything else is needed.
      </Modal>
    </ClientPageContent>
  );
}

export function ClientClaimDetailPage() {
  const { claimId } = useParams();
  const navigate = useNavigate();
  const [claim, setClaim] = useState<Claim>();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  useEffect(() => {
    if (!claimId) {
      setLoading(false);
      setLoadError("Claim not found");
      return;
    }
    let cancelled = false;

    async function loadClaim() {
      setLoading(true);
      setLoadError(undefined);
      setClaim(undefined);
      try {
        const found = await getMyClaimById(claimId);
        if (!cancelled) setClaim(found);
      } catch (error) {
        if (!cancelled) setLoadError(errorMessage(error, "Could not load claim."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadClaim();
    return () => {
      cancelled = true;
    };
  }, [claimId]);
  if (loading) {
    return (
      <ClientPageContent>
        <ClientLoadingWait title="Loading claim" />
      </ClientPageContent>
    );
  }
  if (loadError || !claim) return <EmptyState title={loadError ?? "Claim not found"} />;
  return (
    <ClientPageContent>
      <PageHeader title={`Claim ${getClaimDisplayIdentifier(claim)}`} />
      <div className="grid items-stretch gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel animated className="h-full min-w-0">
          <h2 className="mb-4 text-lg font-bold text-slate-950">Claim details</h2>
          <ClientClaimDetailGrid
            items={[
              ["Status", <StatusBadge status={getClientClaimStatus(claim)} />],
              ["Property address", claim.propertyAddress],
              ["Incident type", claim.claimType],
              ["Date/time", `${claim.incidentDate} ${claim.incidentTime}`],
              ["Estimated damage", formatCurrency(claim.estimatedDamage)],
              ["Emergency services", claim.emergencyServices ? "Yes" : "No"],
              ["Phone", claim.contactPhone],
              ["Email", claim.contactEmail],
              ["Description", claim.description, true]
            ]}
          />
        </Panel>
        <Panel animated className="h-full min-w-0" revealDelay={0.08}>
          <h2 className="text-lg font-bold text-slate-950">Uploaded documents</h2>
          <div className="mt-4 grid gap-3">
            {claim.evidence.length ? (
              claim.evidence.map((document, index) => (
                <ClientClaimDocumentRow delay={staggerCardDelay(index)} document={document} key={document.id} />
              ))
            ) : (
              <AnimatedCardReveal className="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-500">
                No uploaded documents.
              </AnimatedCardReveal>
            )}
          </div>
        </Panel>
      </div>
      <Panel animated className="mt-4" revealDelay={0.16}>
        <p className="text-sm font-semibold text-slate-700">{getClaimStatusMessage(claim)}</p>
      </Panel>
      <div className="mt-6 flex justify-end">
        <Button className="min-h-8 px-3 py-1 text-xs" onClick={() => navigate("/client/claims")} variant="primary">Back</Button>
      </div>
    </ClientPageContent>
  );
}

function ClientClaimDetailGrid({ items }: { items: Array<[string, ReactNode, boolean?]> }) {
  return (
    <dl className="grid gap-2.5 sm:grid-cols-2">
      {items.map(([label, value, fullWidth], index) => (
        <AnimatedCardReveal className={`rounded-lg bg-slate-50 p-2.5 ${fullWidth ? "sm:col-span-2" : ""}`} delay={staggerCardDelay(index)} key={label}>
          <dt className="text-xs font-bold uppercase text-slate-500">{label}</dt>
          <dd className="mt-1 break-words text-sm font-semibold text-slate-900">{value}</dd>
        </AnimatedCardReveal>
      ))}
    </dl>
  );
}

function ClientClaimDocumentRow({ delay = 0, document }: { delay?: number; document: MockDocument }) {
  return (
    <AnimatedCardReveal className="flex w-full flex-col gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between" delay={delay}>
      <div className="min-w-0 flex-1">
        <p className="truncate font-bold text-slate-900">{document.fileName || document.label}</p>
        <p className="mt-0.5 truncate text-xs font-semibold text-slate-500">
          {formatDocumentMeta(document)}
        </p>
      </div>
      {document.url ? (
        <a
          className="shrink-0 text-sm font-bold text-orange-600 hover:text-orange-700"
          href={document.url}
          rel="noopener noreferrer"
          target="_blank"
        >
          View document
        </a>
      ) : (
        <span className="shrink-0 text-sm font-bold text-slate-400">Unavailable</span>
      )}
    </AnimatedCardReveal>
  );
}

function formatDocumentMeta(document: MockDocument) {
  const parts = [
    document.label && document.label !== document.fileName ? document.label : null,
    document.type,
    document.contentType,
    typeof document.sizeBytes === "number" ? formatDocumentSize(document.sizeBytes) : null
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Uploaded document";
}

function formatDocumentSize(sizeBytes: number) {
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getClaimStatusMessage(claim: Claim) {
  const status = getClientClaimStatus(claim);
  if (status === "Submitted") {
    return "Your claim has been submitted and is waiting for review. We will get back to you soon.";
  }
  if (status === "Rejected") {
    return "Your claim did not pass the precheck and was marked as rejected. Please review the rejection details for next steps.";
  }
  if (status === "Approved") {
    return "Your claim payment decision is recorded as approved. Compensation will follow the terms and limits of your contract.";
  }
  if (status === "Declined") {
    return "Your claim payment decision is recorded as declined. Please review the reason provided by the underwriting team.";
  }
  return "An on-premises inspection has been requested. A representative will investigate the damage before a final decision is made.";
}

function formatClaimAddress(address: typeof defaultClaimAddress) {
  return [
    `${address.street} ${address.number}`.trim(),
    address.city,
    address.county,
    address.country,
    address.postal_code
  ].filter(Boolean).join(", ");
}

function claimableAddressText(contract: ClaimableContract) {
  const address = contract.address;
  if (!address) return "Address unavailable";
  if (address.full_text) return address.full_text;
  return [
    `${address.street} ${address.number}`.trim(),
    address.city,
    address.county,
    address.country,
    address.postal_code
  ].filter(Boolean).join(", ") || "Address unavailable";
}

function claimablePeriodLabel(contract: ClaimableContract) {
  const effective = contract.effective_date ? formatDate(contract.effective_date) : "Unknown start";
  const expiration = contract.expiration_date ? formatDate(contract.expiration_date) : "No expiration date";
  return `${effective} - ${expiration}`;
}

function claimableOptionLabel(contract: ClaimableContract) {
  const contractNumber = getContractDisplayIdentifier(contract);
  return `${claimableAddressText(contract)} - Contract #${contractNumber} (${claimablePeriodLabel(contract)})`;
}

function applyClaimableContractToDraft(draft: ClaimDraft, contract: ClaimableContract): ClaimDraft {
  return {
    ...draft,
    contractId: contract.contract_id,
    policyNumber: contract.policy_number || contract.contract_number,
    propertyAddress: claimableAddressText(contract)
  };
}

function clearClaimDraftContract(draft: ClaimDraft): ClaimDraft {
  return {
    ...draft,
    contractId: "",
    policyNumber: "",
    propertyAddress: ""
  };
}

function reconcileClaimDraftContract(draft: ClaimDraft, contracts: ClaimableContract[]) {
  const selected = contracts.find((contract) => contract.contract_id === draft.contractId);
  if (selected) return applyClaimableContractToDraft(draft, selected);
  if (contracts.length === 1) return applyClaimableContractToDraft(draft, contracts[0]);
  return clearClaimDraftContract(draft);
}

export function ClientAccountPage() {
  const { user, logout } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [documents, setDocuments] = useState<CustomerProfileDocument[]>([]);
  const [docs, setDocs] = useState<Record<string, string>>({});
  const [savedDocs, setSavedDocs] = useState<Record<string, string>>({});
  const [selectedDocumentFiles, setSelectedDocumentFiles] = useState<Record<string, File[]>>({});
  const [documentsStatus, setDocumentsStatus] = useState<"loading" | "loaded" | "error">("loading");
  const [documentsError, setDocumentsError] = useState<string>();
  const [savingDocuments, setSavingDocuments] = useState(false);

  async function loadDocuments() {
    setDocumentsStatus("loading");
    setDocumentsError(undefined);
    try {
      const loaded = await listMyProfileDocuments();
      const nextDocs = evidenceFilesFromProfileDocuments(loaded);
      setDocuments(loaded);
      setDocs(nextDocs);
      setSavedDocs(nextDocs);
      setSelectedDocumentFiles({});
      setDocumentsStatus("loaded");
      clearLegacyAccountDocuments(user?.id);
    } catch (error) {
      setDocumentsStatus("error");
      setDocumentsError(errorMessage(error, "Could not load documents."));
    }
  }

  useEffect(() => {
    void loadDocuments();
  }, [user?.id]);

  async function saveDocuments() {
    if (savingDocuments) return;
    setSavingDocuments(true);
    try {
      const existingByLabel = documentsByLabel(documents);
      await Promise.all(
        accountDocumentLabels.map(async (label) => {
          const selectedFile = selectedDocumentFiles[label]?.[0];
          const existing = existingByLabel[label];
          if (!docs[label] && existing) {
            await deleteMyProfileDocument(existing.id);
            return;
          }
          if (selectedFile) {
            await uploadMyProfileDocument({
              label,
              documentType: documentRoleForEvidenceLabel(label) || label,
              file: selectedFile
            });
          }
        })
      );
      await loadDocuments();
      setEditing(false);
      showToast("Documents saved.");
    } catch (error) {
      showToast(errorMessage(error, "Could not save documents."), "error");
    } finally {
      setSavingDocuments(false);
    }
  }

  return (
    <ClientPageContent>
      <PageHeader
        action={
          <>
            <Button
              className="min-h-8 px-3 py-1 text-xs"
              onClick={() => {
                logout();
                navigate("/");
              }}
              variant="primary"
            >
              Sign Out
            </Button>
            <Button className="min-h-8 px-3 py-1 text-xs" onClick={() => navigate("/client")} variant="primary">Back</Button>
          </>
        }
        title="Account"
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
        <CustomerProfilePanel />
        <Panel animated className="flex h-full flex-col" revealDelay={0.08}>
          <h2 className="text-lg font-bold text-slate-950">Documents</h2>
          {documentsStatus === "loading" ? (
            <ClientLoadingWait className="min-h-52" title="Loading documents" />
          ) : documentsStatus === "error" ? (
            <div className="mt-4">
              <EmptyState animated description={documentsError} title="Could not load documents" />
              <div className="mt-3 flex justify-end">
                <Button onClick={() => void loadDocuments()} type="button" variant="secondary">Retry</Button>
              </div>
            </div>
          ) : (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {accountDocumentLabels.map((label, index) => (
                <UploadCard
                  animated
                  displayFiles={displayFilesForLabel(label, docs, metadataFromProfileDocuments(documents))}
                  fileName={docs[label]}
                  key={label}
                  label={label}
                  optional
                  revealDelay={staggerCardDelay(index)}
                  disabled={!editing || savingDocuments}
                  onFilesSelected={(files) => {
                    setSelectedDocumentFiles((current) => ({ ...current, [label]: files }));
                    setDocs((current) => ({ ...current, [label]: joinedFileNames(files) }));
                  }}
                  onRemoveFile={() => {
                    setSelectedDocumentFiles((current) => {
                      const next = { ...current };
                      delete next[label];
                      return next;
                    });
                    setDocs((current) => {
                      const next = { ...current };
                      delete next[label];
                      return next;
                    });
                  }}
                  selectedFiles={selectedDocumentFiles[label] ?? []}
                />
              ))}
            </div>
          )}
          <div className="mt-auto flex flex-wrap justify-end gap-2 pt-4">
            {editing ? (
              <>
                <Button
                  onClick={() => {
                    setDocs(savedDocs);
                    setSelectedDocumentFiles({});
                    setEditing(false);
                  }}
                  disabled={savingDocuments}
                >
                  Cancel
                </Button>
                <Button disabled={savingDocuments} icon={Save} onClick={() => void saveDocuments()} variant="primary">
                  {savingDocuments ? "Saving..." : "Save Documents"}
                </Button>
              </>
            ) : (
              <Button disabled={documentsStatus !== "loaded"} icon={Pencil} onClick={() => setEditing(true)} variant="primary">
                Edit
              </Button>
            )}
          </div>
        </Panel>
      </div>
    </ClientPageContent>
  );
}

function ClaimStep({
  claimableContracts,
  claimableContractsError,
  claimableContractsStatus,
  draft,
  evidenceFileMetadata,
  evidenceFiles,
  profileDocumentsError,
  profileDocumentsStatus,
  removeEvidenceFile,
  retryClaimableContracts,
  selectClaimableContract,
  selectedEvidenceFiles,
  step,
  update,
  updateEvidence
}: {
  claimableContracts: ClaimableContract[];
  claimableContractsError?: string;
  claimableContractsStatus: "loading" | "loaded" | "error";
  draft: ClaimDraft;
  evidenceFileMetadata: Record<string, DraftUploadMetadata[]>;
  evidenceFiles: Record<string, string>;
  profileDocumentsError?: string;
  profileDocumentsStatus: "loading" | "loaded" | "error";
  removeEvidenceFile: (label: string, index: number) => void;
  retryClaimableContracts: () => void;
  selectClaimableContract: (contractId: string) => void;
  selectedEvidenceFiles: Record<string, File[]>;
  step: number;
  update: (field: keyof ClaimDraft, value: string) => void;
  updateEvidence: (label: string, files: File[]) => void;
}) {
  if (step === 0) {
    return (
      <div>
        <StepIntro
          title="What happened?"
          description="Start with the closest category. You can explain the details in your own words later."
          why="The category tells us which documents and policy checks are relevant. It does not decide the claim by itself."
        />
        <div className="mt-4">
          <ReadOnlyField label="Claim reference" value={draft.claimId ?? ""} />
        </div>
        <ChoiceGrid
          onChange={(value) => update("claimType", value)}
          options={[
            ["Fire", "Fire or smoke", "Fire, smoke damage, electrical short"],
            ["Water damage", "Water damage", "Leak, burst pipe, flood inside the property"],
            ["Theft", "Theft or break-in", "Stolen items or forced entry"],
            ["Storm", "Storm damage", "Hail, wind, broken window, roof damage"],
            ["Other", "Something else", "If none of the above fits"]
          ]}
          value={draft.claimType}
        />
      </div>
    );
  }

  if (step === 1) {
    const selectedContract = claimableContracts.find((contract) => contract.contract_id === draft.contractId);
    if (claimableContractsStatus === "loading") {
      return (
        <ClientLoadingWait
          className="min-h-40"
          description="We are checking your active insured contracts."
          title="Loading insured properties"
        />
      );
    }
    if (claimableContractsStatus === "error") {
      return (
        <div>
          <EmptyState
            animated
            description={claimableContractsError ?? "Could not load insured properties."}
            title="Could not load insured properties"
          />
          <div className="mt-3 flex justify-end">
            <Button onClick={retryClaimableContracts} type="button" variant="secondary">Retry</Button>
          </div>
        </div>
      );
    }
    if (!claimableContracts.length) {
      return (
        <EmptyState
          animated
          description="Only issued, unexpired contracts can be used to file a claim."
          title="No claimable insured properties"
        />
      );
    }
    return (
      <div>
        <StepIntro
          title="Which insured property is affected?"
          description="Choose the contract connected to the damaged property. We only show contracts that can be used for a claim."
          why="The contract tells us what is covered, the limits, and the policy period."
        />
        <div className="mt-3">
          <SelectInput
            label="Insured property"
            onChange={selectClaimableContract}
            options={claimableContracts.map((contract) => [contract.contract_id, claimableOptionLabel(contract)])}
            value={draft.contractId}
          />
        </div>
        {selectedContract ? (
          <div className="mt-4">
            <DetailGrid
              animated
              items={[
                ["Address", claimableAddressText(selectedContract)],
                ["Contract", getContractDisplayIdentifier(selectedContract)],
                ["Policy period", claimablePeriodLabel(selectedContract)],
                ["Coverage amount", formatCurrency(numberValue(selectedContract.coverage_amount))]
              ]}
            />
          </div>
        ) : null}
      </div>
    );
  }

  if (step === 2) {
    return (
      <div>
        <StepIntro
          title="When did it happen?"
          description="Use the best time you know. If the exact minute is unclear, choose an approximate time."
          why="The incident date helps us confirm that the policy was active and understand the claim timeline."
        />
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <TextInput label="Date of incident" onChange={(value) => update("incidentDate", value)} type="date" value={draft.incidentDate} />
          <TextInput label="Time of incident" onChange={(value) => update("incidentTime", value)} type="time" value={draft.incidentTime} />
          <SelectInput
            label="Were emergency services involved?"
            onChange={(value) => update("emergencyServices", value)}
            options={[["Yes", "Yes"], ["No", "No"]]}
            value={draft.emergencyServices}
          />
        </div>
      </div>
    );
  }

  if (step === 3) {
    return (
      <div>
        <StepIntro
          title="What was damaged?"
          description="Describe the damage like you would explain it to a person. The amount can be an estimate; invoices can come later."
          why="A clear description helps us decide what evidence is needed and avoids unnecessary back-and-forth."
          examples={{
            better: "A pipe burst under the sink and damaged the kitchen cabinet and wall.",
            avoid: "Something broke."
          }}
        />
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <TextInput
            helper="Estimate the repair or replacement cost. You can update it if you receive an invoice."
            label="Estimated damage amount (RON)"
            onChange={(value) => update("estimatedDamage", value)}
            placeholder="5000"
            type="number"
            value={draft.estimatedDamage}
          />
          <div className="md:col-span-2">
            <TextAreaInput
              helper="Example: A pipe burst under the sink and damaged the kitchen cabinet and wall."
              label="Describe what happened"
              onChange={(value) => update("description", value)}
              placeholder="Tell us what happened, what was damaged, and what you have already done."
              value={draft.description}
            />
          </div>
        </div>
      </div>
    );
  }

  if (step === 4) {
    return (
      <div>
        <StepIntro
          title="How should we contact you?"
          description="Use the best phone and email for claim updates. We will use these for follow-up requests and decision messages."
          why="Wrong contact details can delay inspection, document requests, or payment updates."
        />
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <TextInput label="Full name of insured" onChange={(value) => update("fullName", value)} value={draft.fullName} />
          <TextInput label="Phone" onChange={(value) => update("phone", value)} value={draft.phone} />
          <TextInput label="Email" onChange={(value) => update("email", value)} type="email" value={draft.email} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <StepIntro
        title="Upload what you have now"
        description="Photos are the most useful first evidence. Other documents are optional here; if something is missing, we will ask for it clearly."
        why="Documents help us verify the event faster, but you should not need to upload the same documents repeatedly."
      />
      <div className="mt-3 space-y-4">
        <div className="border-l-4 border-orange-500 pl-3">
          <p className="mb-2 text-xs font-bold uppercase tracking-normal text-orange-600">Required</p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {requiredClaimDocumentLabels.map((label) => (
              <UploadCard
                displayFiles={displayFilesForLabel(label, evidenceFiles, evidenceFileMetadata)}
                fileName={evidenceFiles[label]}
                key={label}
                label={label}
                multiple
                onFilesSelected={(files) => updateEvidence(label, files)}
                onRemoveFile={(index) => removeEvidenceFile(label, index)}
                selectedFiles={selectedEvidenceFiles[label] ?? []}
                size="compact"
              />
            ))}
          </div>
        </div>
        <div className="border-l border-slate-200 pl-3">
          <p className="mb-2 text-xs font-bold uppercase tracking-normal text-slate-500">Optional</p>
          {profileDocumentsStatus === "loading" ? (
            <p className="mb-2 text-xs font-semibold text-slate-500">Loading account documents...</p>
          ) : null}
          {profileDocumentsStatus === "error" ? (
            <p className="mb-2 text-xs font-semibold text-red-600">{profileDocumentsError ?? "Could not load account documents."}</p>
          ) : null}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {accountDocumentLabels.map((label) => (
              <UploadCard
                displayFiles={displayFilesForLabel(label, evidenceFiles, evidenceFileMetadata)}
                fileName={evidenceFiles[label]}
                key={label}
                label={label}
                multiple
                optional
                onFilesSelected={(files) => updateEvidence(label, files)}
                onRemoveFile={(index) => removeEvidenceFile(label, index)}
                selectedFiles={selectedEvidenceFiles[label] ?? []}
                size="compact"
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function StepIntro({
  title,
  description,
  why,
  examples
}: {
  title: string;
  description: string;
  why: string;
  examples?: {
    better: string;
    avoid: string;
  };
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
      <h2 className="text-xl font-extrabold text-zinc-950">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-zinc-600">{description}</p>
      <p className="mt-3 rounded-lg border border-orange-100 bg-orange-50 px-3 py-2 text-sm leading-6 text-orange-900">
        <span className="font-extrabold">Helps with:</span> {why}
      </p>
      {examples ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm leading-5 text-emerald-900">
            <span className="block font-extrabold">Better</span>
            {examples.better}
          </div>
          <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm leading-5 text-zinc-600">
            <span className="block font-extrabold text-zinc-800">Avoid</span>
            {examples.avoid}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ChoiceGrid({
  options,
  value,
  onChange
}: {
  options: Array<[string, string, string]>;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      {options.map(([optionValue, title, description]) => {
        const selected = value === optionValue;
        return (
          <button
            className={`rounded-xl border p-4 text-left transition focus:outline-none focus:ring-4 focus:ring-orange-100 ${
              selected
                ? "border-orange-500 bg-orange-50 text-zinc-950 shadow-sm"
                : "border-zinc-200 bg-white text-zinc-800 hover:border-zinc-300 hover:bg-zinc-50"
            }`}
            key={optionValue}
            onClick={() => onChange(optionValue)}
            type="button"
          >
            <span className="block text-sm font-extrabold">{title}</span>
            <span className="mt-1 block text-sm leading-5 text-zinc-600">{description}</span>
          </button>
        );
      })}
    </div>
  );
}

function QuickPickRow({
  label,
  options,
  onPick
}: {
  label: string;
  options: Array<[string, string]>;
  onPick: (value: string) => void;
}) {
  return (
    <div className="mt-3">
      <p className="text-xs font-extrabold uppercase tracking-[0.12em] text-zinc-500">{label}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map(([value, labelText]) => (
          <button
            className="rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs font-extrabold text-zinc-700 transition hover:border-orange-300 hover:bg-orange-50 hover:text-orange-700 focus:outline-none focus:ring-4 focus:ring-orange-100"
            key={`${value}-${labelText}`}
            onClick={() => onPick(value)}
            type="button"
          >
            {labelText}
          </button>
        ))}
      </div>
    </div>
  );
}

function QuoteFlowGuide({
  draft,
  pricing,
  stepId
}: {
  draft: QuoteDraft;
  pricing: ReturnType<typeof getPremiumPreviewBreakdown>;
  stepId: QuoteStepId;
}) {
  const coverage = Number(draft.coverageAmount);
  const missing = [
    !draft.propertyType ? "property type" : null,
    !(draft.address.city && draft.address.street) ? "address" : null,
    !Number.isFinite(coverage) || coverage <= 0 ? "protected amount" : null,
    !draft.areaSqm ? "size" : null,
    !draft.yearBuilt ? "build year" : null,
    !draft.constructionType ? "structure" : null
  ].filter(Boolean);
  const premium = pricing.estimatedPremium ?? pricing.finalPremium;

  return (
    <aside className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm xl:sticky xl:top-4">
      <div className="rounded-xl bg-zinc-950 p-4 text-white">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-white/60">Live monthly estimate</p>
        <p className="mt-2 text-3xl font-extrabold">{formatCurrency(premium || 0)}</p>
      </div>
      <div className="mt-4 space-y-3">
        <MiniFact label="Current step" value={quoteStepDefinitions.find((step) => step.id === stepId)?.label ?? "Quote"} />
        <MiniFact label="Still needed" value={missing.length ? missing.slice(0, 3).join(", ") : "ready to review"} />
      </div>
    </aside>
  );
}

function ClaimFlowGuide({
  claimableContracts,
  draft,
  evidenceFiles,
  step
}: {
  claimableContracts: ClaimableContract[];
  draft: ClaimDraft;
  evidenceFiles: Record<string, string>;
  step: number;
}) {
  const selectedContract = claimableContracts.find((contract) => contract.contract_id === draft.contractId);
  const hasPhotos = hasEvidenceForLabel(evidenceFiles, "Photos from incident");
  const missing = [
    !draft.claimType ? "what happened" : null,
    !selectedContract ? "insured property" : null,
    !draft.incidentDate ? "incident date" : null,
    !draft.description ? "damage description" : null,
    !hasPhotos ? "photos" : null
  ].filter(Boolean);

  return (
    <aside className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm xl:sticky xl:top-4">
      <div className="grid gap-3">
        <MiniFact label="Current step" value={claimSteps[step] ?? "Claim"} />
        <MiniFact label="Property" value={selectedContract ? getContractDisplayIdentifier(selectedContract) : "not selected"} />
        <MiniFact label="Still needed" value={missing.length ? missing.slice(0, 3).join(", ") : "ready to send"} />
      </div>
    </aside>
  );
}

function QuoteStep({ draft, stepId, update, updateAddress }: { draft: QuoteDraft; stepId: QuoteStepId; update: (field: keyof QuoteDraft, value: any) => void; updateAddress: (field: keyof QuoteDraft["address"], value: string) => void }) {
  if (stepId === "propertyType") {
    return (
      <div>
        <StepIntro
          title="What do you want to protect?"
          description="Choose the closest option. This only helps us start with the right questions and price model."
          why="Different property types have different common risks. A house, an apartment, and a commercial space are not priced the same way."
        />
        <ChoiceGrid
          onChange={(value) => update("propertyType", value)}
          options={[
            ["Apartment", "Apartment", "Flat or apartment in a block"],
            ["House", "House", "Individual house or duplex"],
            ["Commercial", "Commercial", "Office, shop, or business property"]
          ]}
          value={draft.propertyType}
        />
      </div>
    );
  }

  if (stepId === "address") {
    const fields: Array<[keyof QuoteDraft["address"], string, string]> = [
      ["country", "Country", "Romania"],
      ["county", "County", "București"],
      ["city", "City", "București"],
      ["street", "Street", "Str. Aviatorilor"],
      ["number", "Number", "12"],
      ["postal_code", "Postal code", "010862"]
    ];
    return (
      <div>
        <StepIntro
          title="Where is the property?"
          description="The address helps us understand local risks and connect the quote to the right home."
          why="Some risks depend on location. For example, flood exposure, storm history, or building density can affect the recommendation."
        />
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {fields.map(([field, label, placeholder]) => (
            <TextInput key={field} label={label} onChange={(value) => updateAddress(field, value)} placeholder={placeholder} value={draft.address[field]} />
          ))}
        </div>
      </div>
    );
  }

  if (stepId === "coverage") {
    return (
      <div>
        <StepIntro
          title="How much should be protected?"
          description="This is the amount the policy is built around. It should be close to the value needed to repair or replace the property, not the emotional value of the home."
          why="A lower amount can make the price cheaper, but it can also leave you under-protected. A higher amount can increase the price."
          examples={{
            better: "Use a realistic repair or rebuild estimate, such as 350,000 RON.",
            avoid: "Choosing a very low amount only to reduce the price."
          }}
        />
        <div className="mt-4">
          <TextInput
            helper="Estimate is fine. You can adjust this after you compare the offer."
            label="Protected amount (RON)"
            onChange={(value) => update("coverageAmount", value)}
            placeholder="350000"
            type="number"
            value={draft.coverageAmount}
          />
          <QuickPickRow
            label="Use a quick estimate"
            options={[
              ["150000", "150k RON"],
              ["250000", "250k RON"],
              ["350000", "350k RON"],
              ["500000", "500k RON"]
            ]}
            onPick={(value) => update("coverageAmount", value)}
          />
        </div>
      </div>
    );
  }

  if (stepId === "size") {
    return (
      <div>
        <StepIntro
          title="How large is it?"
          description="You do not need the exact cadastral measurement. A close estimate is enough to calculate a first price."
          why="Larger homes usually cost more to repair, so size affects the premium."
        />
        <div className="mt-4">
          <TextInput
            helper="Use the useful area if you know it. If not, choose one of the estimates below."
            label="Approximate size in square meters"
            onChange={(value) => update("areaSqm", value)}
            placeholder="78"
            type="number"
            value={draft.areaSqm}
          />
          <QuickPickRow
            label="I am not sure"
            options={[
              ["55", "Small apartment"],
              ["78", "Typical apartment"],
              ["120", "House"],
              ["180", "Large home"]
            ]}
            onPick={(value) => update("areaSqm", value)}
          />
        </div>
      </div>
    );
  }

  if (stepId === "age") {
    return (
      <div>
        <StepIntro
          title="When was it built?"
          description="If you do not know the exact year, use a realistic estimate. We will not hide that it is an estimate."
          why="Older buildings may have different plumbing, electrical, and structural risks."
        />
        <div className="mt-4">
          <TextInput
            helper="Look in the property documents if you have them. Otherwise pick the closest decade."
            label="Construction year"
            onChange={(value) => update("yearBuilt", value)}
            placeholder="2012"
            type="number"
            value={draft.yearBuilt}
          />
          <QuickPickRow
            label="Use an estimate"
            options={[
              ["1980", "Older"],
              ["2000", "Not sure"],
              ["2015", "Newer"],
              [String(new Date().getFullYear() - 2), "Almost new"]
            ]}
            onPick={(value) => update("yearBuilt", value)}
          />
        </div>
      </div>
    );
  }

  if (stepId === "construction") {
    return (
      <div>
        <StepIntro
          title="What is it mostly built from?"
          description="Choose the closest structure type. If you do not know, use the recommended option and we can confirm later from documents."
          why="The structure affects fire, earthquake, and repair-cost assumptions."
        />
        <ChoiceGrid
          onChange={(value) => update("constructionType", value)}
          options={[
            ["Concrete", "Concrete", "Recommended if you are unsure for most apartment blocks"],
            ["Brick", "Brick", "Common masonry structure"],
            ["Wood", "Wood", "Usually higher fire risk"],
            ["Steel", "Steel", "Often used in commercial buildings"]
          ]}
          value={draft.constructionType}
        />
      </div>
    );
  }

  if (stepId === "use") {
    return (
      <div>
        <StepIntro
          title="How is the property used?"
          description="This tells us how often the property is occupied and what kind of activity happens there."
          why="A vacant or rented property can have different claim frequency than a home you live in."
        />
        <ChoiceGrid
          onChange={(value) => update("usageType", value)}
          options={[
            ["Owner occupied", "I live there", "Main residence"],
            ["Rented", "Rented out", "Tenant lives there"],
            ["Holiday home", "Holiday home", "Used occasionally"],
            ["Vacant", "Vacant", "Usually empty"],
            ["Commercial use", "Business use", "Used for business activity"]
          ]}
          value={draft.usageType}
        />
      </div>
    );
  }

  if (stepId === "claims") {
    return (
      <div>
        <StepIntro
          title="Any previous property claims?"
          description="We ask about recent claims so the price is transparent. This does not automatically mean rejection."
          why="Previous claims can influence risk, but the type and number matter."
        />
        <ChoiceGrid
          onChange={(value) => {
            update("hadClaims", value);
            if (value === "No") update("previousClaimsCount", "0");
          }}
          options={[
            ["No", "No", "No property claims in the last 5 years"],
            ["Yes", "Yes", "There were one or more claims"]
          ]}
          value={draft.hadClaims}
        />
        {draft.hadClaims === "Yes" ? (
          <div className="mt-4 max-w-sm">
            <TextInput
              helper="Approximate count is enough. We may ask for details later if needed."
              label="How many claims?"
              onChange={(value) => update("previousClaimsCount", value)}
              type="number"
              value={draft.previousClaimsCount}
            />
          </div>
        ) : null}
      </div>
    );
  }

  if (stepId === "security") {
    return (
      <div>
        <StepIntro
          title="What safety features are already installed?"
          description="Select what you have. These can reduce risk and may improve the offer."
          why="Alarms, detectors, and secure doors can reduce the chance or size of a claim."
        />
        <SecuritySelector selected={draft.securityFeatures} onChange={(features) => update("securityFeatures", features)} />
      </div>
    );
  }

  return (
    <div>
      <StepIntro
        title="Confirm your contact details"
        description="These details are used to issue the quote and contract documents correctly."
        why="Wrong contact or ID data can slow down contract generation or claim handling later."
      />
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <TextInput label="Full name" onChange={(value) => update("fullName", value)} value={draft.fullName} />
        <TextInput label="Email" onChange={(value) => update("email", value)} type="email" value={draft.email} />
        <TextInput label="Phone number" onChange={(value) => update("phone", value)} value={draft.phone} />
        <TextInput helper="For Romanian individuals this is usually CNP." label="ID / national identifier" onChange={(value) => update("nationalId", value)} value={draft.nationalId} />
      </div>
    </div>
  );
}

function TextInput({
  disabled = false,
  helper,
  label,
  onChange,
  placeholder,
  type = "text",
  value
}: {
  disabled?: boolean;
  helper?: string;
  label: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
  value: string;
}) {
  return (
    <label className="block text-sm font-bold text-zinc-700">
      {label}
      <input
        className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none transition placeholder:text-zinc-400 focus:border-orange-500 focus:ring-4 focus:ring-orange-100 ${
          disabled ? "border-zinc-200 bg-zinc-50 text-zinc-600" : "border-zinc-200 bg-white text-zinc-900"
        }`}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        type={type}
        value={value}
      />
      {helper ? <span className="mt-1 block text-xs font-semibold leading-5 text-zinc-500">{helper}</span> : null}
    </label>
  );
}

function TextAreaInput({
  helper,
  label,
  onChange,
  placeholder,
  value
}: {
  helper?: string;
  label: string;
  onChange: (value: string) => void;
  placeholder?: string;
  value: string;
}) {
  return (
    <label className="block text-sm font-bold text-zinc-700">
      {label}
      <textarea
        className="mt-1 min-h-32 w-full resize-y rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-400 focus:border-orange-500 focus:ring-4 focus:ring-orange-100"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        value={value}
      />
      {helper ? <span className="mt-1 block text-xs font-semibold leading-5 text-zinc-500">{helper}</span> : null}
    </label>
  );
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return <label className="block text-sm font-bold text-zinc-700">{label}<input className="mt-1 w-full rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-700" readOnly value={value} /></label>;
}

function SelectInput({
  disabled = false,
  label,
  onChange,
  options,
  value
}: {
  disabled?: boolean;
  label: string;
  onChange: (value: string) => void;
  options: string[][];
  value: string;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const selectedLabel = options.find(([optionValue]) => optionValue === value)?.[1] ?? "Select";

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function selectValue(nextValue: string) {
    if (disabled) return;
    onChange(nextValue);
    setOpen(false);
  }

  return (
    <div className="relative block text-sm font-bold text-slate-700" ref={containerRef}>
      <p>{label}</p>
      <button
        aria-expanded={open}
        className={`mt-1 flex w-full items-center justify-between rounded-lg border-2 px-3 py-2 text-left text-sm font-semibold shadow-sm outline-none transition focus:border-orange-600 focus:ring-4 focus:ring-orange-100 ${
          disabled
            ? "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-600"
            : "border-slate-500 bg-white text-slate-800 hover:border-orange-600 hover:bg-slate-50"
        }`}
        disabled={disabled}
        onClick={() => {
          if (!disabled) setOpen((current) => !current);
        }}
        type="button"
      >
        <span className={value ? "text-slate-900" : "text-slate-400"}>{selectedLabel}</span>
        <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-48 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          <button
            className="block w-full px-3 py-2 text-left text-sm font-semibold text-slate-500 hover:bg-slate-50"
            onClick={() => {
              selectValue("");
            }}
            type="button"
          >
            Select
          </button>
          {options.map(([optionValue, optionLabel]) => (
            <button
              className={`block w-full px-3 py-2 text-left text-sm font-semibold hover:bg-orange-50 ${
                value === optionValue ? "bg-orange-50 text-orange-600" : "text-slate-700"
              }`}
              key={optionValue}
              onClick={() => {
                selectValue(optionValue);
              }}
              type="button"
            >
              {optionLabel}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function OptionGroup({ label, options, value, onChange }: { label: string; options: string[]; value: string; onChange: (value: string) => void }) {
  return (
    <div>
      <p className="text-base font-bold text-slate-950">{label}</p>
      <div className="mt-3 max-w-xl">
        <SelectInput
          label="Answer"
          onChange={onChange}
          options={options.map((option) => [option, option])}
          value={value}
        />
      </div>
    </div>
  );
}

function SecuritySelector({ selected, onChange }: { selected: SecurityFeature[]; onChange: (features: SecurityFeature[]) => void }) {
  const options: SecurityFeature[] = ["Alarm", "Smoke detector", "Sprinklers", "Security cameras", "Security door", "Security guard"];
  return (
    <div className="mt-4">
      <div className="grid gap-2 md:grid-cols-3">
        {options.map((option) => {
          const checked = selected.includes(option);
          return (
            <label
              className={`cursor-pointer rounded-xl border px-3 py-3 text-sm font-bold shadow-sm transition ${
                checked
                  ? "border-orange-400 bg-orange-50 text-zinc-950 ring-1 ring-orange-100"
                  : "border-zinc-200 bg-white text-zinc-800 hover:border-zinc-300 hover:bg-zinc-50"
              }`}
              key={option}
            >
              <input
                checked={checked}
                className="mr-2 accent-orange-600"
                onChange={(event) => onChange(event.target.checked ? [...selected, option] : selected.filter((item) => item !== option))}
                type="checkbox"
              />
              {option}
            </label>
          );
        })}
      </div>
      <p className="mt-3 text-sm leading-6 text-zinc-600">
        Select only what exists today. We can ask for proof later only if it affects the final offer.
      </p>
    </div>
  );
}

