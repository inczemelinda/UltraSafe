type ContractDisplaySource = {
  id?: string | null;
  contract_id?: string | null;
  contract_number?: string | null;
  policy_number?: string | null;
  displayId?: string | null;
  display_id?: string | null;
  contractDisplayId?: string | null;
  customer?: {
    full_name?: string | null;
  } | null;
};

export type ContractLifecycleDisplayStatus =
  | "awaiting_client_signing"
  | "issued"
  | "signed"
  | "declined";

export function getContractDisplayIdentifier(
  contract?: ContractDisplaySource | null
) {
  const explicitDisplayId =
    cleanIdentifier(contract?.displayId) ||
    cleanIdentifier(contract?.contractDisplayId) ||
    cleanIdentifier(contract?.display_id);
  if (explicitDisplayId) return explicitDisplayId;

  const generatedDisplayId = buildContractDisplayIdentifier(
    contract?.contract_number || contract?.policy_number,
    contract?.customer?.full_name,
    contract?.id || contract?.contract_id
  );
  if (generatedDisplayId) return generatedDisplayId;

  return (
    cleanIdentifier(contract?.contract_number) ||
    cleanIdentifier(contract?.policy_number) ||
    cleanIdentifier(contract?.id) ||
    cleanIdentifier(contract?.contract_id)
  );
}

export function getClaimContractDisplayIdentifier(claim: {
  contractId?: string | null;
  contractDisplayId?: string | null;
  policyNumber?: string | null;
  clientName?: string | null;
}) {
  return (
    cleanIdentifier(claim.contractDisplayId) ||
    buildContractDisplayIdentifier(claim.policyNumber, claim.clientName, claim.contractId) ||
    cleanIdentifier(claim.contractId)
  );
}

export function getContractLifecycleDisplayStatus(
  status?: string | null
): ContractLifecycleDisplayStatus {
  if (status === "generated" || status === "awaiting_client_signing") return "awaiting_client_signing";
  if (status === "declined") return "declined";
  if (status === "issued" || status === "active") return "signed";
  return "issued";
}

export function getContractLifecycleStatusLabel(status?: string | null) {
  const displayStatus = getContractLifecycleDisplayStatus(status);
  if (displayStatus === "awaiting_client_signing") return "Awaiting client signing";
  if (displayStatus === "signed") return "Signed";
  if (displayStatus === "declined") return "Declined";
  return "Issued";
}

function buildContractDisplayIdentifier(
  contractNumber?: string | null,
  legalName?: string | null,
  fallbackId?: string | null
) {
  const template = contractTemplate(contractNumber, legalName);
  const differentiator = contractDifferentiator(contractNumber, fallbackId);
  const name = legalNameDisplayPart(legalName);
  if (template && name && differentiator) {
    return `${template}-${name}-${differentiator}`;
  }
  return "";
}

function contractTemplate(contractNumber?: string | null, legalName?: string | null) {
  const parts = contractNumberParts(contractNumber);
  if (!parts.length) return "";
  let templateParts = parts.slice(0, -1);
  if (/^\d{4}$/.test(templateParts[templateParts.length - 1] ?? "")) {
    templateParts = templateParts.slice(0, -1);
  }

  templateParts = withoutLegalNameSuffix(templateParts, legalName);
  return templateParts.join("-");
}

function contractDifferentiator(contractNumber?: string | null, fallbackId?: string | null) {
  const parts = contractNumberParts(contractNumber);
  if (parts.length) return parts[parts.length - 1];
  const fallback = cleanIdentifier(fallbackId);
  return fallback ? fallback.split("-").pop() ?? fallback : "";
}

function contractNumberParts(contractNumber?: string | null) {
  const cleaned = cleanIdentifier(contractNumber);
  if (isUuidIdentifier(cleaned)) return [];
  return cleaned
    .split("-")
    .map((part) => part.trim())
    .filter(Boolean);
}

function isUuidIdentifier(value: string) {
  return /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(value);
}

function withoutLegalNameSuffix(templateParts: string[], legalName?: string | null) {
  const name = cleanIdentifier(legalName);
  if (templateParts.length <= 1 || !name) return templateParts;

  const normalizedName = normalizeToken(name);
  const firstLegalToken = normalizeToken(name.split(" ")[0] ?? "");
  for (let suffixLength = templateParts.length - 1; suffixLength > 0; suffixLength -= 1) {
    const suffix = templateParts.slice(-suffixLength).join(" ");
    if (normalizeToken(suffix) === normalizedName) {
      return templateParts.slice(0, -suffixLength);
    }
  }

  if (normalizeToken(templateParts[templateParts.length - 1]) === firstLegalToken) {
    return templateParts.slice(0, -1);
  }
  return templateParts;
}

function normalizeToken(value: string) {
  return value.toUpperCase().replace(/[^A-Z0-9]/g, "");
}

function cleanIdentifier(value?: string | null) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function legalNameDisplayPart(value?: string | null) {
  return cleanIdentifier(value).replace(/\s+/g, "_");
}

