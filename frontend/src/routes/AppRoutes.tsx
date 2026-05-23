import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ClientLayout, EmployeeLayout, PublicLayout } from "../layouts/AppLayouts";
import {
  AboutPage,
  ContactPage,
  HomePage,
  RegisterPage,
  SignInPage
} from "../pages/PublicPages";
import {
  ClientAccountPage,
  ClientClaimDetailPage,
  ClientClaimsPage,
  ClientContractDetailPage,
  ClientContractsPage,
  ClientHomePage,
  ClientQuoteDetailPage,
  ClientQuotesPage,
  NewClaimPage,
  NewQuotePage
} from "../pages/ClientPages";
import {
  EmployeeAccountPage,
  EmployeeClaimDetailPage,
  EmployeeClaimsPage,
  EmployeeContractDetailPage,
  EmployeeContractsPage,
  EmployeeCustomerDetailPage,
  EmployeeCustomersPage,
  EmployeeHomePage,
  EmployeeQuoteDetailPage,
  EmployeeQuotesPage,
  EmployeeRulesPage,
  LegalReviewChangesView,
  LegalReviewDraftView,
  LegalReviewPage,
  LegalReviewQueueView,
  LegalReviewTemplatesView,
  LegalReviewUpdateDetailView
} from "../pages/EmployeePages";
import type { UserRole } from "../types";

function RequireRole({ role, children }: { role: UserRole; children: JSX.Element }) {
  const { getUser } = useAuth();
  const user = getUser(role);
  if (!user) return <Navigate replace to="/signin" />;
  if (user.role !== role) return <Navigate replace to={user.role === "client" ? "/client" : "/employee"} />;
  return children;
}

function ClaimReviewDefaultRedirect() {
  const { claimId } = useParams();
  return <Navigate replace to={claimId ? `/employee/claims/${claimId}/details` : "/employee/claims"} />;
}

function LegalReviewTemplatesRedirect({ step }: { step?: "changes" | "draft" }) {
  const { templateId, updateId } = useParams();
  const target =
    updateId && templateId
      ? `/legal-review/${encodeURIComponent(updateId)}/documents/${encodeURIComponent(templateId)}${step ? `/${step}` : ""}`
      : updateId
        ? `/legal-review/${encodeURIComponent(updateId)}/documents`
        : "/legal-review";
  return <Navigate replace to={target} />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/signin" element={<SignInPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route
        element={
          <RequireRole role="client">
            <ClientLayout />
          </RequireRole>
        }
      >
        <Route path="/client" element={<ClientHomePage />} />
        <Route path="/client/quotes" element={<ClientQuotesPage />} />
        <Route path="/client/quotes/:quoteId" element={<ClientQuoteDetailPage />} />
        <Route path="/client/quote/new" element={<NewQuotePage />} />
        <Route path="/client/quote/:quoteId" element={<ClientQuoteDetailPage />} />
        <Route path="/client/contracts" element={<ClientContractsPage />} />
        <Route path="/client/contracts/:contractId" element={<ClientContractDetailPage />} />
        <Route path="/client/claims" element={<ClientClaimsPage />} />
        <Route path="/client/claims/new" element={<NewClaimPage />} />
        <Route path="/client/claims/:claimId" element={<ClientClaimDetailPage />} />
        <Route path="/client/account" element={<ClientAccountPage />} />
      </Route>

      <Route
        element={
          <RequireRole role="employee">
            <EmployeeLayout />
          </RequireRole>
        }
      >
        <Route path="/employee" element={<EmployeeHomePage />} />
        <Route path="/legal-review" element={<LegalReviewPage />}>
          <Route index element={<LegalReviewQueueView />} />
          <Route path=":updateId" element={<LegalReviewUpdateDetailView />} />
          <Route path=":updateId/documents" element={<LegalReviewTemplatesView />} />
          <Route path=":updateId/documents/:templateId/changes" element={<LegalReviewChangesView />} />
          <Route path=":updateId/documents/:templateId/draft" element={<LegalReviewDraftView />} />
          <Route path=":updateId/templates" element={<LegalReviewTemplatesRedirect />} />
          <Route path=":updateId/templates/:templateId/changes" element={<LegalReviewTemplatesRedirect step="changes" />} />
          <Route path=":updateId/templates/:templateId/draft" element={<LegalReviewTemplatesRedirect step="draft" />} />
          <Route path="*" element={<Navigate replace to="/legal-review" />} />
        </Route>
        <Route path="/employee/quotes" element={<EmployeeQuotesPage />} />
        <Route path="/employee/quotes/:quoteId" element={<EmployeeQuoteDetailPage />} />
        <Route path="/employee/contracts" element={<EmployeeContractsPage />} />
        <Route path="/employee/contracts/:contractId" element={<EmployeeContractDetailPage />} />
        <Route path="/contracts/:contractId" element={<EmployeeContractDetailPage />} />
        <Route path="/employee/customers" element={<EmployeeCustomersPage />} />
        <Route path="/employee/customers/:customerId" element={<EmployeeCustomerDetailPage />} />
        <Route path="/employee/claims" element={<EmployeeClaimsPage />} />
        <Route path="/employee/claims/:claimId" element={<ClaimReviewDefaultRedirect />} />
        <Route path="/employee/claims/:claimId/:reviewStep" element={<EmployeeClaimDetailPage />} />
        <Route path="/employee/rules" element={<EmployeeRulesPage />} />
        <Route path="/employee/account" element={<EmployeeAccountPage />} />
      </Route>

      <Route path="/auth/login" element={<Navigate replace to="/signin" />} />
      <Route path="/auth/register" element={<Navigate replace to="/register" />} />
      <Route path="/underwriter/*" element={<Navigate replace to="/employee" />} />
      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  );
}

