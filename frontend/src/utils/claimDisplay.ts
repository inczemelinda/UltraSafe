type ClaimDisplaySource = {
  id?: string | null;
  displayClaimId?: string | null;
  claimNumber?: string | null;
  claimReference?: string | null;
  publicId?: string | null;
  externalId?: string | null;
};

export function getClaimDisplayIdentifier(claim?: ClaimDisplaySource | null) {
  return (
    cleanDisplayIdentifier(claim?.displayClaimId) ||
    cleanDisplayIdentifier(claim?.claimNumber) ||
    cleanDisplayIdentifier(claim?.claimReference) ||
    cleanDisplayIdentifier(claim?.publicId) ||
    cleanDisplayIdentifier(claim?.externalId) ||
    cleanDisplayIdentifier(claim?.id) ||
    "Claim reference pending"
  );
}

function cleanDisplayIdentifier(value?: string | null) {
  if (typeof value !== "string" || !value.trim()) return "";
  const cleaned = value.trim();
  return isUuidIdentifier(cleaned) ? "" : cleaned;
}

function isUuidIdentifier(value: string) {
  return /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(value);
}

