import { createContext, type ComponentType, type CSSProperties, type FormEvent, type KeyboardEvent, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ClipboardList,
  Download,
  Eye,
  FilePlus2,
  FileText,
  PenLine,
  RefreshCw,
  Send,
  Sparkles,
  UserSearch,
  Users,
  X
} from "lucide-react";
import { Link, Navigate, Outlet, useLocation, useNavigate, useOutletContext, useParams } from "react-router-dom";
import {
  Button,
  DataTable,
  DetailGrid,
  EmptyState,
  MockDocumentItem,
  Modal,
  Panel,
  RulesTable,
  StatusBadge,
  formatCurrency,
  formatDate
} from "../components/ui";
import { GeneratedDocumentPdfViewer } from "../components/GeneratedDocumentPdfViewer";
import { EmployeePageHeader } from "../components/navigation/EmployeePageHeader";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { DATA_SOURCE_MODE } from "../config/dataSource";
import {
  approveClaim,
  dismissClaimAiSuggestion,
  generateEvidenceRequestDraft,
  getAllClaims,
  getLatestClaimReview,
  refreshClaimAttachmentAnalysis,
  rewordClaimDecisionJustification,
  rejectClaim,
  requestOnPremisesInspection,
  startClaimAnalysis,
  startClaimReview,
  sendDemoInboundClaimEmail,
  sendEvidenceRequestDraft,
  sendClaimDecisionEmail,
  updateEvidenceRequestDraft
} from "../services/claimService";
import { apiBlobRequest } from "../services/backend/http";
import {
  convertQuoteToContract,
  createGeneratedDocumentPdf,
  downloadGeneratedDocumentPdf,
  generateContractDocument,
  getContract,
  getContracts,
  getLatestContractDocument,
  resolveQuoteContract
} from "../services/contractService";
import {
  getCustomerAuthUsers,
  getCustomerProfile,
  listCustomers,
  linkAuthUserToCustomer,
  relinkAuthUserToCustomer,
  unlinkAuthUserFromCustomer
} from "../services/customerAdminService";
import { getCustomerEmailHistory } from "../services/emailService";
import { searchAuthUsers } from "../services/authUserAdminService";
import {
  acceptTemplateChangeSuggestionHunk,
  createDraftRevisionFromSuggestion,
  createTemplateChangeSuggestion,
  getTemplateChangeSuggestion,
  getLegalChanges,
  rejectTemplateChangeSuggestionHunk,
  submitDraftRevisionForApproval,
  updateTemplateChangeSuggestionHunk
} from "../services/legalChangeService";
import {
  employeeApproveQuote,
  employeeRejectQuote,
  getAllQuotes,
  getQuoteAcceptance,
  getQuoteDecisionAudit,
  getQuoteById
} from "../services/quoteService";
import { getUnderwritingRules, updateUnderwritingRules } from "../services/rulesService";
import type {
  AiFollowUpSuggestion,
  AiReviewFinding,
  AiReviewLifecycleStatus,
  Claim,
  ClaimStatus,
  ClaimType,
  AuthUserSearchResult,
  BackendValidationIssue,
  ContractDetail,
  CustomerAuthUserRelinkResult,
  CustomerAdminSummary,
  CustomerEmailMessage,
  CustomerLinkedAuthUser,
  CustomerLegalDocument,
  CustomerProfileDetail,
  CustomerProfileStatus,
  EvidenceRequestDraft,
  SuggestedEmailDraft,
  GeneratedDocument,
  GeneratedDocumentPdfArtifact,
  LegalChangeItem,
  LegalTemplateReviewCandidate,
  PropertyType,
  Quote,
  QuoteAcceptance,
  QuoteContractResolution,
  QuoteDecisionAuditRecord,
  QuoteStatus,
  TemplateChangeSuggestion,
  TemplateChangeSuggestionDetail,
  TemplateChangeSuggestionHunk,
  TemplateDraftRevision,
  UnderwritingRuleBlock,
  UnderwritingRulesDocument
} from "../types";
import {
  getQuotePremium,
  getQuotePricingSourceLabel,
  getQuoteRiskRecommendation,
  getQuoteRiskSourceLabel,
  isQuotePricingBackendDriven,
  isQuotePricingUnavailable,
  isQuoteRiskBackendDriven,
  isQuoteRiskUnavailable
} from "../utils/quotePricing";
import {
  getClaimContractDisplayIdentifier,
  getContractDisplayIdentifier,
  getContractLifecycleDisplayStatus,
  getContractLifecycleStatusLabel,
  type ContractLifecycleDisplayStatus
} from "../utils/contractDisplay";
import { getClaimDisplayIdentifier } from "../utils/claimDisplay";

export function EmployeeHomePage() {
  const { user } = useAuth();
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [quotePeriod, setQuotePeriod] = useState<DashboardPeriod>("month");
  const [claimPeriod, setClaimPeriod] = useState<DashboardPeriod>("month");
  const { showToast } = useToast();

  function loadDashboardData() {
    setIsLoading(true);
    setLoadError(undefined);
    void Promise.all([getAllQuotes(), getAllClaims()])
      .then(([quoteItems, claimItems]) => {
        setQuotes(quoteItems);
        setClaims(claimItems);
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : "Could not load dashboard data.";
        setLoadError(message);
        showToast(message, "error");
        setQuotes([]);
        setClaims([]);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }

  useEffect(() => {
    loadDashboardData();
  }, []);

  const metrics = useMemo(() => buildDashboardMetrics(quotes, claims), [quotes, claims]);
  const quoteSeries = useMemo(
    () => buildDateSeries(quotes, (quote) => quote.createdAt, quotePeriod),
    [quotePeriod, quotes]
  );
  const claimSeries = useMemo(
    () => buildDateSeries(claims, (claim) => claim.createdAt, claimPeriod),
    [claimPeriod, claims]
  );
  const quoteAttentionQueue = useMemo(() => buildQuoteAttentionQueue(quotes), [quotes]);
  const claimAttentionQueue = useMemo(() => buildClaimAttentionQueue(claims), [claims]);
  const greetingTitle = user?.fullName?.trim() ? `Hello, ${user.fullName}` : "Hello";

  return (
    <>
      <EmployeePageHeader
        actions={
          <Button disabled={isLoading} icon={RefreshCw} onClick={loadDashboardData}>
            Refresh
          </Button>
        }
        title={greetingTitle}
      />
      {loadError ? (
        <Panel className="mb-4 border-red-200 bg-red-50">
          <p className="text-sm font-semibold text-red-700">{loadError}</p>
        </Panel>
      ) : null}
      <div className="grid gap-4 md:grid-cols-3">
        <DashboardStatCard
          detail={`${formatWholeNumber(quotes.length)} quote records and ${formatWholeNumber(claims.length)} claim records`}
          icon={Users}
          isLoading={isLoading}
          title="Clients"
          tone="blue"
          value={metrics.clientCount}
        />
        <DashboardStatCard
          detail={formatDate(metrics.today)}
          icon={FilePlus2}
          isLoading={isLoading}
          title="New requests today"
          tone="emerald"
          value={metrics.newQuoteRequestsToday}
        />
        <DashboardStatCard
          detail={formatDate(metrics.today)}
          icon={ClipboardList}
          isLoading={isLoading}
          title="New claims today"
          tone="amber"
          value={metrics.newClaimsToday}
        />
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <DashboardStatCard
          detail={`${formatWholeNumber(metrics.quoteDecisionCount)} completed quote decisions`}
          icon={FileText}
          isLoading={isLoading}
          title="Open quote backlog"
          tone="blue"
          value={metrics.openQuoteBacklog}
        />
        <DashboardStatCard
          detail={`${formatWholeNumber(metrics.claimOutcomeCount)} tracked claim outcomes`}
          icon={ClipboardList}
          isLoading={isLoading}
          title="Open claim backlog"
          tone="amber"
          value={metrics.openClaimBacklog}
        />
        <DashboardStatCard
          detail={`Avg ${formatCurrency(metrics.averageQuotePremium)} across ${formatWholeNumber(metrics.premiumOpportunityCount)} active quotes`}
          icon={Sparkles}
          isLoading={isLoading}
          title="Premium opportunity"
          tone="emerald"
          value={formatCurrency(metrics.premiumOpportunityTotal)}
          valueClassName="text-2xl"
        />
        <DashboardStatCard
          detail={`Avg ${formatCurrency(metrics.averageClaimDamage)} across ${formatWholeNumber(metrics.claimExposureCount)} claims`}
          icon={Eye}
          isLoading={isLoading}
          title="Claim exposure"
          tone="blue"
          value={formatCurrency(metrics.claimExposureTotal)}
          valueClassName="text-2xl"
        />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <DashboardBarChart
          emptyText="No quote request data available for this period."
          icon={FilePlus2}
          onPeriodChange={setQuotePeriod}
          period={quotePeriod}
          points={quoteSeries}
          title="Quote requests"
          tone="emerald"
        />
        <DashboardBarChart
          emptyText="No claim data available for this period."
          icon={ClipboardList}
          onPeriodChange={setClaimPeriod}
          period={claimPeriod}
          points={claimSeries}
          title="Claims"
          tone="amber"
        />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <DashboardBreakdownPanel
          detail={`${formatPercent(metrics.quoteApprovalRate)} approval rate`}
          emptyText="No completed quote decisions yet."
          icon={Check}
          items={metrics.quoteDecisionMix}
          title="Quote decision mix"
          tone="emerald"
        />
        <DashboardBreakdownPanel
          detail={`${formatWholeNumber(metrics.openClaimBacklog)} claims still open`}
          emptyText="No completed claim outcomes yet."
          icon={ClipboardList}
          items={metrics.claimDecisionMix}
          title="Claim outcome mix"
          tone="amber"
        />
        <DashboardBreakdownPanel
          detail={`${formatWholeNumber(metrics.highRiskQuoteCount)} high-risk quote${metrics.highRiskQuoteCount === 1 ? "" : "s"}`}
          emptyText="No claim type data available yet."
          icon={UserSearch}
          items={metrics.claimTypeMix}
          title="Claim type mix"
          tone="blue"
        />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <DashboardAttentionPanel
          detail="High-risk and newest open quote requests"
          emptyText="No quotes need review right now."
          icon={FilePlus2}
          items={quoteAttentionQueue.map((quote) => ({
            key: quote.id,
            title: quote.clientName || "Unknown client",
            description: `${quote.propertyType} · ${quote.propertyAddress}`,
            href: `/employee/quotes/${quote.id}`,
            badge: formatQuoteRiskBadge(quote),
            meta: `${formatQuotePremiumForDisplay(quote)} · ${formatDate(quote.createdAt)}`
          }))}
          title="Quote review queue"
          tone="emerald"
        />
        <DashboardAttentionPanel
          detail="Largest open claims needing action"
          emptyText="No claims need action right now."
          icon={ClipboardList}
          items={claimAttentionQueue.map((claim) => ({
            key: claim.id,
            title: getClaimDisplayIdentifier(claim),
            description: `${claim.clientName} · ${claim.claimType}`,
            href: `/employee/claims/${claim.id}`,
            badge: claim.status === "inspection_requested" ? "Inspection" : titleCaseLabel(claim.status),
            meta: `${formatCurrency(claim.estimatedDamage)} · ${formatDate(claim.createdAt)}`
          }))}
          title="Claim action queue"
          tone="amber"
        />
      </div>
    </>
  );
}

type DashboardPeriod = "day" | "week" | "month" | "year";
type DashboardTone = "blue" | "emerald" | "amber";

interface DashboardPoint {
  key: string;
  label: string;
  value: number;
}

interface DashboardBreakdownItem {
  key: string;
  label: string;
  value: number;
}

interface DashboardAttentionItem {
  key: string;
  title: string;
  description: string;
  href: string;
  badge: string;
  meta: string;
}

const dashboardPeriods: Array<{ value: DashboardPeriod; label: string }> = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "year", label: "Year" }
];

const dashboardTones: Record<
  DashboardTone,
  {
    card: string;
    icon: string;
    bar: string;
    button: string;
  }
> = {
  blue: {
    card: "border-slate-200 bg-white text-orange-600",
    icon: "bg-orange-100 text-orange-600",
    bar: "bg-orange-600",
    button: "bg-orange-600 text-white"
  },
  emerald: {
    card: "border-slate-200 bg-white text-emerald-700",
    icon: "bg-emerald-100 text-emerald-700",
    bar: "bg-emerald-600",
    button: "bg-emerald-600 text-white"
  },
  amber: {
    card: "border-slate-200 bg-white text-amber-700",
    icon: "bg-amber-100 text-amber-700",
    bar: "bg-amber-500",
    button: "bg-amber-500 text-white"
  }
};

function DashboardStatCard({
  detail,
  icon: Icon,
  isLoading,
  title,
  tone,
  value,
  valueClassName = "text-3xl"
}: {
  detail: string;
  icon: ComponentType<{ className?: string }>;
  isLoading: boolean;
  title: string;
  tone: DashboardTone;
  value: ReactNode;
  valueClassName?: string;
}) {
  const colors = dashboardTones[tone];
  const displayValue = typeof value === "number" ? formatWholeNumber(value) : value;
  return (
    <Panel className={`border ${colors.card}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold uppercase tracking-normal opacity-80">{title}</p>
          <p className={`mt-3 font-bold text-slate-950 ${valueClassName}`}>
            {isLoading ? "..." : displayValue}
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-600">{detail}</p>
        </div>
        <span className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${colors.icon}`}>
          <Icon className="h-5 w-5" />
        </span>
      </div>
    </Panel>
  );
}

function DashboardBarChart({
  emptyText,
  icon: Icon,
  onPeriodChange,
  period,
  points,
  title,
  tone
}: {
  emptyText: string;
  icon: ComponentType<{ className?: string }>;
  onPeriodChange: (period: DashboardPeriod) => void;
  period: DashboardPeriod;
  points: DashboardPoint[];
  title: string;
  tone: DashboardTone;
}) {
  const colors = dashboardTones[tone];
  const maxValue = Math.max(1, ...points.map((point) => point.value));
  const hasData = points.some((point) => point.value > 0);

  return (
    <Panel className="bg-white">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <span className={`inline-flex h-10 w-10 items-center justify-center rounded-lg ${colors.icon}`}>
            <Icon className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-lg font-bold text-slate-950">{title}</h2>
            <p className="text-sm font-semibold text-slate-500">Volume by selected period</p>
          </div>
        </div>
        <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1">
          {dashboardPeriods.map((item) => (
            <button
              className={`min-h-8 rounded-md px-2.5 text-xs font-bold transition ${
                item.value === period ? colors.button : "text-slate-600 hover:bg-white hover:text-slate-950"
              }`}
              key={item.value}
              onClick={() => onPeriodChange(item.value)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {hasData ? (
        <div
          aria-label={`${title} chart`}
          className="mt-6 grid min-h-72 items-end gap-2"
          role="img"
          style={{ gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))` }}
        >
          {points.map((point) => {
            const height = 16 + Math.round((point.value / maxValue) * 188);
            return (
              <div className="flex min-w-0 flex-col items-center justify-end gap-2" key={point.key}>
                <span className="text-xs font-bold text-slate-700">{formatWholeNumber(point.value)}</span>
                <div className="flex h-52 w-full items-end rounded-md bg-slate-100 px-1.5 py-1.5">
                  <div
                    className={`w-full rounded ${colors.bar}`}
                    style={{ height }}
                    title={`${point.label}: ${formatWholeNumber(point.value)}`}
                  />
                </div>
                <span className="w-full truncate text-center text-[11px] font-semibold text-slate-500">
                  {point.label}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-6">
          <EmptyState description="Try a broader period once more records are available." title={emptyText} />
        </div>
      )}
    </Panel>
  );
}

function DashboardBreakdownPanel({
  detail,
  emptyText,
  icon: Icon,
  items,
  title,
  tone
}: {
  detail: string;
  emptyText: string;
  icon: ComponentType<{ className?: string }>;
  items: DashboardBreakdownItem[];
  title: string;
  tone: DashboardTone;
}) {
  const colors = dashboardTones[tone];
  const maxValue = Math.max(1, ...items.map((item) => item.value));
  const hasData = items.some((item) => item.value > 0);

  return (
    <Panel className="bg-white">
      <div className="flex items-start gap-3">
        <span className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${colors.icon}`}>
          <Icon className="h-5 w-5" />
        </span>
        <div>
          <h2 className="text-lg font-bold text-slate-950">{title}</h2>
          <p className="text-sm font-semibold text-slate-500">{detail}</p>
        </div>
      </div>
      {hasData ? (
        <div className="mt-5 space-y-3">
          {items.map((item) => (
            <div key={item.key}>
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="font-semibold text-slate-700">{item.label}</span>
                <span className="font-bold text-slate-950">{formatWholeNumber(item.value)}</span>
              </div>
              <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={`h-full rounded-full ${colors.bar}`}
                  style={{ width: `${Math.max(4, Math.round((item.value / maxValue) * 100))}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-5 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-sm font-semibold text-slate-500">
          {emptyText}
        </p>
      )}
    </Panel>
  );
}

function DashboardAttentionPanel({
  detail,
  emptyText,
  icon: Icon,
  items,
  title,
  tone
}: {
  detail: string;
  emptyText: string;
  icon: ComponentType<{ className?: string }>;
  items: DashboardAttentionItem[];
  title: string;
  tone: DashboardTone;
}) {
  const colors = dashboardTones[tone];
  return (
    <Panel className="bg-white">
      <div className="flex items-start gap-3">
        <span className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${colors.icon}`}>
          <Icon className="h-5 w-5" />
        </span>
        <div>
          <h2 className="text-lg font-bold text-slate-950">{title}</h2>
          <p className="text-sm font-semibold text-slate-500">{detail}</p>
        </div>
      </div>
      {items.length ? (
        <div className="mt-5 space-y-2">
          {items.map((item) => (
            <Link
              className="block rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm transition hover:border-orange-200 hover:bg-orange-50/50 focus:outline-none focus:ring-4 focus:ring-orange-100"
              key={item.key}
              to={item.href}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-bold text-slate-950">{item.title}</p>
                  <p className="mt-0.5 truncate text-xs font-semibold text-slate-500">{item.description}</p>
                </div>
                <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-700 ring-1 ring-slate-200">
                  {item.badge}
                </span>
              </div>
              <p className="mt-2 text-xs font-semibold text-slate-600">{item.meta}</p>
            </Link>
          ))}
        </div>
      ) : (
        <p className="mt-5 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-sm font-semibold text-slate-500">
          {emptyText}
        </p>
      )}
    </Panel>
  );
}

const openQuoteStatuses = new Set<QuoteStatus>(["submitted", "in_review"]);
const quoteApprovedStatuses = new Set<QuoteStatus>(["approved", "accepted_by_client", "contract_generated"]);
const quoteRejectedStatuses = new Set<QuoteStatus>(["rejected"]);
const premiumOpportunityExcludedStatuses = new Set<QuoteStatus>(["rejected", "declined_by_client"]);
const openClaimStatuses = new Set<ClaimStatus>(["submitted", "in_review", "inspection_requested"]);
const claimOutcomeStatuses = ["accepted", "rejected", "inspection_requested", "paid"] as const;
const claimTypeOrder: ClaimType[] = ["Fire", "Water damage", "Theft", "Storm", "Other"];

function buildDashboardMetrics(quotes: Quote[], claims: Claim[]) {
  const today = toDateKey(new Date());
  const clientIds = new Set<string>();
  quotes.forEach((quote) => clientIds.add(quote.clientId || quote.clientName));
  claims.forEach((claim) => clientIds.add(claim.clientId || claim.clientName));
  const approvedQuotes = quotes.filter((quote) => quoteApprovedStatuses.has(quote.status)).length;
  const rejectedQuotes = quotes.filter((quote) => quoteRejectedStatuses.has(quote.status)).length;
  const quoteDecisionCount = approvedQuotes + rejectedQuotes;
  const premiumOpportunityQuotes = quotes.filter(
    (quote) =>
      !premiumOpportunityExcludedStatuses.has(quote.status) &&
      isQuotePricingBackendDriven(quote)
  );
  const premiumOpportunityTotal = sumNumbers(premiumOpportunityQuotes.map((quote) => getQuotePremium(quote)));
  const claimDamageValues = claims
    .map((claim) => claim.estimatedDamage)
    .filter((value) => Number.isFinite(value) && value > 0);
  const claimExposureTotal = sumNumbers(claimDamageValues);
  const claimDecisionMix = claimOutcomeStatuses.map((status) => ({
    key: status,
    label: claimOutcomeLabel(status),
    value: claims.filter((claim) => claim.status === status).length
  }));
  const claimTypeMix = claimTypeOrder.map((claimType) => ({
    key: claimType,
    label: claimType,
    value: claims.filter((claim) => claim.claimType === claimType).length
  }));

  return {
    today,
    clientCount: clientIds.size,
    newQuoteRequestsToday: quotes.filter((quote) => toDateKey(parseLocalDate(quote.createdAt)) === today).length,
    newClaimsToday: claims.filter((claim) => toDateKey(parseLocalDate(claim.createdAt)) === today).length,
    openQuoteBacklog: quotes.filter((quote) => openQuoteStatuses.has(quote.status)).length,
    openClaimBacklog: claims.filter((claim) => openClaimStatuses.has(claim.status)).length,
    quoteDecisionCount,
    quoteApprovalRate: quoteDecisionCount ? approvedQuotes / quoteDecisionCount : 0,
    quoteDecisionMix: [
      { key: "approved", label: "Approved", value: approvedQuotes },
      { key: "rejected", label: "Rejected", value: rejectedQuotes }
    ],
    premiumOpportunityCount: premiumOpportunityQuotes.length,
    premiumOpportunityTotal,
    averageQuotePremium: averageNumber(premiumOpportunityTotal, premiumOpportunityQuotes.length),
    claimDecisionMix,
    claimOutcomeCount: sumNumbers(claimDecisionMix.map((item) => item.value)),
    claimExposureCount: claimDamageValues.length,
    claimExposureTotal,
    averageClaimDamage: averageNumber(claimExposureTotal, claimDamageValues.length),
    highRiskQuoteCount: quotes.filter(isHighRiskQuote).length,
    claimTypeMix
  };
}

function isHighRiskQuote(quote: Quote) {
  if (!isQuoteRiskBackendDriven(quote)) return false;
  return (
    quote.requiresManualReview === true ||
    quote.riskLevel === "High" ||
    quote.riskScore <= 70
  );
}

function formatQuoteRiskBadge(quote: Quote) {
  if (isQuoteRiskUnavailable(quote)) return "Risk unavailable";
  if (quote.riskSource === "preview") return `${quote.riskLevel ?? "Risk"} preview`;
  if (quote.requiresManualReview) return "Review required";
  if (quote.riskLevel) return `${quote.riskLevel} risk`;
  return `Risk ${quote.riskScore}`;
}

function claimOutcomeLabel(status: (typeof claimOutcomeStatuses)[number]) {
  if (status === "inspection_requested") return "Inspection requested";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function sumNumbers(values: number[]) {
  return values.reduce((total, value) => total + (Number.isFinite(value) ? value : 0), 0);
}

function averageNumber(total: number, count: number) {
  return count ? total / count : 0;
}

function buildQuoteAttentionQueue(quotes: Quote[]) {
  return quotes
    .filter((quote) => openQuoteStatuses.has(quote.status))
    .sort((first, second) => {
      const riskPriority = Number(isHighRiskQuote(second)) - Number(isHighRiskQuote(first));
      if (riskPriority) return riskPriority;
      const riskScorePriority = quoteRiskSortScore(first) - quoteRiskSortScore(second);
      if (riskScorePriority) return riskScorePriority;
      return dateTimeMs(second.createdAt) - dateTimeMs(first.createdAt);
    })
    .slice(0, 5);
}

function quoteRiskSortScore(quote: Quote) {
  return isQuoteRiskBackendDriven(quote) ? quote.riskScore : 101;
}

function formatQuotePremiumForDisplay(quote: Quote) {
  return isQuotePricingUnavailable(quote)
    ? "Pricing unavailable"
    : formatCurrency(getQuotePremium(quote));
}

function buildClaimAttentionQueue(claims: Claim[]) {
  return claims
    .filter((claim) => openClaimStatuses.has(claim.status))
    .sort((first, second) => {
      const damagePriority = second.estimatedDamage - first.estimatedDamage;
      if (damagePriority) return damagePriority;
      return dateTimeMs(second.createdAt) - dateTimeMs(first.createdAt);
    })
    .slice(0, 5);
}

function dateTimeMs(value?: string) {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function buildDateSeries<T>(
  items: T[],
  getDateValue: (item: T) => string | undefined,
  period: DashboardPeriod
): DashboardPoint[] {
  const buckets = createDateBuckets(period);
  const counts = new Map(buckets.map((bucket) => [bucket.key, 0]));

  items.forEach((item) => {
    const date = parseLocalDate(getDateValue(item));
    if (!date) return;
    const key = bucketKeyForDate(date, period);
    if (counts.has(key)) {
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  });

  return buckets.map((bucket) => ({
    ...bucket,
    value: counts.get(bucket.key) ?? 0
  }));
}

function createDateBuckets(period: DashboardPeriod): Array<Omit<DashboardPoint, "value">> {
  const today = new Date();
  if (period === "day") {
    return Array.from({ length: 7 }, (_, index) => {
      const date = addDays(startOfDay(today), index - 6);
      return { key: toDateKey(date), label: shortDateLabel(date) };
    });
  }

  if (period === "week") {
    const currentWeek = startOfWeek(today);
    return Array.from({ length: 8 }, (_, index) => {
      const date = addDays(currentWeek, (index - 7) * 7);
      return { key: toDateKey(date), label: shortDateLabel(date) };
    });
  }

  if (period === "month") {
    const currentMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    return Array.from({ length: 12 }, (_, index) => {
      const date = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + index - 11, 1);
      return { key: monthKey(date), label: monthLabel(date) };
    });
  }

  const currentYear = today.getFullYear();
  return Array.from({ length: 5 }, (_, index) => {
    const year = currentYear + index - 4;
    return { key: String(year), label: String(year) };
  });
}

function bucketKeyForDate(date: Date, period: DashboardPeriod) {
  if (period === "day") return toDateKey(date);
  if (period === "week") return toDateKey(startOfWeek(date));
  if (period === "month") return monthKey(date);
  return String(date.getFullYear());
}

function parseLocalDate(value?: string) {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (match) {
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function startOfWeek(date: Date) {
  const day = date.getDay() || 7;
  return addDays(startOfDay(date), 1 - day);
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function toDateKey(date: Date | null) {
  if (!date) return "";
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function monthKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function shortDateLabel(date: Date) {
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short" }).format(date);
}

function monthLabel(date: Date) {
  return new Intl.DateTimeFormat("en-GB", { month: "short", year: "2-digit" }).format(date);
}

function formatWholeNumber(value: number) {
  return new Intl.NumberFormat("en-GB").format(value || 0);
}

type LegalReviewEditorState = Record<string, { newText: string; notes: string }>;
type LegalReviewQueueTab = "active" | "processed";

type LegalReviewWorkflowContext = {
  actionError?: string;
  draftRevision?: TemplateDraftRevision;
  editorState: LegalReviewEditorState;
  isLoading: boolean;
  isWorking: boolean;
  legalChanges: LegalChangeItem[];
  suggestion?: TemplateChangeSuggestion;
  suggestionDetail?: TemplateChangeSuggestionDetail;
  clearWorkflow: () => void;
  onCreateDraftRevision: () => Promise<void>;
  onSubmitDraftRevisionForApproval: (revision: TemplateDraftRevision) => Promise<void>;
  onCreateSuggestion: (candidate: LegalTemplateReviewCandidate) => Promise<void>;
  onHunkDecision: (hunk: TemplateChangeSuggestionHunk, decision: "accept" | "reject") => Promise<void>;
  onSaveHunk: (hunk: TemplateChangeSuggestionHunk) => Promise<void>;
  onUndoHunkAcceptance: (hunk: TemplateChangeSuggestionHunk) => Promise<void>;
  onUpdateDraft: (hunkId: string, patch: Partial<{ newText: string; notes: string }>) => void;
};

const LegalReviewTabsContext = createContext<ReactNode>(null);

export function LegalReviewPage() {
  const [legalChanges, setLegalChanges] = useState<LegalChangeItem[]>([]);
  const [suggestion, setSuggestion] = useState<TemplateChangeSuggestion>();
  const [suggestionDetail, setSuggestionDetail] = useState<TemplateChangeSuggestionDetail>();
  const [draftRevision, setDraftRevision] = useState<TemplateDraftRevision>();
  const [editorState, setEditorState] = useState<LegalReviewEditorState>({});
  const [actionError, setActionError] = useState<string>();
  const [isLoading, setIsLoading] = useState(false);
  const [isWorking, setIsWorking] = useState(false);
  const { showToast } = useToast();
  useEffect(() => {
    setIsLoading(true);
    void Promise.all([
      getLegalChanges("needs_review"),
      getLegalChanges("processed")
    ])
      .then(([activeItems, processedItems]) => {
        setLegalChanges(mergeLegalChangeItems([...activeItems, ...processedItems]));
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : "Could not load legal changes.";
        showToast(message, "error");
        setLegalChanges([]);
        clearWorkflow();
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [showToast]);

  async function handleCreateSuggestion(candidate: LegalTemplateReviewCandidate) {
    setIsWorking(true);
    setActionError(undefined);
    try {
      const created = await createTemplateChangeSuggestion(candidate.candidate_id);
      const detail = await getTemplateChangeSuggestion(created.id);
      setSuggestion(detail.suggestion);
      setSuggestionDetail(detail);
      setDraftRevision(detail.draft_revision ?? undefined);
      setEditorState(stateFromHunks(detail.suggestion.hunks));
      showToast(detail.draft_revision ? "Draft loaded." : "Suggestion ready.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not create suggestion.";
      setActionError(message);
      showToast(message, "error");
    } finally {
      setIsWorking(false);
    }
  }

  async function handleSaveHunk(hunk: TemplateChangeSuggestionHunk) {
    if (!suggestion) return;
    const draft = editorState[hunk.id] ?? { newText: hunk.new_text, notes: hunk.reviewer_notes ?? "" };
    setIsWorking(true);
    setActionError(undefined);
    try {
      const updated = await updateTemplateChangeSuggestionHunk(suggestion.id, hunk.id, {
        new_text: draft.newText,
        reviewer_notes: draft.notes
      });
      setSuggestion(updated);
      setSuggestionDetail((detail) => detail ? { ...detail, suggestion: updated } : detail);
      setEditorState(stateFromHunks(updated.hunks));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not save hunk edit.";
      setActionError(message);
      showToast(message, "error");
    } finally {
      setIsWorking(false);
    }
  }

  async function handleHunkDecision(hunk: TemplateChangeSuggestionHunk, decision: "accept" | "reject") {
    if (!suggestion) return;
    setIsWorking(true);
    setActionError(undefined);
    try {
      const updated =
        decision === "accept"
          ? await acceptTemplateChangeSuggestionHunk(suggestion.id, hunk.id)
          : await rejectTemplateChangeSuggestionHunk(suggestion.id, hunk.id);
      setSuggestion(updated);
      setSuggestionDetail((detail) => detail ? { ...detail, suggestion: updated } : detail);
      setEditorState(stateFromHunks(updated.hunks));
      if (isDismissedSuggestion(updated)) {
        setLegalChanges((current) =>
          markLegalReviewCandidateStatus(current, updated.candidate_id, "dismissed")
        );
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not update hunk status.";
      setActionError(message);
      showToast(message, "error");
    } finally {
      setIsWorking(false);
    }
  }

  async function handleUndoHunkAcceptance(hunk: TemplateChangeSuggestionHunk) {
    if (!suggestion) return;
    setIsWorking(true);
    setActionError(undefined);
    try {
      const updated = await updateTemplateChangeSuggestionHunk(suggestion.id, hunk.id, {
        status: "edited"
      });
      setSuggestion(updated);
      setSuggestionDetail((detail) => detail ? { ...detail, suggestion: updated } : detail);
      setEditorState(stateFromHunks(updated.hunks));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not undo acceptance.";
      setActionError(message);
      showToast(message, "error");
    } finally {
      setIsWorking(false);
    }
  }

  async function handleCreateDraftRevision() {
    if (!suggestion) return;
    setIsWorking(true);
    setActionError(undefined);
    try {
      const revision = await createDraftRevisionFromSuggestion(suggestion.id);
      const candidateStatus = revision.applied_hunk_ids.length ? "accepted" : "dismissed";
      setDraftRevision(revision);
      setSuggestion((current) => current ? { ...current, status: "applied_to_draft" } : current);
      setSuggestionDetail((detail) =>
        detail ? { ...detail, suggestion: { ...detail.suggestion, status: "applied_to_draft" } } : detail
      );
      setLegalChanges((current) =>
        markLegalReviewCandidateStatus(current, suggestion.candidate_id, candidateStatus)
      );
      showToast("Draft created.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not create draft.";
      setActionError(message);
      showToast(message, "error");
    } finally {
      setIsWorking(false);
    }
  }

  async function handleSubmitDraftRevisionForApproval(revision: TemplateDraftRevision) {
    setIsWorking(true);
    setActionError(undefined);
    try {
      const submitted = await submitDraftRevisionForApproval(revision.id);
      setDraftRevision(submitted);
      setSuggestionDetail((detail) => detail ? { ...detail, draft_revision: submitted } : detail);
      showToast("Draft sent for legal approval.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not send draft for legal approval.";
      setActionError(message);
      showToast(message, "error");
    } finally {
      setIsWorking(false);
    }
  }

  function clearWorkflow() {
    setSuggestion(undefined);
    setSuggestionDetail(undefined);
    setDraftRevision(undefined);
    setEditorState({});
    setActionError(undefined);
  }

  const contextValue: LegalReviewWorkflowContext = {
    actionError,
    draftRevision,
    editorState,
    isLoading,
    isWorking,
    legalChanges,
    suggestion,
    suggestionDetail,
    clearWorkflow,
    onCreateDraftRevision: handleCreateDraftRevision,
    onSubmitDraftRevisionForApproval: handleSubmitDraftRevisionForApproval,
    onCreateSuggestion: handleCreateSuggestion,
    onHunkDecision: handleHunkDecision,
    onSaveHunk: handleSaveHunk,
    onUndoHunkAcceptance: handleUndoHunkAcceptance,
    onUpdateDraft: (hunkId, patch) => setEditorState((current) => ({
      ...current,
      [hunkId]: { ...(current[hunkId] ?? { newText: "", notes: "" }), ...patch }
    }))
  };

  return <Outlet context={contextValue} />;
}

export function LegalReviewQueueView() {
  const { clearWorkflow, draftRevision, isLoading, legalChanges, suggestion } = useLegalReviewWorkflow();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<LegalReviewQueueTab>("active");
  const activeItems = legalChanges.filter(
    (item) => !isLegalUpdateProcessedForQueue(item, suggestion, draftRevision)
  );
  const processedItems = legalChanges.filter((item) =>
    isLegalUpdateProcessedForQueue(item, suggestion, draftRevision)
  );
  const visibleItems = activeTab === "processed" ? processedItems : activeItems;

  return (
    <section className="flex flex-col">
      <EmployeePageHeader
        className="shrink-0"
        title="Legal Review"
      />
      <LawChangeQueue
        activeCount={activeItems.length}
        activeTab={activeTab}
        emptyDescription={
          activeTab === "processed"
            ? "Processed legal updates will appear here after they are drafted or dismissed."
            : "Nothing is waiting for review."
        }
        emptyTitle={activeTab === "processed" ? "No processed legal updates" : "No legal updates"}
        draftRevision={draftRevision}
        isLoading={isLoading}
        items={visibleItems}
        onTabChange={setActiveTab}
        onSelect={(item) => {
          clearWorkflow();
          navigate(`/legal-review/${encodeURIComponent(item.legal_document.id)}`);
        }}
        processed={activeTab === "processed"}
        processedCount={processedItems.length}
        suggestion={suggestion}
        title={activeTab === "processed" ? "Processed updates" : "Legal updates"}
      />
    </section>
  );
}

export function LegalReviewUpdateDetailView() {
  const { draftRevision, item, isLoading, suggestion } = useLegalReviewUpdateRoute();

  if (!item) {
    return (
      <LegalReviewMissingState
        description="That legal update is no longer in the review queue."
        isLoading={isLoading}
        title="Legal update not found"
      />
    );
  }

  return (
    <LegalReviewWorkflowLayout
      draftRevision={draftRevision}
      item={item}
      suggestion={suggestion}
    >
      <LegalUpdateDetailPanel
        item={item}
        nextTo={`/legal-review/${encodeURIComponent(item.legal_document.id)}/documents`}
      />
    </LegalReviewWorkflowLayout>
  );
}

export function LegalReviewTemplatesView() {
  const { clearWorkflow, draftRevision, isLoading, isWorking, item, suggestion, suggestionDetail } = useLegalReviewUpdateRoute();
  const navigate = useNavigate();

  if (!item) {
    return (
      <LegalReviewMissingState
        description="That legal update is no longer in the review queue."
        isLoading={isLoading}
        title="Legal update not found"
      />
    );
  }

  return (
    <LegalReviewWorkflowLayout
      draftRevision={draftRevision}
      item={item}
      suggestion={suggestion}
    >
      <TemplateImpactPanel
        isWorking={isWorking}
        item={item}
        onReviewCandidate={(candidate) => {
          if (!isSuggestionForCandidate(suggestion, candidate)) clearWorkflow();
          navigate(
            `/legal-review/${encodeURIComponent(item.legal_document.id)}/documents/${encodeURIComponent(candidateRouteId(candidate))}/changes`
          );
        }}
        suggestionDetail={suggestionDetail}
      />
    </LegalReviewWorkflowLayout>
  );
}

export function LegalReviewChangesView() {
  const route = useLegalReviewCandidateRoute();
  const {
    actionError,
    draftRevision,
    editorState,
    isLoading,
    isWorking,
    item,
    candidate,
    onCreateSuggestion,
    onHunkDecision,
    onSaveHunk,
    onUndoHunkAcceptance,
    onUpdateDraft,
    suggestion,
    suggestionDetail
  } = route;
  const navigate = useNavigate();
  const currentSuggestion = suggestionForCandidate(candidate, suggestion);
  const currentDraftRevision = currentSuggestion ? draftRevision : undefined;
  const currentSuggestionDetail = suggestionDetailForCandidate(candidate, suggestionDetail);
  const canContinueToDraft = Boolean(currentSuggestion?.hunks.length && currentSuggestion.hunks.every(isReviewedHunk));

  useEffect(() => {
    if (!candidate || isLoading || isWorking || actionError) return;
    if (currentSuggestion && currentSuggestionDetail) return;
    void onCreateSuggestion(candidate);
  }, [actionError, candidate?.candidate_id, currentSuggestion?.id, currentSuggestionDetail?.candidate.candidate_id, isLoading, isWorking]);

  if (!item || !candidate) {
    return (
      <LegalReviewMissingState
        description="That document impact is no longer available for this legal update."
        isLoading={isLoading}
        title="Document impact not found"
      />
    );
  }

  const updateId = encodeURIComponent(item.legal_document.id);
  const templateId = encodeURIComponent(candidateRouteId(candidate));

  return (
    <LegalReviewWorkflowLayout
      candidate={candidate}
      contentMode="contained"
      draftRevision={draftRevision}
      item={item}
      suggestion={suggestion}
    >
      {actionError ? <ValidationBanner message={actionError} tone="danger" /> : null}
      {!currentSuggestion ? (
        <Panel className="flex flex-col overflow-hidden">
          <LegalReviewPanelTabs />
          <div className="mt-4 flex min-h-40 items-center">
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-orange-600" />
              <p className="text-sm font-semibold text-slate-700">Generating...</p>
            </div>
          </div>
        </Panel>
      ) : (
        <SuggestionDiffEditor
          canContinueToDraft={canContinueToDraft}
          draftRevision={currentDraftRevision}
          editorState={editorState}
          isWorking={isWorking}
          onContinueToDraft={() => navigate(`/legal-review/${updateId}/documents/${templateId}/draft`)}
          onHunkDecision={onHunkDecision}
          onSaveHunk={onSaveHunk}
          onUndoHunkAcceptance={onUndoHunkAcceptance}
          onUpdateDraft={onUpdateDraft}
          suggestion={currentSuggestion}
          templateContent={currentSuggestionDetail?.template.content}
        />
      )}
    </LegalReviewWorkflowLayout>
  );
}

export function LegalReviewDraftView() {
  const {
    actionError,
    candidate,
    draftRevision,
    isLoading,
    isWorking,
    item,
    onCreateDraftRevision,
    onCreateSuggestion,
    onSubmitDraftRevisionForApproval,
    suggestion,
    suggestionDetail
  } = useLegalReviewCandidateRoute();
  const currentSuggestion = suggestionForCandidate(candidate, suggestion);
  const currentDraftRevision = currentSuggestion ? draftRevision : undefined;
  const currentSuggestionDetail = suggestionDetailForCandidate(candidate, suggestionDetail);

  useEffect(() => {
    if (!candidate || isLoading || isWorking || actionError) return;
    if (currentSuggestion && currentSuggestionDetail) return;
    void onCreateSuggestion(candidate);
  }, [actionError, candidate?.candidate_id, currentSuggestion?.id, currentSuggestionDetail?.candidate.candidate_id, isLoading, isWorking]);

  if (!item || !candidate) {
    return (
      <LegalReviewMissingState
        description="That document impact is no longer available for this legal update."
        isLoading={isLoading}
        title="Document impact not found"
      />
    );
  }

  return (
    <LegalReviewWorkflowLayout
      candidate={candidate}
      draftRevision={draftRevision}
      item={item}
      suggestion={suggestion}
    >
      {actionError ? <ValidationBanner message={actionError} tone="danger" /> : null}
      {!currentSuggestion ? (
        <Panel className="flex flex-col overflow-hidden">
          <LegalReviewPanelTabs />
          <div className="mt-4 flex min-h-40 items-center">
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-orange-600" />
              <p className="text-sm font-semibold text-slate-700">Preparing...</p>
            </div>
          </div>
        </Panel>
      ) : (
        <DraftCreationPanel
          candidate={candidate}
          draftRevision={currentDraftRevision}
          item={item}
          isWorking={isWorking}
          onCreateDraftRevision={onCreateDraftRevision}
          onSubmitDraftRevisionForApproval={onSubmitDraftRevisionForApproval}
          suggestion={currentSuggestion}
          suggestionDetail={currentSuggestionDetail}
        />
      )}
    </LegalReviewWorkflowLayout>
  );
}

function useLegalReviewWorkflow() {
  return useOutletContext<LegalReviewWorkflowContext>();
}

function useLegalReviewUpdateRoute() {
  const context = useLegalReviewWorkflow();
  const { updateId } = useParams();
  const item = context.legalChanges.find((change) => change.legal_document.id === updateId);
  return { ...context, item, updateId };
}

function useLegalReviewCandidateRoute() {
  const route = useLegalReviewUpdateRoute();
  const { templateId } = useParams();
  const candidate = findCandidateForRoute(route.item, templateId);
  return { ...route, candidate, templateId };
}

function LegalReviewWorkflowLayout({
  candidate,
  children,
  contentMode = "contained",
  draftRevision,
  item,
  suggestion
}: {
  candidate?: LegalTemplateReviewCandidate;
  children: ReactNode;
  contentMode?: "scroll" | "contained";
  draftRevision?: TemplateDraftRevision;
  item: LegalChangeItem;
  suggestion?: TemplateChangeSuggestion;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const activeSuggestion = suggestionForUpdate(item, suggestion);
  const activeDraftRevision = draftRevisionForUpdate(item, suggestion, draftRevision);
  const activeStep = legalReviewStepFromPath(location.pathname);
  const workflowTabs = (
    <LegalReviewWorkflowTabs
      activePath={location.pathname}
      candidate={candidate}
      item={item}
      suggestion={activeSuggestion}
    />
  );

  return (
    <section className="flex flex-col">
      <EmployeePageHeader
        actions={
          <Button className="min-h-9 px-3.5 py-2 text-sm" onClick={() => navigate("/legal-review")} variant="secondary">
            Back to queue
          </Button>
        }
        className="mb-3 shrink-0"
        title={legalQueueTitle(item.legal_document)}
      >
        <LegalReviewSummaryStrip
          draftRevision={activeDraftRevision}
          item={item}
          suggestion={activeSuggestion}
        />
      </EmployeePageHeader>
      <LegalReviewTabsContext.Provider value={workflowTabs}>
        <div
          aria-labelledby={legalReviewTabId(activeStep)}
          className="space-y-3"
          id={legalReviewPanelId(activeStep)}
          role="tabpanel"
          tabIndex={0}
        >
          <div className="space-y-3">{children}</div>
        </div>
      </LegalReviewTabsContext.Provider>
    </section>
  );
}

function LegalReviewSummaryStrip({
  draftRevision,
  item,
  suggestion
}: {
  draftRevision?: TemplateDraftRevision;
  item: LegalChangeItem;
  suggestion?: TemplateChangeSuggestion;
}) {
  const reviewed = reviewedHunkCount(suggestion);
  const total = suggestion?.hunks.length ?? 0;
  const draftState = draftRevision ? "Draft created" : "No draft";

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-slate-200 pt-3 text-xs font-semibold text-slate-600">
      <span>{item.affected_template_count} template{item.affected_template_count === 1 ? "" : "s"}</span>
      <span>{total ? `${reviewed}/${total} reviewed` : "Not reviewed"}</span>
      <span>Effective {formatOptionalDate(item.legal_document.effective_date)}</span>
      <span>{draftState}</span>
    </div>
  );
}

function LegalReviewPanelTabs() {
  const tabs = useContext(LegalReviewTabsContext);
  return tabs ? <div className="-mx-5 -mt-5 mb-4 shrink-0 sm:-mx-6">{tabs}</div> : null;
}

function LegalReviewQueueTabs({
  activeCount,
  activeTab,
  onChange,
  processedCount
}: {
  activeCount: number;
  activeTab: LegalReviewQueueTab;
  onChange: (tab: LegalReviewQueueTab) => void;
  processedCount: number;
}) {
  const tabs: Array<{ id: LegalReviewQueueTab; label: string; count: number }> = [
    { id: "active", label: "Needs review", count: activeCount },
    { id: "processed", label: "Processed", count: processedCount }
  ];
  return (
    <div
      aria-label="Legal update queue views"
      className="inline-flex w-fit max-w-full flex-wrap rounded-lg border border-slate-200 bg-white p-1 shadow-sm"
      role="tablist"
    >
      {tabs.map((tab) => {
        const selected = activeTab === tab.id;
        return (
          <button
            aria-selected={selected}
            className={`inline-flex min-h-9 items-center gap-2 rounded-md px-3 text-sm font-bold transition focus:outline-none focus:ring-4 focus:ring-orange-100 ${
              selected
                ? "bg-orange-50 text-orange-600"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"
            }`}
            key={tab.id}
            onClick={() => onChange(tab.id)}
            role="tab"
            type="button"
          >
            {tab.label}
            <span className="rounded-full bg-white px-2 py-0.5 text-xs text-slate-500 ring-1 ring-slate-200">
              {tab.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function LawChangeQueue({
  activeCount,
  activeTab,
  draftRevision,
  emptyDescription,
  emptyTitle,
  isLoading,
  items,
  onTabChange,
  onSelect,
  processed = false,
  processedCount,
  suggestion,
  title
}: {
  activeCount: number;
  activeTab: LegalReviewQueueTab;
  draftRevision?: TemplateDraftRevision;
  emptyDescription: string;
  emptyTitle: string;
  isLoading: boolean;
  items: LegalChangeItem[];
  onTabChange: (tab: LegalReviewQueueTab) => void;
  onSelect: (item: LegalChangeItem) => void;
  processed?: boolean;
  processedCount: number;
  suggestion?: TemplateChangeSuggestion;
  title: string;
}) {
  return (
    <Panel className="flex flex-col overflow-hidden">
      <div className="flex shrink-0 flex-col gap-3 border-b border-slate-100 pb-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-950">{title}</h2>
        </div>
        <LegalReviewQueueTabs
          activeCount={activeCount}
          activeTab={activeTab}
          onChange={onTabChange}
          processedCount={processedCount}
        />
      </div>
      <div className="mt-4 pt-3">
        {isLoading ? <p className="text-sm font-semibold text-slate-500">Loading legal updates...</p> : null}
        {!isLoading && !items.length ? (
          <EmptyState description={emptyDescription} title={emptyTitle} />
        ) : null}
        {items.length ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {items.map((item) => {
              const document = item.legal_document;
              const synthetic = isSynthetic(document.source_metadata);
              const status = legalUpdateStatusForItem(item, suggestion, draftRevision);
              const actionLabel = processed ? "View" : status === "Needs review" ? "Start review" : "Continue";
              return (
                <div
                  className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
                  key={document.id}
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <h3 className="text-base font-bold leading-6 text-slate-950">{legalQueueTitle(document)}</h3>
                      <p className="mt-1 text-xs font-bold uppercase tracking-wide text-slate-500">
                        {legalUpdateSourceLabel(document)}{synthetic ? " · Demo" : ""}
                      </p>
                    </div>
                    <Button
                      className="shrink-0 self-start whitespace-nowrap px-2.5 py-1 text-xs"
                      icon={Eye}
                      onClick={() => onSelect(item)}
                      variant={status === "Needs review" ? "primary" : "secondary"}
                    >
                      {actionLabel}
                    </Button>
                  </div>
                  <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-2 border-t border-slate-100 pt-3 text-xs">
                    <QueueMeta label="Documents" value={item.affected_template_count} />
                    <QueueMeta label="Effective" value={formatOptionalDate(document.effective_date)} />
                    <QueueMeta label="Confidence" value={formatPercent(item.highest_confidence)} />
                    <QueueMeta label="Status" value={status} />
                  </dl>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function QueueMeta({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center gap-1.5">
      <dt className="font-bold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="font-bold text-slate-800">{value}</dd>
    </div>
  );
}

function LegalUpdateDetailPanel({ item, nextTo }: { item: LegalChangeItem; nextTo: string }) {
  const document = item.legal_document;
  const normalizedReferences = formatReferenceList([...document.legal_references, ...document.amends, ...document.repeals]);
  return (
    <Panel className="flex flex-col overflow-hidden">
      <LegalReviewPanelTabs />
      <div className="mt-4">
        <div className="space-y-5">
          <div className="grid gap-x-6 gap-y-5 xl:grid-cols-2">
            <ClaimWorkspaceSection title="Legal update">
              <ClaimFieldGrid
                items={[
                  ["Title", legalQueueTitle(document), true],
                  ["Source", legalUpdateSourceLabel(document)],
                  ["Status", titleCaseLabel(document.status ?? "unknown")],
                  ["Confidence", formatPercent(document.extraction_confidence)]
                ]}
              />
            </ClaimWorkspaceSection>
            <ClaimWorkspaceSection title="Publication details">
              <ClaimFieldGrid
                items={[
                  ["Issuer", document.issuer ?? "Unknown"],
                  ["Jurisdiction", humanJurisdiction(document.jurisdiction)],
                  ["Published", formatOptionalDate(document.publication_date)],
                  ["Effective", formatOptionalDate(document.effective_date)],
                  ["Publication reference", document.publication_reference ?? "Unknown", true]
                ]}
              />
            </ClaimWorkspaceSection>
            <ClaimWorkspaceSection title="Reference details">
              <ClaimFieldGrid
                items={[
                  ["External ID", document.external_identifier ?? "-"],
                  ["Source key", document.source_key],
                  ["Legal references", formatReferenceList(document.legal_references), true],
                  ["Amends", formatReferenceList(document.amends), true],
                  ["Repeals", formatReferenceList(document.repeals), true],
                  ["Normalized references", normalizedReferences, true]
                ]}
              />
            </ClaimWorkspaceSection>
            <ClaimWorkspaceSection title="Source excerpt">
              <ClaimFieldGrid
                items={[
                  ["Excerpt", <ExpandableClaimDescription text={sourceExcerpt(document)} />, true]
                ]}
              />
            </ClaimWorkspaceSection>
          </div>
        </div>
      </div>

      <div className="mt-4 flex shrink-0 justify-end border-t border-slate-200 pt-4">
        <RouteActionLink to={nextTo}>Review affected documents</RouteActionLink>
      </div>
    </Panel>
  );
}

function TemplateImpactPanel({
  isWorking,
  item,
  onReviewCandidate,
  suggestionDetail
}: {
  isWorking: boolean;
  item: LegalChangeItem;
  onReviewCandidate: (candidate: LegalTemplateReviewCandidate) => void;
  suggestionDetail?: TemplateChangeSuggestionDetail;
}) {
  return (
    <Panel className="flex flex-col overflow-hidden">
      <LegalReviewPanelTabs />
      <div className="mt-4 pt-3">
        <h2 className="text-xl font-bold text-slate-950">Document affected by change</h2>
        <div className="mt-4 grid gap-3">
          {item.candidates.map((candidate) => {
          return (
            <div className="rounded-lg border border-slate-200 bg-white p-4 text-left" key={candidate.candidate_id}>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <h3 className="text-lg font-bold leading-6 text-slate-950">{candidate.template_name}</h3>
                  <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {candidate.template_code} · v{candidate.template_version}
                  </p>
                  <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs">
                    <QueueMeta label="Reference" value={candidate.matched_reference ?? "None"} />
                    <QueueMeta label="Confidence" value={formatPercent(candidate.confidence)} />
                    <QueueMeta label="Domain" value={productLineFor(candidate, suggestionDetail)} />
                  </dl>
                </div>
                <Button
                  className="shrink-0 self-start whitespace-nowrap"
                  disabled={isWorking}
                  icon={FileText}
                  onClick={() => onReviewCandidate(candidate)}
                  variant="primary"
                >
                  Review wording
                </Button>
              </div>
              <p className="mt-3 border-t border-slate-100 pt-3 text-sm font-semibold leading-5 text-slate-700">
                {plainCandidateReason(candidate)}
              </p>
            </div>
          );
          })}
        </div>
      </div>
    </Panel>
  );
}

function ImpactDetail({ className = "bg-slate-50", label, value }: { className?: string; label: string; value: ReactNode }) {
  return (
    <div className={`rounded-lg p-3 ${className}`}>
      <p className="text-xs font-bold uppercase text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold leading-5 text-slate-800">{value}</p>
    </div>
  );
}

function SuggestionDiffEditor({
  canContinueToDraft,
  draftRevision,
  editorState,
  isWorking,
  suggestion,
  onContinueToDraft,
  onHunkDecision,
  onSaveHunk,
  onUndoHunkAcceptance,
  onUpdateDraft,
  templateContent
}: {
  canContinueToDraft: boolean;
  draftRevision?: TemplateDraftRevision;
  editorState: Record<string, { newText: string; notes: string }>;
  isWorking: boolean;
  suggestion: TemplateChangeSuggestion;
  onContinueToDraft: () => void;
  onHunkDecision: (hunk: TemplateChangeSuggestionHunk, decision: "accept" | "reject") => void;
  onSaveHunk: (hunk: TemplateChangeSuggestionHunk) => void;
  onUndoHunkAcceptance: (hunk: TemplateChangeSuggestionHunk) => void;
  onUpdateDraft: (hunkId: string, patch: Partial<{ newText: string; notes: string }>) => void;
  templateContent?: string;
}) {
  const [editingHunks, setEditingHunks] = useState<Record<string, boolean>>({});

  return (
    <Panel className="flex flex-col overflow-hidden">
      <LegalReviewPanelTabs />
      <div className="mt-4 pt-3">
        <h2 className="text-xl font-bold text-slate-950">Wording changes</h2>
        <ValidationMessages validation={suggestion.validation_result} />
        <div className="mt-4 space-y-4">
          {suggestion.hunks.map((hunk) => {
            const draft = editorState[hunk.id] ?? { newText: hunk.new_text, notes: hunk.reviewer_notes ?? "" };
            const displayStatus = hunkDisplayStatus(hunk, draftRevision);
            const templateContext = templateContextForHunk(hunk, templateContent);
            const isEditing = Boolean(editingHunks[hunk.id]);
            const canEdit = hunk.status !== "accepted" && hunk.status !== "rejected" && !draftRevision;
            return (
              <div className="rounded-lg border border-slate-200 bg-white p-4" key={hunk.id}>
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h3 className="text-lg font-bold text-slate-950">{changeNameForHunk(hunk)}</h3>
                    <p className="mt-2 text-sm font-semibold leading-5 text-slate-600">{hunk.rationale}</p>
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    {displayStatus !== "Draft" ? (
                      <Badge tone={hunkStatusTone(displayStatus)}>{displayStatus}</Badge>
                    ) : null}
                    {hunk.status === "accepted" ? (
                      <Button disabled={isWorking || Boolean(draftRevision)} onClick={() => onUndoHunkAcceptance(hunk)} variant="secondary">
                        Undo
                      </Button>
                    ) : hunk.status === "rejected" ? (
                      null
                    ) : (
                      <>
                        <Button disabled={isWorking || Boolean(draftRevision)} icon={Check} onClick={() => onHunkDecision(hunk, "accept")} variant="primary">
                          Accept
                        </Button>
                        <Button disabled={isWorking || Boolean(draftRevision)} icon={X} onClick={() => onHunkDecision(hunk, "reject")} variant="secondary">
                          Reject
                        </Button>
                        {canEdit && !isEditing ? (
                          <Button disabled={isWorking} icon={PenLine} onClick={() => setEditingHunks((current) => ({ ...current, [hunk.id]: true }))}>
                            Edit
                          </Button>
                        ) : null}
                        {canEdit && isEditing ? (
                          <Button
                            disabled={isWorking}
                            icon={PenLine}
                            onClick={() => {
                              void onSaveHunk(hunk);
                              setEditingHunks((current) => ({ ...current, [hunk.id]: false }));
                            }}
                          >
                            Save
                          </Button>
                        ) : null}
                      </>
                    )}
                  </div>
                </div>

                <TemplateContextPanel
                  canEdit={canEdit}
                  context={templateContext}
                  isEditing={isEditing}
                  onSuggestedTextChange={(value) => onUpdateDraft(hunk.id, { newText: value })}
                  suggestedText={draft.newText}
                />

                <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_320px]">
                  <p className="rounded-lg bg-slate-50 p-3 text-sm font-semibold leading-5 text-slate-700">
                    Source: {hunk.source_reference}
                  </p>
                  <label className="block rounded-lg bg-white p-3">
                    <span className="text-xs font-bold uppercase text-slate-500">Reviewer notes</span>
                    <textarea
                      className="mt-2 min-h-20 w-full rounded-md border border-slate-200 bg-white p-2 text-sm leading-5 text-slate-800 focus:border-orange-300 focus:outline-none focus:ring-4 focus:ring-orange-100"
                      disabled={!isEditing || Boolean(draftRevision)}
                      onChange={(event) => onUpdateDraft(hunk.id, { notes: event.target.value })}
                      value={draft.notes}
                    />
                  </label>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="mt-4 flex shrink-0 justify-end border-t border-slate-200 pt-4">
        <Button
          disabled={!canContinueToDraft || isWorking}
          icon={FileText}
          onClick={onContinueToDraft}
          variant="primary"
        >
          Continue to draft
        </Button>
      </div>
    </Panel>
  );
}

type TemplateContext = {
  hunkId?: string;
  sectionTitle?: string;
  articleTitle?: string;
  beforeContext?: string;
  changedText: string;
  afterContext?: string;
  fullContextExcerpt?: string;
  startOffset?: number;
  endOffset?: number;
};

function TemplateContextPanel({
  canEdit,
  context,
  isEditing,
  onSuggestedTextChange,
  suggestedText
}: {
  canEdit: boolean;
  context: TemplateContext;
  isEditing: boolean;
  onSuggestedTextChange: (value: string) => void;
  suggestedText: string;
}) {
  const draftContext = {
    ...context,
    changedText: suggestedText
  };
  return (
    <div className="mt-4 rounded-lg bg-slate-50 p-4">
      <div>
        <p className="text-xs font-bold uppercase text-slate-500">Wording context</p>
        <h4 className="text-sm font-bold text-slate-950">{context.sectionTitle ?? "Template clause"}</h4>
        {context.articleTitle ? (
          <p className="mt-0.5 text-xs font-semibold text-slate-500">{context.articleTitle}</p>
        ) : null}
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <ContextExcerptCard context={context} label="Current wording" tone="amber" />
        <ContextExcerptCard
          context={draftContext}
          disabled={!canEdit}
          isEditing={isEditing}
          label="Suggested wording"
          onChange={onSuggestedTextChange}
          tone="emerald"
        />
      </div>

      {context.hunkId || (context.startOffset != null && context.endOffset != null) || context.fullContextExcerpt ? (
        <details className="mt-3 rounded-lg bg-slate-50 p-2">
          <summary className="cursor-pointer text-xs font-bold text-slate-500">Show technical location</summary>
          <div className="mt-2 space-y-2 text-xs leading-5 text-slate-600">
            {context.hunkId ? (
              <p><span className="font-bold text-slate-700">Hunk ID:</span> <span className="font-mono">{context.hunkId}</span></p>
            ) : null}
            {context.startOffset != null && context.endOffset != null ? (
              <p><span className="font-bold text-slate-700">Character range:</span> {context.startOffset}-{context.endOffset}</p>
            ) : null}
            {context.fullContextExcerpt ? (
              <p className="whitespace-pre-wrap rounded bg-white p-2">{context.fullContextExcerpt}</p>
            ) : null}
          </div>
        </details>
      ) : null}
    </div>
  );
}

function ContextExcerptCard({
  context,
  disabled,
  isEditing = false,
  label,
  onChange,
  tone
}: {
  context: TemplateContext;
  disabled?: boolean;
  isEditing?: boolean;
  label: string;
  onChange?: (value: string) => void;
  tone: "amber" | "emerald";
}) {
  const markClass =
    tone === "emerald"
      ? "rounded bg-emerald-100 px-1 font-semibold text-slate-950 ring-1 ring-emerald-200"
      : "rounded bg-amber-100 px-1 font-semibold text-slate-950 ring-1 ring-amber-200";
  const beforeJoiner =
    context.beforeContext && needsContextJoiner(context.beforeContext, context.changedText)
      ? " "
      : "";
  const afterJoiner =
    context.afterContext && needsContextJoiner(context.changedText, context.afterContext)
      ? " "
      : "";
  return (
    <div className="rounded-lg bg-white p-3 text-sm leading-6 text-slate-700">
      <p className="mb-2 text-xs font-bold uppercase text-slate-500">{label}</p>
      <div className="whitespace-pre-wrap">
        {context.beforeContext ? <span>{context.beforeContext}{beforeJoiner}</span> : null}
        {isEditing ? (
          <textarea
            className="my-2 block min-h-28 w-full rounded-md border border-emerald-200 bg-white p-3 text-sm font-semibold leading-6 text-slate-900 focus:border-emerald-400 focus:outline-none focus:ring-4 focus:ring-emerald-100"
            disabled={disabled}
            onChange={(event) => onChange?.(event.target.value)}
            value={context.changedText}
          />
        ) : (
          <mark className={markClass}>{context.changedText}</mark>
        )}
        {context.afterContext ? <span>{afterJoiner}{context.afterContext}</span> : null}
      </div>
    </div>
  );
}

function DraftCreationPanel({
  candidate,
  draftRevision,
  item,
  isWorking,
  onCreateDraftRevision,
  onSubmitDraftRevisionForApproval,
  suggestion,
  suggestionDetail
}: {
  candidate: LegalTemplateReviewCandidate;
  draftRevision?: TemplateDraftRevision;
  item: LegalChangeItem;
  isWorking: boolean;
  onCreateDraftRevision: () => void;
  onSubmitDraftRevisionForApproval: (revision: TemplateDraftRevision) => void;
  suggestion: TemplateChangeSuggestion;
  suggestionDetail?: TemplateChangeSuggestionDetail;
}) {
  const acceptedHunks = suggestion.hunks.filter((hunk) => hunk.status === "accepted");
  const editedHunks = suggestion.hunks.filter((hunk) => hunk.status === "edited");
  const rejectedHunks = suggestion.hunks.filter((hunk) => hunk.status === "rejected");
  const reviewedHunks = suggestion.hunks.filter(isReviewedHunk);
  const unreviewedHunks = suggestion.hunks.filter((hunk) => !isReviewedHunk(hunk));
  const hasUnreviewedHunks = suggestion.hunks.some((hunk) => !isReviewedHunk(hunk));
  const canCreateDraft = Boolean(reviewedHunks.length && !hasUnreviewedHunks && !draftRevision);
  const documentTitle = candidate.template_name;
  const wordingReviewPath = `/legal-review/${encodeURIComponent(item.legal_document.id)}/documents/${encodeURIComponent(candidateRouteId(candidate))}/changes`;
  const baseWordingContent = suggestionDetail?.template.content ?? "";
  const draftPreviewContent = baseWordingContent
    ? buildDraftPreviewContent(baseWordingContent, suggestion.hunks)
    : "";
  const beforeHighlights = reviewedHunks
    .filter((hunk) => hunk.status !== "rejected")
    .map((hunk) => hunk.old_text);
  const afterHighlights = reviewedHunks
    .filter((hunk) => hunk.status !== "rejected")
    .map((hunk) => hunk.new_text);

  if (draftRevision) {
    return (
      <DraftRevisionSuccess
        afterHighlights={afterHighlights}
        beforeHighlights={beforeHighlights}
        documentTitle={documentTitle}
        isWorking={isWorking}
        item={item}
        onSubmitForApproval={onSubmitDraftRevisionForApproval}
        revision={draftRevision}
      />
    );
  }

  if (hasUnreviewedHunks) {
    return (
      <Panel className="flex flex-col overflow-hidden">
        <LegalReviewPanelTabs />
        <div className="mt-4">
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <h2 className="text-xl font-bold text-amber-950">Review remaining changes</h2>
            <div className="mt-3 space-y-2">
              {unreviewedHunks.map((hunk) => (
                <div className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-slate-800" key={hunk.id}>
                  {changeNameForHunk(hunk)} · {changeSummaryForHunk(hunk)}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-4 flex shrink-0 justify-end border-t border-slate-200 pt-4">
          <RouteActionLink to={wordingReviewPath} variant="secondary">Back to wording review</RouteActionLink>
        </div>
      </Panel>
    );
  }

  return (
    <Panel className="flex flex-col overflow-hidden">
      <LegalReviewPanelTabs />
      <div className="mt-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-950">Draft</h2>
            <p className="mt-1 text-sm font-semibold text-slate-500">
              {acceptedHunks.length + editedHunks.length} to apply · {rejectedHunks.length} rejected
            </p>
          </div>
        </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <ImpactDetail label="Legal update" value={legalQueueTitle(item.legal_document)} />
        <ImpactDetail label="Impacted template" value={`${candidate.template_name} · ${candidate.template_code}`} />
        <ImpactDetail label="Draft status" value="Unpublished draft" />
        <ImpactDetail label="Template domain" value={productLineFor(candidate, suggestionDetail)} />
      </div>

      <div className="mt-5 rounded-xl bg-slate-50 p-4">
        <h3 className="text-lg font-bold text-slate-950">Final summary</h3>
        <div className="mt-3 space-y-3">
          {suggestion.hunks.map((hunk) => (
            <div className="rounded-xl bg-white p-4" key={hunk.id}>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase text-slate-500">{reviewDecisionLabel(hunk)}</p>
                  <h4 className="mt-2 text-base font-bold text-slate-950">
                    {changeNameForHunk(hunk)}: {changeSummaryForHunk(hunk)}
                  </h4>
                </div>
                {hunk.reviewer_notes?.trim() ? (
                  <div className="min-w-0 text-sm font-semibold text-slate-600 lg:max-w-sm">
                    Notes: {hunk.reviewer_notes.trim()}
                  </div>
                ) : null}
              </div>
              <DraftHunkDecisionSummary hunk={hunk} />
            </div>
          ))}
        </div>
      </div>

      {baseWordingContent ? (
        <LegalWordingPdfComparison
          afterContent={draftPreviewContent}
          afterFilename={legalWordingPdfFilename(candidate.template_code, "draft")}
          afterHighlights={afterHighlights}
          afterTitle={documentTitle}
          beforeContent={baseWordingContent}
          beforeFilename={legalWordingPdfFilename(candidate.template_code, "current")}
          beforeHighlights={beforeHighlights}
          beforeTitle={documentTitle}
        />
      ) : null}

      <details className="mt-4 rounded-lg bg-slate-50 p-3">
        <summary className="cursor-pointer text-sm font-bold text-orange-600">Show draft metadata</summary>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <ImpactDetail className="bg-white" label="Template" value={`${candidate.template_name} · v${candidate.template_version}`} />
          <ImpactDetail className="bg-white" label="Jurisdiction" value={humanJurisdiction(item.legal_document.jurisdiction)} />
          <ImpactDetail className="bg-white" label="Source legal update" value={legalUpdateSourceLabel(item.legal_document)} />
          <ImpactDetail className="bg-white" label="Draft visibility" value="Unpublished draft" />
        </div>
      </details>

      <ValidationMessages validation={suggestion.validation_result} />
      </div>
      <div className="mt-4 flex shrink-0 flex-wrap justify-end gap-2 border-t border-slate-200 pt-4">
        <RouteActionLink to={wordingReviewPath} variant="secondary">Back to wording review</RouteActionLink>
        <Button disabled={!canCreateDraft || isWorking} icon={FileText} onClick={onCreateDraftRevision} variant="primary">
          Create draft
        </Button>
      </div>
    </Panel>
  );
}

function DraftHunkDecisionSummary({ hunk }: { hunk: TemplateChangeSuggestionHunk }) {
  if (hunk.status === "rejected") {
    return (
      <div className="mt-3 rounded-lg bg-slate-50 p-3">
        <p className="text-sm font-semibold text-slate-600">No change applied.</p>
      </div>
    );
  }

  if (hunk.status === "edited") {
    return (
      <div className="mt-3 rounded-lg bg-emerald-50 p-3">
        <p className="text-xs font-bold uppercase text-emerald-700">Final wording</p>
        <p className="mt-2 whitespace-pre-wrap text-sm font-semibold leading-6 text-slate-800">{hunk.new_text}</p>
      </div>
    );
  }

  if (hunk.status === "accepted") {
    return (
      <div className="mt-3 rounded-lg bg-emerald-50 p-3">
        <p className="text-xs font-bold uppercase text-emerald-700">Final wording</p>
        <p className="mt-2 whitespace-pre-wrap text-sm font-semibold leading-6 text-slate-800">{hunk.new_text}</p>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-lg bg-amber-50 p-3">
      <p className="text-xs font-bold uppercase text-amber-700">Decision required</p>
    </div>
  );
}

function DraftRevisionSuccess({
  afterHighlights,
  beforeHighlights,
  documentTitle,
  isWorking,
  item,
  onSubmitForApproval,
  revision
}: {
  afterHighlights: string[];
  beforeHighlights: string[];
  documentTitle: string;
  isWorking: boolean;
  item: LegalChangeItem;
  onSubmitForApproval: (revision: TemplateDraftRevision) => void;
  revision: TemplateDraftRevision;
}) {
  const approvalSent = revision.status === "submitted_for_approval";
  const recipientInstitution = draftApprovalRecipient(revision, item);
  return (
    <Panel className="flex flex-col overflow-hidden border-emerald-200 bg-emerald-50">
      <LegalReviewPanelTabs />
      <div className="mt-4">
        <h3 className="text-lg font-bold text-emerald-950">{approvalSent ? "Draft sent for approval" : "Draft created"}</h3>
        <p className="mt-2 text-sm text-emerald-800">Draft ID: <span className="font-mono font-bold">{revision.id}</span></p>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <ImpactDetail className="bg-white" label="Responsible institution" value={recipientInstitution} />
          <ImpactDetail className="bg-white" label="Approval status" value={approvalSent ? "Sent for approval" : "Ready to send"} />
        </div>
        <LegalWordingPdfComparison
          afterContent={revision.revised_content}
          afterFilename={legalWordingPdfFilename(revision.template_code, approvalSent ? "submitted" : "draft")}
          afterHighlights={afterHighlights}
          afterTitle={documentTitle || revision.template_name}
          beforeContent={revision.base_content}
          beforeFilename={legalWordingPdfFilename(revision.template_code, "current")}
          beforeHighlights={beforeHighlights}
          beforeTitle={documentTitle || revision.template_name}
        />
      </div>
      <div className="mt-4 flex shrink-0 flex-wrap justify-end gap-2 border-t border-emerald-200 pt-4">
        <RouteActionLink to="/legal-review" variant="secondary">Back to queue</RouteActionLink>
        <Button
          disabled={isWorking || approvalSent}
          icon={Send}
          onClick={() => onSubmitForApproval(revision)}
          variant="primary"
        >
          {approvalSent ? "Sent for approval" : "Send for legal approval"}
        </Button>
      </div>
    </Panel>
  );
}

function LegalWordingPdfComparison({
  afterContent,
  afterFilename,
  afterHighlights = [],
  afterTitle,
  beforeContent,
  beforeFilename,
  beforeHighlights = [],
  beforeTitle
}: {
  afterContent: string;
  afterFilename: string;
  afterHighlights?: string[];
  afterTitle: string;
  beforeContent: string;
  beforeFilename: string;
  beforeHighlights?: string[];
  beforeTitle: string;
}) {
  return (
    <div className="mt-5 grid gap-4 xl:grid-cols-2">
      <LegalWordingPdfPreview
        content={beforeContent}
        filename={beforeFilename}
        highlights={beforeHighlights}
        title={beforeTitle}
        tone="amber"
      />
      <LegalWordingPdfPreview
        content={afterContent}
        filename={afterFilename}
        highlights={afterHighlights}
        title={afterTitle}
        tone="emerald"
      />
    </div>
  );
}

function LegalWordingPdfPreview({
  content,
  filename,
  highlights,
  title,
  tone
}: {
  content: string;
  filename: string;
  highlights: string[];
  title: string;
  tone: "amber" | "emerald";
}) {
  const accentClass = tone === "emerald" ? "text-emerald-700" : "text-amber-700";
  const [pdfUrl, setPdfUrl] = useState<string>();
  const [pdfError, setPdfError] = useState<string>();

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | undefined;

    try {
      const blob = createLegalWordingPdfBlob({
        content,
        highlights,
        title,
        tone
      });
      objectUrl = URL.createObjectURL(blob);
      if (!cancelled) {
        setPdfUrl(objectUrl);
        setPdfError(undefined);
      }
    } catch {
      if (!cancelled) {
        setPdfUrl(undefined);
        setPdfError("PDF preview could not be generated.");
      }
    }

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [content, filename, highlights, title, tone]);

  function downloadPdf() {
    const blob = createLegalWordingPdfBlob({
      content,
      highlights,
      title,
      tone
    });
    triggerBlobDownload(blob, filename);
  }

  return (
    <section className="flex min-h-[720px] min-w-0 flex-col rounded-lg border border-slate-200 bg-slate-100 p-3 shadow-inner">
      <div className="mb-3 flex min-h-10 items-center justify-between gap-3 rounded-md bg-white px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className={`h-4 w-4 shrink-0 ${accentClass}`} />
          <div className="min-w-0">
            <h3 className="truncate text-sm font-bold text-slate-950">{title}</h3>
            <p className="truncate text-xs font-semibold text-slate-500">{filename}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded bg-slate-100 px-2 py-1 text-[10px] font-bold uppercase text-slate-500">
            PDF
          </span>
          <button
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-4 focus:ring-slate-100"
            onClick={downloadPdf}
            title={`Download ${filename}`}
            type="button"
          >
            <Download className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden rounded-md border border-slate-200 bg-slate-200/80 p-2">
        {pdfUrl ? (
          <iframe
            className="h-full min-h-[650px] w-full rounded bg-white"
            src={pdfUrl}
            title={title}
          />
        ) : (
          <div className="flex h-full min-h-[650px] items-center justify-center rounded bg-white text-center">
            <div className="max-w-xs px-6">
              <FileText className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-3 text-sm font-bold text-slate-700">
                {pdfError ?? "Preparing PDF preview..."}
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function createLegalWordingPdfBlob({
  content,
  highlights,
  title,
  tone
}: {
  content: string;
  highlights: string[];
  title: string;
  tone: "amber" | "emerald";
}) {
  const pages = renderLegalWordingCanvases({
    content,
    highlights,
    title,
    tone
  });
  return new Blob([buildPdfFromJpegPages(pages)], { type: "application/pdf" });
}

function renderLegalWordingCanvases({
  content,
  highlights,
  title,
  tone
}: {
  content: string;
  highlights: string[];
  title: string;
  tone: "amber" | "emerald";
}) {
  const pageWidth = 1240;
  const pageHeight = 1754;
  const marginX = 120;
  const topMargin = 110;
  const bottomMargin = 110;
  const lineHeight = 34;
  const bodyFont = "24px Arial, sans-serif";
  const bodyColor = "#1f2937";
  const highlightColor = tone === "emerald" ? "#d1fae5" : "#fef3c7";
  const accentColor = tone === "emerald" ? "#047857" : "#b45309";
  const sourceLines = legalWordingPdfLines(content, highlights, pageWidth - marginX * 2, bodyFont);
  const pages: HTMLCanvasElement[] = [];
  let index = 0;

  while (index < sourceLines.length || pages.length === 0) {
    const isFirstPage = pages.length === 0;
    const canvas = document.createElement("canvas");
    canvas.width = pageWidth;
    canvas.height = pageHeight;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas rendering is unavailable.");

    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, pageWidth, pageHeight);
    if (isFirstPage) {
      context.fillStyle = "#e2e8f0";
      context.fillRect(marginX, topMargin - 28, pageWidth - marginX * 2, 2);
      context.fillStyle = accentColor;
      context.font = "bold 32px Arial, sans-serif";
      context.textAlign = "center";
      context.fillText(title, pageWidth / 2, topMargin + 24);
    }
    context.textAlign = "left";
    context.font = bodyFont;

    let y = isFirstPage ? topMargin + 88 : topMargin;
    while (index < sourceLines.length && y < pageHeight - bottomMargin) {
      const line = sourceLines[index];
      if (!line.text) {
        y += lineHeight * 0.7;
        index += 1;
        continue;
      }
      if (line.highlighted) {
        context.fillStyle = highlightColor;
        context.fillRect(marginX - 8, y - 25, pageWidth - marginX * 2 + 16, 32);
      }
      context.fillStyle = bodyColor;
      context.font = line.bold ? "bold 24px Arial, sans-serif" : bodyFont;
      context.fillText(line.text, marginX, y);
      y += lineHeight;
      index += 1;
    }

    context.fillStyle = "#cbd5e1";
    context.fillRect(marginX, pageHeight - 82, pageWidth - marginX * 2, 2);
    context.fillStyle = "#94a3b8";
    context.font = "18px Arial, sans-serif";
    context.textAlign = "center";
    context.fillText(`Page ${pages.length + 1}`, pageWidth / 2, pageHeight - 42);
    pages.push(canvas);
  }

  return pages;
}

function legalWordingPdfLines(
  content: string,
  highlights: string[],
  maxWidth: number,
  font: string
) {
  const measuringCanvas = document.createElement("canvas");
  const context = measuringCanvas.getContext("2d");
  if (!context) throw new Error("Canvas rendering is unavailable.");
  context.font = font;
  const normalizedHighlights = highlights.map((value) => normalizeLegalPdfText(value)).filter(Boolean);
  const lines: Array<{ text: string; highlighted: boolean; bold: boolean }> = [];
  for (const paragraph of content.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n")) {
    const trimmed = paragraph.trim();
    if (!trimmed) {
      lines.push({ text: "", highlighted: false, bold: false });
      continue;
    }
    const wrapped = wrapPdfTextLine(context, trimmed, maxWidth);
    for (const line of wrapped) {
      const normalizedLine = normalizeLegalPdfText(line);
      const highlighted = normalizedHighlights.some((phrase) =>
        phrase.includes(normalizedLine) || normalizedLine.includes(phrase)
      );
      lines.push({
        text: line,
        highlighted,
        bold: /^(capitolul|art\.|section|article)\b/i.test(trimmed)
      });
    }
  }
  return lines;
}

function wrapPdfTextLine(
  context: CanvasRenderingContext2D,
  text: string,
  maxWidth: number
) {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (context.measureText(next).width <= maxWidth || !current) {
      current = next;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines;
}

function normalizeLegalPdfText(value: string) {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

function buildPdfFromJpegPages(pages: HTMLCanvasElement[]) {
  const encoder = new TextEncoder();
  const objects: Uint8Array[] = [];
  const pageCount = pages.length;
  const pageWidth = 595;
  const pageHeight = 842;
  const pageObjectIds = pages.map((_, index) => 3 + index * 3);
  const contentObjectIds = pages.map((_, index) => 4 + index * 3);
  const imageObjectIds = pages.map((_, index) => 5 + index * 3);

  objects[0] = encoder.encode("<< /Type /Catalog /Pages 2 0 R >>");
  objects[1] = encoder.encode(
    `<< /Type /Pages /Kids [${pageObjectIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${pageCount} >>`
  );

  pages.forEach((canvas, index) => {
    const pageId = pageObjectIds[index];
    const contentId = contentObjectIds[index];
    const imageId = imageObjectIds[index];
    const imageName = `Im${index + 1}`;
    const jpegBytes = dataUrlBytes(canvas.toDataURL("image/jpeg", 0.94));
    const contentStream = encoder.encode(`q ${pageWidth} 0 0 ${pageHeight} 0 0 cm /${imageName} Do Q`);
    objects[pageId - 1] = encoder.encode(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /XObject << /${imageName} ${imageId} 0 R >> >> /Contents ${contentId} 0 R >>`
    );
    objects[contentId - 1] = pdfStreamObject(contentStream);
    objects[imageId - 1] = pdfStreamObject(
      jpegBytes,
      ` /Type /XObject /Subtype /Image /Width ${canvas.width} /Height ${canvas.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode`
    );
  });

  return serializePdfObjects(objects);
}

function dataUrlBytes(dataUrl: string) {
  const base64 = dataUrl.split(",", 2)[1] ?? "";
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function pdfStreamObject(content: Uint8Array, extraDictionary = "") {
  const encoder = new TextEncoder();
  return concatBytes(
    encoder.encode(`<< /Length ${content.length}${extraDictionary} >>\nstream\n`),
    content,
    encoder.encode("\nendstream")
  );
}

function serializePdfObjects(objects: Uint8Array[]) {
  const encoder = new TextEncoder();
  const parts: Uint8Array[] = [encoder.encode("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")];
  const offsets: number[] = [0];
  let cursor = parts[0].length;

  objects.forEach((object, index) => {
    offsets.push(cursor);
    const prefix = encoder.encode(`${index + 1} 0 obj\n`);
    const suffix = encoder.encode("\nendobj\n");
    parts.push(prefix, object, suffix);
    cursor += prefix.length + object.length + suffix.length;
  });

  const xrefOffset = cursor;
  const rows = offsets.map((offset, index) =>
    index === 0 ? "0000000000 65535 f " : `${String(offset).padStart(10, "0")} 00000 n `
  );
  const trailer = [
    "xref",
    `0 ${objects.length + 1}`,
    ...rows,
    "trailer",
    `<< /Size ${objects.length + 1} /Root 1 0 R >>`,
    "startxref",
    String(xrefOffset),
    "%%EOF",
    ""
  ].join("\n");
  parts.push(encoder.encode(trailer));
  return concatBytes(...parts);
}

function concatBytes(...chunks: Uint8Array[]) {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const output = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

function buildDraftPreviewContent(
  baseContent: string,
  hunks: TemplateChangeSuggestionHunk[]
) {
  return hunks.reduce((content, hunk) => {
    if (!isReviewedHunk(hunk) || hunk.status === "rejected") return content;
    if (hunk.change_type === "delete") return content.replace(hunk.old_text, "");
    if (hunk.change_type === "insert_before") {
      return content.replace(hunk.old_text, `${hunk.new_text}\n${hunk.old_text}`);
    }
    if (hunk.change_type === "insert_after") {
      return content.replace(hunk.old_text, `${hunk.old_text}\n${hunk.new_text}`);
    }
    return content.replace(hunk.old_text, hunk.new_text);
  }, baseContent);
}

function legalWordingPdfFilename(templateCode: string, state: string) {
  const slug = templateCode.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `${slug || "legal-wording"}-${state}.pdf`;
}

function draftApprovalRecipient(revision: TemplateDraftRevision, item: LegalChangeItem) {
  const approvalRequest = revision.source_metadata.approval_request;
  if (approvalRequest && typeof approvalRequest === "object") {
    const recipient = (approvalRequest as { recipient_institution?: unknown }).recipient_institution;
    if (typeof recipient === "string" && recipient.trim()) return recipient.trim();
  }
  return item.legal_document.issuer?.trim() || item.legal_document.source_id || "responsible legal institution";
}

type BadgeTone = "amber" | "blue" | "green" | "red" | "slate";
type ClaimReviewStep = "details" | "evidence" | "communicate" | "decision";
type LegalReviewStep = "what-changed" | "what-affected" | "review-wording" | "create-draft";

const claimReviewSteps: Array<{ id: ClaimReviewStep; label: string }> = [
  { id: "details", label: "Details" },
  { id: "evidence", label: "Evidence" },
  { id: "communicate", label: "Communicate" },
  { id: "decision", label: "Decision" }
];

const legalReviewSteps: Array<{ id: LegalReviewStep; label: string }> = [
  { id: "what-changed", label: "Change" },
  { id: "what-affected", label: "Documents" },
  { id: "review-wording", label: "Wording" },
  { id: "create-draft", label: "Draft" }
];

function parseClaimReviewStep(value?: string): ClaimReviewStep | undefined {
  return claimReviewSteps.some((step) => step.id === value)
    ? (value as ClaimReviewStep)
    : undefined;
}

function LegalReviewWorkflowTabs({
  activePath,
  candidate,
  item,
  suggestion
}: {
  activePath: string;
  candidate?: LegalTemplateReviewCandidate;
  item: LegalChangeItem;
  suggestion?: TemplateChangeSuggestion;
}) {
  const navigate = useNavigate();
  const updatePath = `/legal-review/${encodeURIComponent(item.legal_document.id)}`;
  const routeCandidate =
    candidate ??
    item.candidates.find((current) => current.candidate_id === suggestion?.candidate_id) ??
    item.candidates[0];
  const templatePath = routeCandidate
    ? `${updatePath}/documents/${encodeURIComponent(candidateRouteId(routeCandidate))}`
    : undefined;
  const stepTargets: Array<{ id: LegalReviewStep; label: string; to: string; enabled: boolean }> = legalReviewSteps.map((step) => {
    if (step.id === "what-changed") {
      return { ...step, to: updatePath, enabled: true };
    }
    if (step.id === "what-affected") {
      return { ...step, to: `${updatePath}/documents`, enabled: true };
    }
    if (step.id === "review-wording") {
      return {
        ...step,
        to: templatePath ? `${templatePath}/changes` : `${updatePath}/documents`,
        enabled: Boolean(templatePath)
      };
    }
    return {
      ...step,
      to: templatePath ? `${templatePath}/draft` : `${updatePath}/documents`,
      enabled: Boolean(templatePath)
    };
  });
  const activeStep = workflowStepFromPath(activePath);

  function focusTab(stepId: LegalReviewStep) {
    window.setTimeout(() => document.getElementById(legalReviewTabId(stepId))?.focus(), 0);
  }

  function navigateToTab(stepId: LegalReviewStep) {
    const target = stepTargets.find((step) => step.id === stepId);
    if (!target?.enabled) return;
    navigate(target.to);
    focusTab(stepId);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLElement>, index: number) {
    if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
      event.preventDefault();
      navigateToTab(stepTargets[index].id);
      return;
    }

    const enabledTargets = stepTargets
      .map((step, stepIndex) => ({ ...step, stepIndex }))
      .filter((step) => step.enabled);
    const currentEnabledIndex = enabledTargets.findIndex((step) => step.stepIndex === index);
    if (currentEnabledIndex < 0) return;

    const lastIndex = enabledTargets.length - 1;
    let nextIndex: number | undefined;

    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      nextIndex = currentEnabledIndex === lastIndex ? 0 : currentEnabledIndex + 1;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      nextIndex = currentEnabledIndex === 0 ? lastIndex : currentEnabledIndex - 1;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = lastIndex;
    }

    if (nextIndex === undefined) return;
    event.preventDefault();
    navigateToTab(enabledTargets[nextIndex].id);
  }

  return (
    <div className="flex h-12 shrink-0 items-end overflow-y-hidden border-b border-slate-200 bg-slate-50/80 px-5 pt-2 sm:px-6">
      <div className="min-w-0 max-w-full overflow-x-auto overflow-y-hidden pb-px scrollbar-none">
        <div
          aria-label="Legal review tabs"
          className="inline-flex min-w-max items-end gap-1"
          role="tablist"
        >
          {stepTargets.map((step, index) => {
            const selected = activeStep === index;
            const tabClass = `relative -mb-px inline-flex h-10 items-center justify-center rounded-t-lg border px-4 text-sm transition focus-visible:z-20 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-orange-100 ${
              selected
                ? "border-slate-200 border-b-white bg-white font-bold text-orange-700 shadow-sm after:absolute after:inset-x-4 after:top-0 after:h-0.5 after:rounded-full after:bg-orange-600"
                : "border-transparent bg-slate-100/70 font-semibold text-slate-600 hover:bg-slate-200/70 hover:text-slate-950"
            }`;

            if (!step.enabled) {
              return (
                <span
                  aria-disabled="true"
                  aria-controls={legalReviewPanelId(step.id)}
                  className={`${tabClass} cursor-not-allowed opacity-50 hover:bg-slate-100/70 hover:text-slate-600`}
                  id={legalReviewTabId(step.id)}
                  key={step.id}
                  role="tab"
                  tabIndex={-1}
                >
                  {step.label}
                </span>
              );
            }

            return (
              <Link
                aria-controls={legalReviewPanelId(step.id)}
                aria-current={selected ? "page" : undefined}
                aria-selected={selected ? "true" : undefined}
                className={tabClass}
                id={legalReviewTabId(step.id)}
                key={step.id}
                onKeyDown={(event) => handleKeyDown(event, index)}
                role="tab"
                tabIndex={selected ? 0 : -1}
                to={step.to}
              >
                {step.label}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function legalReviewTabId(step: LegalReviewStep) {
  return `legal-review-tab-${step}`;
}

function legalReviewPanelId(step: LegalReviewStep) {
  return `legal-review-panel-${step}`;
}

function legalReviewStepFromPath(pathname: string) {
  return legalReviewSteps[workflowStepFromPath(pathname)].id;
}

function workflowStepFromPath(pathname: string) {
  if (pathname.endsWith("/draft")) return 3;
  if (pathname.endsWith("/changes")) return 2;
  if (pathname.endsWith("/documents") || pathname.endsWith("/templates")) return 1;
  return 0;
}

function LegalReviewMissingState({
  description,
  isLoading,
  title
}: {
  description: string;
  isLoading: boolean;
  title: string;
}) {
  return (
    <>
      <EmployeePageHeader title="Legal Review" />
      {isLoading ? (
        <Panel>
          <p className="text-sm font-semibold text-slate-500">Loading legal review data...</p>
        </Panel>
      ) : (
        <div className="space-y-4">
          <EmptyState description={description} title={title} />
          <RouteActionLink to="/legal-review" variant="secondary">Back to queue</RouteActionLink>
        </div>
      )}
    </>
  );
}

function RouteActionLink({
  children,
  className = "",
  to,
  variant = "primary"
}: {
  children: ReactNode;
  className?: string;
  to: string;
  variant?: "primary" | "secondary";
}) {
  const classes =
    variant === "primary"
      ? "bg-orange-600 text-white hover:bg-orange-600 focus:ring-orange-100"
      : "border border-slate-200 bg-white text-slate-700 shadow-sm hover:bg-slate-50 focus:ring-slate-100";
  return (
    <Link
      className={`inline-flex min-h-9 items-center justify-center gap-2 rounded-md px-3.5 py-1.5 text-sm font-semibold transition focus:outline-none focus:ring-4 ${classes} ${className}`}
      to={to}
    >
      {children}
    </Link>
  );
}

function legalUpdateStatusForItem(
  item: LegalChangeItem,
  suggestion?: TemplateChangeSuggestion,
  draftRevision?: TemplateDraftRevision
) {
  return legalUpdateStatus(
    item,
    suggestionForUpdate(item, suggestion),
    draftRevisionForUpdate(item, suggestion, draftRevision)
  );
}

function suggestionForUpdate(item: LegalChangeItem, suggestion?: TemplateChangeSuggestion) {
  return suggestion?.normalized_legal_document_id === item.legal_document.id ? suggestion : undefined;
}

function draftRevisionForUpdate(
  item: LegalChangeItem,
  suggestion?: TemplateChangeSuggestion,
  draftRevision?: TemplateDraftRevision
) {
  const activeSuggestion = suggestionForUpdate(item, suggestion);
  return activeSuggestion && draftRevision?.suggestion_id === activeSuggestion.id ? draftRevision : undefined;
}

function suggestionForCandidate(
  candidate?: LegalTemplateReviewCandidate,
  suggestion?: TemplateChangeSuggestion
) {
  return candidate && isSuggestionForCandidate(suggestion, candidate) ? suggestion : undefined;
}

function suggestionDetailForCandidate(
  candidate?: LegalTemplateReviewCandidate,
  suggestionDetail?: TemplateChangeSuggestionDetail
) {
  return candidate && suggestionDetail?.candidate.candidate_id === candidate.candidate_id ? suggestionDetail : undefined;
}

function isSuggestionForCandidate(
  suggestion: TemplateChangeSuggestion | undefined,
  candidate: LegalTemplateReviewCandidate
) {
  return suggestion?.candidate_id === candidate.candidate_id;
}

function findCandidateForRoute(item: LegalChangeItem | undefined, templateId: string | undefined) {
  if (!item || !templateId) return undefined;
  const decodedTemplateId = safeDecodeRouteParam(templateId);
  return item.candidates.find((candidate) => {
    return (
      candidateRouteId(candidate) === decodedTemplateId ||
      candidate.candidate_id === decodedTemplateId ||
      candidate.template_code === decodedTemplateId
    );
  });
}

function candidateRouteId(candidate: LegalTemplateReviewCandidate) {
  return String(candidate.template_id);
}

function safeDecodeRouteParam(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function legalUpdateStatus(
  item: LegalChangeItem,
  suggestion?: TemplateChangeSuggestion,
  draftRevision?: TemplateDraftRevision
): "Needs review" | "Suggestion ready" | "Wording edited" | "Changes accepted" | "Draft created" | "Draft submitted" | "Processed" | "Dismissed" {
  if (draftRevision?.status === "submitted_for_approval") return "Draft submitted";
  if (draftRevision) return "Draft created";
  if (isDismissedSuggestion(suggestion)) return "Dismissed";
  if (suggestion?.hunks.some((hunk) => hunk.status === "accepted")) return "Changes accepted";
  if (suggestion?.hunks.some((hunk) => hunk.status === "edited")) return "Wording edited";
  if (suggestion) return "Suggestion ready";
  if (item.candidates.length && item.candidates.every((candidate) => candidate.status === "dismissed")) return "Dismissed";
  if (item.candidates.length && item.candidates.every((candidate) => candidate.status !== "needs_review")) return "Processed";
  return "Needs review";
}

function isLegalUpdateProcessedForQueue(
  item: LegalChangeItem,
  suggestion?: TemplateChangeSuggestion,
  draftRevision?: TemplateDraftRevision
) {
  if (item.candidates.length) {
    return item.candidates.every((candidate) => candidate.status !== "needs_review");
  }
  return ["Draft created", "Draft submitted", "Processed", "Dismissed"].includes(
    legalUpdateStatusForItem(item, suggestion, draftRevision)
  );
}

function isDismissedSuggestion(suggestion?: TemplateChangeSuggestion) {
  return Boolean(
    suggestion?.hunks.length &&
      suggestion.hunks.every((hunk) => hunk.status === "rejected")
  );
}

function isReviewedHunk(hunk: TemplateChangeSuggestionHunk) {
  return hunk.status === "accepted" || hunk.status === "rejected" || hunk.status === "edited";
}

function reviewedHunkCount(suggestion?: TemplateChangeSuggestion) {
  return suggestion?.hunks.filter(isReviewedHunk).length ?? 0;
}

function hunkDisplayStatus(
  hunk: TemplateChangeSuggestionHunk,
  draftRevision?: TemplateDraftRevision
): "Draft" | "Edited" | "Accepted" | "Rejected" | "Applied to draft" {
  if (draftRevision?.applied_hunk_ids.includes(hunk.id)) return "Applied to draft";
  if (hunk.status === "accepted") return "Accepted";
  if (hunk.status === "rejected") return "Rejected";
  if (hunk.status === "edited") return "Edited";
  return "Draft";
}

function hunkStatusTone(status: ReturnType<typeof hunkDisplayStatus>): BadgeTone {
  if (status === "Accepted" || status === "Applied to draft") return "green";
  if (status === "Rejected") return "red";
  if (status === "Edited") return "blue";
  return "slate";
}

function changeNameForHunk(hunk: TemplateChangeSuggestionHunk) {
  const text = `${hunk.section_label ?? ""} ${hunk.old_text} ${hunk.new_text}`.toLowerCase();
  if (text.includes("notific") && text.includes("10") && text.includes("5")) {
    return "Claim notification deadline";
  }
  return hunk.section_label ?? "Template wording";
}

function changeSummaryForHunk(hunk: TemplateChangeSuggestionHunk) {
  const text = `${hunk.old_text} ${hunk.new_text}`.toLowerCase();
  if (text.includes("10") && text.includes("5")) {
    return "10 days â†’ 5 days";
  }
  return readableLabel(hunk.change_type);
}

function reviewDecisionLabel(hunk: TemplateChangeSuggestionHunk) {
  if (hunk.status === "accepted") return "Accepted";
  if (hunk.status === "rejected") return "Rejected";
  if (hunk.status === "edited") return "Edited";
  return "Not reviewed";
}

function legalQueueTitle(document: LegalChangeItem["legal_document"]) {
  const summary = `${document.summary ?? ""} ${document.full_text}`.toLowerCase();
  if (summary.includes("notific") && summary.includes("10") && summary.includes("5")) {
    return "Claim notification deadline changed";
  }
  return plainLegalTitle(document);
}

function legalDeadlineChangeLabel(document: LegalChangeItem["legal_document"]) {
  const summary = `${document.summary ?? ""} ${document.full_text}`.toLowerCase();
  if (summary.includes("10") && summary.includes("5")) {
    return "10 days â†’ 5 days";
  }
  return "Legal requirement changed";
}

function legalUpdateSourceLabel(document: LegalChangeItem["legal_document"]) {
  if (document.instrument_type && document.instrument_number && document.instrument_year) {
    const prefix = document.title.startsWith("DEMO") ? "DEMO - " : "";
    const instrument = document.instrument_type === "lege" ? "Legea" : readableLabel(document.instrument_type);
    return `${prefix}${instrument} nr. ${document.instrument_number}/${document.instrument_year}`;
  }
  return document.publication_reference ?? document.title;
}

function plainLegalTitle(document: LegalChangeItem["legal_document"]) {
  const currentReference = firstReference(document.legal_references);
  const amendedReference = firstReference(document.amends);
  if (currentReference && amendedReference) {
    const prefix = document.title.startsWith("DEMO") ? "DEMO - " : "";
    return `${prefix}${humanLegalReference(currentReference)} modifies ${humanLegalReference(amendedReference)}`;
  }
  return document.title;
}

function plainLegalSummary(document: LegalChangeItem["legal_document"]) {
  return document.summary ?? firstSentence(document.full_text);
}

function sourceExcerpt(document: LegalChangeItem["legal_document"]) {
  return document.full_text.length > 700 ? `${document.full_text.slice(0, 700)}...` : document.full_text;
}

function productLineFor(
  candidate: LegalTemplateReviewCandidate,
  suggestionDetail?: TemplateChangeSuggestionDetail
) {
  if (suggestionDetail?.candidate.candidate_id === candidate.candidate_id && suggestionDetail.template.product_line) {
    return readableLabel(suggestionDetail.template.product_line);
  }
  const metadataProductLine = candidate.source_metadata.product_line;
  if (typeof metadataProductLine === "string") return readableLabel(metadataProductLine);
  if (candidate.template_code.toLowerCase().includes("pad")) return "Property";
  return "Product line pending";
}

function plainCandidateReason(candidate: LegalTemplateReviewCandidate) {
  if (candidate.match_type === "amended_reference" && candidate.matched_reference) {
    return `References ${humanLegalReference(candidate.matched_reference)}, which was amended.`;
  }
  if (candidate.match_type === "repealed_reference" && candidate.matched_reference) {
    return `References ${humanLegalReference(candidate.matched_reference)}, which was repealed.`;
  }
  if (candidate.match_type === "direct_reference" && candidate.matched_reference) {
    return `References ${humanLegalReference(candidate.matched_reference)} directly.`;
  }
  return candidate.review_reason;
}

function templateContextForHunk(hunk: TemplateChangeSuggestionHunk, content: string | undefined): TemplateContext {
  const sectionTitle = contextStringField(hunk, "templateSectionTitle", "template_section_title") ?? hunk.section_label ?? "Template clause";
  const articleTitle = contextStringField(hunk, "templateArticleTitle", "template_article_title");
  const providedBefore = contextTextField(hunk, "beforeContext", "before_context");
  const providedAfter = contextTextField(hunk, "afterContext", "after_context");
  const fullContextExcerpt = contextTextField(hunk, "fullContextExcerpt", "full_context_excerpt");
  const startOffset = contextNumberField(hunk, "startOffset", "start_offset");
  const endOffset = contextNumberField(hunk, "endOffset", "end_offset");
  const derivedContext = fullContextExcerpt
    ? deriveTemplateContext(fullContextExcerpt, hunk.old_text)
    : deriveTemplateContext(content, hunk.old_text);

  if (providedBefore || providedAfter || fullContextExcerpt) {
    return {
      sectionTitle,
      articleTitle,
      hunkId: hunk.id,
      beforeContext: derivedContext.beforeContext ?? providedBefore,
      changedText: hunk.old_text,
      afterContext: derivedContext.afterContext ?? providedAfter,
      fullContextExcerpt,
      startOffset,
      endOffset
    };
  }

  return {
    sectionTitle,
    articleTitle,
    hunkId: hunk.id,
    changedText: hunk.old_text,
    ...derivedContext
  };
}

function deriveTemplateContext(content: string | undefined, exactText: string): Partial<TemplateContext> {
  if (!content || !exactText) return {};
  const index = content.indexOf(exactText);
  if (index < 0) return {};
  const [beforeStart, afterEnd] = contextBoundsAroundChange(content, index, index + exactText.length);
  return {
    beforeContext: trimContextBefore(content.slice(beforeStart, index)),
    afterContext: trimContextAfter(content.slice(index + exactText.length, afterEnd)),
    fullContextExcerpt: content.slice(beforeStart, afterEnd).trim(),
    startOffset: index,
    endOffset: index + exactText.length
  };
}

function contextBoundsAroundChange(content: string, start: number, end: number): [number, number] {
  const paragraphBounds = paragraphContextBounds(content, start, end);
  if (paragraphBounds) return paragraphBounds;
  return [
    Math.max(0, start - 700),
    Math.min(content.length, end + 700)
  ];
}

function paragraphContextBounds(content: string, start: number, end: number): [number, number] | undefined {
  const spans = [...content.matchAll(/\S[\s\S]*?(?=\n\s*\n|$)/g)].map((match) => {
    const matchStart = match.index ?? 0;
    return [matchStart, matchStart + match[0].length] as [number, number];
  });
  if (spans.length < 2) return undefined;

  const targetIndex = spans.findIndex(([spanStart, spanEnd]) => spanStart <= start && end <= spanEnd);
  if (targetIndex < 0) return undefined;

  const beforeIndex = Math.max(0, targetIndex - 1);
  const afterIndex = Math.min(spans.length - 1, targetIndex + 1);
  const beforeStart = spans[beforeIndex][0];
  const afterEnd = spans[afterIndex][1];
  if (afterEnd - beforeStart > 2400) {
    return [
      Math.max(0, start - 700),
      Math.min(content.length, end + 700)
    ];
  }
  return [beforeStart, afterEnd];
}

function trimContextBefore(value: string) {
  const trimmed = value.trimStart();
  return trimmed.trim() ? trimmed : undefined;
}

function trimContextAfter(value: string) {
  const trimmed = value.trimEnd();
  return trimmed.trim() ? trimmed : undefined;
}

function needsContextJoiner(left: string, right: string) {
  return !/\s$/.test(left) && !/^\s/.test(right);
}

function contextStringField(hunk: TemplateChangeSuggestionHunk, camelKey: string, snakeKey: string) {
  const raw = hunk as unknown as Record<string, unknown>;
  const value = raw[camelKey] ?? raw[snakeKey];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function contextTextField(hunk: TemplateChangeSuggestionHunk, camelKey: string, snakeKey: string) {
  const raw = hunk as unknown as Record<string, unknown>;
  const value = raw[camelKey] ?? raw[snakeKey];
  return typeof value === "string" && value.trim() ? value : undefined;
}

function contextNumberField(hunk: TemplateChangeSuggestionHunk, camelKey: string, snakeKey: string) {
  const raw = hunk as unknown as Record<string, unknown>;
  const value = raw[camelKey] ?? raw[snakeKey];
  return typeof value === "number" ? value : undefined;
}

function humanJurisdiction(value: string) {
  if (value === "RO") return "Romania";
  if (value === "EU") return "European Union";
  return value;
}

function humanLegalReference(reference: string) {
  const parts = reference.split(":");
  if (parts.length === 4 && parts[0] === "ro") {
    const [, instrument, number, year] = parts;
    const label = instrument === "lege" ? "Legea" : readableLabel(instrument);
    return `${label} nr. ${number}/${year}`;
  }
  if (parts.length === 4 && parts[0] === "eu") {
    const [, instrument, year, number] = parts;
    return `${readableLabel(instrument)} (EU) ${year}/${number}`;
  }
  return reference;
}

function firstReference(value: Array<string | Record<string, unknown>>) {
  const reference = value.find((item): item is string => typeof item === "string");
  return reference;
}

function firstSentence(value: string) {
  return value.match(/[^.!?]+[.!?]/)?.[0]?.trim() ?? value.slice(0, 160);
}

function readableLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function ValidationBanner({ className = "", message, tone }: { className?: string; message: string; tone: "danger" | "success" | "warning" }) {
  const classes =
    tone === "danger"
      ? "border-red-200 bg-red-50 text-red-700"
      : tone === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-emerald-200 bg-emerald-50 text-emerald-700";
  return <div className={`rounded-lg border p-3 text-sm font-semibold ${classes} ${className}`}>{message}</div>;
}

function ValidationMessages({ validation }: { validation: Record<string, unknown> }) {
  const errors = Array.isArray(validation.errors) ? validation.errors : [];
  if (!errors.length) return null;
  return (
    <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3">
      <p className="text-sm font-bold text-red-700">Validation errors</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-red-700">
        {errors.map((error, index) => (
          <li key={`${index}-${JSON.stringify(error)}`}>{validationErrorText(error)}</li>
        ))}
      </ul>
    </div>
  );
}

function Badge({ children, tone }: { children: ReactNode; tone: BadgeTone }) {
  const classes = {
    amber: "bg-amber-50 text-amber-700 ring-amber-200",
    blue: "bg-orange-50 text-orange-600 ring-orange-200",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    red: "bg-red-50 text-red-700 ring-red-200",
    slate: "bg-slate-100 text-slate-700 ring-slate-200"
  };
  return <span className={`inline-flex min-h-6 items-center justify-center rounded-full px-2 py-0.5 text-center text-[11px] font-bold ring-1 ${classes[tone]}`}>{children}</span>;
}

function ShinyText({
  className = "",
  color = "#b5b5b5",
  disabled = false,
  shineColor = "#ffffff",
  speed = 2,
  spread = 120,
  text
}: {
  className?: string;
  color?: string;
  disabled?: boolean;
  shineColor?: string;
  speed?: number;
  spread?: number;
  text: string;
}) {
  const style = {
    "--shiny-text-color": color,
    "--shiny-text-shine": shineColor,
    "--shiny-text-speed": `${speed}s`,
    "--shiny-text-spread": `${spread}deg`
  } as CSSProperties;

  return (
    <span className={`shiny-text ${disabled ? "shiny-text-disabled" : ""} ${className}`} style={style}>
      {text}
    </span>
  );
}

function DemoBadge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex min-h-6 items-center justify-center rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-400 ring-1 ring-slate-100">
      {children}
    </span>
  );
}

function stateFromHunks(hunks: TemplateChangeSuggestionHunk[]) {
  return Object.fromEntries(
    hunks.map((hunk) => [
      hunk.id,
      { newText: hunk.new_text, notes: hunk.reviewer_notes ?? "" }
    ])
  );
}

function mergeLegalChangeItems(items: LegalChangeItem[]): LegalChangeItem[] {
  const byDocumentId = new Map<string, LegalChangeItem>();
  for (const item of items) {
    const existing = byDocumentId.get(item.legal_document.id);
    if (!existing) {
      byDocumentId.set(item.legal_document.id, item);
      continue;
    }
    const candidates = uniqueLegalReviewCandidates([
      ...existing.candidates,
      ...item.candidates
    ]);
    byDocumentId.set(item.legal_document.id, {
      ...existing,
      candidates,
      affected_template_count: new Set(
        candidates.map((candidate) => candidate.template_id)
      ).size,
      highest_confidence: Math.max(existing.highest_confidence, item.highest_confidence)
    });
  }
  return Array.from(byDocumentId.values());
}

function markLegalReviewCandidateStatus(
  items: LegalChangeItem[],
  candidateId: string,
  status: "accepted" | "dismissed"
) {
  return items.map((item) => {
    if (!item.candidates.some((candidate) => candidate.candidate_id === candidateId)) return item;
    return {
      ...item,
      candidates: item.candidates.map((candidate) =>
        candidate.candidate_id === candidateId ? { ...candidate, status } : candidate
      )
    };
  });
}

function uniqueLegalReviewCandidates(candidates: LegalChangeItem["candidates"]) {
  return Array.from(
    new Map(candidates.map((candidate) => [candidate.candidate_id, candidate])).values()
  );
}

function isSynthetic(metadata: Record<string, unknown>) {
  return metadata.is_synthetic === true || typeof metadata.demo_dataset === "string";
}

function formatOptionalDate(value?: string | null) {
  return value ? formatDate(value) : "Unknown";
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatReferenceList(value: Array<string | Record<string, unknown>>) {
  if (!value.length) return "None";
  return value.map((item) => (typeof item === "string" ? item : JSON.stringify(item))).join(", ");
}

function validationErrorText(error: unknown) {
  if (!error || typeof error !== "object") return String(error);
  const record = error as Record<string, unknown>;
  return String(record.message ?? record.code ?? JSON.stringify(record));
}

export function EmployeeQuotesPage() {
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [filters, setFilters] = useState<QuoteQueueFiltersState>({
    query: "",
    dateFrom: "",
    dateTo: "",
    status: "",
    propertyType: ""
  });
  useEffect(() => {
    void getAllQuotes().then(setQuotes);
  }, []);
  const employeeVisibleQuotes = useMemo(
    () => quotes.filter((quote) => quote.status !== "draft"),
    [quotes]
  );
  const filteredQuotes = useMemo(
    () => filterQuotes(employeeVisibleQuotes, filters),
    [employeeVisibleQuotes, filters]
  );
  const hasActiveFilters = Object.values(filters).some(Boolean);
  return (
    <section className="flex h-[calc(100dvh-5.5rem)] min-h-0 flex-col overflow-hidden">
      <EmployeePageHeader className="shrink-0" title="Quotes" />
      <Panel className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <QuoteQueueFilters
          embedded
          filters={filters}
          onChange={setFilters}
          onClear={() => setFilters(emptyQuoteQueueFilters())}
        />
        <DataTable
          className="mt-4 flex min-h-0 flex-1 flex-col"
          columns={[
            { header: "Quote ID", width: "32%", cellClassName: "font-mono text-xs text-slate-600", render: (quote) => quote.id },
            { header: "Date", width: "12%", render: (quote) => formatDate(quote.createdAt) },
            { header: "Client name", width: "22%", render: (quote) => quote.clientName },
            { header: "Property type", width: "14%", render: (quote) => quote.propertyType },
            { header: "Premium", width: "10%", render: (quote) => formatQuotePremiumForDisplay(quote) },
            { header: "Status", width: "10%", render: (quote) => <StatusBadge status={quote.status} /> }
          ]}
          data={filteredQuotes}
          emptyText={hasActiveFilters ? "No quotes match these filters." : "No quotes available."}
          getRowHref={(quote) => `/employee/quotes/${quote.id}`}
          scrollerClassName="min-h-0 flex-1"
          variant="embedded"
        />
      </Panel>
    </section>
  );
}

interface QuoteQueueFiltersState {
  query: string;
  dateFrom: string;
  dateTo: string;
  status: QuoteStatus | "";
  propertyType: PropertyType | "";
}

const quoteStatusOptions: QuoteStatus[] = [
  "submitted",
  "in_review",
  "approved",
  "rejected",
  "contract_generated",
  "accepted_by_client",
  "declined_by_client"
];

const propertyTypeOptions: PropertyType[] = ["Apartment", "House", "Commercial"];

function QueueFilterShell({
  children,
  embedded
}: {
  children: ReactNode;
  embedded?: boolean;
}) {
  if (embedded) {
    return (
      <div className="shrink-0 pb-4">
        {children}
      </div>
    );
  }

  return <Panel className="mb-4">{children}</Panel>;
}

function EmployeeQuotePremiumValue({ quote }: { quote: Quote }) {
  return (
    <span className="inline-flex flex-col gap-0.5">
      <span>{formatQuotePremiumForDisplay(quote)}</span>
      <span className="text-xs font-semibold text-slate-500">
        {getQuotePricingSourceLabel(quote)}
      </span>
    </span>
  );
}

function EmployeeQuoteRiskValue({ quote }: { quote: Quote }) {
  return (
    <span className="inline-flex flex-col gap-0.5">
      <span>{isQuoteRiskUnavailable(quote) ? "Unavailable" : quote.riskScore}</span>
      <span className="text-xs font-semibold text-slate-500">
        {getQuoteRiskSourceLabel(quote)}
      </span>
    </span>
  );
}

function QuoteQueueFilters({
  embedded = false,
  filters,
  onChange,
  onClear
}: {
  embedded?: boolean;
  filters: QuoteQueueFiltersState;
  onChange: (filters: QuoteQueueFiltersState) => void;
  onClear: () => void;
}) {
  const hasActiveFilters = Object.values(filters).some(Boolean);

  function update(patch: Partial<QuoteQueueFiltersState>) {
    onChange({ ...filters, ...patch });
  }

  return (
    <QueueFilterShell embedded={embedded}>
      <div className="grid gap-3 lg:grid-cols-[minmax(220px,1.4fr)_repeat(4,minmax(150px,1fr))_auto] lg:items-end">
        <label className="block">
          <span className="label">Search</span>
          <input
            className="input"
            onChange={(event) => update({ query: event.target.value })}
            placeholder="Client name or quote ID"
            value={filters.query}
          />
        </label>
        <label className="block">
          <span className="label">From</span>
          <input
            className="input"
            onChange={(event) => update({ dateFrom: event.target.value })}
            type="date"
            value={filters.dateFrom}
          />
        </label>
        <label className="block">
          <span className="label">To</span>
          <input
            className="input"
            onChange={(event) => update({ dateTo: event.target.value })}
            type="date"
            value={filters.dateTo}
          />
        </label>
        <label className="block">
          <span className="label">Status</span>
          <select
            className="input"
            onChange={(event) => update({ status: event.target.value as QuoteStatus | "" })}
            value={filters.status}
          >
            <option value="">All statuses</option>
            {quoteStatusOptions.map((status) => (
              <option key={status} value={status}>
                {titleCaseLabel(status)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="label">Property type</span>
          <select
            className="input"
            onChange={(event) => update({ propertyType: event.target.value as PropertyType | "" })}
            value={filters.propertyType}
          >
            <option value="">All property types</option>
            {propertyTypeOptions.map((propertyType) => (
              <option key={propertyType} value={propertyType}>
                {propertyType}
              </option>
            ))}
          </select>
        </label>
        <Button
          className="w-full lg:w-auto"
          disabled={!hasActiveFilters}
          onClick={onClear}
          variant={hasActiveFilters ? "primary" : "secondary"}
        >
          Clear
        </Button>
      </div>
    </QueueFilterShell>
  );
}

function emptyQuoteQueueFilters(): QuoteQueueFiltersState {
  return {
    query: "",
    dateFrom: "",
    dateTo: "",
    status: "",
    propertyType: ""
  };
}

function filterQuotes(quotes: Quote[], filters: QuoteQueueFiltersState) {
  const query = normalizeFilterText(filters.query);
  return quotes.filter((quote) => {
    if (query) {
      const searchable = `${quote.clientName} ${quote.id}`.toLowerCase();
      if (!searchable.includes(query)) return false;
    }

    if (filters.dateFrom || filters.dateTo) {
      const quoteDate = toDateKey(parseLocalDate(quote.createdAt));
      if (!quoteDate) return false;
      if (filters.dateFrom && quoteDate < filters.dateFrom) return false;
      if (filters.dateTo && quoteDate > filters.dateTo) return false;
    }

    if (filters.status && quote.status !== filters.status) return false;
    if (filters.propertyType && quote.propertyType !== filters.propertyType) return false;

    return true;
  });
}

export function EmployeeQuoteDetailPage() {
  const { quoteId } = useParams();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [quote, setQuote] = useState<Quote>();
  const [rejectOpen, setRejectOpen] = useState(false);
  const [approveOpen, setApproveOpen] = useState(false);
  const [approvalReason, setApprovalReason] = useState("");
  const [reason, setReason] = useState("");
  const [acceptance, setAcceptance] = useState<QuoteAcceptance>();
  const [decisionAudit, setDecisionAudit] = useState<QuoteDecisionAuditRecord[]>([]);
  const [decisionSubmitting, setDecisionSubmitting] = useState<"approve" | "reject" | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshQuoteDetail(): Promise<Quote | undefined> {
    if (!quoteId) return undefined;
    const [quoteItem, acceptanceItem, auditItems] = await Promise.all([
      getQuoteById(quoteId),
      getQuoteAcceptance(quoteId),
      getQuoteDecisionAudit(quoteId)
    ]);
    setQuote(quoteItem);
    setAcceptance(acceptanceItem);
    setDecisionAudit(auditItems);
    return quoteItem;
  }

  useEffect(() => {
    if (!quoteId) return;
    let cancelled = false;

    async function loadQuoteDetail() {
      setLoading(true);
      const [quoteItem, acceptanceItem, auditItems] = await Promise.all([
        getQuoteById(quoteId as string),
        getQuoteAcceptance(quoteId as string),
        getQuoteDecisionAudit(quoteId as string)
      ]);
      if (!cancelled) {
        setQuote(quoteItem);
        setAcceptance(acceptanceItem);
        setDecisionAudit(auditItems);
        setLoading(false);
      }
    }

    void loadQuoteDetail();
    return () => {
      cancelled = true;
    };
  }, [quoteId]);
  if (loading) return <EmptyState title="Loading quote" />;
  if (!quote) return <EmptyState title="Quote not found" />;
  const canReviewQuote = isQuoteReviewActionable(quote.status);
  const decisionPending = decisionSubmitting !== null;

  async function approve() {
    if (decisionPending) return;
    if (!canReviewQuote) {
      showToast("This quote has already been processed.", "error");
      return;
    }
    setDecisionSubmitting("approve");
    try {
      const updatedQuote = await employeeApproveQuote(quote.id, approvalReason);
      setQuote(updatedQuote);
      showToast("Quote approved and sent to client.");
      setApproveOpen(false);
      setApprovalReason("");
      await refreshQuoteDetail();
    } catch (error) {
      const refreshedQuote = await refreshQuoteDetail();
      if (refreshedQuote?.status === "approved") {
        setApproveOpen(false);
        setApprovalReason("");
        showToast("Quote approved. The decision was saved.");
        return;
      }
      showToast(errorMessage(error, "Quote approval failed."), "error");
    } finally {
      setDecisionSubmitting(null);
    }
  }

  async function reject(event: FormEvent) {
    event.preventDefault();
    if (decisionPending) return;
    if (!canReviewQuote) {
      showToast("This quote has already been processed.", "error");
      return;
    }
    if (!reason.trim()) {
      showToast("Please provide a rejection reason.", "error");
      return;
    }
    setDecisionSubmitting("reject");
    try {
      const updatedQuote = await employeeRejectQuote(quote.id, reason);
      setQuote(updatedQuote);
      showToast("Quote rejected and sent to client.");
      setRejectOpen(false);
      setReason("");
      await refreshQuoteDetail();
    } catch (error) {
      const refreshedQuote = await refreshQuoteDetail();
      if (refreshedQuote?.status === "rejected") {
        setRejectOpen(false);
        setReason("");
        showToast("Quote rejected. The decision was saved.");
        return;
      }
      showToast(errorMessage(error, "Quote rejection failed."), "error");
    } finally {
      setDecisionSubmitting(null);
    }
  }

  return (
    <>
      <EmployeePageHeader
        actions={<Button className="min-h-8 px-3 py-1 text-xs" onClick={() => navigate("/employee/quotes")} variant="primary">Back</Button>}
        title={`Quote Request ${quote.id}`}
      />
      <div className="grid items-stretch gap-4 lg:grid-cols-2">
        <Panel className="h-full">
          <h2 className="text-lg font-bold text-slate-950">Quote details</h2>
          <div className="mt-3 grid gap-4">
            <DetailGrid
              items={[
                ["Client", quote.clientData.full_name],
                ["Email", quote.clientData.email],
                ["Phone", quote.clientData.phone],
                ["National ID", quote.clientData.national_id],
                ["Property", quote.propertyAddress],
                ["Security features", quote.securityFeatures.length ? quote.securityFeatures.join(", ") : "None"],
                ["Claims history", quote.previousClaimsCount],
                ["Coverage amount", formatCurrency(quote.coverageAmount)]
              ]}
            />
            <div>
              <p className="text-sm font-bold text-slate-900">Uploaded documents</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {quote.attachments.length ? quote.attachments.map((doc) => <MockDocumentItem key={doc.id} name={doc.fileName} />) : <span className="text-sm text-slate-500">No attachments uploaded.</span>}
              </div>
            </div>
          </div>
        </Panel>
        <Panel className="h-full">
          <h2 className="text-lg font-bold text-slate-950">Underwriting Summary</h2>
          <div className="mt-3 space-y-3">
            <DetailGrid
              items={[
                ["Risk score", <EmployeeQuoteRiskValue quote={quote} />],
                ["Premium", <EmployeeQuotePremiumValue quote={quote} />],
                ["Recommendation", getQuoteRiskRecommendation(quote)],
                ["Status", <StatusBadge status={quote.status} />]
              ]}
            />
            <div>
              <p className="text-sm font-bold text-slate-900">Triggered rules</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
                {(quote.riskReasons.length ? quote.riskReasons : ["No risk rationale was returned."]).map((reasonItem) => <li key={reasonItem}>{reasonItem}</li>)}
              </ul>
            </div>
          </div>
          {!canReviewQuote ? (
            <p className="mt-5 rounded-lg bg-slate-50 p-3 text-sm font-semibold text-slate-600">
              This quote has already been processed. No further underwriting action is available.
            </p>
          ) : null}
          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {canReviewQuote ? (
              <>
                <Button className="min-h-8 px-3 py-1 text-xs" disabled={decisionPending} icon={Check} onClick={() => setApproveOpen(true)} variant="success">Accept</Button>
                <Button className="min-h-8 px-3 py-1 text-xs" disabled={decisionPending} icon={X} onClick={() => setRejectOpen(true)} variant="danger">Reject</Button>
              </>
            ) : null}
          </div>
        </Panel>
      </div>
      <QuoteDecisionAuditPanel records={decisionAudit} />
      <Panel className="mt-4">
        <h2 className="text-lg font-bold text-slate-950">Client acceptance provenance</h2>
        {acceptance ? (
          <DetailGrid
            items={[
              ["Signer", acceptance.signer_name],
              ["Signer email", acceptance.signer_email],
              ["Signer role", acceptance.signer_role || "Not provided"],
              ["Accepted at", formatDate(acceptance.accepted_at)],
              ["Quote document ID", acceptance.quote_document_id],
              ["Document hash", acceptance.quote_content_hash],
              ["Method", titleCaseLabel(acceptance.acceptance_method)]
            ]}
          />
        ) : (
          <p className="mt-3 text-sm text-slate-600">
            No client acceptance audit record has been captured for this quote yet.
          </p>
        )}
      </Panel>
      <Modal
        actions={<><Button disabled={decisionPending} onClick={() => setApproveOpen(false)}>Cancel</Button><Button icon={Check} loading={decisionSubmitting === "approve"} onClick={() => void approve()} variant="success">{decisionSubmitting === "approve" ? "Approving" : "Yes"}</Button></>}
        onClose={() => {
          if (!decisionPending) setApproveOpen(false);
        }}
        open={approveOpen}
        title="Approve quote"
      >
        <div className="space-y-3">
          <p>This will approve the quote and send the result back to the client. Continue?</p>
          <label className="block text-sm font-bold text-slate-700">
            Decision note <span className="font-semibold text-slate-500">(optional)</span>
            <textarea
              className="mt-1 min-h-24 w-full rounded-xl border border-slate-200 p-3 text-sm font-semibold text-slate-900 outline-none focus:border-orange-300 focus:ring-4 focus:ring-orange-100"
              disabled={decisionPending}
              onChange={(event) => setApprovalReason(event.target.value)}
              value={approvalReason}
            />
          </label>
        </div>
      </Modal>
      <Modal
        actions={<Button disabled={decisionPending} onClick={() => setRejectOpen(false)}>Cancel</Button>}
        onClose={() => {
          if (!decisionPending) setRejectOpen(false);
        }}
        open={rejectOpen}
        title="Please provide a rejection reason."
      >
        <form onSubmit={reject}>
          <textarea className="w-full rounded-xl border border-slate-200 p-3" disabled={decisionPending} onChange={(event) => setReason(event.target.value)} value={reason} />
          <div className="mt-3 flex justify-end">
            <Button icon={X} loading={decisionSubmitting === "reject"} type="submit" variant="danger">{decisionSubmitting === "reject" ? "Rejecting" : "Reject Quote"}</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

function QuoteDecisionAuditPanel({ records }: { records: QuoteDecisionAuditRecord[] }) {
  return (
    <Panel className="mt-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-bold text-slate-950">Decision audit</h2>
        <span className="text-xs font-bold uppercase tracking-normal text-slate-500">
          {records.length ? `${records.length} event${records.length === 1 ? "" : "s"}` : "No events"}
        </span>
      </div>
      {records.length ? (
        <div className="mt-3 space-y-3">
          {records.map((record) => (
            <article className="rounded-xl border border-slate-200 bg-slate-50 p-3" key={record.id}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={record.decision_status} />
                    <span className="text-xs font-semibold text-slate-500">
                      from {titleCaseLabel(record.previous_status)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-slate-700">
                    {record.reason?.trim() || "No note provided."}
                  </p>
                </div>
                <div className="shrink-0 text-left text-xs font-semibold text-slate-500 sm:text-right">
                  <p>{formatDateTime(record.decided_at)}</p>
                  <p className="mt-1 text-slate-700">
                    {record.decided_by_name || record.decided_by_email || "Unknown employee"}
                  </p>
                  {record.decided_by_email ? <p>{record.decided_by_email}</p> : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-600">
          No underwriter decision has been recorded for this quote yet.
        </p>
      )}
    </Panel>
  );
}

export function EmployeeContractsPage() {
  const [contracts, setContracts] = useState<ContractDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [filters, setFilters] = useState<ContractQueueFiltersState>({
    query: "",
    dateFrom: "",
    dateTo: "",
    status: ""
  });
  useEffect(() => {
    let cancelled = false;

    async function loadContracts() {
      setLoading(true);
      setLoadError(undefined);
      try {
        const items = await getContracts();
        if (!cancelled) setContracts(items);
      } catch (error) {
        if (!cancelled) setLoadError(errorMessage(error, "Could not load contracts."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadContracts();
    return () => {
      cancelled = true;
    };
  }, []);
  const filteredContracts = useMemo(
    () => filterContracts(contracts, filters),
    [contracts, filters]
  );
  const hasActiveFilters = Object.values(filters).some(Boolean);
  return (
    <section className="flex h-[calc(100dvh-5.5rem)] min-h-0 flex-col overflow-hidden">
      <EmployeePageHeader className="shrink-0" title="Contracts" />
      <Panel className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <ContractQueueFilters
          embedded
          filters={filters}
          onChange={setFilters}
          onClear={() => setFilters(emptyContractQueueFilters())}
        />
        <DataTable
          className="mt-4 flex min-h-0 flex-1 flex-col"
          columns={[
            { header: "Contract", width: "34%", cellClassName: "font-mono text-xs text-slate-600", render: (item) => getContractDisplayIdentifier(item) },
            { header: "Properties", width: "12%", render: (item) => getContractPropertyCount(item) },
            { header: "Client name", width: "26%", render: (item) => item.customer?.full_name ?? "Unknown client" },
            { header: "Date", width: "16%", render: (item) => safeFormatDate(item.created_at) },
            { header: "Status", width: "12%", render: (item) => <StatusBadge status={getContractLifecycleStatusLabel(item.status)} /> }
          ]}
          data={filteredContracts}
          emptyText={loadError ?? (loading ? "Loading contracts." : hasActiveFilters ? "No contracts match these filters." : "No contracts available.")}
          getRowHref={(item) => `/employee/contracts/${item.id}`}
          scrollerClassName="min-h-0 flex-1"
          variant="embedded"
        />
      </Panel>
    </section>
  );
}

interface ContractQueueFiltersState {
  query: string;
  dateFrom: string;
  dateTo: string;
  status: ContractLifecycleDisplayStatus | "";
}

const contractStatusOptions: ContractLifecycleDisplayStatus[] = ["awaiting_client_signing", "issued", "signed", "declined"];

function ContractQueueFilters({
  embedded = false,
  filters,
  onChange,
  onClear
}: {
  embedded?: boolean;
  filters: ContractQueueFiltersState;
  onChange: (filters: ContractQueueFiltersState) => void;
  onClear: () => void;
}) {
  const hasActiveFilters = Object.values(filters).some(Boolean);

  function update(patch: Partial<ContractQueueFiltersState>) {
    onChange({ ...filters, ...patch });
  }

  return (
    <QueueFilterShell embedded={embedded}>
      <div className="grid gap-3 lg:grid-cols-[minmax(220px,1.4fr)_repeat(3,minmax(150px,1fr))_auto] lg:items-end">
        <label className="block">
          <span className="label">Search</span>
          <input
            className="input"
            onChange={(event) => update({ query: event.target.value })}
            placeholder="Client name or contract display ID"
            value={filters.query}
          />
        </label>
        <label className="block">
          <span className="label">From</span>
          <input
            className="input"
            onChange={(event) => update({ dateFrom: event.target.value })}
            type="date"
            value={filters.dateFrom}
          />
        </label>
        <label className="block">
          <span className="label">To</span>
          <input
            className="input"
            onChange={(event) => update({ dateTo: event.target.value })}
            type="date"
            value={filters.dateTo}
          />
        </label>
        <label className="block">
          <span className="label">Status</span>
          <select
            className="input"
            onChange={(event) => update({ status: event.target.value as ContractLifecycleDisplayStatus | "" })}
            value={filters.status}
          >
            <option value="">All statuses</option>
            {contractStatusOptions.map((status) => (
              <option key={status} value={status}>
                {getContractLifecycleStatusLabel(status)}
              </option>
            ))}
          </select>
        </label>
        <Button
          className="w-full lg:w-auto"
          disabled={!hasActiveFilters}
          onClick={onClear}
          variant={hasActiveFilters ? "primary" : "secondary"}
        >
          Clear
        </Button>
      </div>
    </QueueFilterShell>
  );
}

function emptyContractQueueFilters(): ContractQueueFiltersState {
  return {
    query: "",
    dateFrom: "",
    dateTo: "",
    status: ""
  };
}

function filterContracts(contracts: ContractDetail[], filters: ContractQueueFiltersState) {
  const query = normalizeFilterText(filters.query);
  return contracts.filter((contract) => {
    if (query) {
      const searchable = [
        getContractDisplayIdentifier(contract),
        contract.contract_number,
        contract.id,
        contract.customer?.full_name,
        contract.asset?.address?.full_text,
        contract.source_quote_request_id,
        contract.source_quote_id
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (!searchable.includes(query)) return false;
    }

    if (filters.dateFrom || filters.dateTo) {
      const contractDate = toDateKey(parseLocalDate(contract.created_at));
      if (!contractDate) return false;
      if (filters.dateFrom && contractDate < filters.dateFrom) return false;
      if (filters.dateTo && contractDate > filters.dateTo) return false;
    }

    if (filters.status && getContractLifecycleDisplayStatus(contract.status) !== filters.status) return false;

    return true;
  });
}

function getContractPropertyCount(contract: ContractDetail) {
  return contract.asset ? 1 : "-";
}

function isLegacyContractRouteId(contractId: string) {
  return contractId.startsWith("C-");
}

function quoteIdFromLegacyContractRoute(contractId: string) {
  return contractId.slice(2);
}

function numberValue(value: number | string | null | undefined) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function safeFormatDate(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return formatDate(value);
}

function formatDateTime(value?: string | null) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return formatDate(value);
  return parsed.toLocaleString(undefined, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    year: "numeric"
  });
}

function applyPdfArtifact(
  document: GeneratedDocument,
  artifact: GeneratedDocumentPdfArtifact
): GeneratedDocument {
  return {
    ...document,
    pdf_storage_key: artifact.pdf_storage_key,
    pdf_filename: artifact.filename,
    pdf_content_hash: artifact.pdf_content_hash,
    pdf_source_content_hash: artifact.source_content_hash,
    pdf_generated_at: artifact.pdf_generated_at
  };
}

function validationIssuesFromError(error: unknown) {
  const payload = isRecord(error) ? error.payload : undefined;
  const rootValidation = isRecord(payload) ? payload.validation : undefined;
  const errorEnvelope = isRecord(payload) ? payload.error : undefined;
  const envelopeValidation = isRecord(errorEnvelope) ? errorEnvelope.validation : undefined;
  const validation = isRecord(rootValidation) ? rootValidation : isRecord(envelopeValidation) ? envelopeValidation : undefined;
  const envelopeBlockingErrors = isRecord(errorEnvelope) ? errorEnvelope.blocking_errors : undefined;
  const blockingErrors = toValidationIssues(
    validation?.blocking_errors ?? envelopeBlockingErrors
  );
  const warnings = toValidationIssues(validation?.warnings);
  return { blockingErrors, warnings };
}

function toValidationIssues(value: unknown): BackendValidationIssue[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((issue) => ({
      code: String(issue.code ?? "VALIDATION_ISSUE"),
      message: String(issue.message ?? "Validation issue"),
      field: typeof issue.field === "string" ? issue.field : null
    }));
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

export function EmployeeContractDetailPage() {
  const { contractId } = useParams();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [contract, setContract] = useState<ContractDetail>();
  const [generatedDocument, setGeneratedDocument] = useState<GeneratedDocument>();
  const [resolution, setResolution] = useState<QuoteContractResolution>();
  const [blockingErrors, setBlockingErrors] = useState<BackendValidationIssue[]>([]);
  const [warnings, setWarnings] = useState<BackendValidationIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [converting, setConverting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  useEffect(() => {
    if (!contractId) return;
    let cancelled = false;

    async function loadContractRoute() {
      setLoading(true);
      setLoadError(undefined);
      setContract(undefined);
      setGeneratedDocument(undefined);
      setResolution(undefined);
      setBlockingErrors([]);
      setWarnings([]);

      try {
        if (isLegacyContractRouteId(contractId)) {
          const quoteId = quoteIdFromLegacyContractRoute(contractId);
          const resolved = await resolveQuoteContract(quoteId);
          if (cancelled) return;

          const canonicalContractId = resolved.contract_id ?? resolved.contract?.id;
          if (canonicalContractId) {
            navigate(`/employee/contracts/${canonicalContractId}`, { replace: true });
            return;
          }

          setResolution(resolved);
          setBlockingErrors(resolved.validation.blocking_errors);
          setWarnings(resolved.validation.warnings);
          return;
        }

        const found = await getContract(contractId);
        if (cancelled) return;
        setContract(found);

        const latestDocument = await getLatestContractDocument(found.id);
        if (!cancelled) setGeneratedDocument(latestDocument);
      } catch (error) {
        if (!cancelled) {
          setLoadError(errorMessage(error, "Could not load contract."));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadContractRoute();
    return () => {
      cancelled = true;
    };
  }, [contractId, navigate]);

  async function convertLegacyQuote() {
    if (!contractId || !isLegacyContractRouteId(contractId)) return;
    setConverting(true);
    setBlockingErrors([]);
    setWarnings([]);

    try {
      const result = await convertQuoteToContract(quoteIdFromLegacyContractRoute(contractId));
      const canonicalContractId = result.contract_id ?? result.contract?.id;
      if (canonicalContractId) {
        showToast("Quote converted to a backend contract.");
        navigate(`/employee/contracts/${canonicalContractId}`, { replace: true });
        return;
      }

      setBlockingErrors(result.validation.blocking_errors);
      setWarnings(result.validation.warnings);
      showToast("Quote could not be converted.", "error");
    } catch (error) {
      const issues = validationIssuesFromError(error);
      setBlockingErrors(issues.blockingErrors);
      setWarnings(issues.warnings);
      showToast(errorMessage(error, "Quote could not be converted."), "error");
    } finally {
      setConverting(false);
    }
  }

  async function generateDocument() {
    if (!contract) return;
    setGenerating(true);
    setBlockingErrors([]);
    setWarnings([]);

    try {
      const document = await generateContractDocument(contract.id);
      setGeneratedDocument(document);
      showToast("Contract document generated.");
    } catch (error) {
      const issues = validationIssuesFromError(error);
      setBlockingErrors(issues.blockingErrors);
      setWarnings(issues.warnings);
      showToast(errorMessage(error, "Contract document generation failed."), "error");
    } finally {
      setGenerating(false);
    }
  }

  async function downloadPdf() {
    if (!generatedDocument || downloadingPdf) return;
    setDownloadingPdf(true);
    try {
      const artifact = await createGeneratedDocumentPdf(generatedDocument.id);
      setGeneratedDocument((current) => current ? applyPdfArtifact(current, artifact) : current);
      const result = await downloadGeneratedDocumentPdf(generatedDocument.id);
      triggerBlobDownload(result.blob, result.filename ?? `contract-${generatedDocument.contract_id}.pdf`);
    } catch (error) {
      showToast(errorMessage(error, "PDF download failed."), "error");
    } finally {
      setDownloadingPdf(false);
    }
  }

  if (loading) return <EmptyState title="Loading contract" />;

  if (resolution && !contract) {
    const canConvert = resolution.validation.can_convert && !resolution.already_converted;
    return (
      <>
        <EmployeePageHeader
          actions={<Button className="min-h-8 px-3 py-1 text-xs" onClick={() => navigate("/employee/contracts")} variant="primary">Back</Button>}
          subtitle="This quote link must be converted before contract content is available."
          title="Contract conversion required"
        />
        <Panel>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-bold text-slate-950">Quote {resolution.quote_id}</p>
              <p className="mt-1 text-sm text-slate-600">Status: {titleCaseLabel(resolution.conversion_status)}</p>
            </div>
            {canConvert ? (
              <Button disabled={converting} icon={FilePlus2} onClick={() => void convertLegacyQuote()} variant="primary">
                {converting ? "Converting" : "Convert to contract"}
              </Button>
            ) : null}
          </div>
          <ContractValidationIssues blockingErrors={blockingErrors} warnings={warnings} />
        </Panel>
      </>
    );
  }

  if (loadError || !contract) {
    return <EmptyState title={loadError ?? "Contract not found"} />;
  }

  return (
    <>
      <EmployeePageHeader
        actions={
          <>
            <Button disabled={generating} icon={RefreshCw} onClick={() => void generateDocument()} variant={generatedDocument ? "secondary" : "primary"}>
              {generating ? "Generating" : generatedDocument ? "Generate new version" : "Generate document"}
            </Button>
            <Button className="min-h-8 px-3 py-1 text-xs" onClick={() => navigate("/employee/contracts")} variant="primary">Back</Button>
          </>
        }
        title={`Contract ${getContractDisplayIdentifier(contract)}`}
      />
      <div className="mt-5 grid items-stretch gap-4 xl:grid-cols-[minmax(0,2.4fr)_minmax(280px,1fr)]">
        <GeneratedDocumentPdfViewer
          canCreatePdf
          document={generatedDocument}
          ensureLatestPdf
          onArtifactReady={(artifact) => {
            setGeneratedDocument((current) => current ? applyPdfArtifact(current, artifact) : current);
          }}
          showEyebrow={false}
          title="Contract PDF"
        />
        <Panel className="flex h-full flex-col overflow-hidden text-sm lg:h-[740px]">
          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            <h2 className="mb-3 text-sm font-bold text-slate-950">Contract summary</h2>
            <EmployeeContractSummaryDetails
              items={[
                ["Contract UUID", contract.id],
                ["Contract display ID", getContractDisplayIdentifier(contract)],
                ["Contract number", contract.contract_number || "-"],
                ["Client name", contract.customer?.full_name ?? "-"],
                ["Property", contract.asset?.address?.full_text ?? "-"],
                ["Status", <StatusBadge status={getContractLifecycleStatusLabel(contract.status)} />],
                ["Source quote", contract.source_quote_request_id ?? contract.source_quote_id ?? "-"],
                ["Premium", formatCurrency(numberValue(contract.pricing?.final_premium_ron))],
                ["Coverage amount", formatCurrency(numberValue(contract.asset?.declared_value))],
                ["Effective date", safeFormatDate(contract.effective_date)],
                ["Expiration date", safeFormatDate(contract.expiration_date)]
              ]}
            />

            <h3 className="mt-5 text-sm font-bold text-slate-900">Document details</h3>
            <EmployeeContractSummaryDetails
              items={[
                ["Document ID", generatedDocument?.id ?? "-"],
                ["Document status", generatedDocument ? <StatusBadge status={generatedDocument.status} /> : "-"],
                ["Template", generatedDocument?.template_code ?? "-"],
                ["Template version", generatedDocument?.template_version ?? "-"],
                ["Content hash", generatedDocument?.content_hash ?? "-"],
                ["Generated at", generatedDocument ? safeFormatDate(generatedDocument.created_at) : "-"]
              ]}
            />

            <ContractValidationIssues blockingErrors={blockingErrors} warnings={warnings} />

            <div className="mt-5 flex flex-wrap justify-end gap-2">
              {generatedDocument ? (
                <button
                  className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md bg-orange-600 px-3.5 py-1.5 text-sm font-semibold text-white transition hover:bg-orange-600 focus:outline-none focus:ring-4 focus:ring-orange-100 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={downloadingPdf}
                  onClick={() => void downloadPdf()}
                  type="button"
                >
                  <Download className="h-4 w-4" />
                  {downloadingPdf ? "Preparing PDF" : "Download PDF"}
                </button>
              ) : null}
            </div>
          </div>
        </Panel>
      </div>
    </>
  );
}

function EmployeeContractSummaryDetails({ items }: { items: Array<[string, ReactNode]> }) {
  return (
    <dl className="grid gap-2 sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2 shadow-sm" key={label}>
          <dt className="text-[10px] font-bold leading-3 text-slate-500">{label}</dt>
          <dd className="mt-1 break-words text-xs font-bold leading-4 text-slate-900">{value}</dd>
        </div>
      ))}
    </dl>
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

function ContractValidationIssues({
  blockingErrors,
  warnings
}: {
  blockingErrors: BackendValidationIssue[];
  warnings: BackendValidationIssue[];
}) {
  if (!blockingErrors.length && !warnings.length) return null;

  return (
    <div className="mt-5 space-y-3">
      {blockingErrors.length ? (
        <ValidationIssueList
          issues={blockingErrors}
          title="Blocking issues"
          tone="danger"
        />
      ) : null}
      {warnings.length ? (
        <ValidationIssueList
          issues={warnings}
          title="Warnings"
          tone="warning"
        />
      ) : null}
    </div>
  );
}

function ValidationIssueList({
  issues,
  title,
  tone
}: {
  issues: BackendValidationIssue[];
  title: string;
  tone: "danger" | "warning";
}) {
  const toneClass = tone === "danger" ? "border-red-200 bg-red-50 text-red-700" : "border-amber-200 bg-amber-50 text-amber-700";
  return (
    <div className={`rounded-lg border p-3 ${toneClass}`}>
      <h3 className="text-xs font-bold uppercase">{title}</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5">
        {issues.map((issue, index) => (
          <li key={`${issue.code}-${issue.field ?? "field"}-${index}`}>
            {issue.field ? `${issue.field}: ` : ""}
            {issue.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EmployeeCustomersPage() {
  const { showToast } = useToast();
  const [customers, setCustomers] = useState<CustomerAdminSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [filters, setFilters] = useState<CustomerProfileFiltersState>({
    query: "",
    status: ""
  });

  useEffect(() => {
    let cancelled = false;

    async function loadCustomerProfiles() {
      setLoading(true);
      setLoadError(undefined);
      try {
        const items = await listCustomers();
        if (!cancelled) setCustomers(items);
      } catch (error) {
        const message = errorMessage(error, "Could not load customer profiles.");
        if (!cancelled) {
          setLoadError(message);
          showToast(message, "error");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadCustomerProfiles();
    return () => {
      cancelled = true;
    };
  }, [showToast]);

  const filteredCustomers = useMemo(
    () => filterCustomerProfiles(customers, filters),
    [customers, filters]
  );
  const hasActiveFilters = Object.values(filters).some(Boolean);

  return (
    <section className="flex h-[calc(100dvh-5.5rem)] min-h-0 flex-col overflow-hidden">
      <EmployeePageHeader
        className="shrink-0"
        title="Customer Profiles"
      />
      <Panel className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <CustomerProfileFilters
          embedded
          filters={filters}
          onChange={setFilters}
          onClear={() => setFilters({ query: "", status: "" })}
        />
        <DataTable
          className="mt-4 flex min-h-0 flex-1 flex-col"
          columns={[
            {
              header: "Customer",
              width: "28%",
              render: (item) => (
                <div className="min-w-56">
                  <p className="font-bold text-slate-900">{item.full_name ?? "Unnamed customer"}</p>
                  <p className="text-xs font-semibold text-slate-500">{item.email ?? "No email"}</p>
                </div>
              )
            },
            { header: "Type", width: "10%", render: (item) => titleCaseLabel(item.type ?? "-") },
            { header: "Status", width: "14%", render: (item) => <CustomerProfileStatusBadge status={item.status} /> },
            { header: "Missing fields", width: "26%", render: (item) => missingFieldsSummary(item.missing_fields) },
            { header: "Last updated", width: "14%", render: (item) => safeFormatDate(item.customer_profile_updated_at) },
            { header: "Auth users", width: "8%", render: (item) => item.linked_auth_user_count ?? 0 }
          ]}
          data={filteredCustomers}
          emptyText={loadError ?? (loading ? "Loading customer profiles." : hasActiveFilters ? "No customer profiles match these filters." : "No customer profiles available.")}
          getRowHref={(item) => item.customer_id ? `/employee/customers/${item.customer_id}` : undefined}
          scrollerClassName="min-h-0 flex-1"
          variant="embedded"
        />
      </Panel>
    </section>
  );
}

export function EmployeeCustomerDetailPage() {
  const { customerId } = useParams();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<CustomerProfileDetail>();
  const [linkedUsers, setLinkedUsers] = useState<CustomerLinkedAuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [unlinkingUserId, setUnlinkingUserId] = useState<string>();
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [linkQuery, setLinkQuery] = useState("");
  const [linkUnlinkedOnly, setLinkUnlinkedOnly] = useState(true);
  const [searchResults, setSearchResults] = useState<AuthUserSearchResult[]>([]);
  const [searchingUsers, setSearchingUsers] = useState(false);
  const [searchError, setSearchError] = useState<string>();
  const [linkingAuthUserId, setLinkingAuthUserId] = useState<string>();
  const [relinkCandidate, setRelinkCandidate] = useState<AuthUserSearchResult | null>(null);
  const [relinkReason, setRelinkReason] = useState("");
  const [relinkResult, setRelinkResult] = useState<CustomerAuthUserRelinkResult | null>(null);

  useEffect(() => {
    if (!customerId) return;
    let cancelled = false;

    async function loadCustomerProfile() {
      setLoading(true);
      setLoadError(undefined);
      try {
        const [profileResult, linkedUserResult] = await Promise.all([
          getCustomerProfile(customerId),
          getCustomerAuthUsers(customerId)
        ]);
        if (!cancelled) {
          setProfile(profileResult);
          setLinkedUsers(linkedUserResult);
        }
      } catch (error) {
        const message = errorMessage(error, "Could not load customer profile.");
        if (!cancelled) {
          setLoadError(message);
          showToast(message, "error");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadCustomerProfile();
    return () => {
      cancelled = true;
    };
  }, [customerId, showToast]);

  async function refreshCustomerLinks() {
    if (!customerId) return;
    const [updatedProfile, updatedUsers] = await Promise.all([
      getCustomerProfile(customerId),
      getCustomerAuthUsers(customerId)
    ]);
    setProfile(updatedProfile);
    setLinkedUsers(updatedUsers);
  }

  function openLinkUserModal() {
    setLinkModalOpen(true);
    setSearchError(undefined);
    if (!searchResults.length) {
      void runAuthUserSearch("");
    }
  }

  async function runAuthUserSearch(query = linkQuery) {
    setSearchingUsers(true);
    setSearchError(undefined);
    try {
      const results = await searchAuthUsers({
        query,
        role: "client",
        unlinkedOnly: linkUnlinkedOnly,
        limit: 20
      });
      setSearchResults(results);
    } catch (error) {
      setSearchError(errorMessage(error, "Could not search auth users."));
      setSearchResults([]);
    } finally {
      setSearchingUsers(false);
    }
  }

  async function linkUser(result: AuthUserSearchResult) {
    if (!customerId) return;
    setLinkingAuthUserId(String(result.id));
    try {
      await linkAuthUserToCustomer(customerId, String(result.id));
      await refreshCustomerLinks();
      setLinkModalOpen(false);
      showToast("Auth user linked to customer.");
    } catch (error) {
      setSearchError(errorMessage(error, "Could not link auth user."));
      showToast(errorMessage(error, "Could not link auth user."), "error");
    } finally {
      setLinkingAuthUserId(undefined);
    }
  }

  function openRelinkUser(result: AuthUserSearchResult) {
    setRelinkCandidate(result);
    setRelinkReason("");
    setRelinkResult(null);
    setSearchError(undefined);
  }

  async function relinkUser() {
    if (!customerId || !relinkCandidate) return;
    const cleanReason = relinkReason.trim();
    if (cleanReason.length < 10) {
      setSearchError("A relink reason of at least 10 characters is required.");
      return;
    }
    const confirmed = window.confirm(
      `Move ${relinkCandidate.email} from ${authUserLinkStatus(relinkCandidate)} to this customer?`
    );
    if (!confirmed) return;

    setLinkingAuthUserId(String(relinkCandidate.id));
    try {
      const result = await relinkAuthUserToCustomer(
        customerId,
        String(relinkCandidate.id),
        cleanReason
      );
      setRelinkResult(result);
      await refreshCustomerLinks();
      await runAuthUserSearch();
      setRelinkCandidate(null);
      setRelinkReason("");
      showToast("Auth user moved to this customer.");
    } catch (error) {
      const message = errorMessage(error, "Could not relink auth user.");
      setSearchError(message);
      showToast(message, "error");
    } finally {
      setLinkingAuthUserId(undefined);
    }
  }

  async function unlinkUser(user: CustomerLinkedAuthUser) {
    if (!customerId) return;
    const authUserId = user.auth_user_id ?? user.user_id;
    if (!authUserId) return;
    const confirmed = window.confirm(`Unlink ${user.email} from this customer profile?`);
    if (!confirmed) return;

    setUnlinkingUserId(String(authUserId));
    try {
      await unlinkAuthUserFromCustomer(customerId, String(authUserId));
      await refreshCustomerLinks();
      showToast("Auth user unlinked from customer.");
    } catch (error) {
      showToast(errorMessage(error, "Could not unlink auth user."), "error");
    } finally {
      setUnlinkingUserId(undefined);
    }
  }

  if (loading) return <EmptyState title="Loading customer profile" />;
  if (loadError || !profile) return <EmptyState title={loadError ?? "Customer profile not found"} />;

  return (
    <>
      <EmployeePageHeader
        actions={
          <Button onClick={() => navigate("/employee/customers")} variant="primary">
            Back to Customers
          </Button>
        }
        title={
          <span className="inline-flex flex-wrap items-center gap-2">
            <span>{profile.full_name ?? `Customer ${profile.customer_id}`}</span>
            <CustomerProfileStatusBadge status={profile.status} />
          </span>
        }
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,1fr)]">
        <div className="space-y-4">
          <Panel>
            <h2 className="mb-3 text-lg font-bold text-slate-950">Legal and Contact Details</h2>
            <DetailGrid
              items={[
                ["Customer ID", profile.customer_id ?? "-"],
                ["Customer type", titleCaseLabel(profile.type ?? "-")],
                ["Legal/full name", profile.full_name ?? "-"],
                ["Email", profile.email ?? "-"],
                ["Phone", profile.phone ?? "-"],
                ["National ID", profile.national_id ?? "-"],
                ["Company ID", profile.company_id ?? "-"],
                ["Address", formatCustomerAddress(profile)]
              ]}
            />
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel>
            <h2 className="mb-3 text-lg font-bold text-slate-950">Profile Audit</h2>
            <DetailGrid
              items={[
                ["Completed at", safeFormatDate(profile.customer_profile_completed_at)],
                ["Last updated", safeFormatDate(profile.customer_profile_updated_at)],
                ["Updated by auth user", profile.customer_profile_updated_by_auth_user_id ?? "-"],
                ["Completion source", titleCaseLabel(profile.customer_profile_completion_source ?? "-")],
                ["Update count", profile.profile_update_count ?? 0]
              ]}
            />
          </Panel>

          <Panel>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <h2 className="text-lg font-bold text-slate-950">Linked Auth Users</h2>
              <Button icon={UserSearch} onClick={openLinkUserModal} variant="primary">Link user</Button>
            </div>
            <div className="mt-4 space-y-3">
              {linkedUsers.length ? linkedUsers.map((user) => {
                const authUserId = user.auth_user_id ?? user.user_id;
                return (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3" key={user.id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-bold text-slate-950">{user.full_name || user.email}</p>
                        <p className="text-xs font-semibold text-slate-500">{user.email}</p>
                        <p className="mt-1 text-xs font-semibold text-slate-600">
                          {titleCaseLabel(user.role)} · {user.customer_profile_status ? titleCaseLabel(user.customer_profile_status) : "Linked"}
                        </p>
                      </div>
                      <Button
                        disabled={!authUserId || unlinkingUserId === String(authUserId)}
                        onClick={() => void unlinkUser(user)}
                        variant="danger"
                      >
                        {unlinkingUserId === String(authUserId) ? "Unlinking" : "Unlink"}
                      </Button>
                    </div>
                  </div>
                );
              }) : (
                <EmptyState description="This profile is not linked to an auth user." title="No linked auth users" />
              )}
            </div>
          </Panel>
        </div>
      </div>
      <div className="mt-4">
        <CustomerEmailHistorySection
          customerId={customerId ?? String(profile.customer_id ?? profile.id)}
        />
      </div>
      <Modal
        actions={
          <>
            <Button onClick={() => setLinkModalOpen(false)}>Close</Button>
            <Button disabled={searchingUsers} icon={UserSearch} onClick={() => void runAuthUserSearch()} variant="primary">
              {searchingUsers ? "Searching" : "Search"}
            </Button>
          </>
        }
        onClose={() => setLinkModalOpen(false)}
        open={linkModalOpen}
        title="Link Client Auth User"
      >
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
            <label className="block">
              <span className="label">Search by email or name</span>
              <input
                className="input"
                onChange={(event) => setLinkQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void runAuthUserSearch();
                }}
                placeholder="client@example.com"
                value={linkQuery}
              />
            </label>
            <label className="flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 px-3 text-xs font-bold text-slate-700">
              <input
                checked={linkUnlinkedOnly}
                className="accent-orange-600"
                onChange={(event) => setLinkUnlinkedOnly(event.target.checked)}
                type="checkbox"
              />
              Unlinked only
            </label>
          </div>
          {searchError ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700">
              {searchError}
            </div>
          ) : null}
          <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
            {searchingUsers ? (
              <p className="text-sm font-semibold text-slate-500">Searching auth users...</p>
            ) : searchResults.length ? (
              searchResults.map((result) => {
                const linkedElsewhere = Boolean(
                  result.client_id && String(result.client_id) !== customerId
                );
                const linkedHere = Boolean(
                  result.client_id && String(result.client_id) === customerId
                );
                return (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3" key={result.id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-bold text-slate-950">{result.full_name}</p>
                        <p className="text-xs font-semibold text-slate-500">{result.email}</p>
                        <p className="mt-1 text-xs font-semibold text-slate-600">
                          {titleCaseLabel(result.role)} · {authUserLinkStatus(result)}
                        </p>
                      </div>
                      {linkedElsewhere ? (
                        <Button
                          disabled={linkingAuthUserId === String(result.id)}
                          onClick={() => openRelinkUser(result)}
                          variant="secondary"
                        >
                          {linkingAuthUserId === String(result.id)
                            ? "Moving"
                            : "Move to this customer"}
                        </Button>
                      ) : (
                        <Button
                          disabled={linkedHere || linkingAuthUserId === String(result.id)}
                          onClick={() => void linkUser(result)}
                          variant={linkedHere ? "secondary" : "primary"}
                        >
                          {linkingAuthUserId === String(result.id)
                            ? "Linking"
                            : linkedHere
                              ? "Linked"
                              : "Link"}
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <EmptyState description="Try a client name or email, or clear the query to see recent unlinked clients." title="No auth users found" />
            )}
          </div>
        </div>
      </Modal>
      <Modal
        actions={
          <>
            <Button onClick={() => setRelinkCandidate(null)}>Cancel</Button>
            <Button
              disabled={
                !relinkCandidate ||
                relinkReason.trim().length < 10 ||
                linkingAuthUserId === String(relinkCandidate.id)
              }
              onClick={() => void relinkUser()}
              variant="danger"
            >
              {relinkCandidate && linkingAuthUserId === String(relinkCandidate.id)
                ? "Moving"
                : "Confirm move"}
            </Button>
          </>
        }
        onClose={() => setRelinkCandidate(null)}
        open={Boolean(relinkCandidate)}
        title="Move Auth User"
      >
        {relinkCandidate ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-bold">This is an explicit relink action.</p>
              <p className="mt-1">
                {relinkCandidate.email} is currently {authUserLinkStatus(relinkCandidate)}.
                It will be moved to {profile.full_name ?? `customer ${profile.customer_id}`}.
              </p>
            </div>
            <label className="block">
              <span className="label">Audit reason</span>
              <textarea
                className="input min-h-28"
                onChange={(event) => setRelinkReason(event.target.value)}
                placeholder="Explain why this client auth user should move to this customer."
                value={relinkReason}
              />
            </label>
            <p className="text-xs font-semibold text-slate-500">
              A reason of at least 10 characters is required and will be stored in the link audit trail.
            </p>
          </div>
        ) : null}
      </Modal>
      {relinkResult ? (
        <div className="sr-only" aria-live="polite">
          Relinked {relinkResult.auth_user_email} from {relinkResult.old_customer_name ?? relinkResult.old_customer_id} to {relinkResult.new_customer_name ?? relinkResult.new_customer_id}.
        </div>
      ) : null}
    </>
  );
}

function CustomerEmailHistorySection({ customerId }: { customerId: string }) {
  const { emails, error, loading, refresh } = useCustomerEmailHistory(customerId);
  const [selectedEmail, setSelectedEmail] = useState<CustomerEmailMessage | null>(null);

  return (
    <Panel>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 className="text-lg font-bold text-slate-950">Email History</h2>
        <Button disabled={loading} icon={RefreshCw} onClick={refresh} variant="secondary">
          {loading ? "Refreshing" : "Refresh"}
        </Button>
      </div>

      <div className="mt-4">
        {loading ? (
          <EmptyState title="Loading email history" />
        ) : error ? (
          <EmptyState description={error} title="Could not load email history" />
        ) : emails.length ? (
          <div className="space-y-3">
            {emails.map((email) => (
              <CustomerEmailHistoryItem
                email={email}
                key={email.id}
                onSelect={() => setSelectedEmail(email)}
              />
            ))}
          </div>
        ) : (
          <EmptyState title="No email activity yet." />
        )}
      </div>
      <CustomerEmailMessageModal
        email={selectedEmail}
        onClose={() => setSelectedEmail(null)}
      />
    </Panel>
  );
}

function CustomerEmailHistoryItem({
  email,
  onSelect
}: {
  email: CustomerEmailMessage;
  onSelect: () => void;
}) {
  const timestamp = email.sent_at ?? email.received_at ?? email.created_at;
  const relatedCase = email.case_reference ?? email.case_id ?? "Unlinked case";
  const primaryParty = email.direction === "INBOUND"
    ? `From ${email.from_email}`
    : `To ${email.to_email}`;
  const preview = email.body_preview?.replace(/\s+/g, " ").trim();

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect();
    }
  }

  return (
    <article
      className="block w-full cursor-pointer rounded-xl border border-slate-200 bg-white p-3 text-left shadow-sm transition hover:border-orange-200 hover:bg-orange-50/40 hover:shadow-md focus:outline-none focus:ring-4 focus:ring-orange-100"
      onClick={onSelect}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <EmailDirectionBadge direction={email.direction} />
            <EmailStatusBadge status={email.status} />
          </div>
          <h3 className="mt-2 truncate text-sm font-bold text-slate-950">{email.subject}</h3>
          <p className="mt-1 truncate text-xs font-semibold text-slate-500">
            {primaryParty} · {relatedCase}
          </p>
        </div>
        <div className="shrink-0 text-left sm:text-right">
          <p className="text-xs font-semibold text-slate-500">{formatDateTime(timestamp)}</p>
          <p className="mt-1 text-xs font-bold text-orange-600">View message</p>
        </div>
      </div>

      {preview ? (
        <p className="mt-3 truncate text-sm leading-6 text-slate-700">{preview}</p>
      ) : null}

      {email.error_message ? (
        <div className="mt-3 truncate rounded-lg border border-red-200 bg-red-50 p-2 text-xs font-semibold text-red-700">
          {email.error_message}
        </div>
      ) : null}
    </article>
  );
}

function CustomerEmailMessageModal({
  email,
  onClose
}: {
  email: CustomerEmailMessage | null;
  onClose: () => void;
}) {
  if (!email) return null;

  const timestamp = email.sent_at ?? email.received_at ?? email.created_at;
  const relatedCase = email.case_reference ?? email.case_id ?? "Unlinked case";
  const fullBody = email.body_text || email.body_preview || "";
  const titleId = `email-message-title-${email.id}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
      <section
        aria-labelledby={titleId}
        aria-modal="true"
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-soft"
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <EmailDirectionBadge direction={email.direction} />
              <EmailStatusBadge status={email.status} />
            </div>
            <h2 className="break-words text-lg font-bold text-slate-950" id={titleId}>{email.subject}</h2>
            <p className="mt-1 text-sm font-semibold text-slate-500">
              {relatedCase} · {formatDateTime(timestamp)}
            </p>
          </div>
          <button
            aria-label="Close email message"
            className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
            onClick={onClose}
            type="button"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 overflow-auto px-5 py-4">
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <EmailMetadataRow label="From" value={email.from_email} />
            <EmailMetadataRow label="To" value={email.to_email} />
            <EmailMetadataRow label="Direction" value={titleCaseLabel(email.direction)} />
            <EmailMetadataRow label="Status" value={titleCaseLabel(email.status)} />
          </dl>

          <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50 p-4">
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Message</p>
            {fullBody.trim() ? (
              <div className="max-h-[460px] overflow-auto whitespace-pre-wrap break-words text-sm leading-7 text-slate-800">
                {fullBody}
              </div>
            ) : (
              <p className="text-sm font-semibold text-slate-500">No email body available.</p>
            )}
          </div>
        </div>

        <div className="flex justify-end border-t border-slate-200 px-5 py-3">
          <Button onClick={onClose} variant="secondary">Close</Button>
        </div>
      </section>
    </div>
  );
}

function EmailMetadataRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="min-w-0 rounded-lg bg-slate-50 px-3 py-2">
      <dt className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-sm font-semibold text-slate-800">
        {value || "-"}
      </dd>
    </div>
  );
}

function EmailDirectionBadge({ direction }: { direction: string }) {
  const normalized = direction.toUpperCase();
  const tone = normalized === "INBOUND"
    ? "border-sky-200 bg-sky-50 text-sky-700"
    : "border-orange-200 bg-orange-50 text-orange-600";

  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-bold ${tone}`}>
      {titleCaseLabel(direction)}
    </span>
  );
}

function EmailStatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const tone = normalized === "sent" || normalized === "received"
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : normalized === "failed"
      ? "border-red-200 bg-red-50 text-red-700"
      : "border-slate-200 bg-white text-slate-600";

  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-bold ${tone}`}>
      {titleCaseLabel(status)}
    </span>
  );
}

function useCustomerEmailHistory(customerId: string) {
  const [emails, setEmails] = useState<CustomerEmailMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();

  function loadEmailHistory() {
    setLoading(true);
    setError(undefined);
    void getCustomerEmailHistory(customerId)
      .then((items) => setEmails(items))
      .catch((loadError) => {
        setEmails([]);
        setError(errorMessage(loadError, "Could not load email history."));
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadEmailHistory();
  }, [customerId]);

  return {
    emails,
    error,
    loading,
    refresh: loadEmailHistory,
  };
}

interface CustomerProfileFiltersState {
  query: string;
  status: CustomerProfileStatus | "";
}

function CustomerProfileFilters({
  embedded = false,
  filters,
  onChange,
  onClear
}: {
  embedded?: boolean;
  filters: CustomerProfileFiltersState;
  onChange: (filters: CustomerProfileFiltersState) => void;
  onClear: () => void;
}) {
  const hasActiveFilters = Object.values(filters).some(Boolean);

  function update(patch: Partial<CustomerProfileFiltersState>) {
    onChange({ ...filters, ...patch });
  }

  return (
    <QueueFilterShell embedded={embedded}>
      <div className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_minmax(180px,0.4fr)_auto] md:items-end">
        <label className="block">
          <span className="label">Search</span>
          <input
            className="input"
            onChange={(event) => update({ query: event.target.value })}
            placeholder="Name, email, or customer ID"
            value={filters.query}
          />
        </label>
        <label className="block">
          <span className="label">Status</span>
          <select
            className="input"
            onChange={(event) => update({ status: event.target.value as CustomerProfileStatus | "" })}
            value={filters.status}
          >
            <option value="">All statuses</option>
            {customerProfileStatusOptions.map((status) => (
              <option key={status} value={status}>{titleCaseLabel(status)}</option>
            ))}
          </select>
        </label>
        <Button
          className="w-full md:w-auto"
          disabled={!hasActiveFilters}
          onClick={onClear}
          variant={hasActiveFilters ? "primary" : "secondary"}
        >
          Clear
        </Button>
      </div>
    </QueueFilterShell>
  );
}

const customerProfileStatusOptions: CustomerProfileStatus[] = [
  "complete",
  "incomplete",
  "pending_customer_link"
];

function filterCustomerProfiles(
  customers: CustomerAdminSummary[],
  filters: CustomerProfileFiltersState
) {
  const query = normalizeFilterText(filters.query);
  return customers.filter((customer) => {
    if (filters.status && customer.status !== filters.status) return false;
    if (!query) return true;
    const searchable = [
      customer.customer_id,
      customer.full_name,
      customer.email,
      customer.type,
      customer.status,
      customer.customer_profile_completion_source
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return searchable.includes(query);
  });
}

function CustomerProfileStatusBadge({ status }: { status: CustomerProfileStatus }) {
  const classes: Record<CustomerProfileStatus, string> = {
    complete: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    incomplete: "bg-amber-50 text-amber-700 ring-amber-200",
    pending_customer_link: "bg-slate-100 text-slate-700 ring-slate-200"
  };
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-bold ring-1 ring-inset ${classes[status]}`}>
      {titleCaseLabel(status)}
    </span>
  );
}

function missingFieldsSummary(fields: string[]) {
  if (!fields.length) return "None";
  const shown = fields.slice(0, 2).map(formatProfileField).join(", ");
  const remaining = fields.length - 2;
  return remaining > 0 ? `${shown} +${remaining} more` : shown;
}

function formatProfileField(field: string) {
  return titleCaseLabel(field.replace(/^address\./, "address "));
}

function formatCustomerAddress(profile: CustomerProfileDetail) {
  const address = profile.address;
  if (!address) return "-";
  return (
    address.full_text ||
    [
      `${address.street ?? ""} ${address.number ?? ""}`.trim(),
      address.city,
      address.county,
      address.country,
      address.postal_code
    ].filter(Boolean).join(", ") ||
    "-"
  );
}

function authUserLinkStatus(result: AuthUserSearchResult) {
  if (result.client_id) {
    return result.customer_full_name
      ? `Linked to ${result.customer_full_name}`
      : `Linked to customer ${result.client_id}`;
  }
  return result.status ? titleCaseLabel(result.status) : "Unlinked";
}

export function EmployeeClaimsPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [filters, setFilters] = useState<ClaimQueueFiltersState>({
    query: "",
    dateFrom: "",
    dateTo: "",
    status: "",
    claimType: ""
  });
  useEffect(() => {
    void getAllClaims().then(setClaims);
  }, []);
  const filteredClaims = useMemo(
    () => filterClaims(claims, filters),
    [claims, filters]
  );
  const hasActiveFilters = Object.values(filters).some(Boolean);
  return (
    <section className="flex h-[calc(100dvh-5.5rem)] min-h-0 flex-col overflow-hidden">
      <EmployeePageHeader className="shrink-0" title="Claims" />
      <Panel className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <ClaimQueueFilters
          embedded
          claimTypes={claimTypeOptions}
          filters={filters}
          onChange={setFilters}
          onClear={() => setFilters(emptyClaimQueueFilters())}
          statuses={claimStatusOptions}
        />
        <DataTable
          className="mt-4 flex min-h-0 flex-1 flex-col"
          columns={[
            { header: "Claim ID", width: "30%", cellClassName: "font-mono text-xs text-slate-600", render: (claim) => getClaimDisplayIdentifier(claim) },
            { header: "Client name", width: "18%", render: (claim) => claim.clientName },
            { header: "Date", width: "12%", render: (claim) => formatDate(claim.incidentDate) },
            { header: "Claim type", width: "14%", render: (claim) => claim.claimType },
            { header: "Estimated damage", width: "14%", render: (claim) => formatCurrency(claim.estimatedDamage) },
            { header: "Status", width: "12%", render: (claim) => <StatusBadge status={claim.status} /> }
          ]}
          data={filteredClaims}
          emptyText={hasActiveFilters ? "No claims match these filters." : "No claims available."}
          getRowHref={(claim) => `/employee/claims/${claim.id}`}
          scrollerClassName="min-h-0 flex-1"
          variant="embedded"
        />
      </Panel>
    </section>
  );
}

interface ClaimQueueFiltersState {
  query: string;
  dateFrom: string;
  dateTo: string;
  status: ClaimStatus | "";
  claimType: ClaimType | "";
}

const claimStatusOptions: ClaimStatus[] = [
  "submitted",
  "in_review",
  "accepted",
  "rejected",
  "inspection_requested",
  "paid"
];

const claimTypeOptions: ClaimType[] = [
  "Fire",
  "Water damage",
  "Theft",
  "Storm",
  "Other"
];

function ClaimQueueFilters({
  embedded = false,
  claimTypes,
  filters,
  onChange,
  onClear,
  statuses
}: {
  embedded?: boolean;
  claimTypes: ClaimType[];
  filters: ClaimQueueFiltersState;
  onChange: (filters: ClaimQueueFiltersState) => void;
  onClear: () => void;
  statuses: ClaimStatus[];
}) {
  const hasActiveFilters = Object.values(filters).some(Boolean);

  function update(patch: Partial<ClaimQueueFiltersState>) {
    onChange({ ...filters, ...patch });
  }

  return (
    <QueueFilterShell embedded={embedded}>
      <div className="grid gap-3 lg:grid-cols-[minmax(220px,1.4fr)_repeat(4,minmax(150px,1fr))_auto] lg:items-end">
        <label className="block">
          <span className="label">Search</span>
          <input
            className="input"
            onChange={(event) => update({ query: event.target.value })}
            placeholder="Client name or claim ID"
            value={filters.query}
          />
        </label>
        <label className="block">
          <span className="label">From</span>
          <input
            className="input"
            onChange={(event) => update({ dateFrom: event.target.value })}
            type="date"
            value={filters.dateFrom}
          />
        </label>
        <label className="block">
          <span className="label">To</span>
          <input
            className="input"
            onChange={(event) => update({ dateTo: event.target.value })}
            type="date"
            value={filters.dateTo}
          />
        </label>
        <label className="block">
          <span className="label">Status</span>
          <select
            className="input"
            onChange={(event) => update({ status: event.target.value as ClaimStatus | "" })}
            value={filters.status}
          >
            <option value="">All statuses</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {titleCaseLabel(status)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="label">Claim type</span>
          <select
            className="input"
            onChange={(event) => update({ claimType: event.target.value as ClaimType | "" })}
            value={filters.claimType}
          >
            <option value="">All types</option>
            {claimTypes.map((claimType) => (
              <option key={claimType} value={claimType}>
                {claimType}
              </option>
            ))}
          </select>
        </label>
        <Button
          className="w-full lg:w-auto"
          disabled={!hasActiveFilters}
          onClick={onClear}
          variant={hasActiveFilters ? "primary" : "secondary"}
        >
          Clear
        </Button>
      </div>
    </QueueFilterShell>
  );
}

function emptyClaimQueueFilters(): ClaimQueueFiltersState {
  return {
    query: "",
    dateFrom: "",
    dateTo: "",
    status: "",
    claimType: ""
  };
}

function filterClaims(claims: Claim[], filters: ClaimQueueFiltersState) {
  const query = normalizeFilterText(filters.query);
  return claims.filter((claim) => {
    if (query) {
      const searchable = `${claim.clientName} ${getClaimDisplayIdentifier(claim)} ${claim.id}`.toLowerCase();
      if (!searchable.includes(query)) return false;
    }

    if (filters.dateFrom || filters.dateTo) {
      const claimDate = toDateKey(parseLocalDate(claim.incidentDate || claim.createdAt));
      if (!claimDate) return false;
      if (filters.dateFrom && claimDate < filters.dateFrom) return false;
      if (filters.dateTo && claimDate > filters.dateTo) return false;
    }

    if (filters.status && claim.status !== filters.status) return false;
    if (filters.claimType && claim.claimType !== filters.claimType) return false;

    return true;
  });
}

function normalizeFilterText(value: string) {
  return value.trim().toLowerCase();
}

export function EmployeeClaimDetailPage() {
  const { claimId, reviewStep } = useParams();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [claim, setClaim] = useState<Claim>();
  const [claimLoading, setClaimLoading] = useState(true);
  const [claimError, setClaimError] = useState<string>();
  const [clientLegalDocuments, setClientLegalDocuments] = useState<CustomerLegalDocument[]>([]);
  const [clientLegalDocumentsError, setClientLegalDocumentsError] = useState<string>();
  const [clientLegalDocumentsLoading, setClientLegalDocumentsLoading] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState<ClaimEvidenceScaffoldItem | null>(null);
  const [selectedClientDocument, setSelectedClientDocument] = useState<CustomerLegalDocument | null>(null);
  const [selectedEvidenceRequestDraft, setSelectedEvidenceRequestDraft] = useState<EvidenceRequestDraft | null>(null);
  const [selectedAiSuggestion, setSelectedAiSuggestion] = useState<AiFollowUpSuggestion | null>(null);
  const [editingAiSuggestion, setEditingAiSuggestion] = useState<AiFollowUpSuggestion | null>(null);
  const [editingEvidenceRequestEmail, setEditingEvidenceRequestEmail] = useState(false);
  const [communicationPendingAction, setCommunicationPendingAction] = useState<string>();
  const [communicationAnalysisRunning, setCommunicationAnalysisRunning] = useState(false);
  const [communicationNotice, setCommunicationNotice] = useState<{ tone: "danger" | "success" | "warning"; message: string }>();
  const [evidenceAnalysisRefreshing, setEvidenceAnalysisRefreshing] = useState(false);
  const [decisionJustification, setDecisionJustification] = useState("");
  const [decisionSuggestion, setDecisionSuggestion] = useState("");
  const [decisionSuggestionVisible, setDecisionSuggestionVisible] = useState(false);
  const [decisionPendingAction, setDecisionPendingAction] = useState<ClaimDecisionActionKind>();
  const [decisionNotice, setDecisionNotice] = useState<{ tone: "danger" | "success"; message: string }>();
  const [decisionEmailSending, setDecisionEmailSending] = useState(false);
  const [decisionEmailNotice, setDecisionEmailNotice] = useState<{ tone: "danger" | "success"; message: string }>();
  const autoCommunicationAnalysisClaimIds = useRef<Set<string>>(new Set());
  const activeReviewStep = parseClaimReviewStep(reviewStep) ?? "details";
  const invalidReviewStep = Boolean(reviewStep && !parseClaimReviewStep(reviewStep));

  useEffect(() => {
    let cancelled = false;
    async function loadLatestReview() {
      if (!claimId) {
        setClaim(undefined);
        setClaimLoading(false);
        return;
      }
      setClaimLoading(true);
      setClaimError(undefined);
      try {
        let loadedClaim = await getLatestClaimReview(claimId);
        if (loadedClaim.status === "submitted") {
          await startClaimReview(claimId);
          loadedClaim = await getLatestClaimReview(claimId);
        }
        if (cancelled) return;
        setClaim(loadedClaim);
      } catch (error) {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "Could not load latest claim review.";
        setClaim(undefined);
        setClaimError(message);
      } finally {
        if (!cancelled) setClaimLoading(false);
      }
    }
    void loadLatestReview();
    return () => {
      cancelled = true;
    };
  }, [claimId]);

  useEffect(() => {
    setSelectedAiSuggestion(null);
    setEditingAiSuggestion(null);
  }, [claimId]);

  useEffect(() => {
    if (!claim || activeReviewStep !== "communicate" || !claimNeedsCommunicationAnalysis(claim)) return;
    if (autoCommunicationAnalysisClaimIds.current.has(claim.id)) return;
    autoCommunicationAnalysisClaimIds.current.add(claim.id);

    let cancelled = false;
    setCommunicationAnalysisRunning(true);
    setCommunicationNotice({
      tone: "warning",
      message: "Running claim analysis so missing evidence can be identified."
    });

    void startClaimAnalysis(claim.id)
      .then(() => getLatestClaimReview(claim.id))
      .then((refreshedClaim) => {
        if (cancelled) return;
        setClaim(refreshedClaim);
        setCommunicationNotice(undefined);
      })
      .catch((error) => {
        if (cancelled) return;
        const message = errorMessage(error, "Could not run claim analysis.");
        setCommunicationNotice({ tone: "danger", message });
        showToast(message, "error");
      })
      .finally(() => {
        if (!cancelled) setCommunicationAnalysisRunning(false);
      });

    return () => {
      cancelled = true;
    };
  }, [
    activeReviewStep,
    claim?.availableActions?.join("|"),
    claim?.id,
    claim?.reviewState,
    showToast
  ]);

  useEffect(() => {
    if (!claim?.clientId) {
      setClientLegalDocuments([]);
      setClientLegalDocumentsError(undefined);
      setClientLegalDocumentsLoading(false);
      return;
    }

    let cancelled = false;
    setClientLegalDocumentsLoading(true);
    setClientLegalDocumentsError(undefined);
    void getCustomerProfile(claim.clientId)
      .then((profile) => {
        if (cancelled) return;
        setClientLegalDocuments(buildClientLegalDocuments(profile));
      })
      .catch((error) => {
        if (cancelled) return;
        setClientLegalDocuments([]);
        setClientLegalDocumentsError(errorMessage(error, "Could not load client legal documents."));
      })
      .finally(() => {
        if (!cancelled) setClientLegalDocumentsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [claim?.clientId]);

  if (claimLoading) {
    return <EmptyState description="Loading claim workspace." title="Loading claim" />;
  }
  if (claimError) {
    return <EmptyState description={claimError} title="Could not load claim" />;
  }
  if (!claim) return <EmptyState title="Claim not found" />;
  const evidenceItems = buildClaimEvidenceScaffoldItems(claim);
  const uploadedEvidenceCount = evidenceItems.filter((item) => item.hasFile).length;
  const communicationWorkspace = buildClaimCommunicationWorkspace(claim, evidenceItems);

  async function handleCommunicationAction(action: ClaimCommunicationActionRequest) {
    if (communicationAnalysisRunning && action.kind === "generate_draft") {
      setCommunicationNotice({
        tone: "warning",
        message: "Claim analysis is still running. Document requests will be available when it finishes."
      });
      return;
    }

    if (action.kind === "write_email") {
      setSelectedAiSuggestion(null);
      setEditingAiSuggestion(null);
      setSelectedEvidenceRequestDraft(null);
      setEditingEvidenceRequestEmail(true);
      return;
    }

    const aiSuggestion = action.suggestionId
      ? communicationWorkspace.aiFollowUpSuggestions.find((suggestion) => suggestion.id === action.suggestionId)
      : undefined;

    if (action.kind === "review_ai_suggestion") {
      if (aiSuggestion) setSelectedAiSuggestion(aiSuggestion);
      return;
    }

    if (action.kind === "create_request_from_ai" || action.kind === "edit_ai_draft") {
      if (aiSuggestion) {
        setSelectedAiSuggestion(null);
        setEditingAiSuggestion(aiSuggestion);
      }
      return;
    }

    if (action.kind === "dismiss_ai_suggestion") {
      if (action.suggestionId) {
        setCommunicationPendingAction(action.id);
        setCommunicationNotice(undefined);
        try {
          await dismissClaimAiSuggestion(claim.id, action.suggestionId);
          setClaim(await getLatestClaimReview(claim.id));
          setSelectedAiSuggestion(null);
          setEditingAiSuggestion(null);
          setCommunicationNotice({
            tone: "success",
            message: "AI follow-up suggestion dismissed."
          });
        } catch (error) {
          const message = errorMessage(error, "Could not dismiss the AI follow-up suggestion.");
          setCommunicationNotice({ tone: "danger", message });
          showToast(message, "error");
        } finally {
          setCommunicationPendingAction(undefined);
        }
      }
      return;
    }

    if (action.kind === "view_draft") {
      if (claim.evidenceRequestDraft) setSelectedEvidenceRequestDraft(claim.evidenceRequestDraft);
      return;
    }

    if (action.kind === "send_draft") {
      if (!claim.evidenceRequestDraft) return;
      setCommunicationPendingAction(action.id);
      setCommunicationNotice(undefined);
      try {
        const draft = await sendEvidenceRequestDraft(claim.id);
        setSelectedEvidenceRequestDraft(draft);
        setClaim(await getLatestClaimReview(claim.id));
        setCommunicationNotice({
          tone: "success",
          message: "Evidence request email sent."
        });
        showToast("Evidence request email sent.");
      } catch (error) {
        const message = errorMessage(error, "Could not send the evidence request draft.");
        try {
          const refreshedClaim = await getLatestClaimReview(claim.id);
          setClaim(refreshedClaim);
          if (refreshedClaim.evidenceRequestDraft) setSelectedEvidenceRequestDraft(refreshedClaim.evidenceRequestDraft);
        } catch {}
        setCommunicationNotice({ tone: "danger", message });
        showToast(message, "error");
      } finally {
        setCommunicationPendingAction(undefined);
      }
      return;
    }

    if (action.kind === "trigger_demo_inbound_email") {
      setCommunicationPendingAction(action.id);
      setCommunicationNotice(undefined);
      try {
        const response = await sendDemoInboundClaimEmail(claim.id);
        setCommunicationNotice({
          tone: "success",
          message: `${response.message} Waiting for the inbound webhook.`
        });
        showToast("Demo inbound email sent through Postmark.");
        const refreshClaim = async () => {
          try {
            setClaim(await getLatestClaimReview(claim.id));
          } catch {}
        };
        await refreshClaim();
        window.setTimeout(() => {
          void refreshClaim();
        }, 5000);
      } catch (error) {
        const message = errorMessage(error, "Could not send the demo inbound email.");
        setCommunicationNotice({ tone: "danger", message });
        showToast(message, "error");
      } finally {
        setCommunicationPendingAction(undefined);
      }
      return;
    }

    if (action.kind === "view_document" && action.evidenceItemId) {
      const evidenceItem = evidenceItems.find((item) => item.id === action.evidenceItemId);
      if (evidenceItem) setSelectedEvidence(evidenceItem);
      return;
    }

    if (action.kind !== "generate_draft") return;

    setCommunicationPendingAction(action.id);
    setCommunicationNotice(undefined);
    try {
      const response = await generateEvidenceRequestDraft(claim.id);
      const refreshedClaim = await getLatestClaimReview(claim.id);
      setClaim(refreshedClaim);
      if (response.draft) {
        setSelectedEvidenceRequestDraft(response.draft);
        setCommunicationNotice({ tone: "success", message: response.message });
        showToast(response.message);
      } else {
        const tone = response.message.toLowerCase().startsWith("no evidence request") ? "success" : "warning";
        setCommunicationNotice({ tone, message: response.message });
        showToast(response.message, tone === "warning" ? "info" : "success");
      }
    } catch (error) {
      const message = errorMessage(error, "Could not generate the evidence request draft.");
      setCommunicationNotice({ tone: "danger", message });
      showToast(message, "error");
    } finally {
      setCommunicationPendingAction(undefined);
    }
  }

  async function handleRefreshEvidenceAnalysis() {
    setEvidenceAnalysisRefreshing(true);
    try {
      const refreshedClaim = await refreshClaimAttachmentAnalysis(claim.id);
      setClaim(refreshedClaim);
      showToast("AI analysis refreshed.");
    } catch (error) {
      const message = errorMessage(error, "Could not refresh the AI analysis.");
      showToast(message, "error");
    } finally {
      setEvidenceAnalysisRefreshing(false);
    }
  }

  async function handleSaveAiSuggestionDraft(
    suggestion: AiFollowUpSuggestion,
    draft: SuggestedEmailDraft
  ) {
    const pendingId = `save-ai-draft-${suggestion.id}`;
    setCommunicationPendingAction(pendingId);
    setCommunicationNotice(undefined);
    try {
      const savedDraft = await updateEvidenceRequestDraft(claim.id, {
        body: draft.body,
        dueDate: draft.dueDate,
        recipients: claim.contactEmail ? [claim.contactEmail] : [],
        requestedDocumentType: draft.requestedDocumentType,
        requiredDocuments: draft.requestedDocumentType ? [draft.requestedDocumentType] : [],
        sourceSuggestionId: suggestion.id,
        subject: draft.subject
      });
      setSelectedEvidenceRequestDraft(savedDraft);
      setSelectedAiSuggestion(null);
      setEditingAiSuggestion(null);
      setCommunicationNotice({
        tone: "success",
        message: "Email request draft saved. It has not been sent."
      });
      showToast("Email request draft saved.");
      try {
        const refreshedClaim = await getLatestClaimReview(claim.id);
        setClaim(refreshedClaim);
        if (refreshedClaim.evidenceRequestDraft) {
          setSelectedEvidenceRequestDraft(refreshedClaim.evidenceRequestDraft);
        }
      } catch {}
    } catch (error) {
      const message = errorMessage(error, "Could not save the email request draft.");
      setCommunicationNotice({ tone: "danger", message });
      showToast(message, "error");
      throw new Error(message);
    } finally {
      setCommunicationPendingAction(undefined);
    }
  }

  async function handleSaveEvidenceRequestEmailDraft(draft: SuggestedEmailDraft) {
    const pendingId = "save-evidence-request-email";
    setCommunicationPendingAction(pendingId);
    setCommunicationNotice(undefined);
    try {
      const savedDraft = await updateEvidenceRequestDraft(claim.id, {
        body: draft.body,
        dueDate: draft.dueDate,
        recipients: claim.contactEmail ? [claim.contactEmail] : [],
        requestedDocumentType: draft.requestedDocumentType,
        requiredDocuments: draft.requestedDocumentType ? [draft.requestedDocumentType] : evidenceRequestDocumentNames(claim),
        subject: draft.subject
      });
      setSelectedEvidenceRequestDraft(savedDraft);
      setEditingEvidenceRequestEmail(false);
      setClaim(await getLatestClaimReview(claim.id));
      setCommunicationNotice({
        tone: "success",
        message: "Email draft saved. It has not been sent."
      });
      showToast("Email draft saved.");
    } catch (error) {
      const message = errorMessage(error, "Could not save the email draft.");
      setCommunicationNotice({ tone: "danger", message });
      showToast(message, "error");
    } finally {
      setCommunicationPendingAction(undefined);
    }
  }

  async function handleClaimDecisionAction(action: ClaimDecisionActionKind, justification: string) {
    const trimmedJustification = justification.trim();
    if (!trimmedJustification) {
      setDecisionNotice({ tone: "danger", message: "Decision justification is required." });
      return;
    }

    setDecisionPendingAction(action);
    setDecisionNotice(undefined);
    try {
      const updatedClaim =
        action === "approve"
          ? await approveClaim(claim.id, trimmedJustification)
          : action === "deny"
            ? await rejectClaim(claim.id, trimmedJustification)
            : await requestOnPremisesInspection(claim.id, trimmedJustification);
      try {
        setClaim(await getLatestClaimReview(claim.id));
      } catch {
        setClaim(updatedClaim);
      }
    } catch (error) {
      const message = errorMessage(error, "Could not submit the claim decision.");
      setDecisionNotice({ tone: "danger", message });
      showToast(message, "error");
    } finally {
      setDecisionPendingAction(undefined);
    }
  }

  async function handleSendClaimDecisionEmail() {
    const blocker = claimDecisionEmailDisabledReason(claim);
    if (blocker) {
      setDecisionEmailNotice({ tone: "danger", message: blocker });
      return;
    }
    setDecisionEmailSending(true);
    setDecisionEmailNotice(undefined);
    try {
      const email = await sendClaimDecisionEmail(claim.id);
      const success = email.status.toLowerCase() === "sent";
      const message = success
        ? `Claim decision email sent to ${email.to_email}.`
        : `Claim decision email ${titleCaseLabel(email.status)}: ${email.error_message ?? "Delivery failed."}`;
      setDecisionEmailNotice({ tone: success ? "success" : "danger", message });
      showToast(message, success ? "success" : "error");
      try {
        setClaim(await getLatestClaimReview(claim.id));
      } catch {}
    } catch (error) {
      const message = errorMessage(error, "Could not send the claim decision email.");
      setDecisionEmailNotice({ tone: "danger", message });
      showToast(message, "error");
    } finally {
      setDecisionEmailSending(false);
    }
  }

  if (invalidReviewStep && claimId) {
    return <Navigate replace to={`/employee/claims/${claimId}/details`} />;
  }

  return (
    <>
      <div className="flex min-h-[calc(100dvh-8rem)] w-full flex-1 flex-col">
        <section className="flex min-h-0 w-full flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <header className="border-b border-slate-200 px-5 py-5 sm:px-6 sm:py-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="min-w-0">
                <h1 className="text-xl font-bold tracking-normal text-slate-950">{claimReviewTitle(claim)}</h1>
                <div className="mt-3 flex flex-wrap gap-2">
                  <ClaimMetadataPill label="Policy" value={claim.policyNumber} />
                  <ClaimMetadataPill label="Claim ID" value={getClaimDisplayIdentifier(claim)} />
                  <ClaimMetadataPill label="Claim date" value={formatDate(claim.incidentDate)} />
                  <ClaimMetadataPill label="Incident" value={claim.claimType} />
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                <Button className="min-h-9 px-3.5 py-2 text-sm" onClick={() => navigate("/employee/claims")} variant="primary">
                  Back to claims
                </Button>
              </div>
            </div>
          </header>
          <ClaimWorkspaceTabs activeStep={activeReviewStep} claimId={claim.id} />
          <div
            aria-labelledby={claimReviewTabId(activeReviewStep)}
            className="min-h-0 flex-1 overflow-y-auto px-5 py-4 sm:px-6 sm:py-5"
            id={claimReviewPanelId(activeReviewStep)}
            role="tabpanel"
          >
            {activeReviewStep === "details" ? (
              <ClaimDetailsTab
                clientLegalDocuments={clientLegalDocuments}
                claim={claim}
                legalDocumentsError={clientLegalDocumentsError}
                legalDocumentsLoading={clientLegalDocumentsLoading}
                onSelectClientDocument={setSelectedClientDocument}
              />
            ) : null}
            {activeReviewStep === "evidence" ? (
              <ClaimEvidenceTab
                aiFindings={claim.aiReviewFindings ?? []}
                analysisRefreshing={evidenceAnalysisRefreshing}
                claim={claim}
                evidenceItems={evidenceItems}
                onAction={handleCommunicationAction}
                onRefreshAnalysis={handleRefreshEvidenceAnalysis}
                onSelectEvidence={setSelectedEvidence}
                pendingActionId={communicationPendingAction}
              />
            ) : null}
            {activeReviewStep === "communicate" ? (
              <ClaimCommunicateTab
                createRequestDisabledReason={
                  communicationAnalysisRunning ? "Claim analysis is still running." : undefined
                }
                demoInboundDisabledReason={
                  evidenceRequestDraftIsSent(claim.evidenceRequestDraft)
                    ? undefined
                    : "Send an evidence request before triggering a demo reply."
                }
                notice={communicationNotice}
                onAction={handleCommunicationAction}
                pendingActionId={communicationPendingAction}
                workspace={communicationWorkspace}
              />
            ) : null}
            {activeReviewStep === "decision" ? (
              <ClaimDecisionTab
                claim={claim}
                emailNotice={decisionEmailNotice}
                emailSending={decisionEmailSending}
                evidenceItems={evidenceItems}
                justification={decisionJustification}
                notice={decisionNotice}
                onChangeJustification={setDecisionJustification}
                onChangeSuggestion={(value) => {
                  setDecisionSuggestion(value);
                  if (value.trim()) setDecisionSuggestionVisible(true);
                }}
                onDismissSuggestion={() => setDecisionSuggestionVisible(false)}
                onSendDecisionEmail={handleSendClaimDecisionEmail}
                onSubmitDecision={handleClaimDecisionAction}
                pendingAction={decisionPendingAction}
                suggestion={decisionSuggestion}
                suggestionVisible={decisionSuggestionVisible}
              />
            ) : null}
          </div>
        </section>
      </div>
      <ClaimEvidencePreviewModal item={selectedEvidence} onClose={() => setSelectedEvidence(null)} />
      <ClientDocumentPreviewModal item={selectedClientDocument} onClose={() => setSelectedClientDocument(null)} />
      <AiFollowUpSuggestionModal
        onAction={handleCommunicationAction}
        onClose={() => setSelectedAiSuggestion(null)}
        pendingActionId={communicationPendingAction}
        suggestion={selectedAiSuggestion}
      />
      <AiSuggestionDraftEditorModal
        onClose={() => setEditingAiSuggestion(null)}
        onSaveDraft={handleSaveAiSuggestionDraft}
        pending={Boolean(
          editingAiSuggestion &&
            communicationPendingAction === `save-ai-draft-${editingAiSuggestion.id}`
        )}
        suggestion={editingAiSuggestion}
      />
      <EvidenceRequestEmailEditorModal
        draft={evidenceRequestEmailDraftFromClaim(claim, communicationWorkspace)}
        onClose={() => setEditingEvidenceRequestEmail(false)}
        onSaveDraft={handleSaveEvidenceRequestEmailDraft}
        open={editingEvidenceRequestEmail}
        pending={communicationPendingAction === "save-evidence-request-email"}
      />
      <EvidenceRequestDraftModal
        draft={selectedEvidenceRequestDraft}
        onClose={() => setSelectedEvidenceRequestDraft(null)}
        onSend={() =>
          handleCommunicationAction({ id: "evidence-draft-send", kind: "send_draft" })
        }
        pendingSend={communicationPendingAction === "evidence-draft-send"}
      />
    </>
  );
}

function ClaimWorkspaceTabs({
  activeStep,
  claimId
}: {
  activeStep: ClaimReviewStep;
  claimId: string;
}) {
  const navigate = useNavigate();

  function focusTab(stepId: ClaimReviewStep) {
    window.setTimeout(() => document.getElementById(claimReviewTabId(stepId))?.focus(), 0);
  }

  function navigateToTab(stepId: ClaimReviewStep) {
    navigate(`/employee/claims/${claimId}/${stepId}`);
    focusTab(stepId);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLAnchorElement>, index: number) {
    const lastIndex = claimReviewSteps.length - 1;
    let nextIndex: number | undefined;

    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      nextIndex = index === lastIndex ? 0 : index + 1;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      nextIndex = index === 0 ? lastIndex : index - 1;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = lastIndex;
    }

    if (nextIndex === undefined) return;
    event.preventDefault();
    navigateToTab(claimReviewSteps[nextIndex].id);
  }

  return (
    <div className="flex h-12 shrink-0 items-end overflow-y-hidden border-b border-slate-200 bg-slate-50/80 px-5 pt-2 sm:px-6">
      <div className="min-w-0 max-w-full overflow-x-auto overflow-y-hidden pb-px scrollbar-none">
        <div
          aria-label="Claim review tabs"
          className="inline-flex min-w-max items-end gap-1"
          role="tablist"
        >
          {claimReviewSteps.map((step, index) => {
            const selected = activeStep === step.id;
            const tabClass = `relative -mb-px inline-flex h-10 items-center justify-center rounded-t-lg border px-4 text-sm transition focus-visible:z-20 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-orange-100 ${
              selected
                ? "border-slate-200 border-b-white bg-white font-bold text-orange-700 shadow-sm after:absolute after:inset-x-4 after:top-0 after:h-0.5 after:rounded-full after:bg-orange-600"
                : "border-transparent bg-slate-100/70 font-semibold text-slate-600 hover:bg-slate-200/70 hover:text-slate-950"
            }`;

            return (
              <Link
                aria-controls={claimReviewPanelId(step.id)}
                aria-current={selected ? "page" : undefined}
                aria-selected={selected ? "true" : undefined}
                className={tabClass}
                id={claimReviewTabId(step.id)}
                key={step.id}
                onKeyDown={(event) => handleKeyDown(event, index)}
                role="tab"
                tabIndex={selected ? 0 : -1}
                to={`/employee/claims/${claimId}/${step.id}`}
              >
                {step.label}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function claimReviewTabId(step: ClaimReviewStep) {
  return `claim-review-tab-${step}`;
}

function claimReviewPanelId(step: ClaimReviewStep) {
  return `claim-review-panel-${step}`;
}

interface ClaimEvidenceScaffoldItem {
  id: string;
  name: string;
  type: string;
  contentType?: string;
  uploadStatus: string;
  confidence: string;
  fileName: string;
  fileUrl?: string;
  previewUrl?: string;
  source: string;
  uploadedDate: string;
  reviewStatus: string;
  primaryAction: string;
  hasFile: boolean;
  issue?: string;
}

type ClaimCommunicationActionKind =
  | "generate_draft"
  | "write_email"
  | "view_draft"
  | "view_document"
  | "review_ai_suggestion"
  | "create_request_from_ai"
  | "edit_ai_draft"
  | "dismiss_ai_suggestion"
  | "send_draft"
  | "trigger_demo_inbound_email"
  | "unsupported";
type ClaimDecisionActionKind = "approve" | "deny" | "inspection";

interface ClaimCommunicationActionRequest {
  id: string;
  kind: ClaimCommunicationActionKind;
  evidenceItemId?: string;
  suggestionId?: string;
}

interface ClaimDecisionConfirmation {
  action: ClaimDecisionActionKind;
  title: string;
  description: string;
}

interface ClaimCommunicationWorkspace {
  aiReviewStatus: AiReviewLifecycleStatus;
  aiReviewFindings: AiReviewFinding[];
  aiFollowUpSuggestions: AiFollowUpSuggestion[];
  automation: ClaimEmailAutomationPanel;
  requests: ClaimCommunicationRequestRow[];
  inboundEmails: ClaimInboundEmailItem[];
  timeline: ClaimCommunicationTimelineEvent[];
}

interface ClaimEmailAutomationPanel {
  status: string;
  statusTone: BadgeTone;
  recipient: string;
  lastEmailSent: string;
  subject: string;
  deliveryStatus: string;
  actionLabel: string;
  actionKind: ClaimCommunicationActionKind;
  disabledReason?: string;
}

interface ClaimCommunicationRequestRow {
  id: string;
  document: string;
  status: string;
  statusTone: BadgeTone;
  actionLabel: string;
  actionKind: ClaimCommunicationActionKind;
  evidenceItemId?: string;
  disabledReason?: string;
}

interface ClaimInboundEmailItem {
  id: string;
  sender: string;
  receivedAt: string;
  subject: string;
  processingStatus: string;
  processingTone: BadgeTone;
  attachments: ClaimInboundAttachmentItem[];
}

interface ClaimInboundAttachmentItem {
  id: string;
  fileName: string;
  classification: string;
  linkedRequirement: string;
  status: string;
  statusTone: BadgeTone;
  actionRequired: boolean;
  evidenceItemId?: string;
}

interface ClaimCommunicationTimelineEvent {
  id: string;
  timestamp: string;
  eventType: string;
  description: string;
  status: string;
  tone: BadgeTone;
}

function ClaimDetailsTab({
  clientLegalDocuments,
  claim,
  legalDocumentsError,
  legalDocumentsLoading,
  onSelectClientDocument
}: {
  clientLegalDocuments: CustomerLegalDocument[];
  claim: Claim;
  legalDocumentsError?: string;
  legalDocumentsLoading: boolean;
  onSelectClientDocument: (document: CustomerLegalDocument) => void;
}) {
  const visibleLegalDocuments = mergeClientLegalDocuments([
    ...clientLegalDocuments.filter(isVisibleClientLegalDocument),
    ...buildSubmittedClaimLegalDocuments(claim)
  ]);
  return (
    <div className="space-y-5">
      <div className="grid gap-x-6 gap-y-5 xl:grid-cols-2">
        <ClaimWorkspaceSection title="Claim details">
          <ClaimFieldGrid
            items={[
              ["Claim ID", getClaimDisplayIdentifier(claim)],
              ["Contract", <ClaimContractDetailsLink claim={claim} />],
              ["Incident", claim.claimType],
              ["Incident date", formatDate(claim.incidentDate)],
              ["Estimated damage", formatCurrency(claim.estimatedDamage)]
            ]}
          />
        </ClaimWorkspaceSection>
        <ClaimWorkspaceSection title="Client details">
          <ClaimFieldGrid
            items={[
              ["Full name", claim.clientName],
              ["Email", claim.contactEmail],
              ["Phone", claim.contactPhone],
              ["Policy number", claim.policyNumber]
            ]}
          />
        </ClaimWorkspaceSection>
      </div>
      <ClaimWorkspaceSection title="Legal and identity documents">
        <ClientLegalDocumentsTable
          error={legalDocumentsError}
          loading={legalDocumentsLoading}
          onSelectDocument={onSelectClientDocument}
          rows={visibleLegalDocuments}
        />
      </ClaimWorkspaceSection>
    </div>
  );
}

function ClaimContractDetailsLink({ claim }: { claim: Claim }) {
  const label = getClaimContractDisplayIdentifier(claim);
  if (!claim.contractId) return <>{label}</>;

  return (
    <Link
      className="font-bold text-orange-600 underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-orange-100"
      to={`/contracts/${encodeURIComponent(claim.contractId)}`}
    >
      {label}
    </Link>
  );
}

function isVisibleClientLegalDocument(document: CustomerLegalDocument) {
  const text = normalizeEvidenceText(
    `${document.label || ""} ${document.document_type || ""} ${document.file_name || ""}`
  );
  const source = normalizeEvidenceText(document.source || "");

  if (isClaimEvidencePhotoLikeClientDocument(document, text, source)) return false;

  const sourceLooksLegal = ["client profile", "legal document"].some((phrase) =>
    normalizedTextIncludesPhrase(source, phrase)
  );
  if (sourceLooksLegal) return true;

  return [
    "id document",
    "identity document",
    "identity card",
    "photo id",
    "passport",
    "national id",
    "company registration",
    "bank document",
    "bank statement",
    "existing policy",
    "land registry",
    "proof of ownership",
    "policy",
    "property deed",
    "property ownership",
    "insurance contract",
    "contract document",
    "terms consent",
    "consent document",
    "legal document",
    "signature",
    "title deed"
  ].some((phrase) => normalizedTextIncludesPhrase(text, phrase));
}

function buildSubmittedClaimLegalDocuments(claim: Claim): CustomerLegalDocument[] {
  return (claim.evidence ?? [])
    .map((document) => clientLegalDocumentFromClaimEvidence(claim.id, document))
    .filter((document): document is CustomerLegalDocument => Boolean(document));
}

function clientLegalDocumentFromClaimEvidence(
  claimId: string,
  document: ClaimEvidenceDocument
): CustomerLegalDocument | null {
  const text = claimEvidenceDocumentText(document);
  if (!isClientLegalProfileDocumentText(text)) return null;

  const extractedFields = recordFromUnknown(document.metadata?.extracted_fields);
  const aiInterpretation = stringFromMetadata(document.metadata?.extracted_text);
  const profileDocumentId = documentMetadataText(document, "profile_document_id");
  const label = clientLegalDocumentLabelFromClaimEvidence(document);

  return {
    id: `claim-submitted-${document.id || documentIdentityKey(document)}`,
    label,
    document_type: label,
    file_name: document.fileName,
    content_type: document.contentType ?? null,
    size_bytes: document.sizeBytes ?? null,
    file_url: profileDocumentId
      ? `/claims/${claimId}/profile-documents/${profileDocumentId}`
      : document.fileUrl || document.url || null,
    source: documentMetadataText(document, "source") || "client_upload",
    extracted_fields: extractedFields,
    ai_interpretation: aiInterpretation || null
  };
}

function mergeClientLegalDocuments(documents: CustomerLegalDocument[]) {
  const byIdentity = new Map<string, CustomerLegalDocument>();
  documents.forEach((document) => {
    const identity = normalizeEvidenceText(
      `${document.file_name || document.id} ${document.document_type || document.label}`
    );
    if (!byIdentity.has(identity)) byIdentity.set(identity, document);
  });
  return Array.from(byIdentity.values());
}

function clientLegalDocumentLabelFromClaimEvidence(document: ClaimEvidenceDocument) {
  const explicitLabel = documentMetadataText(document, "label");
  if (explicitLabel && explicitLabel !== document.fileName) return explicitLabel;

  const text = claimEvidenceDocumentText(document);
  const normalizedRole = normalizeEvidenceText(documentMetadataText(document, "document_role"));
  const labelByRole: Record<string, string> = {
    bank_document: "Bank document",
    existing_policy: "Existing policy document",
    identity_document: "ID document",
    land_registry: "Property ownership document",
    land_registry_extract: "Property ownership document",
    policy_document: "Existing policy document",
    property_ownership: "Property ownership document",
    property_ownership_document: "Property ownership document"
  };
  const roleKey = normalizedRole.replace(/\s+/g, "_");
  if (labelByRole[roleKey]) return labelByRole[roleKey];
  if (normalizedTextIncludesPhrase(text, "bank")) return "Bank document";
  if (normalizedTextIncludesPhrase(text, "ownership") || normalizedTextIncludesPhrase(text, "land registry")) {
    return "Property ownership document";
  }
  if (normalizedTextIncludesPhrase(text, "policy")) return "Existing policy document";
  if (normalizedTextIncludesPhrase(text, "identity") || normalizedTextIncludesPhrase(text, "id document")) {
    return "ID document";
  }
  return document.label || "Client legal document";
}

function recordFromUnknown(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  return value as Record<string, unknown>;
}

function isClaimEvidencePhotoLikeClientDocument(
  document: CustomerLegalDocument,
  text: string,
  source: string
) {
  const documentType = normalizeEvidenceText(document.document_type || "");
  const fileName = document.file_name || "";
  const contentType = normalizeEvidenceText(document.content_type || "");
  const isIdentityDocument = [
    "id document",
    "identity document",
    "identity card",
    "photo id",
    "passport",
    "national id"
  ].some((phrase) => normalizedTextIncludesPhrase(text, phrase));

  if (isIdentityDocument) return false;

  const evidenceSource = [
    "claim evidence",
    "claim attachment",
    "evidence upload",
    "email attachment",
    "inbound attachment"
  ].some((phrase) => normalizedTextIncludesPhrase(source, phrase));
  if (evidenceSource) return true;

  const evidencePhotoType = [
    "damage photos",
    "incident photos",
    "property photos",
    "damage photo",
    "incident photo",
    "property photo"
  ].some((phrase) => normalizedTextIncludesPhrase(documentType, phrase));
  if (evidencePhotoType) return true;

  const imageFile = /\.(jpe?g|png|gif|webp|heic|avif)$/i.test(fileName) ||
    normalizedTextIncludesPhrase(contentType, "image");
  const photoSignal = ["photo", "photos", "image"].some((phrase) =>
    normalizedTextIncludesPhrase(text, phrase)
  );
  const claimEvidenceSignal = [
    "claim evidence",
    "supporting evidence",
    "incident",
    "damage",
    "property"
  ].some((phrase) => normalizedTextIncludesPhrase(text, phrase));

  return (photoSignal || imageFile) && claimEvidenceSignal;
}

function normalizedTextIncludesPhrase(text: string, phrase: string) {
  const normalizedText = normalizeEvidenceText(text);
  const normalizedPhrase = normalizeEvidenceText(phrase);
  if (!normalizedText || !normalizedPhrase) return false;
  return ` ${normalizedText} `.includes(` ${normalizedPhrase} `);
}

function buildClientLegalDocuments(profile: CustomerProfileDetail): CustomerLegalDocument[] {
  return (profile.legal_documents ?? []).filter(hasClientDocumentFile);
}

function slugFileName(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "client-profile";
}

function hasClientDocumentFile(document: CustomerLegalDocument) {
  return Boolean(document.file_url);
}

function ClaimEvidenceTab({
  aiFindings,
  analysisRefreshing,
  claim,
  evidenceItems,
  onAction,
  onRefreshAnalysis,
  onSelectEvidence,
  pendingActionId
}: {
  aiFindings: AiReviewFinding[];
  analysisRefreshing: boolean;
  claim: Claim;
  evidenceItems: ClaimEvidenceScaffoldItem[];
  onAction: (action: ClaimCommunicationActionRequest) => void;
  onRefreshAnalysis: () => void;
  onSelectEvidence: (item: ClaimEvidenceScaffoldItem) => void;
  pendingActionId?: string;
}) {
  const visibleAiFindings = visibleClaimEvidenceFindings(aiFindings);

  return (
    <div className="space-y-4">
      <ClaimWorkspaceSection title="Claim evidence details">
        <ClaimFieldGrid
          items={[
            ["Client statement", <ExpandableClaimDescription text={claim.description || "-"} />, true],
            ["Incident date", formatDate(claim.incidentDate)],
            ["Incident time", claim.incidentTime || "-"],
            ["Estimated damage", formatCurrency(claim.estimatedDamage)],
            ["Property", claim.propertyAddress]
          ]}
        />
      </ClaimWorkspaceSection>
      <ClaimWorkspaceSection
        action={
          <Button
            className="min-h-8 px-3 py-1 text-xs"
            icon={RefreshCw}
            loading={analysisRefreshing}
            onClick={onRefreshAnalysis}
            variant="secondary"
          >
            Refresh
          </Button>
        }
        title="AI analysis"
      >
        {visibleAiFindings.length ? (
          <AiDocumentAnalysisPanel findings={visibleAiFindings} />
        ) : (
          <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-500">
            No AI analysis is available yet.
          </div>
        )}
      </ClaimWorkspaceSection>
      {evidenceItems.length ? (
        <div className="space-y-2">
          {evidenceItems.map((item) => (
            <ClaimEvidenceItemRow
              item={item}
              key={item.id}
              onAction={onAction}
              onSelectEvidence={onSelectEvidence}
              pendingActionId={pendingActionId}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-500">
          No claim-specific evidence documents are attached or requested yet.
        </div>
      )}
    </div>
  );
}

function visibleClaimEvidenceFindings(findings: AiReviewFinding[]) {
  return findings;
}

function AiDocumentAnalysisPanel({
  findings
}: {
  findings: AiReviewFinding[];
}) {
  if (!findings.length) {
    return null;
  }

  return (
    <div className="space-y-2">
      {findings.map((finding) => (
        <article className="rounded-lg border border-slate-200 bg-white px-3 py-3" key={finding.id}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-bold text-slate-950">{cleanClaimUiTitle(finding.findingType)}</h3>
              </div>
              <FormattedClaimSummary className="mt-2" text={finding.description} />
              {finding.relatedDocument || finding.recommendation ? (
                <dl className="mt-3 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
                  {finding.relatedDocument ? (
                    <CommunicationInlineFact label="Related document" value={finding.relatedDocument} />
                  ) : null}
                  {finding.recommendation ? (
                    <CommunicationInlineFact label="Recommendation" value={finding.recommendation} />
                  ) : null}
                </dl>
              ) : null}
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function ClaimEvidenceItemRow({
  item,
  onAction,
  onSelectEvidence,
  pendingActionId
}: {
  item: ClaimEvidenceScaffoldItem;
  onAction: (action: ClaimCommunicationActionRequest) => void;
  onSelectEvidence: (item: ClaimEvidenceScaffoldItem) => void;
  pendingActionId?: string;
}) {
  const details = [item.fileName, item.source, item.uploadedDate].filter(Boolean).join(" - ");
  const action = claimEvidenceItemActionRequest(item);
  const pending = pendingActionId === action.id;
  const actionDisabled = Boolean(pendingActionId) || action.kind === "unsupported";
  const rowContent = (
    <>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="min-w-0 truncate text-sm font-bold text-slate-950">{item.name}</h3>
        </div>
        {details ? <p className="mt-1 truncate text-xs font-semibold text-slate-500">{details}</p> : null}
        {item.issue ? (
          <p className="mt-2 line-clamp-2 text-xs font-semibold leading-5 text-slate-600">{item.issue}</p>
        ) : null}
      </div>
    </>
  );
  const actionClasses =
    "inline-flex min-h-8 shrink-0 items-center justify-center rounded-md border border-orange-100 bg-orange-50 px-3 text-xs font-bold text-orange-600";

  if (item.hasFile) {
    return (
      <button
        className="flex w-full min-w-0 flex-col gap-3 rounded-lg border border-slate-200 bg-white px-3 py-3 text-left transition hover:border-orange-200 hover:bg-orange-50/40 focus:outline-none focus:ring-4 focus:ring-orange-100 sm:flex-row sm:items-center sm:justify-between"
        onClick={() => onSelectEvidence(item)}
        type="button"
      >
        {rowContent}
        <span className={actionClasses}>{item.primaryAction}</span>
      </button>
    );
  }

  return (
    <div className="flex min-w-0 flex-col gap-3 rounded-lg border border-slate-200 bg-white px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
      {rowContent}
      <button
        className={`${actionClasses} transition focus:outline-none focus:ring-4 focus:ring-orange-100 ${
          actionDisabled
            ? "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400"
            : "hover:bg-orange-100"
        }`}
        disabled={actionDisabled}
        onClick={() => onAction(action)}
        type="button"
      >
        {pending ? "Working..." : item.primaryAction}
      </button>
    </div>
  );
}

function claimEvidenceItemActionRequest(item: ClaimEvidenceScaffoldItem): ClaimCommunicationActionRequest {
  const kind = claimEvidenceItemActionKind(item);
  return {
    id: `evidence-${item.id}-${kind}`,
    kind,
    evidenceItemId: item.id
  };
}

function claimEvidenceItemActionKind(item: ClaimEvidenceScaffoldItem): ClaimCommunicationActionKind {
  if (item.primaryAction === "Open preview") return "view_document";
  if (item.primaryAction === "Request") return "generate_draft";
  if (item.primaryAction === "View request") return "view_draft";
  return "unsupported";
}

function evidenceUploadTone(status: string): BadgeTone {
  const normalized = status.toLowerCase();
  if (normalized.includes("received") || normalized.includes("uploaded")) return "green";
  if (normalized.includes("blocked")) return "red";
  if (normalized.includes("pending") || normalized.includes("requested") || normalized.includes("missing")) return "amber";
  return "slate";
}

function ClaimEvidencePreviewModal({
  item,
  onClose
}: {
  item: ClaimEvidenceScaffoldItem | null;
  onClose: () => void;
}) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string>();
  const [docxHtml, setDocxHtml] = useState<string>();
  const [previewError, setPreviewError] = useState<string>();
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (!item) return;

    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", handleKeyDown);
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [item, onClose]);

  useEffect(() => {
    if (!item?.hasFile || !item.fileUrl) {
      setPreviewBlobUrl(undefined);
      setDocxHtml(undefined);
      setPreviewError(undefined);
      setPreviewLoading(false);
      return;
    }

    let cancelled = false;
    let objectUrl: string | undefined;
    setPreviewLoading(true);
    setDocxHtml(undefined);
    setPreviewError(undefined);

    void apiBlobRequest(item.fileUrl)
      .then(async ({ blob }) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPreviewBlobUrl(objectUrl);

        const fileName = item.fileName.toLowerCase();
        const mimeType = (item.contentType || "").toLowerCase();
        const isDocx =
          fileName.endsWith(".docx") ||
          mimeType.includes("application/vnd.openxmlformats-officedocument.wordprocessingml.document");

        if (isDocx) {
          const mammoth = await import("mammoth/mammoth.browser");
          const arrayBuffer = await blob.arrayBuffer();
          const conversion = await mammoth.convertToHtml({ arrayBuffer });
          if (!cancelled) {
            setDocxHtml(conversion.value || "");
          }
        }
      })
      .catch((error) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "Could not load document preview.";
        setPreviewBlobUrl(undefined);
        setDocxHtml(undefined);
        setPreviewError(message);
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [item]);

  if (!item) return null;

  const lowerFileName = item.fileName.toLowerCase();
  const mimeType = (item.contentType || "").toLowerCase();
  const imagePreview = mimeType.startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(lowerFileName);
  const pdfPreview = mimeType.includes("pdf") || lowerFileName.endsWith(".pdf");
  const docxPreview =
    lowerFileName.endsWith(".docx") ||
    mimeType.includes("application/vnd.openxmlformats-officedocument.wordprocessingml.document");

  const previewFields: Array<[string, ReactNode]> = [
    ["File name", item.fileName],
    ["Document type", item.type],
    ["Source", item.source],
    ["Uploaded date", item.uploadedDate],
    ...(item.issue ? ([["Blocking issue", item.issue]] as Array<[string, ReactNode]>) : [])
  ];

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" role="presentation">
      <button
        aria-label="Close evidence preview"
        className="absolute inset-0 h-full w-full bg-slate-950/40 backdrop-blur-[1px]"
        onClick={onClose}
        type="button"
      />
      <section
        aria-label="Evidence document preview"
        aria-modal="true"
        className="relative z-10 flex max-h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-slate-950">Evidence preview: {item.name}</h2>
            <p className="mt-1 text-sm font-semibold text-slate-500">{item.fileName}</p>
          </div>
          <button
            aria-label="Close evidence preview"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-orange-100"
            onClick={onClose}
            ref={closeButtonRef}
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="grid min-h-0 flex-1 gap-0 overflow-y-auto lg:grid-cols-[minmax(0,1.25fr)_minmax(340px,0.75fr)]">
          <div className="min-h-[420px] border-b border-slate-200 bg-slate-100 p-5 lg:border-b-0 lg:border-r">
            <div
              className={`flex h-full min-h-[360px] rounded-xl border border-dashed border-slate-300 bg-white ${
                docxPreview ? "items-stretch justify-stretch text-left" : "items-center justify-center text-center"
              }`}
            >
              {previewLoading ? (
                <div className="px-6">
                  <FileText className="mx-auto h-10 w-10 animate-pulse text-slate-300" />
                  <p className="mt-4 text-base font-bold text-slate-950">Loading preview...</p>
                  <p className="mt-2 text-sm font-semibold text-slate-500">{item.fileName}</p>
                </div>
              ) : docxPreview && docxHtml ? (
                <iframe
                  className="h-full min-h-[360px] w-full rounded-xl"
                  sandbox=""
                  srcDoc={`<!doctype html><html><head><meta charset=\"utf-8\" /><style>body{margin:0;padding:24px;font-family:Georgia,\"Times New Roman\",serif;color:#0f172a;line-height:1.6;}p{margin:0 0 12px;}h1,h2,h3,h4{margin:16px 0 8px;}table{border-collapse:collapse;}td,th{border:1px solid #cbd5e1;padding:6px 8px;}img{max-width:100%;height:auto;}</style></head><body>${docxHtml}</body></html>`}
                  title={`Preview ${item.fileName}`}
                />
              ) : previewBlobUrl && imagePreview ? (
                <img alt={item.fileName} className="max-h-full max-w-full rounded-lg object-contain" src={previewBlobUrl} />
              ) : previewBlobUrl && pdfPreview ? (
                <iframe className="h-full min-h-[360px] w-full rounded-lg" src={previewBlobUrl} title={`Preview ${item.fileName}`} />
              ) : (
                <div className="px-6">
                  <FileText className="mx-auto h-10 w-10 text-slate-300" />
                  <p className="mt-4 text-base font-bold text-slate-950">{item.fileName}</p>
                  <p className="mt-2 text-sm font-semibold text-slate-500">
                    {previewError
                      ? "Preview could not be loaded."
                      : "Inline preview is available for PDF, DOCX, and image evidence."}
                  </p>
                  {item.previewUrl ? (
                    <a
                      className="mt-3 inline-flex min-h-8 items-center justify-center rounded-md border border-orange-100 bg-orange-50 px-3 text-xs font-bold text-orange-600 transition hover:bg-orange-100"
                      href={item.previewUrl}
                      rel="noreferrer"
                      target="_blank"
                    >
                      Open file
                    </a>
                  ) : null}
                </div>
              )}
            </div>
          </div>
          <div className="p-5">
            <h3 className="text-base font-bold text-slate-950">Evidence details</h3>
            <dl className="mt-4 space-y-3">
              {previewFields.map(([label, value]) => (
                <div className="border-b border-slate-100 pb-3 last:border-b-0" key={label}>
                  <dt className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{label}</dt>
                  <dd className="mt-1 text-sm font-semibold leading-6 text-slate-900">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>
    </div>
  );
}

function ClientDocumentPreviewModal({
  item,
  onClose
}: {
  item: CustomerLegalDocument | null;
  onClose: () => void;
}) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string>();
  const [docxHtml, setDocxHtml] = useState<string>();
  const [previewError, setPreviewError] = useState<string>();
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (!item) return;

    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", handleKeyDown);
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [item, onClose]);

  useEffect(() => {
    if (!item?.file_url) {
      setPreviewBlobUrl(undefined);
      setDocxHtml(undefined);
      setPreviewError(undefined);
      setPreviewLoading(false);
      return;
    }

    let cancelled = false;
    let objectUrl: string | undefined;
    setPreviewLoading(true);
    setDocxHtml(undefined);
    setPreviewError(undefined);

    void apiBlobRequest(item.file_url)
      .then(async ({ blob }) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPreviewBlobUrl(objectUrl);

        const fileName = item.file_name.toLowerCase();
        const mimeType = (item.content_type || "").toLowerCase();
        const isDocx =
          fileName.endsWith(".docx") ||
          mimeType.includes("application/vnd.openxmlformats-officedocument.wordprocessingml.document");

        if (isDocx) {
          const mammoth = await import("mammoth/mammoth.browser");
          const arrayBuffer = await blob.arrayBuffer();
          const conversion = await mammoth.convertToHtml({ arrayBuffer });
          if (!cancelled) setDocxHtml(conversion.value || "");
        }
      })
      .catch((error) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "Could not load document preview.";
        setPreviewBlobUrl(undefined);
        setDocxHtml(undefined);
        setPreviewError(message);
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [item]);

  if (!item) return null;

  const lowerFileName = item.file_name.toLowerCase();
  const mimeType = (item.content_type || "").toLowerCase();
  const imagePreview = mimeType.startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(lowerFileName);
  const pdfPreview = mimeType.includes("pdf") || lowerFileName.endsWith(".pdf");
  const docxPreview =
    lowerFileName.endsWith(".docx") ||
    mimeType.includes("application/vnd.openxmlformats-officedocument.wordprocessingml.document");
  const extractedFields = Object.entries(item.extracted_fields ?? {}).filter(([, value]) => value != null && value !== "");

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" role="presentation">
      <button
        aria-label="Close client document preview"
        className="absolute inset-0 h-full w-full bg-slate-950/40 backdrop-blur-[1px]"
        onClick={onClose}
        type="button"
      />
      <section
        aria-label="Client legal document preview"
        aria-modal="true"
        className="relative z-10 flex max-h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-slate-950">Client document preview: {item.label || item.document_type}</h2>
            <p className="mt-1 text-sm font-semibold text-slate-500">{item.file_name}</p>
          </div>
          <button
            aria-label="Close client document preview"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-orange-100"
            onClick={onClose}
            ref={closeButtonRef}
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="grid min-h-0 flex-1 gap-0 overflow-y-auto lg:grid-cols-[minmax(0,1.25fr)_minmax(340px,0.75fr)]">
          <div className="min-h-[420px] border-b border-slate-200 bg-slate-100 p-5 lg:border-b-0 lg:border-r">
            <div
              className={`flex h-full min-h-[360px] rounded-xl border border-dashed border-slate-300 bg-white ${
                docxPreview ? "items-stretch justify-stretch text-left" : "items-center justify-center text-center"
              }`}
            >
              {previewLoading ? (
                <div className="px-6">
                  <FileText className="mx-auto h-10 w-10 animate-pulse text-slate-300" />
                  <p className="mt-4 text-base font-bold text-slate-950">Loading preview...</p>
                  <p className="mt-2 text-sm font-semibold text-slate-500">{item.file_name}</p>
                </div>
              ) : docxPreview && docxHtml ? (
                <iframe
                  className="h-full min-h-[360px] w-full rounded-xl"
                  sandbox=""
                  srcDoc={`<!doctype html><html><head><meta charset=\"utf-8\" /><style>body{margin:0;padding:24px;font-family:Georgia,\"Times New Roman\",serif;color:#0f172a;line-height:1.6;}p{margin:0 0 12px;}h1,h2,h3,h4{margin:16px 0 8px;}table{border-collapse:collapse;}td,th{border:1px solid #cbd5e1;padding:6px 8px;}img{max-width:100%;height:auto;}</style></head><body>${docxHtml}</body></html>`}
                  title={`Preview ${item.file_name}`}
                />
              ) : previewBlobUrl && imagePreview ? (
                <img alt={item.file_name} className="max-h-full max-w-full rounded-lg object-contain" src={previewBlobUrl} />
              ) : previewBlobUrl && pdfPreview ? (
                <iframe className="h-full min-h-[360px] w-full rounded-lg" src={previewBlobUrl} title={`Preview ${item.file_name}`} />
              ) : (
                <div className="px-6">
                  <FileText className="mx-auto h-10 w-10 text-slate-300" />
                  <p className="mt-4 text-base font-bold text-slate-950">{item.file_name}</p>
                  <p className="mt-2 text-sm font-semibold text-slate-500">
                    {previewError
                      ? "Preview could not be loaded."
                      : item.file_url
                        ? "Inline preview is available for PDF, DOCX, and image documents."
                        : "No source file is attached to this document row."}
                  </p>
                </div>
              )}
            </div>
          </div>
          <div className="p-5">
            <h3 className="text-base font-bold text-slate-950">Document interpretation</h3>
            <dl className="mt-4 space-y-3">
              <ClientDocumentPreviewFact label="Document type" value={item.document_type} />
              <ClientDocumentPreviewFact label="Source" value={formatClientDocumentSource(item.source)} />
              <ClientDocumentPreviewFact label="File name" value={item.file_name} />
              {extractedFields.map(([label, value]) => (
                <ClientDocumentPreviewFact key={label} label={titleCaseLabel(label)} value={String(value)} />
              ))}
            </dl>
            {item.ai_interpretation ? (
              <FormattedClaimSummary className="mt-4 rounded-lg bg-orange-50 p-3" text={item.ai_interpretation} />
            ) : null}
          </div>
        </div>
      </section>
    </div>
  );
}

function ClientDocumentPreviewFact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="border-b border-slate-100 pb-3 last:border-b-0">
      <dt className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-semibold leading-6 text-slate-900">{value}</dd>
    </div>
  );
}

function ClaimCommunicateTab({
  createRequestDisabledReason,
  demoInboundDisabledReason,
  notice,
  onAction,
  pendingActionId,
  workspace
}: {
  createRequestDisabledReason?: string;
  demoInboundDisabledReason?: string;
  notice?: { tone: "danger" | "success" | "warning"; message: string };
  onAction: (action: ClaimCommunicationActionRequest) => void;
  pendingActionId?: string;
  workspace: ClaimCommunicationWorkspace;
}) {
  const openRequestCount = claimCommunicationOpenRequestCount(workspace);
  const inboundEmailCount = workspace.inboundEmails.length;
  const emptyWorkspace = openRequestCount === 0 && inboundEmailCount === 0;
  const showAutomationDetails = !emptyWorkspace && shouldShowEmailAutomationDetails(workspace.automation);
  const showFollowUpSuggestions =
    workspace.aiFollowUpSuggestions.length > 0 ||
    normalizeAiStatus(workspace.aiReviewStatus) === "processing";

  return (
    <div className="space-y-4">
      <ClaimWorkspaceSection
        action={
          <CommunicationComposeBar
            demoInboundDisabledReason={demoInboundDisabledReason}
            onAction={onAction}
            pendingActionId={pendingActionId}
          />
        }
        title="Email"
      >
        <div className="space-y-3">
          {notice ? <ValidationBanner message={notice.message} tone={notice.tone} /> : null}
          {emptyWorkspace ? (
            <CommunicationStartPanel
              createRequestDisabledReason={createRequestDisabledReason}
              onAction={onAction}
              pendingActionId={pendingActionId}
              workspace={workspace}
            />
          ) : null}
          {showAutomationDetails ? (
            <ClaimEmailAutomationCard
              automation={workspace.automation}
              createRequestDisabledReason={createRequestDisabledReason}
              onAction={onAction}
              pendingActionId={pendingActionId}
            />
          ) : !emptyWorkspace ? (
            <CommunicationAutomationInactive
              createRequestDisabledReason={createRequestDisabledReason}
              hasOpenRequests={openRequestCount > 0}
              onAction={onAction}
              pendingActionId={pendingActionId}
            />
          ) : null}
        </div>
      </ClaimWorkspaceSection>
      {showFollowUpSuggestions ? (
        <ClaimWorkspaceSection title="Follow-up suggestions">
          <AiFollowUpSuggestionsSection
            onAction={onAction}
            pendingActionId={pendingActionId}
            status={workspace.aiReviewStatus}
            suggestions={workspace.aiFollowUpSuggestions}
          />
        </ClaimWorkspaceSection>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ClaimWorkspaceSection title="Requests">
          <RequestedDocumentsCommunicationTable
            createRequestDisabledReason={createRequestDisabledReason}
            onAction={onAction}
            pendingActionId={pendingActionId}
            rows={workspace.requests}
          />
        </ClaimWorkspaceSection>
        <ClaimWorkspaceSection title="Replies">
          <InboundEmailIngestionList
            emails={workspace.inboundEmails}
            onAction={onAction}
            pendingActionId={pendingActionId}
          />
        </ClaimWorkspaceSection>
      </div>
      <ClaimWorkspaceSection title="History">
        <CommunicationTimeline events={workspace.timeline} />
      </ClaimWorkspaceSection>
    </div>
  );
}

function CommunicationComposeBar({
  demoInboundDisabledReason,
  onAction,
  pendingActionId
}: {
  demoInboundDisabledReason?: string;
  onAction: (action: ClaimCommunicationActionRequest) => void;
  pendingActionId?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <CommunicationActionButton
        action={{ id: "communication-write-email", kind: "write_email" }}
        label="Write email"
        onAction={onAction}
        pendingActionId={pendingActionId}
      />
      <CommunicationActionButton
        action={{ id: "communication-demo-inbound-email", kind: "trigger_demo_inbound_email" }}
        disabledReason={demoInboundDisabledReason}
        label="Send demo reply"
        onAction={onAction}
        pendingActionId={pendingActionId}
      />
    </div>
  );
}

function CommunicationStartPanel({
  createRequestDisabledReason,
  onAction,
  pendingActionId,
  workspace
}: {
  createRequestDisabledReason?: string;
  onAction: (action: ClaimCommunicationActionRequest) => void;
  pendingActionId?: string;
  workspace: ClaimCommunicationWorkspace;
}) {
  const createAction: ClaimCommunicationActionRequest = {
    id: "communication-start-create",
    kind: "generate_draft"
  };

  return (
    <section className="rounded-lg border border-orange-100 bg-orange-50/60 px-4 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-bold text-slate-950">Client communication</h2>
          <p className="mt-1 text-sm leading-5 text-slate-600">
            No active client requests are currently open for this claim.
          </p>
          <p className="mt-2 text-xs font-semibold text-slate-500">{workspace.automation.recipient || "-"}</p>
        </div>
        <Button
          disabled={pendingActionId === createAction.id || Boolean(createRequestDisabledReason)}
          onClick={() => onAction(createAction)}
          variant="primary"
        >
          {pendingActionId === createAction.id ? "Creating" : "Create document request"}
        </Button>
      </div>
    </section>
  );
}

function CommunicationInlineFact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 truncate text-xs font-semibold text-slate-900">{value || "-"}</dd>
    </div>
  );
}

function CommunicationAutomationInactive({
  createRequestDisabledReason,
  hasOpenRequests,
  onAction,
  pendingActionId
}: {
  createRequestDisabledReason?: string;
  hasOpenRequests: boolean;
  onAction: (action: ClaimCommunicationActionRequest) => void;
  pendingActionId?: string;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm font-semibold text-slate-600">
        {hasOpenRequests
          ? "Create a request email for the missing documents."
          : "No client request is needed right now."}
      </p>
      <CommunicationActionButton
        action={{ id: "automation-create-request", kind: "generate_draft" }}
        disabledReason={createRequestDisabledReason}
        label="Create document request"
        onAction={onAction}
        pendingActionId={pendingActionId}
      />
    </div>
  );
}

function AiFollowUpSuggestionsSection({
  onAction,
  pendingActionId,
  status,
  suggestions
}: {
  onAction: (action: ClaimCommunicationActionRequest) => void;
  pendingActionId?: string;
  status: AiReviewLifecycleStatus;
  suggestions: AiFollowUpSuggestion[];
}) {
  if (!suggestions.length) {
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-bold text-slate-950">{aiFollowUpEmptyTitle(status)}</p>
          <p className="mt-1 text-sm leading-5 text-slate-600">{aiFollowUpEmptyDescription(status)}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {suggestions.map((suggestion) => (
        <button
          className="block w-full rounded-lg border border-slate-200 bg-white px-3 py-3 text-left transition hover:border-orange-200 hover:bg-orange-50/40 focus:outline-none focus:ring-4 focus:ring-orange-100"
          key={suggestion.id}
          onClick={() =>
            onAction({
              id: `ai-review-${suggestion.id}`,
              kind: "review_ai_suggestion",
              suggestionId: suggestion.id
            })
          }
          type="button"
        >
          <h3 className="text-sm font-bold text-slate-950">{suggestion.title}</h3>
          <p className="mt-1 text-sm font-semibold leading-5 text-slate-700">
            {claimSummaryPreviewText(suggestion.reason)}
          </p>
        </button>
      ))}
    </div>
  );
}

function AiFollowUpSuggestionModal({
  onAction,
  onClose,
  pendingActionId,
  suggestion
}: {
  onAction: (action: ClaimCommunicationActionRequest) => void;
  onClose: () => void;
  pendingActionId?: string;
  suggestion: AiFollowUpSuggestion | null;
}) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!suggestion) return;
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [suggestion, onClose]);

  if (!suggestion) return null;
  const draftDisabledReason = aiSuggestionDraftDisabledReason(suggestion);

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" role="presentation">
      <button
        aria-label="Close AI follow-up suggestion"
        className="absolute inset-0 h-full w-full bg-slate-950/40 backdrop-blur-[1px]"
        onClick={onClose}
        type="button"
      />
      <section
        aria-label="AI follow-up suggestion review"
        aria-modal="true"
        className="relative z-10 flex max-h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-slate-950">{suggestion.title}</h2>
          </div>
          <button
            aria-label="Close AI follow-up suggestion"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-orange-100"
            onClick={onClose}
            ref={closeButtonRef}
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="grid min-h-0 flex-1 gap-0 overflow-y-auto lg:grid-cols-[minmax(0,0.95fr)_minmax(420px,1.05fr)]">
          <div className="space-y-5 border-b border-slate-200 p-6 lg:border-b-0 lg:border-r">
            <section>
              <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">Reason</h3>
              <FormattedClaimSummary className="mt-2 text-slate-800" text={suggestion.reason} />
            </section>
          </div>
          <div className="bg-slate-50/70 p-6">
            <section>
              <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">Proposal</h3>
              <div className="mt-2 space-y-3">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">Subject</p>
                  <p className="mt-1 text-sm font-bold leading-6 text-slate-950">{suggestion.suggestedEmailSubject}</p>
                </div>
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">Message</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700">{suggestion.suggestedEmailBody}</p>
                </div>
              </div>
            </section>
            <div className="mt-4 flex flex-wrap gap-2">
              <CommunicationActionButton
                action={{ id: `modal-ai-create-${suggestion.id}`, kind: "create_request_from_ai", suggestionId: suggestion.id }}
                disabledReason={draftDisabledReason}
                label="Create request"
                onAction={onAction}
                pendingActionId={pendingActionId}
              />
              <CommunicationActionButton
                action={{ id: `modal-ai-edit-${suggestion.id}`, kind: "edit_ai_draft", suggestionId: suggestion.id }}
                disabledReason={draftDisabledReason}
                label="Edit draft"
                onAction={onAction}
                pendingActionId={pendingActionId}
              />
              <CommunicationActionButton
                action={{ id: `modal-ai-dismiss-${suggestion.id}`, kind: "dismiss_ai_suggestion", suggestionId: suggestion.id }}
                label="Dismiss"
                onAction={onAction}
                pendingActionId={pendingActionId}
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function AiSuggestionDraftEditorModal({
  onClose,
  onSaveDraft,
  pending,
  suggestion
}: {
  onClose: () => void;
  onSaveDraft: (suggestion: AiFollowUpSuggestion, draft: SuggestedEmailDraft) => Promise<void> | void;
  pending?: boolean;
  suggestion: AiFollowUpSuggestion | null;
}) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const [draft, setDraft] = useState<SuggestedEmailDraft>(() => suggestedDraftFromAiSuggestion(suggestion));
  const [saveError, setSaveError] = useState<string>();

  useEffect(() => {
    setDraft(suggestedDraftFromAiSuggestion(suggestion));
    setSaveError(undefined);
  }, [suggestion]);

  useEffect(() => {
    if (!suggestion) return;
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [suggestion, onClose]);

  if (!suggestion) return null;

  async function submitDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveError(undefined);
    try {
      await onSaveDraft(suggestion, draft);
    } catch (error) {
      setSaveError(errorMessage(error, "Could not save the email request draft."));
    }
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" role="presentation">
      <button
        aria-label="Close request draft editor"
        className="absolute inset-0 h-full w-full bg-slate-950/40 backdrop-blur-[1px]"
        onClick={onClose}
        type="button"
      />
      <form
        aria-label="Edit request draft"
        aria-modal="true"
        className="relative z-10 flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
        onSubmit={submitDraft}
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-slate-950">{suggestion.title}</h2>
          </div>
          <button
            aria-label="Close request draft editor"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-orange-100"
            onClick={onClose}
            ref={closeButtonRef}
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.55fr)]">
            <div className="space-y-3">
              <AiDraftEditorField
                label="Subject"
                onChange={(value) => setDraft((current) => ({ ...current, subject: value }))}
                placeholder="Subject"
                value={draft.subject}
              />
              <AiDraftEditorField
                label="Body"
                multiline
                onChange={(value) => setDraft((current) => ({ ...current, body: value }))}
                placeholder="Message"
                value={draft.body}
              />
            </div>
            <div className="space-y-3">
              <AiDraftEditorField
                label="Requested document name"
                onChange={(value) => setDraft((current) => ({ ...current, requestedDocumentType: value }))}
                placeholder="Requested document"
                value={draft.requestedDocumentType || ""}
              />
              <AiDraftEditorField
                label="Due date"
                onChange={(value) => setDraft((current) => ({ ...current, dueDate: value }))}
                placeholder="Due date"
                type="date"
                value={draft.dueDate || ""}
              />
              <p className="rounded-lg border border-orange-100 bg-orange-50 px-3 py-2 text-xs font-semibold leading-5 text-orange-700">
                Saved as a draft until you send it.
              </p>
              {saveError ? (
                <p className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs font-semibold leading-5 text-red-700">
                  {saveError}
                </p>
              ) : null}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 px-5 py-4">
          <Button onClick={onClose} type="button" variant="secondary">Close</Button>
          <Button disabled={pending || !draft.subject.trim() || !draft.body.trim()} loading={pending} type="submit" variant="primary">
            {pending ? "Saving" : "Save request draft"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function EvidenceRequestEmailEditorModal({
  draft: initialDraft,
  onClose,
  onSaveDraft,
  open,
  pending
}: {
  draft: SuggestedEmailDraft;
  onClose: () => void;
  onSaveDraft: (draft: SuggestedEmailDraft) => Promise<void> | void;
  open: boolean;
  pending?: boolean;
}) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const [draft, setDraft] = useState<SuggestedEmailDraft>(initialDraft);

  useEffect(() => {
    if (open) setDraft(initialDraft);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  function submitDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSaveDraft(draft);
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" role="presentation">
      <button
        aria-label="Close email editor"
        className="absolute inset-0 h-full w-full bg-slate-950/40 backdrop-blur-[1px]"
        onClick={onClose}
        type="button"
      />
      <form
        aria-label="Write email"
        aria-modal="true"
        className="relative z-10 flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
        onSubmit={submitDraft}
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <h2 className="truncate text-lg font-bold text-slate-950">Write email</h2>
          <button
            aria-label="Close email editor"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-orange-100"
            onClick={onClose}
            ref={closeButtonRef}
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]">
            <div className="space-y-3">
              <AiDraftEditorField
                label="Email subject"
                onChange={(value) => setDraft((current) => ({ ...current, subject: value }))}
                placeholder="Subject"
                showLabel
                value={draft.subject}
              />
              <AiDraftEditorField
                label="Email message"
                multiline
                onChange={(value) => setDraft((current) => ({ ...current, body: value }))}
                placeholder="Message"
                showLabel
                value={draft.body}
              />
            </div>
            <div className="space-y-3">
              <AiDraftEditorField
                label="Requested document"
                onChange={(value) => setDraft((current) => ({ ...current, requestedDocumentType: value }))}
                placeholder="Requested document"
                showLabel
                value={draft.requestedDocumentType || ""}
              />
              <AiDraftEditorField
                label="Due date"
                onChange={(value) => setDraft((current) => ({ ...current, dueDate: value }))}
                placeholder="Due date"
                showLabel
                type="date"
                value={draft.dueDate || ""}
              />
              <p className="rounded-lg border border-orange-100 bg-orange-50 px-3 py-2 text-xs font-semibold leading-5 text-orange-700">
                Saved as a draft until you send it.
              </p>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 px-5 py-4">
          <Button onClick={onClose} type="button" variant="secondary">Close</Button>
          <Button disabled={pending || !draft.subject.trim() || !draft.body.trim()} type="submit" variant="primary">
            {pending ? "Saving" : "Save email draft"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function AiDraftEditorField({
  label,
  multiline,
  onChange,
  placeholder,
  showLabel = false,
  type = "text",
  value
}: {
  label: string;
  multiline?: boolean;
  onChange: (value: string) => void;
  placeholder?: string;
  showLabel?: boolean;
  type?: string;
  value: string;
}) {
  const inputClass =
    "mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 shadow-sm transition focus:border-orange-300 focus:outline-none focus:ring-4 focus:ring-orange-100";
  return (
    <label className="block">
      <span className={showLabel ? "mb-1 block text-sm font-bold text-slate-800" : "sr-only"}>
        {label}
      </span>
      {multiline ? (
        <textarea
          className={`${inputClass} min-h-64 resize-y leading-6`}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder || label}
          value={value}
        />
      ) : (
        <input
          className={inputClass}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder || label}
          type={type}
          value={value}
        />
      )}
    </label>
  );
}

function claimCommunicationOpenRequestCount(workspace: ClaimCommunicationWorkspace) {
  return workspace.requests.filter((row) => row.status !== "Received").length;
}

function shouldShowEmailAutomationDetails(automation: ClaimEmailAutomationPanel) {
  return (
    automation.status !== "Not active" &&
    (
      automation.actionKind === "view_draft" ||
      automation.deliveryStatus.toLowerCase().includes("failed")
    )
  );
}

function ClaimEmailAutomationCard({
  automation,
  createRequestDisabledReason,
  onAction,
  pendingActionId
}: {
  automation: ClaimEmailAutomationPanel;
  createRequestDisabledReason?: string;
  onAction: (action: ClaimCommunicationActionRequest) => void;
  pendingActionId?: string;
}) {
  const primaryDisabledReason =
    automation.actionKind === "generate_draft"
      ? createRequestDisabledReason || automation.disabledReason
      : automation.disabledReason;
  const secondaryDetails = [
    automation.recipient,
    automation.deliveryStatus,
    automation.lastEmailSent !== "Not sent" && automation.lastEmailSent !== "Not needed"
      ? automation.lastEmailSent
      : ""
  ].filter(Boolean);
  const emailCardTitle =
    automation.status === "Sent"
      ? "Sent email"
      : automation.status === "Failed"
        ? "Email delivery failed"
        : "Email draft";

  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-slate-500">{emailCardTitle}</p>
          <div className="flex flex-wrap items-center gap-2">
            <p className="min-w-0 flex-1 truncate text-sm font-bold text-slate-900">{automation.subject}</p>
            <Badge tone={automation.statusTone}>{automation.status}</Badge>
          </div>
          {secondaryDetails.length ? (
            <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">{secondaryDetails.join(" · ")}</p>
          ) : null}
        </div>
        <CommunicationActionButton
          action={{
            id: "automation-primary",
            kind: automation.actionKind
          }}
          disabledReason={primaryDisabledReason}
          label={automation.actionLabel}
          onAction={onAction}
          pendingActionId={pendingActionId}
        />
      </div>
    </div>
  );
}

function RequestedDocumentsCommunicationTable({
  createRequestDisabledReason,
  onAction,
  pendingActionId,
  rows
}: {
  createRequestDisabledReason?: string;
  onAction: (action: ClaimCommunicationActionRequest) => void;
  pendingActionId?: string;
  rows: ClaimCommunicationRequestRow[];
}) {
  if (!rows.length) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3">
        <p className="text-sm font-bold text-slate-950">No document requests</p>
        <p className="mt-1 text-sm leading-5 text-slate-600">
          No document requests have been sent for this claim. Create a request to ask the client for missing evidence.
        </p>
        <div className="mt-3">
          <CommunicationActionButton
            action={{ id: "requested-documents-create", kind: "generate_draft" }}
            disabledReason={createRequestDisabledReason}
            label="Create document request"
            onAction={onAction}
            pendingActionId={pendingActionId}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200 bg-white">
      {rows.map((row) => (
        <div className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between" key={row.id}>
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="truncate text-sm font-semibold text-slate-950">{row.document}</span>
            <Badge tone={row.statusTone}>{row.status}</Badge>
          </div>
          <CommunicationActionButton
            action={{
              evidenceItemId: row.evidenceItemId,
              id: row.id,
              kind: row.actionKind
            }}
            disabledReason={
              row.disabledReason ||
              (row.actionKind === "generate_draft" ? createRequestDisabledReason : undefined)
            }
            label={row.actionLabel}
            onAction={onAction}
            pendingActionId={pendingActionId}
          />
        </div>
      ))}
    </div>
  );
}

function InboundEmailIngestionList({
  emails,
  onAction,
  pendingActionId
}: {
  emails: ClaimInboundEmailItem[];
  onAction: (action: ClaimCommunicationActionRequest) => void;
  pendingActionId?: string;
}) {
  if (!emails.length) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3">
        <p className="text-sm font-bold text-slate-950">No replies yet</p>
        <p className="mt-1 text-sm leading-5 text-slate-600">
          Client replies and attachments will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {emails.map((email) => (
        <article className="rounded-lg border border-slate-200 bg-white px-3 py-3" key={email.id}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-950">{email.sender}</p>
              <p className="mt-0.5 text-xs font-semibold text-slate-500">
                {email.receivedAt} · {email.subject}
              </p>
            </div>
            <Badge tone={email.processingTone}>{email.processingStatus}</Badge>
          </div>
          <p className="mt-3 text-xs font-semibold text-slate-500">
            {email.attachments.length} attachment{email.attachments.length === 1 ? "" : "s"}
          </p>
          <div className="mt-2 space-y-2">
            {email.attachments.map((attachment) => (
              <div className="rounded-md border border-slate-100 bg-slate-50 px-3 py-2" key={attachment.id}>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold text-slate-950">{attachment.fileName}</p>
                    <p className="mt-1 text-xs font-semibold leading-5 text-slate-600">
                      {attachment.classification} · {attachment.linkedRequirement}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    <Badge tone={attachment.statusTone}>{attachment.status}</Badge>
                    <CommunicationActionButton
                      action={{
                        evidenceItemId: attachment.evidenceItemId,
                        id: attachment.id,
                        kind: attachment.evidenceItemId ? "view_document" : "unsupported"
                      }}
                      disabledReason={attachment.evidenceItemId ? undefined : "No document preview is available for this attachment yet."}
                      label={attachment.actionRequired ? "Review" : "Open"}
                      onAction={onAction}
                      pendingActionId={pendingActionId}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function CommunicationTimeline({ events }: { events: ClaimCommunicationTimelineEvent[] }) {
  if (!events.length) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-500">
        No communication timeline events are available yet.
      </div>
    );
  }

  return (
    <ol className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
      {events.map((event) => (
        <li className="flex flex-wrap items-center gap-x-1.5 gap-y-1 px-3 py-2 text-xs leading-5" key={event.id}>
          <span className="whitespace-nowrap font-semibold text-slate-500">{event.timestamp}</span>
          <span className="text-slate-300">·</span>
          <span className="min-w-0 text-slate-700">
            <span className="font-bold text-slate-950">{event.eventType}</span>
            <span className="mx-1 text-slate-300">—</span>
            <span>{event.description}</span>
          </span>
          <CommunicationMiniBadge tone={event.tone}>{event.status}</CommunicationMiniBadge>
        </li>
      ))}
    </ol>
  );
}

function CommunicationMiniBadge({ children, tone }: { children: ReactNode; tone: BadgeTone }) {
  const classes = {
    amber: "bg-amber-50 text-amber-700 ring-amber-200",
    blue: "bg-orange-50 text-orange-600 ring-orange-200",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    red: "bg-red-50 text-red-700 ring-red-200",
    slate: "bg-slate-100 text-slate-700 ring-slate-200"
  };
  return <span className={`rounded-full px-1.5 py-0.5 text-[11px] font-bold ring-1 ${classes[tone]}`}>{children}</span>;
}

function CommunicationActionButton({
  action,
  disabledReason,
  label,
  onAction,
  pendingActionId
}: {
  action: ClaimCommunicationActionRequest;
  disabledReason?: string;
  label: string;
  onAction: (action: ClaimCommunicationActionRequest) => void;
  pendingActionId?: string;
}) {
  const pending = pendingActionId === action.id;
  const disabled = Boolean(pendingActionId) || action.kind === "unsupported" || Boolean(disabledReason);

  return (
    <button
      className={`inline-flex min-h-8 items-center justify-center rounded-md border px-3 text-xs font-bold transition focus:outline-none focus:ring-4 focus:ring-orange-100 ${
        disabled
          ? "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400"
          : "border-orange-100 bg-orange-50 text-orange-600 hover:bg-orange-100"
      }`}
      disabled={disabled}
      onClick={() => onAction(action)}
      title={disabledReason}
      type="button"
    >
      {pending ? "Working..." : label}
    </button>
  );
}

function aiFollowUpEmptyTitle(status: AiReviewLifecycleStatus) {
  const normalized = normalizeAiStatus(status);
  if (normalized === "processing") return "Checking for follow-up suggestions";
  if (normalized === "failed" || normalized === "unavailable") return "No follow-up suggestions returned";
  return "No AI follow-up suggestions";
}

function aiFollowUpEmptyDescription(status: AiReviewLifecycleStatus) {
  const normalized = normalizeAiStatus(status);
  if (normalized === "processing") return "Suggestions will appear here once the review finishes.";
  if (normalized === "failed" || normalized === "unavailable") return "The underwriter can still create document requests manually.";
  return "No AI follow-up suggestions at this time.";
}

function normalizeAiStatus(status?: AiReviewLifecycleStatus) {
  const normalized = normalizeEvidenceText(String(status || "not_started"));
  if (normalized.includes("processing") || normalized.includes("running") || normalized.includes("queued")) return "processing";
  if (normalized.includes("failed") || normalized.includes("error")) return "failed";
  if (normalized.includes("unavailable")) return "unavailable";
  if (normalized.includes("complete") || normalized.includes("full review") || normalized.includes("coverage precheck")) return "completed";
  if (normalized.includes("not started") || normalized.includes("draft")) return "not_started";
  return normalized || "not_started";
}

function aiFindingSeverityTone(severity?: string): BadgeTone {
  const normalized = normalizeEvidenceText(severity || "");
  if (normalized.includes("high") || normalized.includes("critical")) return "red";
  if (normalized.includes("medium") || normalized.includes("warning")) return "amber";
  if (normalized.includes("low")) return "blue";
  return "slate";
}

function aiFindingStatusTone(status?: string): BadgeTone {
  const normalized = normalizeEvidenceText(status || "");
  if (normalized.includes("accepted") || normalized.includes("sent") || normalized.includes("complete")) return "green";
  if (normalized.includes("dismiss")) return "slate";
  if (normalized.includes("review")) return "blue";
  return "amber";
}

function suggestedDraftFromAiSuggestion(suggestion: AiFollowUpSuggestion | null): SuggestedEmailDraft {
  if (!suggestion) {
    return {
      subject: "",
      body: "",
      requestedDocumentType: "",
      dueDate: ""
    };
  }
  return {
    subject: suggestion.suggestedEmailDraft?.subject || suggestion.suggestedEmailSubject,
    body: suggestion.suggestedEmailDraft?.body || suggestion.suggestedEmailBody,
    requestedDocumentType:
      suggestion.suggestedEmailDraft?.requestedDocumentType ||
      suggestion.relatedRequirement ||
      suggestion.recommendedRequest,
    dueDate: suggestion.suggestedEmailDraft?.dueDate || ""
  };
}

function evidenceRequestEmailDraftFromClaim(
  claim: Claim,
  workspace: ClaimCommunicationWorkspace
): SuggestedEmailDraft {
  const draft = claim.evidenceRequestDraft;
  const documentNames = evidenceRequestDocumentNames(claim);
  const requestedDocumentType =
    draft?.requestedDocumentType ||
    draft?.requiredDocuments?.[0] ||
    workspace.requests.find((row) => row.status !== "Received")?.document ||
    documentNames[0] ||
    "";

  return {
    subject: draft?.subject || "Additional evidence required for your claim",
    body: draft?.body || defaultEvidenceRequestEmailBody(claim, requestedDocumentType),
    requestedDocumentType,
    dueDate: draft?.dueDate || ""
  };
}

function defaultEvidenceRequestEmailBody(claim: Claim, requestedDocumentType: string) {
  const greeting = claim.clientName ? `Hello ${claim.clientName},` : "Hello,";
  const request = requestedDocumentType
    ? `Please send ${articleFor(requestedDocumentType)} ${requestedDocumentType.toLowerCase()} so we can continue reviewing your claim.`
    : "Please send the missing supporting documents so we can continue reviewing your claim.";

  return `${greeting}\n\n${request}\n\nThank you.`;
}

function ClaimDecisionTab({
  claim,
  emailNotice,
  emailSending,
  evidenceItems,
  justification,
  notice,
  onChangeJustification,
  onChangeSuggestion,
  onDismissSuggestion,
  onSendDecisionEmail,
  onSubmitDecision,
  pendingAction,
  suggestion,
  suggestionVisible
}: {
  claim: Claim;
  emailNotice?: { tone: "danger" | "success"; message: string };
  emailSending: boolean;
  evidenceItems: ClaimEvidenceScaffoldItem[];
  justification: string;
  notice?: { tone: "danger" | "success"; message: string };
  onChangeJustification: (value: string) => void;
  onChangeSuggestion: (value: string) => void;
  onDismissSuggestion: () => void;
  onSendDecisionEmail: () => Promise<void>;
  onSubmitDecision: (action: ClaimDecisionActionKind, justification: string) => Promise<void>;
  pendingAction?: ClaimDecisionActionKind;
  suggestion: string;
  suggestionVisible: boolean;
}) {
  const justificationInputId = "claim-decision-justification";
  const suggestionInputId = "claim-decision-ai-suggestion";
  const justificationRef = useRef<HTMLTextAreaElement | null>(null);
  const suggestionPanelRef = useRef<HTMLDivElement | null>(null);
  const [aiError, setAiError] = useState<string>();
  const [validationError, setValidationError] = useState<string>();
  const [copyStatus, setCopyStatus] = useState<string>();
  const [confirmation, setConfirmation] = useState<ClaimDecisionConfirmation | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const decisionSummary = claimDecisionSummary(claim);
  const alreadyFinal = decisionSummary.final;
  const emailDisabledReason = claimDecisionEmailDisabledReason(claim);
  const emailSent = Boolean(claim.decisionEmailSentAt);
  const emailStatus = claimDecisionEmailStatus(claim);
  const readinessItems = claimDecisionReadinessItems(claim, evidenceItems);
  const trimmedJustification = justification.trim();
  const decisionButtonsDisabled = Boolean(pendingAction) || alreadyFinal;
  const confirmationOpen = Boolean(confirmation);

  useEffect(() => {
    if (!suggestionVisible) return;
    window.setTimeout(() => suggestionPanelRef.current?.focus(), 0);
  }, [suggestionVisible]);

  function closeDecisionConfirmation() {
    setConfirmation(null);
  }

  async function handleRewordWithAi() {
    setAiError(undefined);
    if (!trimmedJustification) {
      setAiError("Enter a decision justification before requesting an AI suggestion.");
      justificationRef.current?.focus();
      return;
    }
    const decisionForSuggestion = claim.decision ?? inferDecisionFromJustification(trimmedJustification);
    setAiLoading(true);
    try {
      const suggestionText = await rewordClaimDecisionJustification({
        decision: decisionForSuggestion,
        justification: trimmedJustification
      });
      onChangeSuggestion(
        sanitizeClaimDecisionAiSuggestion(suggestionText, decisionForSuggestion, claim)
      );
      setCopyStatus(undefined);
    } catch (error) {
      const status = typeof error === "object" && error !== null && "status" in error
        ? (error as { status?: number }).status
        : undefined;
      setAiError(
        status === 503
          ? "AI rewording is not configured for this environment."
          : "AI suggestion could not be generated. Please try again or continue manually."
      );
    } finally {
      setAiLoading(false);
    }
  }

  function requestDecisionConfirmation(action: ClaimDecisionActionKind) {
    if (!trimmedJustification || trimmedJustification.length < 10) {
      setValidationError("Enter a decision justification of at least 10 characters before submitting.");
      justificationRef.current?.focus();
      return;
    }
    setValidationError(undefined);
    setConfirmation(claimDecisionConfirmation(action));
  }

  async function confirmDecision() {
    if (!confirmation) return;
    const action = confirmation.action;
    closeDecisionConfirmation();
    await onSubmitDecision(action, justification);
  }

  function insertSuggestionAtCursor() {
    const text = suggestion.trim();
    if (!text) return;
    const input = justificationRef.current;
    const start = input?.selectionStart ?? justification.length;
    const end = input?.selectionEnd ?? justification.length;
    const nextValue = `${justification.slice(0, start)}${text}${justification.slice(end)}`;
    onChangeJustification(nextValue);
    setCopyStatus(undefined);
    onDismissSuggestion();
    window.setTimeout(() => {
      input?.focus();
      const cursor = start + text.length;
      input?.setSelectionRange(cursor, cursor);
    }, 0);
  }

  function useSuggestion() {
    if (!suggestion.trim()) return;
    onChangeJustification(suggestion);
    setCopyStatus(undefined);
    onDismissSuggestion();
    window.setTimeout(() => justificationRef.current?.focus(), 0);
  }

  async function copySuggestion() {
    setCopyStatus(undefined);
    try {
      await navigator.clipboard.writeText(suggestion);
      setCopyStatus("Copied.");
    } catch {
      setCopyStatus("Copy failed.");
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
      <div className="min-w-0 space-y-5">
        <ClaimWorkspaceSection title="Underwriter decision">
          <div className="space-y-3 rounded-lg border border-slate-200 bg-white px-4 py-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-bold text-slate-950">Decision status:</span>
                  <Badge tone={decisionSummary.tone}>{decisionSummary.label}</Badge>
                </div>
                {decisionSummary.justification ? (
                  <p className="mt-2 text-sm font-medium leading-5 text-slate-700">
                    Final justification: {decisionSummary.justification}
                  </p>
                ) : (
                  <p className="mt-2 text-sm font-medium leading-5 text-slate-600">
                    No final decision has been submitted for this claim.
                  </p>
                )}
              </div>
            </div>
            {notice ? <ValidationBanner message={notice.message} tone={notice.tone} /> : null}
            <div>
              <div className="flex flex-wrap items-end justify-between gap-2">
                <div>
                  <label className="text-sm font-bold text-slate-950" htmlFor={justificationInputId}>
                    Decision justification
                  </label>
                </div>
                <span className="text-xs font-semibold text-slate-500">{justification.length} characters</span>
              </div>
              <textarea
                className="mt-2 min-h-36 w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium leading-6 text-slate-900 shadow-sm transition placeholder:text-slate-400 focus:border-orange-300 focus:outline-none focus:ring-4 focus:ring-orange-100 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
                disabled={alreadyFinal}
                id={justificationInputId}
                onChange={(event) => {
                  setValidationError(undefined);
                  onChangeJustification(event.target.value);
                }}
                placeholder="Summarize the evidence reviewed, coverage reasoning, and decision rationale."
                ref={justificationRef}
                value={justification}
              />
              {validationError ? <p className="mt-1 text-xs font-bold text-red-700">{validationError}</p> : null}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                disabled={alreadyFinal || !trimmedJustification || aiLoading}
                icon={Sparkles}
                onClick={() => void handleRewordWithAi()}
                variant="secondary"
              >
                {aiLoading ? (
                  <ShinyText
                    className="font-bold"
                    color="#2563eb"
                    shineColor="#0f172a"
                    speed={1.45}
                    text="Thinking..."
                  />
                ) : (
                  "Reword with AI"
                )}
              </Button>
            </div>
            {aiError ? <ValidationBanner message={aiError} tone="danger" /> : null}
          </div>
        </ClaimWorkspaceSection>

        <ClaimWorkspaceSection title="Decision actions">
          <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white px-4 py-4 sm:flex-row sm:items-center">
            <Button
              disabled={decisionButtonsDisabled}
              onClick={() => requestDecisionConfirmation("approve")}
              variant="success"
            >
              {pendingAction === "approve" ? "Approving..." : "Approve claim"}
            </Button>
            <Button
              disabled={decisionButtonsDisabled}
              onClick={() => requestDecisionConfirmation("deny")}
              variant="danger"
            >
              {pendingAction === "deny" ? "Denying..." : "Deny claim"}
            </Button>
            <Button
              disabled={decisionButtonsDisabled}
              onClick={() => requestDecisionConfirmation("inspection")}
              variant="warning"
            >
              {pendingAction === "inspection" ? "Requesting..." : "Request on-site inspection"}
            </Button>
          </div>
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-sm font-bold text-slate-950">Claim decision email</h3>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Badge tone={emailStatus.tone}>{emailStatus.label}</Badge>
                  <span className="text-xs font-semibold text-slate-500">
                    Recipient: {claim.contactEmail || "-"}
                  </span>
                </div>
              </div>
              <Button
                disabled={emailSending || Boolean(emailDisabledReason)}
                icon={Send}
                onClick={() => void onSendDecisionEmail()}
                variant="primary"
              >
                {emailSending ? "Sending..." : emailSent ? "Email sent" : "Send decision email"}
              </Button>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <ClaimDecisionContextFact
                label="Sent at"
                value={claim.decisionEmailSentAt ? formatDateTime(claim.decisionEmailSentAt) : "-"}
              />
              <ClaimDecisionContextFact label="Message ID" value={claim.decisionEmailMessageId || "-"} />
            </div>
            {emailDisabledReason ? (
              <p className="mt-2 text-xs font-bold text-slate-500">{emailDisabledReason}</p>
            ) : null}
            {emailNotice ? (
              <ValidationBanner className="mt-3" message={emailNotice.message} tone={emailNotice.tone} />
            ) : null}
          </div>
        </ClaimWorkspaceSection>
      </div>

      <aside className="min-w-0 space-y-5">
        <ClaimWorkspaceSection title="Decision context">
          <div className="space-y-3 rounded-lg border border-slate-200 bg-white px-4 py-4">
            <ClaimDecisionContextFact label="Estimated damage" value={formatCurrency(claim.estimatedDamage)} />
            <ClaimDecisionContextFact label="Incident" value={`${claim.claimType} · ${formatDate(claim.incidentDate)}`} />
            <ClaimDecisionContextFact
              label="Required evidence"
              value={`${evidenceItems.filter((item) => item.hasFile).length}/${evidenceItems.length || 0} received`}
            />
          </div>
        </ClaimWorkspaceSection>

        <ClaimWorkspaceSection title="Decision readiness">
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
            {readinessItems.map((item) => (
              <li className="flex items-start justify-between gap-3 px-3 py-2.5" key={item.label}>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-slate-950">{item.label}</p>
                  <p className="mt-0.5 text-xs font-semibold text-slate-500">{item.detail}</p>
                </div>
                <Badge tone={item.tone}>{item.status}</Badge>
              </li>
            ))}
          </ul>
        </ClaimWorkspaceSection>
      </aside>

      <Modal
        actions={
          <>
            <Button disabled={!suggestion.trim()} onClick={insertSuggestionAtCursor} variant="primary">
              Insert at cursor
            </Button>
            <Button disabled={!suggestion.trim()} onClick={useSuggestion} variant="secondary">
              Use suggestion
            </Button>
            <Button disabled={!suggestion.trim()} onClick={() => void copySuggestion()} variant="secondary">
              Copy
            </Button>
            <Button
              onClick={() => {
                setCopyStatus(undefined);
                onDismissSuggestion();
              }}
              variant="ghost"
            >
              Dismiss
            </Button>
          </>
        }
        onClose={() => {
          setCopyStatus(undefined);
          onDismissSuggestion();
        }}
        open={suggestionVisible}
        title="AI suggested wording"
      >
        <div ref={suggestionPanelRef} tabIndex={-1}>
          <label className="text-sm font-bold text-slate-950" htmlFor={suggestionInputId}>
            AI suggested wording
          </label>
          <textarea
            className="mt-2 min-h-36 w-full resize-y rounded-lg border border-orange-100 bg-white px-3 py-2 text-sm font-medium leading-6 text-slate-900 shadow-sm transition focus:border-orange-300 focus:outline-none focus:ring-4 focus:ring-orange-100"
            id={suggestionInputId}
            onChange={(event) => onChangeSuggestion(event.target.value)}
            value={suggestion}
          />
          {copyStatus ? <p className="mt-2 text-xs font-bold text-slate-500">{copyStatus}</p> : null}
        </div>
      </Modal>

      <Modal
        actions={
          <>
            <Button disabled={Boolean(pendingAction)} onClick={closeDecisionConfirmation} variant="secondary">
              Cancel
            </Button>
            <Button
              disabled={Boolean(pendingAction)}
              onClick={() => void confirmDecision()}
              variant={
                confirmation?.action === "approve" ? "success" : confirmation?.action === "deny" ? "danger" : "secondary"
              }
            >
              Confirm
            </Button>
          </>
        }
        onClose={closeDecisionConfirmation}
        open={confirmationOpen}
        title={confirmation?.title ?? "Submit claim decision"}
      >
        {confirmation?.description}
      </Modal>
    </div>
  );
}

function ClaimDecisionContextFact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-sm font-semibold leading-5 text-slate-900">{value || "-"}</dd>
    </div>
  );
}

function claimDecisionSummary(claim: Claim): {
  final: boolean;
  justification?: string;
  label: string;
  tone: BadgeTone;
} {
  if (hasPersistedClaimDecision(claim)) {
    if (claim.decision === "approved") {
      return {
        final: true,
        justification: claim.decisionJustification,
        label: "Approved",
        tone: "green"
      };
    }
    if (claim.decision === "denied") {
      return {
        final: true,
        justification: claim.decisionJustification,
        label: "Denied",
        tone: "red"
      };
    }
    return {
      final: true,
      justification: claim.decisionJustification,
      label: "On-site inspection requested",
      tone: "amber"
    };
  }

  return {
    final: false,
    label: "Pending",
    tone: "slate"
  };
}

function hasPersistedClaimDecision(claim: Claim) {
  return Boolean(
    claim.decision &&
      claim.decisionStatus &&
      claim.decisionStatus !== "pending" &&
      claim.decisionJustification &&
      claim.decidedAt
  );
}

function claimDecisionEmailDisabledReason(claim: Claim) {
  if (!hasPersistedClaimDecision(claim)) {
    return "Submit a claim decision before sending the decision email.";
  }
  if (claim.decisionEmailSentAt) {
    return "The claim decision email has already been sent.";
  }
  if (!claim.contactEmail.trim()) {
    return "Client email is missing.";
  }
  return "";
}

function claimDecisionEmailStatus(claim: Claim): { label: string; tone: BadgeTone } {
  if (claim.decisionEmailSentAt) {
    return { label: "Sent", tone: "green" };
  }
  if (!hasPersistedClaimDecision(claim)) {
    return { label: "Waiting for decision", tone: "slate" };
  }
  if (!claim.contactEmail.trim()) {
    return { label: "Missing recipient", tone: "red" };
  }
  return { label: "Ready to send", tone: "blue" };
}

const claimDecisionMetaCommentPhrases = [
  "the justification provided is inappropriate",
  "the provided justification is inappropriate",
  "justification provided is inappropriate",
  "lacks professionalism",
  "lack professionalism",
  "unprofessional",
  "inappropriate",
  "please provide",
  "cannot reword",
  "can't reword",
  "unable to reword",
  "i cannot",
  "i can't",
  "as an ai"
];

function sanitizeClaimDecisionAiSuggestion(
  suggestion: string,
  decision: Claim["decision"] | undefined,
  claim: Claim
) {
  const trimmed = suggestion.trim();
  if (!trimmed || isClaimDecisionMetaComment(trimmed)) {
    return claimDecisionFallbackSuggestion(decision, claim);
  }
  return trimmed;
}

function isClaimDecisionMetaComment(suggestion: string) {
  const normalized = suggestion.toLowerCase().replace(/\s+/g, " ");
  return claimDecisionMetaCommentPhrases.some((phrase) => normalized.includes(phrase));
}

function claimDecisionFallbackSuggestion(
  decision: Claim["decision"] | undefined,
  claim: Claim
) {
  const claimType = claim.claimType ? `${claim.claimType.toLowerCase()} claim` : "claim";
  if (decision === "approved") {
    return `Based on the review of this ${claimType}, the submitted information supports approval under the applicable policy terms. The claim has therefore been approved, and the claims team will continue with the next steps.`;
  }
  if (decision === "inspection_requested") {
    return `Based on the review of this ${claimType}, additional on-site assessment is required before a final decision can be completed. An inspection has therefore been requested so the claims team can verify the damage and supporting details.`;
  }
  if (decision === "denied") {
    return `Based on the review of this ${claimType}, the submitted information does not provide sufficient support for approval under the applicable policy terms. The claim has therefore been denied. Please contact the claims team if you would like additional clarification or wish to provide further documentation.`;
  }
  return `Based on the review of this ${claimType}, the submitted information has been assessed under the applicable policy terms. The decision explanation should reflect the evidence available, any remaining documentation gaps, and the policy reasoning used by the claims team.`;
}

function inferDecisionFromJustification(
  justification: string
): Claim["decision"] | undefined {
  const normalized = justification.toLowerCase();
  if (/(deny|denied|reject|rejected|not covered|not eligible|insufficient|no coverage)/.test(normalized)) {
    return "denied";
  }
  if (/(inspect|inspection|on-site|onsite|site visit|assess in person)/.test(normalized)) {
    return "inspection_requested";
  }
  if (/(approve|approved|covered|eligible|valid claim)/.test(normalized)) {
    return "approved";
  }
  return undefined;
}

function claimDecisionConfirmation(action: ClaimDecisionActionKind): ClaimDecisionConfirmation {
  if (action === "approve") {
    return {
      action,
      description: "This will approve the claim and save your justification to the audit trail.",
      title: "Approve this claim?"
    };
  }

  if (action === "deny") {
    return {
      action,
      description: "This will deny the claim and save your justification to the audit trail.",
      title: "Deny this claim?"
    };
  }

  return {
    action,
    description: "This will pause final decisioning and request an inspection for this claim.",
    title: "Request on-site inspection?"
  };
}

function claimDecisionReadinessItems(
  claim: Claim,
  evidenceItems: ClaimEvidenceScaffoldItem[]
): Array<{ detail: string; label: string; status: string; tone: BadgeTone }> {
  const receivedCount = evidenceItems.filter((item) => item.hasFile).length;
  const items: Array<{ detail: string; label: string; status: string; tone: BadgeTone }> = [
    {
      detail: evidenceItems.length
        ? `${receivedCount}/${evidenceItems.length} claim evidence items received.`
        : "No required evidence surfaced in the latest review.",
      label: "Evidence requirements",
      status: evidenceItems.length && receivedCount < evidenceItems.length ? "Open" : "Ready",
      tone: evidenceItems.length && receivedCount < evidenceItems.length ? "amber" : "green"
    },
    {
      detail: `Review state is ${titleCaseLabel(claim.reviewState || "not_started")}.`,
      label: "AI analysis",
      status: claim.reviewState && claim.reviewState !== "not_started" ? "Available" : "Pending",
      tone: claim.reviewState && claim.reviewState !== "not_started" ? "green" : "amber"
    },
    {
      detail: claim.documentConsistency?.message || titleCaseLabel(claim.documentConsistency?.status || "not_started"),
      label: "Document consistency",
      status: claim.documentConsistency?.discrepancyCount ? "Issues" : "Checked",
      tone: claim.documentConsistency?.discrepancyCount ? "amber" : "green"
    },
    {
      detail: claim.status === "inspection_requested" ? "An on-site inspection has been requested." : "No on-site inspection requested.",
      label: "On-site inspection",
      status: claim.status === "inspection_requested" ? "Requested" : "Not requested",
      tone: claim.status === "inspection_requested" ? "amber" : "slate"
    }
  ];

  return items;
}

function evidenceRequestDraftIsSent(draft?: EvidenceRequestDraft | null) {
  return Boolean(draft && (draft.status === "sent" || draft.sendStatus === "mock_sent" || draft.sendStatus === "sent"));
}

function evidenceRequestDraftSendStatusLabel(draft: EvidenceRequestDraft) {
  if (draft.sendStatus === "failed") return "Failed";
  if (evidenceRequestDraftIsSent(draft)) return "Sent";
  return "Draft only";
}

function EvidenceRequestDraftModal({
  draft,
  onClose,
  onSend,
  pendingSend
}: {
  draft: EvidenceRequestDraft | null;
  onClose: () => void;
  onSend: () => void;
  pendingSend?: boolean;
}) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!draft) return;

    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", handleKeyDown);
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [draft, onClose]);

  if (!draft) return null;
  const sent = evidenceRequestDraftIsSent(draft);
  const modalTitle = sent ? "Sent email" : "Evidence request";
  const requestDetails = [
    evidenceRequestDraftSendStatusLabel(draft),
    draft.recipients?.length ? draft.recipients.join(", ") : "",
    draft.sentAt ? formatDateTime(draft.sentAt) : "",
    draft.dueDate || ""
  ].filter(Boolean);

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" role="presentation">
      <button
        aria-label="Close evidence request draft"
        className="absolute inset-0 h-full w-full bg-slate-950/40 backdrop-blur-[1px]"
        onClick={onClose}
        type="button"
      />
      <section
        aria-label="Evidence request draft"
        aria-modal="true"
        className="relative z-10 flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-slate-950">{modalTitle}</h2>
            <p className="mt-1 text-sm font-semibold text-slate-500">{draft.subject}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button
              disabled={pendingSend || sent || !draft.subject.trim() || !draft.body.trim()}
              onClick={onSend}
              type="button"
              variant="primary"
            >
              {sent ? "Sent" : pendingSend ? "Sending" : "Send request"}
            </Button>
            <button
              aria-label="Close evidence request draft"
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-orange-100"
              onClick={onClose}
              ref={closeButtonRef}
              type="button"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="grid min-h-0 flex-1 gap-0 overflow-y-auto lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.55fr)]">
          <div className="border-b border-slate-200 p-5 lg:border-b-0 lg:border-r">
            <div className="mb-3">
              <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">Email title</p>
              <p className="mt-1 text-sm font-bold leading-6 text-slate-950">{draft.subject}</p>
            </div>
            <p className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm font-medium leading-6 text-slate-800">
              {draft.body}
            </p>
          </div>
          <div className="p-5">
            {requestDetails.length ? (
              <p className="text-sm font-semibold leading-6 text-slate-700">{requestDetails.join(" · ")}</p>
            ) : null}
            {draft.sendStatus === "failed" ? (
              <p className="mt-4 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs font-semibold leading-5 text-red-700">
                {draft.sendErrorMessage || "Email delivery failed."}
              </p>
            ) : null}
            <ul className="mt-2 space-y-1 text-sm font-semibold text-slate-700">
              {draft.requiredDocuments.length ? (
                draft.requiredDocuments.map((document) => <li key={document}>{document}</li>)
              ) : (
                <li>No required documents listed.</li>
              )}
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}

function ClaimWorkspaceSection({
  action,
  children,
  title
}: {
  action?: ReactNode;
  children: ReactNode;
  title: string;
}) {
  return (
    <section className="min-w-0">
      <div className="mb-2 flex min-h-9 items-center justify-between gap-3 border-b border-slate-200 pb-1.5">
        <h3 className="text-xs font-bold uppercase tracking-wide text-slate-600">{title}</h3>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

function ClaimFieldGrid({ items }: { items: Array<[string, ReactNode, boolean?]> }) {
  return (
    <dl className="grid gap-x-5 gap-y-3 sm:grid-cols-2">
      {items.map(([label, value, fullWidth]) => (
        <div className={fullWidth ? "sm:col-span-2" : ""} key={label}>
          <dt className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</dt>
          <dd className="mt-0.5 break-words text-sm font-semibold leading-5 text-slate-950">{value || "-"}</dd>
        </div>
      ))}
    </dl>
  );
}

function ExpandableClaimDescription({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const previewLimit = 120;
  const normalizedText = text.trim() || "-";
  const canExpand = normalizedText.length > previewLimit;
  const previewText = canExpand && !expanded
    ? `${normalizedText.slice(0, previewLimit).trimEnd()}...`
    : normalizedText;

  return (
    <span className="block text-sm font-medium leading-5 text-slate-800">
      <span>{previewText}</span>
      {canExpand ? (
        <button
          aria-expanded={expanded}
          className="ml-2 inline-flex min-h-6 items-center rounded-md px-1 text-xs font-bold text-orange-600 transition hover:bg-orange-50 hover:text-orange-700 focus:outline-none focus:ring-4 focus:ring-orange-100"
          onClick={() => setExpanded((current) => !current)}
          type="button"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      ) : null}
    </span>
  );
}

function ClaimTinyFact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-bold text-slate-950">{value}</dd>
    </div>
  );
}

function ClientLegalDocumentsTable({
  error,
  loading,
  onSelectDocument,
  rows
}: {
  error?: string;
  loading: boolean;
  onSelectDocument: (document: CustomerLegalDocument) => void;
  rows: CustomerLegalDocument[];
}) {
  if (loading) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-500">
        Loading client legal documents.
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-3 text-sm font-semibold text-red-700">
        {error}
      </div>
    );
  }

  if (!rows.length) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-500">
        No client legal documents are available for this profile.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-xs">
          <thead className="bg-slate-50">
            <tr>
              {["Document type", "File name", "Source"].map((header) => (
                <th className="px-3 py-1.5 text-left text-[11px] font-bold uppercase tracking-wide text-slate-500" key={header}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {rows.map((row) => (
              <tr
                className="cursor-pointer transition hover:bg-orange-50/40 focus-within:bg-orange-50/40"
                key={row.id}
                onClick={() => onSelectDocument(row)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectDocument(row);
                  }
                }}
                role="button"
                tabIndex={0}
              >
                <td className="whitespace-nowrap px-3 py-2 font-semibold text-slate-900">
                  <span className="rounded-md text-left font-semibold text-orange-600">
                    {row.label || row.document_type}
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.file_name}</td>
                <td className="whitespace-nowrap px-3 py-2 text-slate-700">{formatClientDocumentSource(row.source)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatClientDocumentSource(source?: string | null) {
  if (source === "legal_document") return "Legal document";
  if (source === "client_upload") return "Client upload";
  if (source === "employee_upload") return "Employee upload";
  return "Client profile";
}

type ClaimEvidenceDocument = Claim["evidence"][number];
type ClaimEvidenceRequirementItem = NonNullable<Claim["requiredEvidence"]>[number];

function buildClaimEvidenceScaffoldItems(claim: Claim): ClaimEvidenceScaffoldItem[] {
  const requirements = claim.requiredEvidence ?? [];
  const uploadedDate = claim.createdAt ? formatDate(claim.createdAt) : formatDate(claim.incidentDate);
  const claimEvidenceDocuments = (Array.isArray(claim.evidence) ? claim.evidence : []).filter(
    isClaimEvidenceDocumentForEvidenceTab
  );
  const documentGroups = groupClaimEvidenceDocuments(claimEvidenceDocuments);
  const uploadedItems = documentGroups.flatMap((documents) =>
    claimEvidenceItemFromDocuments(documents, requirements, uploadedDate)
  );
  const pendingItems = requirements
    .filter((requirement) =>
      !documentGroups.some((documents) =>
        documents.some((document) => documentMatchesEvidenceRequirement(document, requirement))
      )
    )
    .map((requirement, index) => claimEvidenceItemFromRequirement(claim, requirement, index));

  return [...uploadedItems, ...pendingItems];
}

function groupClaimEvidenceDocuments(evidence: ClaimEvidenceDocument[]): ClaimEvidenceDocument[][] {
  const groups = new Map<string, ClaimEvidenceDocument[]>();
  evidence.forEach((document) => {
    const key = documentIdentityKey(document);
    groups.set(key, [...(groups.get(key) ?? []), document]);
  });
  return Array.from(groups.values());
}

function claimEvidenceItemFromDocuments(
  documents: ClaimEvidenceDocument[],
  requirements: ClaimEvidenceRequirementItem[],
  uploadedDate: string
): ClaimEvidenceScaffoldItem[] {
  const groupText = documents.map(claimEvidenceDocumentText).join(" ");
  const legalProfileDocument = isClientLegalProfileDocumentText(groupText);
  const claimEvidenceCategory = inferClaimEvidenceCategory(groupText);
  const requiredByClaim = documents.some((document) =>
    requirements.some((requirement) => documentMatchesEvidenceRequirement(document, requirement))
  );
  const claimSpecificDocument = Boolean(claimEvidenceCategory && claimEvidenceCategory !== "identity") || requiredByClaim;

  if (legalProfileDocument && !claimSpecificDocument) return [];

  const selectedDocument = selectClaimEvidenceDocument(documents);
  const duplicateIssue = documents.length > 1 ? "Duplicate attachment consolidated into one evidence row." : undefined;
  const classificationIssue =
    legalProfileDocument && claimSpecificDocument
      ? "Classification mismatch: this file is tagged as both client legal/profile document and claim evidence."
      : undefined;
  const issue = classificationIssue ?? duplicateIssue;
  const extractionInfo = claimEvidenceExtractionInfo(selectedDocument);
  const confidence = stringFromMetadata(selectedDocument.metadata?.confidence);
  const uploadStatus = stringFromMetadata(selectedDocument.metadata?.status);
  const reviewStatus = stringFromMetadata(selectedDocument.metadata?.review_status);

  return [
    {
      id: selectedDocument.id || documentIdentityKey(selectedDocument),
      name: claimEvidenceDisplayName(selectedDocument, groupText),
      type: selectedDocument.type || inferDocumentType(selectedDocument.fileName),
      contentType: selectedDocument.contentType,
      uploadStatus: uploadStatus || "Received",
      confidence: confidence || (issue ? "Low confidence" : "Pending classification"),
      fileName: selectedDocument.fileName,
      fileUrl: selectedDocument.fileUrl,
      previewUrl: selectedDocument.url,
      source: inferClaimEvidenceSource(selectedDocument),
      uploadedDate,
      reviewStatus: issue ? "Needs review" : reviewStatus || extractionInfo.reviewStatus,
      primaryAction: issue ? "Review" : "Preview",
      hasFile: true,
      issue
    }
  ];
}

function stringFromMetadata(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const normalized = value.trim();
  return normalized ? normalized : undefined;
}

function claimEvidenceExtractionInfo(document: ClaimEvidenceDocument) {
  const metadata = document.metadata ?? {};
  const provenance = stringFromMetadata(metadata.extraction_provenance) || "unavailable";
  const status = stringFromMetadata(metadata.extraction_status) || "unavailable";

  return {
    reviewStatus: extractionReviewStatus(status, provenance)
  };
}

function extractionReviewStatus(status: string, provenance: string) {
  const normalizedStatus = status.toLowerCase();
  const normalizedProvenance = provenance.toLowerCase();
  if (normalizedProvenance === "demo_mock") return "Demo/mock extraction";
  if (normalizedStatus === "completed") return "Extraction completed";
  if (normalizedStatus === "pending") return "Extraction pending";
  return "Manual review required";
}

function FormattedClaimSummary({ className = "", text }: { className?: string; text: string }) {
  const blocks = parseClaimSummaryBlocks(text);
  if (!blocks.length) return null;

  return (
    <div className={`space-y-2 text-sm font-semibold leading-6 text-slate-700 ${className}`}>
      {blocks.map((block, index) => {
        if (block.kind === "list") {
          return (
            <ul className="list-disc space-y-1 pl-5" key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{item}</li>
              ))}
            </ul>
          );
        }
        if (block.kind === "heading") {
          return (
            <p className="text-sm font-bold text-slate-950" key={index}>
              {block.text}
            </p>
          );
        }
        return <p key={index}>{block.text}</p>;
      })}
    </div>
  );
}

type ClaimSummaryBlock =
  | { kind: "heading"; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; items: string[] };

function parseClaimSummaryBlocks(text: string): ClaimSummaryBlock[] {
  const blocks: ClaimSummaryBlock[] = [];
  let pendingList: string[] = [];

  function flushList() {
    if (pendingList.length) {
      blocks.push({ kind: "list", items: pendingList });
      pendingList = [];
    }
  }

  normalizeClaimSummaryTextForDisplay(text).split(/\r?\n/).forEach((rawLine) => {
    const line = cleanClaimSummaryLine(rawLine);
    if (!line) {
      flushList();
      return;
    }

    const bullet = line.match(/^[-*]\s+(.+)$/) ?? line.match(/^\d+[.)]\s+(.+)$/);
    if (bullet) {
      pendingList.push(cleanClaimUiTitle(bullet[1]));
      return;
    }

    flushList();
    const heading = line.endsWith(":");
    const cleanLine = cleanClaimUiTitle(heading ? line.replace(/:$/, "") : line);
    blocks.push({ kind: heading ? "heading" : "paragraph", text: cleanLine });
  });

  flushList();
  return blocks;
}

function normalizeClaimSummaryTextForDisplay(text: string) {
  return String(text || "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(
      /(Evidence signals|Out of place\s*\/\s*needs review|Out of place needs review|Follow[- ]up|Needs review|Recommendation|Recommended next step|Document interpretation|AI analysis)\s*:/gi,
      (match, label: string, offset: number, fullText: string) => {
        const prefix = offset > 0 && fullText[offset - 1] !== "\n" ? "\n" : "";
        return `${prefix}${canonicalClaimSummarySectionLabel(label)}:`;
      }
    )
    .replace(/:\s*[-*]\s+/g, ":\n- ")
    .replace(/([.!?])\s+[-*]\s+(?=[A-Z0-9"'])/g, "$1\n- ")
    .replace(/\s+[-*]\s+(?=[A-Z0-9"'])/g, "\n- ");
}

function canonicalClaimSummarySectionLabel(value: string) {
  const normalized = normalizeEvidenceText(value).replace(/\s+\/\s+/g, " / ");
  const labels: Record<string, string> = {
    "ai analysis": "AI analysis",
    "document interpretation": "Document interpretation",
    "evidence signals": "Evidence signals",
    "follow up": "Follow-up",
    "needs review": "Needs review",
    "out of place / needs review": "Out of place / needs review",
    "out of place needs review": "Out of place / needs review",
    "recommendation": "Recommendation",
    "recommended next step": "Recommended next step"
  };
  return labels[normalized] ?? cleanClaimUiTitle(value.replace(/:$/, ""));
}

function claimSummarySectionText(text: string, sectionLabels: string[]) {
  const wantedLabels = new Set(sectionLabels.map((label) => normalizeEvidenceText(label)));
  const collected: string[] = [];
  let collecting = false;

  parseClaimSummaryBlocks(text).forEach((block) => {
    if (block.kind === "heading") {
      collecting = wantedLabels.has(normalizeEvidenceText(block.text));
      return;
    }
    if (!collecting) return;
    if (block.kind === "list") {
      collected.push(...block.items);
      return;
    }
    collected.push(block.text);
  });

  return collected.join(" ").trim();
}

function claimSummaryPreviewText(text: string) {
  const followUpText = claimSummarySectionText(text, ["Follow-up", "Follow up"]);
  if (followUpText) return followUpText;

  const reviewConcernText = claimSummarySectionText(text, [
    "Out of place / needs review",
    "Out of place needs review",
    "Needs review"
  ]);
  if (reviewConcernText) return reviewConcernText;

  for (const block of parseClaimSummaryBlocks(text)) {
    if (block.kind === "list" && block.items[0]) return block.items[0];
    if (block.kind === "paragraph") return block.text;
  }

  return cleanClaimUiTitle(text);
}

function cleanClaimSummaryLine(value: string) {
  return value
    .replace(/^#+\s*/, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/(^|\s)\*([^*]+)\*(?=\s|$)/g, "$1$2")
    .replace(/(^|\s)_([^_]+)_(?=\s|$)/g, "$1$2")
    .trim();
}

function cleanClaimUiTitle(value: string) {
  const originalText = cleanClaimSummaryLine(String(value || ""));
  const text = originalText
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const normalized = text.toLowerCase().replace(/\s*\/\s*/g, " / ");
  const replacements: Record<string, string> = {
    "ai analysis": "AI analysis",
    "document summary": "AI analysis",
    "evidence signals": "Evidence signals",
    "extracted fields / ai interpretation": "Document interpretation",
    "follow up": "Follow-up",
    "out of place / needs review": "Out of place / needs review",
    "out of place needs review": "Out of place / needs review",
    "summary / interpretation": "AI analysis"
  };
  if (replacements[normalized]) return replacements[normalized];
  const noSlash = text.replace(/\s*\/\s*/g, " ").replace(/:$/, "");
  const compactLabel = noSlash.split(/\s+/).length <= 4 && !/[.!?:]/.test(noSlash);
  return compactLabel ? titleCaseLabel(noSlash) : noSlash;
}

function claimEvidenceItemFromRequirement(
  claim: Claim,
  requirement: ClaimEvidenceRequirementItem,
  index: number
): ClaimEvidenceScaffoldItem {
  const requestDraft = evidenceRequestDraftForRequirement(claim, requirement);
  const requestExists = Boolean(requestDraft);
  const requestSent = evidenceRequestDraftIsSent(requestDraft);
  const priorRequestSent = evidenceRequirementWasSent(claim, requirement, index);
  const status = evidenceRequirementStatus(requirement, requestExists || priorRequestSent);
  return {
    id: `required-${slugFileName(requirement.requirementType || requirement.acceptableDocuments.join("-") || "evidence")}-${index}`,
    name: evidenceRequirementDisplayName(requirement),
    type: "Required document",
    uploadStatus: status,
    confidence: "Not available",
    fileName: "Awaiting upload",
    source: "Claim requirement",
    uploadedDate: requestExists && requestDraft?.createdAt ? formatDate(requestDraft.createdAt) : "-",
    reviewStatus: requestSent || priorRequestSent ? "Request sent" : requestExists ? "Draft ready" : "Pending upload",
    primaryAction: requestSent || priorRequestSent ? "Sent" : requestExists ? "View request" : "Request",
    hasFile: false,
    issue: requirement.reason || undefined
  };
}

function evidenceRequestDraftForRequirement(
  claim: Claim,
  requirement: ClaimEvidenceRequirementItem
) {
  const draft = claim.evidenceRequestDraft;
  if (!draft) return undefined;
  return evidenceRequestDraftMatchesRequirement(draft, requirement) ? draft : undefined;
}

function evidenceRequestDraftMatchesRequirement(
  draft: EvidenceRequestDraft,
  requirement: ClaimEvidenceRequirementItem
) {
  const draftValues = [
    draft.requestedDocumentType,
    ...(draft.requiredDocuments ?? [])
  ].map(normalizeEvidenceText).filter(Boolean);
  if (!draftValues.length) return false;

  const requirementValues = [
    requirement.requirementType,
    evidenceRequirementDisplayName(requirement),
    ...requirement.acceptableDocuments,
    ...requirement.acceptableDocuments.map(titleCaseEvidenceLabel)
  ].map(normalizeEvidenceText).filter(Boolean);

  return requirementValues.some((requirementValue) =>
    draftValues.some((draftValue) =>
      draftValue === requirementValue ||
      draftValue.includes(requirementValue) ||
      requirementValue.includes(draftValue)
    )
  );
}

function evidenceRequirementWasSent(
  claim: Claim,
  requirement: ClaimEvidenceRequirementItem,
  index: number
) {
  const state = claim.communicationSuggestionStates?.[
    evidenceRequirementSuggestionId(requirement, index)
  ];
  return aiSuggestionStatusIsSent(state?.status);
}

function evidenceRequirementSuggestionId(
  requirement: ClaimEvidenceRequirementItem,
  index: number
) {
  const documentName = evidenceRequirementDisplayName(requirement);
  return `ai-follow-up-${slugFileName(requirement.requirementType || documentName)}-${index}`;
}

function buildClaimCommunicationWorkspace(
  claim: Claim,
  evidenceItems: ClaimEvidenceScaffoldItem[]
): ClaimCommunicationWorkspace {
  const requests = buildClaimCommunicationRequests(claim, evidenceItems);
  const inboundEmails = buildInboundEmailItems(claim, evidenceItems);
  const automation = buildClaimEmailAutomationPanel(claim, requests);
  const aiReviewFindings = buildClaimAiReviewFindings(claim, evidenceItems);
  const aiFollowUpSuggestions = buildClaimAiFollowUpSuggestions(claim, aiReviewFindings)
    .filter((suggestion) => !isInactiveAiSuggestion(suggestion));
  const timeline = buildCommunicationTimeline(claim, requests, inboundEmails);

  return {
    aiReviewStatus: claim.aiReviewStatus || aiReviewStatusFromClaim(claim),
    aiReviewFindings,
    aiFollowUpSuggestions,
    automation,
    inboundEmails,
    requests,
    timeline
  };
}

function claimNeedsCommunicationAnalysis(claim: Claim) {
  const reviewState = normalizeEvidenceText(claim.reviewState);
  if (hasCommunicationAnalysisOutput(claim)) return false;
  if (reviewState === "not started" || reviewState === "coverage precheck only") return true;
  return !reviewState && Boolean(claim.availableActions?.includes("start_analysis"));
}

function hasCommunicationAnalysisOutput(claim: Claim) {
  const documentConsistencyStatus = normalizeEvidenceText(claim.documentConsistency?.status);
  return Boolean(
    claim.requiredEvidence?.length ||
      claim.aiReviewFindings?.length ||
      claim.aiFollowUpSuggestions?.length ||
      (documentConsistencyStatus && documentConsistencyStatus !== "not started")
  );
}

function buildClaimAiReviewFindings(
  claim: Claim,
  evidenceItems: ClaimEvidenceScaffoldItem[]
): AiReviewFinding[] {
  const backendFindings = claim.aiReviewFindings ?? [];
  const requirementFindings = (claim.requiredEvidence ?? []).map((requirement, index) =>
    aiReviewFindingFromRequirement(claim, requirement, evidenceItems, index)
  );
  const discrepancyFindings = (claim.discrepancies ?? []).map((finding, index) =>
    aiReviewFindingFromDocumentFinding(claim, finding, index)
  );

  return uniqueAiFindings([...backendFindings, ...requirementFindings, ...discrepancyFindings]);
}

function aiReviewFindingFromRequirement(
  claim: Claim,
  requirement: ClaimEvidenceRequirementItem,
  evidenceItems: ClaimEvidenceScaffoldItem[],
  index: number
): AiReviewFinding {
  const evidenceItem = findEvidenceItemForRequirement(evidenceItems, requirement);
  const status = evidenceItem?.hasFile ? "Reviewed" : evidenceRequirementStatus(requirement, Boolean(claim.evidenceRequestDraft));
  const requirementName = evidenceRequirementDisplayName(requirement);
  return {
    id: `required-evidence-finding-${slugFileName(requirement.requirementType || requirementName)}-${index}`,
    claimId: claim.id,
    findingType: evidenceItem?.hasFile ? "Evidence requirement review" : "Missing required document",
    severity: requirement.severity || (evidenceItem?.hasFile ? "low" : "medium"),
    description: requirement.reason || `${requirementName} is required for this claim review.`,
    relatedDocument: evidenceItem?.fileName,
    relatedRequirement: requirementName,
    recommendation: requirement.suggestedNextAction || "Request the missing document from the client.",
    suggestedFollowUpAction: evidenceItem?.hasFile ? "Review evidence" : "Create document request",
    confidence: evidenceItem?.confidence || "Medium",
    reviewStatus: status,
    createdAt: claim.createdAt,
    source: "required_evidence"
  };
}

function aiReviewFindingFromDocumentFinding(
  claim: Claim,
  finding: NonNullable<Claim["discrepancies"]>[number],
  index: number
): AiReviewFinding {
  return {
    id: `document-finding-${slugFileName(finding.field || finding.sourceDocument || "evidence")}-${index}`,
    claimId: claim.id,
    findingType: "Document mismatch",
    severity: finding.severity || "medium",
    description: finding.message || `${finding.field || "Evidence"} needs review.`,
    relatedDocument: finding.sourceDocument,
    relatedRequirement: finding.field || undefined,
    recommendation: "Review the mismatch before deciding whether to request more information.",
    suggestedFollowUpAction: "Review evidence issue",
    confidence: "Medium",
    reviewStatus: "New",
    createdAt: claim.createdAt,
    source: "document_consistency"
  };
}

function uniqueAiFindings(findings: AiReviewFinding[]) {
  const unique = new Map<string, AiReviewFinding>();
  findings.forEach((finding) => unique.set(finding.id, finding));
  return Array.from(unique.values());
}

function buildClaimAiFollowUpSuggestions(
  claim: Claim,
  aiFindings: AiReviewFinding[]
): AiFollowUpSuggestion[] {
  const backendSuggestions = claim.aiFollowUpSuggestions ?? [];
  const generatedSuggestions = buildGeneratedClaimAiFollowUpSuggestions(claim, aiFindings);

  return applyCommunicationSuggestionLifecycle(
    claim,
    uniqueAiFollowUpSuggestions([...backendSuggestions, ...generatedSuggestions])
  );
}

function buildGeneratedClaimAiFollowUpSuggestions(
  claim: Claim,
  aiFindings: AiReviewFinding[]
): AiFollowUpSuggestion[] {
  const requirementSuggestions = (claim.requiredEvidence ?? [])
    .map((requirement, index) => aiFollowUpSuggestionFromRequirement(claim, requirement, index));
  const findingSuggestions = aiFindings
    .filter(shouldCreateAiFollowUpSuggestion)
    .map((finding, index) => aiFollowUpSuggestionFromFinding(claim, finding, index));

  return uniqueAiFollowUpSuggestions([...requirementSuggestions, ...findingSuggestions]);
}

function uniqueAiFollowUpSuggestions(suggestions: AiFollowUpSuggestion[]) {
  const unique = new Map<string, AiFollowUpSuggestion>();
  suggestions.forEach((suggestion) => {
    const key = aiFollowUpSuggestionUniquenessKey(suggestion);
    if (!unique.has(key)) unique.set(key, suggestion);
  });
  return Array.from(unique.values());
}

function aiFollowUpSuggestionUniquenessKey(suggestion: AiFollowUpSuggestion) {
  const target =
    normalizeAiSuggestionTarget(suggestion.relatedRequirement) ||
    normalizeAiSuggestionTarget(suggestion.suggestedEmailDraft?.requestedDocumentType) ||
    normalizeAiSuggestionTarget(suggestion.relatedDocumentId) ||
    normalizeAiSuggestionTarget(suggestion.relatedRequirementId) ||
    normalizeAiSuggestionTarget(suggestion.title);
  return target || suggestion.id;
}

function normalizeAiSuggestionTarget(value: unknown) {
  return normalizeEvidenceText(value)
    .replace(/^request follow-up for /, "")
    .replace(/^request follow up for /, "")
    .replace(/^request /, "")
    .replace(/^additional /, "")
    .replace(/ required for your claim$/, "")
    .trim();
}

function evidenceRequestDraftMatchesAiSuggestion(
  draft: EvidenceRequestDraft | null | undefined,
  suggestion: AiFollowUpSuggestion
) {
  if (!draft) return false;
  if (draft.sourceSuggestionId && draft.sourceSuggestionId === suggestion.id) return true;

  const suggestionTarget = aiFollowUpSuggestionUniquenessKey(suggestion);
  const draftTargets = [draft.requestedDocumentType, ...(draft.requiredDocuments ?? [])]
    .map(normalizeAiSuggestionTarget)
    .filter(Boolean);
  return Boolean(suggestionTarget && draftTargets.includes(suggestionTarget));
}

function applyCommunicationSuggestionLifecycle(
  claim: Claim,
  suggestions: AiFollowUpSuggestion[]
): AiFollowUpSuggestion[] {
  const states = claim.communicationSuggestionStates ?? {};
  return suggestions.map((suggestion) => {
    const state = states[suggestion.id];
    const matchingDraft = evidenceRequestDraftMatchesAiSuggestion(
      claim.evidenceRequestDraft,
      suggestion
    )
      ? claim.evidenceRequestDraft
      : undefined;
    const status = evidenceRequestDraftIsSent(matchingDraft)
      ? "sent"
      : state?.status || suggestion.status;
    return {
      ...suggestion,
      status: titleCaseLabel(status),
      suggestedEmailDraft: matchingDraft
        ? {
            body: matchingDraft.body,
            dueDate: matchingDraft.dueDate,
            requestedDocumentType:
              matchingDraft.requestedDocumentType ||
              matchingDraft.requiredDocuments[0],
            subject: matchingDraft.subject
          }
        : suggestion.suggestedEmailDraft
    };
  });
}

function isInactiveAiSuggestion(suggestion: AiFollowUpSuggestion) {
  const status = normalizeEvidenceText(suggestion.status);
  return status.includes("dismiss") || aiSuggestionStatusIsSent(status);
}

function aiSuggestionDraftDisabledReason(suggestion: AiFollowUpSuggestion) {
  if (aiSuggestionStatusIsSent(suggestion.status)) return "This request has already been sent.";
  return undefined;
}

function aiSuggestionStatusIsSent(status: unknown) {
  return ["email sent", "mock sent", "request sent", "sent"].includes(normalizeEvidenceText(status));
}

function shouldCreateAiFollowUpSuggestion(finding: AiReviewFinding) {
  const text = normalizeEvidenceText(
    `${finding.findingType} ${finding.description} ${finding.recommendation} ${finding.suggestedFollowUpAction}`
  );
  return [
    "missing required document",
    "insufficient proof",
    "unofficial document",
    "wrong document type",
    "low confidence extraction",
    "document mismatch",
    "evidence does not satisfy requirement",
    "additional official document recommended",
    "clarification needed",
    "clarify",
    "follow up",
    "follow up email recommended",
    "create document request",
    "request evidence"
  ].some((phrase) => text.includes(phrase));
}

function aiFollowUpSuggestionFromRequirement(
  claim: Claim,
  requirement: ClaimEvidenceRequirementItem,
  index: number
): AiFollowUpSuggestion {
  const documentName = evidenceRequirementDisplayName(requirement);
  const acceptableDocument = requirement.acceptableDocuments[0] || documentName;
  const subject = `Additional ${documentName.toLowerCase()} required for your claim`;
  const body = [
    `To continue reviewing your claim, please provide ${articleFor(acceptableDocument)} ${acceptableDocument}.`,
    requirement.reason ? `Reason: ${requirement.reason}` : "",
    "Please reply with the document attached or upload it through your client account."
  ].filter(Boolean).join("\n\n");

  return {
    id: `ai-follow-up-${slugFileName(requirement.requirementType || documentName)}-${index}`,
    claimId: claim.id,
    title: `Request ${documentName.toLowerCase()}`,
    reason: requirement.reason || `${documentName} is required for the claim review.`,
    recommendedRequest: `Ask the client to provide ${articleFor(acceptableDocument)} ${acceptableDocument}.`,
    priority: titleCaseLabel(requirement.severity || "Medium"),
    confidence: "Medium",
    relatedRequirementId: `required-evidence-finding-${slugFileName(requirement.requirementType || documentName)}-${index}`,
    relatedRequirement: documentName,
    relatedEvidenceIssue: requirement.reason || "Missing required evidence",
    suggestedEmailSubject: subject,
    suggestedEmailBody: body,
    suggestedEmailDraft: {
      subject,
      body,
      requestedDocumentType: documentName
    },
    status: "New",
    createdAt: claim.createdAt,
    fullReasoning: requirement.reason || `${documentName} is listed by the claim review as required evidence.`
  };
}

function aiFollowUpSuggestionFromFinding(
  claim: Claim,
  finding: AiReviewFinding,
  index: number
): AiFollowUpSuggestion {
  const followUpText = claimSummarySectionText(finding.description, ["Follow-up", "Follow up"]);
  const reviewConcernText = claimSummarySectionText(finding.description, [
    "Out of place / needs review",
    "Out of place needs review",
    "Needs review"
  ]);
  const requestName = finding.relatedRequirement || finding.relatedDocument || titleCaseLabel(finding.findingType);
  const subject = followUpText ? "Clarification needed for your claim" : "Additional information required for your claim";
  const body = followUpText
    ? [
        "To continue reviewing your claim, please clarify the point below.",
        followUpText,
        reviewConcernText ? `Reason: ${reviewConcernText}` : "",
        "Please reply with the clarification or any supporting document attached."
      ].filter(Boolean).join("\n\n")
    : [
        "To continue reviewing your claim, please provide the additional information or document listed below.",
        finding.recommendation || finding.description,
        "Please reply with the document attached or upload it through your client account."
      ].filter(Boolean).join("\n\n");
  const recommendedRequest = finding.recommendation || followUpText || "Ask the client for the missing or corrected evidence.";

  return {
    id: `ai-follow-up-finding-${slugFileName(finding.id)}-${index}`,
    claimId: claim.id,
    title: followUpText ? "Request clarification" : `Request follow-up for ${requestName.toLowerCase()}`,
    reason: finding.description,
    recommendedRequest,
    priority: titleCaseLabel(finding.severity || "Medium"),
    confidence: finding.confidence || "Medium",
    relatedRequirementId: finding.id,
    relatedDocumentId: finding.relatedDocument,
    relatedRequirement: finding.relatedRequirement,
    relatedEvidenceIssue: finding.findingType,
    suggestedEmailSubject: subject,
    suggestedEmailBody: body,
    suggestedEmailDraft: {
      subject,
      body,
      requestedDocumentType: followUpText ? "Clarification" : requestName
    },
    status: "New",
    createdAt: finding.createdAt || claim.createdAt,
    fullReasoning: recommendedRequest
  };
}

function aiReviewStatusFromClaim(claim: Claim): AiReviewLifecycleStatus {
  if (claim.documentConsistency?.status === "not_started") return "not_started";
  if (claim.reviewState && claim.reviewState !== "not_started") return "completed";
  return "not_started";
}

function articleFor(value: string) {
  return /^[aeiou]/i.test(value.trim()) ? "an" : "a";
}

function buildClaimEmailAutomationPanel(
  claim: Claim,
  requests: ClaimCommunicationRequestRow[]
): ClaimEmailAutomationPanel {
  const draft = claim.evidenceRequestDraft;
  const hasOpenRequests = requests.some((row) => row.status !== "Received");

  if (draft) {
    const sent = evidenceRequestDraftIsSent(draft);
    const failed = draft.sendStatus === "failed";
    return {
      status: sent ? "Sent" : failed ? "Failed" : "Draft ready",
      statusTone: sent ? "green" : failed ? "red" : "blue",
      recipient: claim.contactEmail || "-",
      lastEmailSent: draft.sentAt ? formatDateTime(draft.sentAt) : "Not sent",
      subject: draft.subject || "-",
      deliveryStatus: evidenceRequestDraftSendStatusLabel(draft),
      actionLabel: "View request",
      actionKind: "view_draft"
    };
  }

  if (hasOpenRequests) {
    return {
      status: "Draft needed",
      statusTone: "amber",
      recipient: claim.contactEmail || "-",
      lastEmailSent: "Not sent",
      subject: "Additional evidence required for your claim",
      deliveryStatus: "Not started",
      actionLabel: "Create document request",
      actionKind: "generate_draft"
    };
  }

  return {
    status: "Not active",
    statusTone: "slate",
    recipient: claim.contactEmail || "-",
    lastEmailSent: "Not needed",
    subject: "-",
    deliveryStatus: "No open request",
    actionLabel: "Create document request",
    actionKind: "generate_draft"
  };
}

function buildClaimCommunicationRequests(
  claim: Claim,
  evidenceItems: ClaimEvidenceScaffoldItem[]
): ClaimCommunicationRequestRow[] {
  const requirements = claim.requiredEvidence ?? [];
  const draft = claim.evidenceRequestDraft;

  if (!requirements.length && draft?.requiredDocuments.length) {
    return draft.requiredDocuments.map((document, index) =>
      communicationRequestRowFromDraftDocument(document, index)
    );
  }

  return requirements.map((requirement, index) => {
    const evidenceItem = findEvidenceItemForRequirement(evidenceItems, requirement);
    const received = Boolean(evidenceItem?.hasFile);
    const matchingDraft = draft && evidenceRequestDraftMatchesRequirement(draft, requirement) ? draft : undefined;
    const priorRequestSent = evidenceRequirementWasSent(claim, requirement, index);
    const status = received ? "Received" : evidenceRequirementStatus(requirement, Boolean(matchingDraft) || priorRequestSent);
    const actionKind: ClaimCommunicationActionKind = received
      ? "view_document"
      : matchingDraft
        ? "view_draft"
        : priorRequestSent
          ? "unsupported"
          : "generate_draft";

    return {
      id: `request-${slugFileName(requirement.requirementType || requirement.acceptableDocuments.join("-") || "evidence")}-${index}`,
      document: evidenceRequirementDisplayName(requirement),
      status,
      statusTone: evidenceUploadTone(status),
      actionLabel: received ? "Open preview" : matchingDraft ? "View request" : priorRequestSent ? "Sent" : "Create document request",
      actionKind,
      evidenceItemId: evidenceItem?.id
    };
  });
}

function evidenceRequestDocumentNames(claim: Claim) {
  const requirementNames = (claim.requiredEvidence ?? [])
    .map(evidenceRequirementDisplayName)
    .filter(Boolean);
  if (requirementNames.length) return Array.from(new Set(requirementNames));
  return claim.evidenceRequestDraft?.requiredDocuments ?? [];
}

function communicationRequestRowFromDraftDocument(
  document: string,
  index: number
): ClaimCommunicationRequestRow {
  return {
    id: `draft-request-${slugFileName(document || "evidence")}-${index}`,
    document: titleCaseEvidenceLabel(document),
    status: "Drafted",
    statusTone: "blue",
    actionLabel: "View request",
    actionKind: "view_draft"
  };
}

function buildInboundEmailItems(
  claim: Claim,
  evidenceItems: ClaimEvidenceScaffoldItem[]
): ClaimInboundEmailItem[] {
  const inboundDocuments = (claim.evidence ?? []).filter(isInboundEmailDocument);
  const groups = new Map<string, ClaimEvidenceDocument[]>();

  inboundDocuments.forEach((document) => {
    const key = [
      documentMetadataText(document, "sender_email") || claim.contactEmail || "unknown-sender",
      documentMetadataText(document, "received_at") || "unknown-time"
    ].join("|");
    groups.set(key, [...(groups.get(key) ?? []), document]);
  });

  return Array.from(groups.entries()).map(([key, documents], index) => {
    const [sender, receivedAt] = key.split("|");
    const attachments = documents.map((document) =>
      inboundAttachmentItemFromDocument(claim, document, evidenceItems)
    );
    const needsReview = attachments.some((attachment) => attachment.actionRequired);
    return {
      id: `inbound-email-${index}`,
      sender,
      receivedAt: receivedAt === "unknown-time" ? "Received timestamp not exposed" : formatDateTime(receivedAt),
      subject: documentMetadataText(documents[0], "subject") || "Subject not captured",
      processingStatus: needsReview ? "Needs review" : "Processed",
      processingTone: needsReview ? "amber" : "green",
      attachments
    };
  });
}

function inboundAttachmentItemFromDocument(
  claim: Claim,
  document: ClaimEvidenceDocument,
  evidenceItems: ClaimEvidenceScaffoldItem[]
): ClaimInboundAttachmentItem {
  const text = claimEvidenceDocumentText(document);
  const classification = claimEvidenceCategoryLabel(inferClaimEvidenceCategory(text)) || document.label || "Unclassified attachment";
  const matchingRequirement = (claim.requiredEvidence ?? []).find((requirement) =>
    documentMatchesEvidenceRequirement(document, requirement)
  );
  const evidenceItem = evidenceItems.find((item) => item.fileName === document.fileName);
  const confidence = (evidenceItem?.confidence ?? documentMetadataText(document, "confidence")) || "Pending";
  const linkedRequirement = matchingRequirement ? evidenceRequirementDisplayName(matchingRequirement) : "Unmatched";
  const actionRequired = !matchingRequirement || confidence.toLowerCase().includes("low") || confidence.toLowerCase().includes("pending");
  return {
    id: document.id || documentIdentityKey(document),
    fileName: document.fileName,
    classification,
    linkedRequirement,
    status: actionRequired ? "Reviewer action required" : "Linked",
    statusTone: actionRequired ? "amber" : "green",
    actionRequired,
    evidenceItemId: evidenceItem?.id
  };
}

function buildCommunicationTimeline(
  claim: Claim,
  requests: ClaimCommunicationRequestRow[],
  inboundEmails: ClaimInboundEmailItem[]
): ClaimCommunicationTimelineEvent[] {
  const events: ClaimCommunicationTimelineEvent[] = [
    {
      id: "claim-submitted",
      timestamp: formatDateTime(claim.createdAt),
      eventType: "Claim submitted",
      description: `${claim.clientName} submitted the claim intake.`,
      status: "Completed",
      tone: "green"
    }
  ];

  if (claim.evidenceRequestDraft) {
    const draftSent = evidenceRequestDraftIsSent(claim.evidenceRequestDraft);
    const draftFailed = claim.evidenceRequestDraft.sendStatus === "failed";
    events.push({
      id: draftSent ? "evidence-draft-sent" : draftFailed ? "evidence-draft-send-failed" : "evidence-draft-created",
      timestamp: formatDateTime(
        claim.evidenceRequestDraft.sentAt ||
          claim.evidenceRequestDraft.updatedAt ||
          claim.evidenceRequestDraft.createdAt ||
          claim.createdAt
      ),
      eventType: draftSent
        ? "Evidence request sent"
        : draftFailed
          ? "Evidence request delivery failed"
          : "Evidence request draft generated",
      description: claim.evidenceRequestDraft.subject,
      status: draftSent ? "Sent" : draftFailed ? "Failed" : "Draft ready",
      tone: draftSent ? "green" : draftFailed ? "red" : "blue"
    });
  } else if (requests.some((row) => row.status !== "Received")) {
    events.push({
      id: "evidence-request-needed",
      timestamp: formatDateTime(claim.createdAt),
      eventType: "Evidence request needed",
      description: "Open evidence requirements are present, but no draft has been generated yet.",
      status: "Needs action",
      tone: "amber"
    });
  }

  inboundEmails.forEach((email) => {
    events.push({
      id: `${email.id}-received`,
      timestamp: email.receivedAt,
      eventType: "Email received",
      description: `${email.sender} sent ${email.attachments.length} attachment${email.attachments.length === 1 ? "" : "s"}.`,
      status: email.processingStatus,
      tone: email.processingTone
    });
  });

  return events;
}

function findEvidenceItemForRequirement(
  evidenceItems: ClaimEvidenceScaffoldItem[],
  requirement: ClaimEvidenceRequirementItem
) {
  const requirementCategory = inferClaimEvidenceCategory(evidenceRequirementText(requirement));
  const acceptableLabels = requirement.acceptableDocuments.map(normalizeEvidenceText);
  return evidenceItems.find((item) => {
    const itemText = normalizeEvidenceText(`${item.name} ${item.fileName} ${item.type}`);
    const itemCategory = inferClaimEvidenceCategory(itemText);
    if (requirementCategory && itemCategory === requirementCategory) return true;
    return acceptableLabels.some((label) => Boolean(label) && itemText.includes(label));
  });
}

function isInboundEmailDocument(document: ClaimEvidenceDocument) {
  const source = documentMetadataText(document, "source").toLowerCase();
  return (
    source === "email_hook" ||
    source.includes("email") ||
    Boolean(documentMetadataText(document, "sender_email")) ||
    Boolean(documentMetadataText(document, "evidence_request_id"))
  );
}

function documentMetadataText(document: ClaimEvidenceDocument, key: string) {
  const value = document.metadata?.[key];
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function documentIdentityKey(document: ClaimEvidenceDocument) {
  return normalizeEvidenceText(document.fileName || document.id || document.label || "claim-evidence");
}

function claimEvidenceDocumentText(document: ClaimEvidenceDocument) {
  const metadataText = [
    documentMetadataText(document, "document_role"),
    documentMetadataText(document, "document_type"),
    documentMetadataText(document, "category"),
    documentMetadataText(document, "label")
  ].join(" ");
  return normalizeEvidenceText(`${document.label} ${document.fileName} ${document.type} ${metadataText}`);
}

function evidenceRequirementText(requirement: ClaimEvidenceRequirementItem) {
  return normalizeEvidenceText(
    `${requirement.requirementType} ${requirement.reason} ${requirement.acceptableDocuments.join(" ")}`
  );
}

function normalizeEvidenceText(value: unknown) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[_./-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function isClientLegalProfileDocumentText(text: string) {
  const normalized = normalizeEvidenceText(text);
  return [
    "id document",
    "identity document",
    "identity card",
    "passport",
    "national id",
    "property ownership",
    "proof of ownership",
    "property deed",
    "title deed",
    "insurance policy",
    "policy document",
    "existing policy",
    "signed policy",
    "land registry",
    "bank document",
    "bank statement",
    "bank confirmation",
    "terms consent",
    "terms and conditions",
    "consent document",
    "client consent",
    "customer consent",
    "client profile",
    "legal profile",
    "company registration"
  ].some((phrase) => normalized.includes(phrase));
}

function isClaimEvidenceDocumentForEvidenceTab(document: ClaimEvidenceDocument) {
  const text = claimEvidenceDocumentText(document);
  if (isClientLegalProfileDocumentText(text)) return false;
  return Boolean(text);
}

function inferClaimEvidenceCategory(text: string) {
  const normalized = normalizeEvidenceText(text);
  const hasAny = (tokens: string[]) => tokens.some((token) => normalized.includes(token));

  if (hasAny(["damage photo", "damage photos", "photo", "photos", "image"]) || (hasAny(["damage", "incident"]) && hasAny(["jpg", "jpeg", "png"]))) {
    return "damage_photos";
  }
  if (hasAny(["repair estimate", "estimate", "contractor quote", "contractor report"])) return "repair_estimate";
  if (hasAny(["contractor invoice", "invoice", "receipt"])) return "invoice";
  if (hasAny(["bank confirmation", "bank", "iban", "payment confirmation"])) return "bank_confirmation";
  if (hasAny(["proof of ownership", "ownership", "property deed", "title deed"])) return "proof_of_ownership";
  if (hasAny(["claimant statement", "written incident", "incident statement", "incident description", "incident note", "statement"])) {
    return "claimant_statement";
  }
  if (hasAny(["id document", "identity document", "identity card", "passport", "national id"])) return "identity";
  if (hasAny(["supporting document", "supporting documents", "claim evidence", "email attachment", "inbound attachment"])) {
    return "supporting_document";
  }
  return "";
}

function documentMatchesEvidenceRequirement(
  document: ClaimEvidenceDocument,
  requirement: ClaimEvidenceRequirementItem
) {
  const documentText = claimEvidenceDocumentText(document);
  const requirementText = evidenceRequirementText(requirement);
  const documentCategory = inferClaimEvidenceCategory(documentText);
  const requirementCategory = inferClaimEvidenceCategory(requirementText);

  if (documentCategory && requirementCategory && documentCategory === requirementCategory) return true;

  return requirement.acceptableDocuments.some((acceptableDocument) => {
    const acceptableText = normalizeEvidenceText(acceptableDocument);
    const acceptableCategory = inferClaimEvidenceCategory(acceptableText);
    if (!acceptableText) return false;
    return (
      documentText.includes(acceptableText) ||
      (Boolean(acceptableCategory) && acceptableCategory === documentCategory)
    );
  });
}

function selectClaimEvidenceDocument(documents: ClaimEvidenceDocument[]) {
  return (
    documents.find((document) => {
      const text = claimEvidenceDocumentText(document);
      return inferClaimEvidenceCategory(text) !== "identity" && !isClientLegalProfileDocumentText(text);
    }) ?? documents[0]
  );
}

function claimEvidenceDisplayName(document: ClaimEvidenceDocument, groupText: string) {
  const category = inferClaimEvidenceCategory(groupText);
  const label = claimEvidenceCategoryLabel(category);
  if (label) return label;
  if (document.label && !["documents", "document", "files", "attachments"].includes(normalizeEvidenceText(document.label))) {
    return document.label;
  }
  return "Claim supporting document";
}

function claimEvidenceCategoryLabel(category: string) {
  const labels: Record<string, string> = {
    bank_confirmation: "Bank confirmation",
    claimant_statement: "Claimant statement",
    damage_photos: "Damage photos",
    identity: "ID document",
    invoice: "Contractor invoice",
    proof_of_ownership: "Proof of ownership",
    repair_estimate: "Repair estimate",
    supporting_document: "Other claim supporting documents"
  };
  return labels[category] ?? "";
}

function inferClaimEvidenceSource(document: ClaimEvidenceDocument) {
  const text = claimEvidenceDocumentText(document);
  if (text.includes("email") || text.includes("inbound")) return "Email ingestion";
  if (text.includes("client") || document.storageKey || document.fileUrl || document.url) return "Client upload";
  return "Claim evidence";
}

function evidenceRequirementStatus(requirement: ClaimEvidenceRequirementItem, requestSent: boolean) {
  const status = normalizeEvidenceText(requirement.status ?? "");
  if (status.includes("received") || status.includes("uploaded") || status.includes("complete")) return "Received";
  if (status.includes("requested")) return "Requested";
  if (status.includes("missing") || status.includes("pending")) return requestSent ? "Requested" : "Pending client upload";
  return requestSent ? "Requested" : "Pending client upload";
}

function evidenceRequirementDisplayName(requirement: ClaimEvidenceRequirementItem) {
  const categoryLabel = claimEvidenceCategoryLabel(inferClaimEvidenceCategory(evidenceRequirementText(requirement)));
  if (categoryLabel) return categoryLabel;
  const preferredName = requirement.acceptableDocuments[0] || requirement.requirementType || "Additional evidence";
  return titleCaseEvidenceLabel(preferredName);
}

function titleCaseEvidenceLabel(value: string) {
  return normalizeEvidenceText(value).replace(/\b\w/g, (character) => character.toUpperCase());
}

function inferDocumentType(fileName: string) {
  const extension = fileName.split(".").pop()?.toUpperCase();
  return extension && extension.length <= 5 ? extension : "PDF/JPEG";
}

function ClaimMetadataPill({ label, value }: { label: string; value: ReactNode }) {
  return (
    <span className="inline-flex max-w-full items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold shadow-sm">
      <span className="text-slate-500">{label}</span>
      <span className="truncate text-slate-900">{value || "-"}</span>
    </span>
  );
}

export function EmployeeRulesPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [rules, setRules] = useState<UnderwritingRulesDocument>();
  const [draft, setDraft] = useState<UnderwritingRulesDocument>();
  const [loadStatus, setLoadStatus] = useState<"loading" | "loaded" | "empty" | "error">("loading");
  const [loadError, setLoadError] = useState<string>();
  const [editing, setEditing] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const isMockRules = DATA_SOURCE_MODE === "mock";

  const loadRules = useCallback(async (isActive: () => boolean = () => true) => {
    setLoadStatus("loading");
    setLoadError(undefined);
    try {
      const document = await getUnderwritingRules();
      if (!isActive()) return;
      setRules(document);
      setDraft(cloneRulesDocument(document));
      setLoadStatus(document.sections.length ? "loaded" : "empty");
      setEditing(false);
      setConfirmOpen(false);
    } catch (error) {
      if (!isActive()) return;
      setRules(undefined);
      setDraft(undefined);
      setEditing(false);
      setConfirmOpen(false);
      setLoadStatus("error");
      setLoadError(error instanceof Error ? error.message : "Could not load underwriting rules.");
    }
  }, []);

  useEffect(() => {
    let active = true;
    void loadRules(() => active);
    return () => {
      active = false;
    };
  }, [loadRules]);

  const visibleRules = draft ?? rules;

  function startEditing() {
    if (!rules) return;
    setDraft(cloneRulesDocument(rules));
    setEditing(true);
  }

  function cancelEditing() {
    setDraft(rules ? cloneRulesDocument(rules) : undefined);
    setEditing(false);
    setConfirmOpen(false);
  }

  function updateBlock(sectionIndex: number, blockIndex: number, nextBlock: UnderwritingRuleBlock) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        sections: current.sections.map((section, currentSectionIndex) =>
          currentSectionIndex === sectionIndex
            ? {
                ...section,
                blocks: section.blocks.map((block, currentBlockIndex) =>
                  currentBlockIndex === blockIndex ? nextBlock : block
                )
              }
            : section
        )
      };
    });
  }

  async function confirmSave() {
    if (!draft) return;
    setSaving(true);
    try {
      const saved = await updateUnderwritingRules(draft, user?.email ?? user?.fullName);
      setRules(saved);
      setDraft(cloneRulesDocument(saved));
      setEditing(false);
      setConfirmOpen(false);
      setLoadStatus(saved.sections.length ? "loaded" : "empty");
      setLoadError(undefined);
      showToast("Underwriting rules saved.");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Could not save underwriting rules.", "error");
    } finally {
      setSaving(false);
    }
  }

  if (loadStatus !== "loaded" || !visibleRules) {
    return (
      <section className="flex h-[calc(100dvh-5.5rem)] min-h-0 flex-col overflow-hidden">
        <EmployeePageHeader
          className="shrink-0"
          actions={
            loadStatus === "error" ? (
              <Button onClick={() => void loadRules()} variant="secondary">Retry</Button>
            ) : undefined
          }
          title="Underwriting Rules"
        />
        <Panel className="min-h-0 flex-1 overflow-y-auto p-4">
          {loadStatus === "loading" ? (
            <EmptyState title="Loading underwriting rules..." />
          ) : loadStatus === "empty" ? (
            <EmptyState
              description="No backend underwriting rules are configured yet."
              title="No underwriting rules configured"
            />
          ) : (
            <EmptyState
              description={loadError ?? "The backend rules service is unavailable."}
              title="Could not load underwriting rules"
            />
          )}
        </Panel>
      </section>
    );
  }

  return (
    <section className="flex h-[calc(100dvh-5.5rem)] min-h-0 flex-col overflow-hidden">
      <EmployeePageHeader
        className="shrink-0"
        actions={
          editing ? (
            <>
              <Button onClick={cancelEditing} variant="secondary">Cancel</Button>
              <Button onClick={() => setConfirmOpen(true)} variant="primary">Save Changes</Button>
            </>
          ) : (
            <Button icon={PenLine} onClick={startEditing} variant="primary">Edit</Button>
          )
        }
        title="Underwriting Rules"
      />
      <Panel className="min-h-0 flex-1 overflow-hidden p-0">
        <div className="h-full overflow-y-scroll p-4 [scrollbar-gutter:stable]">
          {isMockRules ? (
            <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50/85 p-4">
              <p className="text-sm font-bold text-amber-900">Demo underwriting rules</p>
              <p className="mt-1 text-sm font-semibold text-amber-800">
                Mock data mode is enabled. These local rules are for demos only; backend rules are authoritative outside mock mode.
              </p>
            </div>
          ) : null}
          <div className="space-y-6">
            {visibleRules.sections.map((section, sectionIndex) => (
              <RuleChapter key={section.id} title={section.title}>
                <div className="space-y-4">
                  {section.blocks.map((block, blockIndex) => (
                    <EditableRuleBlock
                      block={block}
                      editing={editing}
                      key={block.id}
                      onChange={(nextBlock) => updateBlock(sectionIndex, blockIndex, nextBlock)}
                    />
                  ))}
                </div>
              </RuleChapter>
            ))}
          </div>
        </div>
      </Panel>
      <Modal
        actions={
          <>
            <Button disabled={saving} onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button disabled={saving} onClick={() => void confirmSave()} variant="primary">
              {saving ? "Saving..." : "OK"}
            </Button>
          </>
        }
        onClose={() => {
          if (!saving) setConfirmOpen(false);
        }}
        open={confirmOpen}
        title="Confirm rule changes"
      >
        Are you sure you want to change the underwriting rules? This will save the new values on the site and in the database.
      </Modal>
    </section>
  );
}

function EditableRuleBlock({
  block,
  editing,
  onChange
}: {
  block: UnderwritingRuleBlock;
  editing: boolean;
  onChange: (block: UnderwritingRuleBlock) => void;
}) {
  if (block.kind === "notice") {
    if (editing) {
      return (
        <textarea
          className="min-h-24 w-full rounded-xl border border-orange-200 bg-orange-50 p-3 text-sm font-bold text-orange-600 outline-none focus:border-orange-500 focus:ring-4 focus:ring-orange-100"
          onChange={(event) => onChange({ ...block, text: event.target.value })}
          value={block.text ?? ""}
        />
      );
    }
    return (
      <p className="rounded-xl bg-orange-50 p-4 text-sm font-bold text-orange-600">
        {block.text}
      </p>
    );
  }

  if (block.kind === "table") {
    return (
      <EditableRulesTable
        block={block}
        editing={editing}
        onChange={onChange}
      />
    );
  }

  const items = block.items ?? [];
  if (editing) {
    return (
      <div className="space-y-2">
        {items.map((item, itemIndex) => (
          <textarea
            className="min-h-16 w-full rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700 outline-none focus:border-orange-500 focus:ring-4 focus:ring-orange-100"
            key={`${block.id}-${itemIndex}`}
            onChange={(event) => {
              const nextItems = items.map((currentItem, currentIndex) =>
                currentIndex === itemIndex ? event.target.value : currentItem
              );
              onChange({ ...block, items: nextItems });
            }}
            value={item}
          />
        ))}
      </div>
    );
  }

  return (
    <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-700">
      {items.map((item, itemIndex) => (
        <li key={`${block.id}-${itemIndex}`}>{item}</li>
      ))}
    </ul>
  );
}

function EditableRulesTable({
  block,
  editing,
  onChange
}: {
  block: UnderwritingRuleBlock;
  editing: boolean;
  onChange: (block: UnderwritingRuleBlock) => void;
}) {
  const headers = block.headers ?? [];
  const rows = block.rows ?? [];

  if (!editing) {
    return <RulesTable headers={headers} rows={rows} />;
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            {headers.map((header) => (
              <th className="px-3 py-2 text-left font-bold text-slate-600" key={header}>
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rows.map((row, rowIndex) => (
            <tr key={`${block.id}-${rowIndex}`}>
              {row.map((cell, cellIndex) => (
                <td className="px-3 py-2" key={`${block.id}-${rowIndex}-${cellIndex}`}>
                  <input
                    className="w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-700 outline-none focus:border-orange-500 focus:ring-4 focus:ring-orange-100"
                    onChange={(event) => {
                      const nextRows = rows.map((currentRow, currentRowIndex) =>
                        currentRowIndex === rowIndex
                          ? currentRow.map((currentCell, currentCellIndex) =>
                              currentCellIndex === cellIndex ? event.target.value : currentCell
                            )
                          : currentRow
                      );
                      onChange({ ...block, rows: nextRows });
                    }}
                    value={cell}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function cloneRulesDocument(document: UnderwritingRulesDocument): UnderwritingRulesDocument {
  return JSON.parse(JSON.stringify(document)) as UnderwritingRulesDocument;
}

function EmployeeClaimActions({
  claim,
  onAccept,
  onVerify,
  reviewOnly
}: {
  claim: Claim;
  onAccept: (claim: Claim) => void;
  onVerify: (claimId: string) => void;
  reviewOnly: boolean;
}) {
  const terminal = isClaimTerminal(claim.status);
  const needsVerification = claim.status === "inspection_requested" || claim.score <= 70;

  return (
    <div className="flex gap-2">
      {!reviewOnly && !terminal && !needsVerification ? (
        <button className="font-bold text-emerald-700" onClick={() => onAccept(claim)} type="button">
          Mock approve
        </button>
      ) : null}
      {!reviewOnly && !terminal && needsVerification ? (
        <button className="font-bold text-orange-700" onClick={() => onVerify(claim.id)} type="button">
          Verify
        </button>
      ) : null}
      <Link className="font-bold text-orange-600" to={`/employee/claims/${claim.id}`}>View</Link>
    </div>
  );
}

function isQuoteReviewActionable(status: Quote["status"]) {
  return status === "submitted" || status === "in_review";
}

function isClaimTerminal(status: Claim["status"]) {
  return status === "accepted" || status === "rejected" || status === "paid";
}

function claimReviewTitle(claim: Claim) {
  const titles: Partial<Record<ClaimType, string>> = {
    Fire: "Fire damage claim",
    "Water damage": "Water damage claim",
    Theft: "Theft claim",
    Storm: "Storm damage claim",
    Other: "Claim review"
  };
  return titles[claim.claimType] ?? `${claim.claimType} claim`;
}

function titleCaseLabel(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/\w\S*/g, (word) => word.charAt(0).toUpperCase() + word.slice(1));
}

export function EmployeeAccountPage() {
  const { logout, user } = useAuth();
  const navigate = useNavigate();

  function signOut() {
    logout();
    navigate("/");
  }

  return (
    <>
      <EmployeePageHeader
        actions={<Button onClick={signOut} variant="primary">Sign Out</Button>}
        title="Account"
      />
      <Panel>
        <DetailGrid
          items={[
            ["Full name", user?.fullName],
            ["Email", user?.email],
            ["Role", user?.role],
            ["Title", user?.title ?? "Employee"]
          ]}
        />
      </Panel>
    </>
  );
}

function RuleChapter({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-4 text-xl font-bold text-slate-950">{title}</h2>
      {children}
    </section>
  );
}
