import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");

function read(path) {
  return readFileSync(resolve(root, path), "utf8");
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const clientPages = read("src/pages/ClientPages.tsx");
const employeePages = read("src/pages/EmployeePages.tsx");
const ui = read("src/components/ui.tsx");
const backendClaimService = read("src/services/backend/claimService.ts");
const backendContractService = read("src/services/backend/contractService.ts");
const backendEmailService = read("src/services/backend/emailService.ts");
const backendQuoteService = read("src/services/backend/quoteService.ts");
const backendAuthUserAdminService = read("src/services/backend/authUserAdminService.ts");
const backendCustomerAdminService = read("src/services/backend/customerAdminService.ts");
const customerProfileService = read("src/services/backend/customerProfileService.ts");
const mockClaimService = read("src/services/mock/claimService.ts");
const mockQuoteService = read("src/services/mock/quoteService.ts");
const routes = read("src/routes/AppRoutes.tsx");

const forbiddenContractRenderingPatterns = [
  "ContractDocumentPreview",
  "repositoryContractPreviewTemplate",
  "renderTemplateSegments",
  "buildContractTemplateContext",
  "ContractPreview",
  "POLIȚĂ",
  "CAPITOLUL I",
  "SEMNĂTURI",
  "contract_meta",
  "parties.insured",
  "signatures.insured"
];

for (const pattern of forbiddenContractRenderingPatterns) {
  assert(!clientPages.includes(pattern), `Client contract page still contains frontend contract rendering pattern: ${pattern}`);
  assert(!ui.includes(pattern), `Shared UI still contains frontend contract rendering pattern: ${pattern}`);
}

assert(
  clientPages.includes("DocumentTextViewer") || clientPages.includes("GeneratedDocumentPdfViewer"),
  "Client contract page must render backend-owned generated document content."
);
assert(clientPages.includes("getLatestMyContractDocument"), "Client contract page must fetch persisted generated documents through /me endpoints.");
assert(clientPages.includes("downloadGeneratedDocumentPdf"), "Client contract page must download PDFs with authenticated backend fetch.");
assert(clientPages.includes("Linked quote"), "Client contract page must render a singular linked quote summary.");
assert(!clientPages.includes("Linked quotes"), "Client contract page must not imply one contract has many linked quotes.");
assert(!clientPages.includes("getQuotesForContract"), "Client contract page must not use an array-shaped contract-to-quotes helper.");
assert(
  employeePages.includes("DocumentTextViewer") || employeePages.includes("GeneratedDocumentPdfViewer"),
  "Employee contract page must render backend-owned generated document content."
);

assert(!backendContractService.includes("quoteService"), "Backend contract service must not derive contracts from quote APIs.");
assert(!backendContractService.includes("getQuoteById"), "Backend getContract must not look up quote data.");
assert(backendContractService.includes("/contracts/${encodeURIComponent(contractId)}"), "getContract must call /contracts/{contract_id}.");
assert(backendContractService.includes('apiRequest<ContractSummary[]>("/me/contracts")'), "Client contract service must call /me/contracts.");
assert(backendContractService.includes('/me/contracts/${encodeURIComponent(contractId)}'), "Client contract detail must call /me/contracts/{id}.");
assert(backendContractService.includes('/me/generated-documents'), "Client PDF download must use /me/generated-documents.");
assert(backendContractService.includes("/me/claimable-contracts"), "Claim flow must fetch claimable contracts from the authenticated backend endpoint.");
assert(clientPages.includes("Insured property"), "Claim property step must render the insured property selector.");
assert(clientPages.includes("No claimable insured properties"), "Claim property step must handle clients without claimable contracts.");
assert(!clientPages.includes("getClientContracts(user.id)"), "Claim flow must not filter all contracts client-side.");
assert(!clientPages.includes("getContracts()"), "Client contract flow must not call global /contracts.");
assert(!clientPages.includes("customerEmail"), "Client contract view must not filter ownership by customer email.");
assert(!clientPages.includes("customerName"), "Client contract view must not filter ownership by customer name.");
assert(!clientPages.includes("href={getGeneratedDocumentPdfUrl"), "Client PDF download must not be a bare unauthenticated href.");
assert(!backendClaimService.includes("property_address: draft.propertyAddress"), "Claim submission must not send a manually edited property address as authoritative data.");
assert(backendClaimService.includes('/claims/${encodeURIComponent(claimId)}/attachments'), "Claim uploads must use claim-scoped attachment routes.");
assert(backendClaimService.includes('/underwriter/claims/${encodeURIComponent(claimId)}/decision'), "Claim decision actions must use the backend decision endpoint.");
assert(backendClaimService.includes('/underwriter/claims/${encodeURIComponent(claimId)}/decision-email'), "Claim decision email must use the backend decision-email endpoint.");
assert(!backendClaimService.includes("Claim decision actions are not available"), "Claim decision actions must not be frontend stubs.");
assert(!mockClaimService.includes("Decision: Approved\",") || mockClaimService.includes("decisionLabel"), "Mock decision emails must not hardcode Approved.");
assert(employeePages.includes("Send claim decision email"), "Employee claim decision UI must expose the claim decision email action.");
assert(employeePages.includes("Submit a claim decision before sending the decision email."), "Employee claim decision email action must explain the pending-decision gate.");

assert(!mockQuoteService.includes("generateContractFromQuote"), "Mock quote acceptance must not silently generate contracts.");

assert(routes.includes("/employee/customers"), "Employee customer admin route must be registered.");
assert(backendCustomerAdminService.includes('apiRequest<CustomerProfile[]>("/customers")'), "Customer admin list must call /customers.");
assert(backendCustomerAdminService.includes('/customers/${encodeURIComponent(customerId)}/profile'), "Customer admin detail must call /customers/{id}/profile.");
assert(backendCustomerAdminService.includes('/customers/${encodeURIComponent(customerId)}/auth-users'), "Customer auth-user list must call /customers/{id}/auth-users.");
assert(backendAuthUserAdminService.includes("`/auth-users${suffix}`"), "Auth-user admin search must call /auth-users.");
assert(backendCustomerAdminService.includes("method: \"POST\""), "Customer auth-user link action must POST to the link endpoint.");
assert(backendCustomerAdminService.includes("method: \"DELETE\""), "Customer auth-user unlink action must DELETE the link endpoint.");
assert(backendCustomerAdminService.includes("/relink"), "Customer auth-user relink action must call the explicit relink endpoint.");
assert(backendCustomerAdminService.includes("relinkAuthUserToCustomer"), "Customer admin service must expose explicit relink support.");
assert(employeePages.includes("Move to this customer"), "Customer detail must show explicit relink wording for users linked elsewhere.");
assert(employeePages.includes("Audit reason"), "Customer detail relink flow must require an audit reason.");
assert(backendEmailService.includes('/emails/customer/${encodeURIComponent(customerId)}'), "Customer email history must call /emails/customer/{id}.");
assert(employeePages.includes("CustomerEmailHistorySection"), "Customer detail must mount the email history section.");
assert(employeePages.includes("Email History"), "Customer detail must label the customer email history section.");
assert(employeePages.includes("View full email"), "Customer email history must expose an expanded full-body view.");
assert(employeePages.includes("body_text"), "Customer email history must render full body_text separately from body_preview.");
assert(!employeePages.includes("POSTMARK_SERVER_TOKEN"), "Frontend must not expose Postmark server-token concepts.");
assert(!employeePages.includes("Postmark"), "Frontend email history must not expose provider implementation details.");
assert(backendClaimService.includes("/claims/decision-justification/reword"), "Claim AI rewording must call the backend reword endpoint.");
assert(employeePages.includes("AI rewording is not configured for this environment."), "Claim AI rewording must show the configuration-specific 503 message.");
assert(employeePages.includes("Use suggestion"), "Claim AI rewording must leave suggestions under user control.");
assert(!employeePages.includes("OPENAI_API_KEY"), "Frontend must not expose OpenAI API key concepts.");
assert(customerProfileService.includes('apiRequest<CustomerProfile>("/me/customer-profile")'), "Client profile service must keep using /me/customer-profile.");
assert(!clientPages.includes("searchAuthUsers"), "Client portal must not call admin auth-user search.");
assert(!clientPages.includes("/auth-users"), "Client portal must not use admin auth-user endpoints.");
assert(!clientPages.includes("relinkAuthUserToCustomer"), "Client portal must not import or use relink support.");
assert(backendQuoteService.includes('/me/quotes/${encodeURIComponent(quoteId)}/acceptance'), "Client quote acceptance must call the backend /me quote acceptance endpoint.");
assert(backendQuoteService.includes('/quotes/${encodeURIComponent(quoteId)}/acceptance'), "Employee quote acceptance visibility must call the global quote acceptance endpoint.");
assert(!backendQuoteService.includes('updateMyRawQuote(quoteId, { request_status: "auto_accepted" })'), "Client quote acceptance must not mutate quote status directly.");
assert(clientPages.includes("signer_name"), "Client quote acceptance must collect signer name.");
assert(clientPages.includes("acceptance_statement"), "Client quote acceptance must collect an acceptance statement.");
assert(employeePages.includes("getQuoteAcceptance"), "Employee quote detail must load quote acceptance provenance.");

console.log("Contract document rendering regression checks passed.");
