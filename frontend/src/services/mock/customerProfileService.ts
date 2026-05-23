import { mockUsers } from "../../data/mockUsers";
import type { AppUser, CustomerLegalDocument, CustomerProfile, CustomerProfileUpdate } from "../../types";
import { readStoredAuthUser, setAuthSession } from "../authSession";
import { delay, readStored, writeStored } from "../storage";

const usersKey = "ultrasafe_users_v4";

export async function getMyCustomerProfile(): Promise<CustomerProfile> {
  return delay(toCustomerProfile(readStoredAuthUser()));
}

export async function updateMyCustomerProfile(
  profile: CustomerProfileUpdate
): Promise<CustomerProfile> {
  const user = readStoredAuthUser();
  if (!user) throw new Error("Sign in is required.");
  const missing = missingFields(profile, user);
  if (missing.length) {
    throw new Error(`CUSTOMER_PROFILE_INCOMPLETE: ${missing.join(", ")}`);
  }
  const customerId = user.customerId ?? String(Date.now());
  const updated: AppUser = {
    ...user,
    id: customerId,
    customerId,
    customerProfileStatus: "complete",
    requiresCustomerProfileCompletion: false,
    fullName: profile.full_name ?? user.fullName,
    email: profile.email ?? user.email,
    phone: profile.phone ?? user.phone,
    nationalId: profile.national_id ?? user.nationalId,
    address: formatAddress(profile.address)
  };
  const users = readStored(usersKey, mockUsers);
  writeStored(
    usersKey,
    users.map((item) => (item.email === user.email ? updated : item))
  );
  if (typeof window !== "undefined") {
    setAuthSession(updated);
  }
  return delay(toCustomerProfile(updated, profile));
}

export async function getCustomerProfiles(): Promise<CustomerProfile[]> {
  const users = readStored(usersKey, mockUsers);
  return delay(
    users.filter((user) => user.role === "client").map((user) => toCustomerProfile(user))
  );
}

function toCustomerProfile(
  user: AppUser | null,
  override?: CustomerProfileUpdate
): CustomerProfile {
  if (!user) {
    return {
      status: "pending_customer_link",
      requires_customer_profile_completion: true,
      missing_fields: ["type", "full_name", "email", "phone", "address.country"]
    };
  }
  const profile: CustomerProfileUpdate = {
    type: override?.type ?? "individual",
    full_name: override?.full_name ?? user.fullName,
    national_id: override?.national_id ?? user.nationalId,
    company_id: override?.company_id,
    email: override?.email ?? user.email,
    phone: override?.phone ?? user.phone,
    address: override?.address ?? parseAddress(user.address)
  };
  const missing = user.requiresCustomerProfileCompletion
    ? missingFields(profile, user)
    : [];
  const complete = Boolean(user.customerId) && !missing.length;
  return {
    customer_id: user.customerId ? Number.parseInt(user.customerId, 10) || null : null,
    status: complete ? "complete" : "pending_customer_link",
    requires_customer_profile_completion: !complete,
    type: profile.type,
    full_name: profile.full_name,
    national_id: profile.national_id,
    company_id: profile.company_id,
    email: profile.email,
    phone: profile.phone,
    address: profile.address,
    missing_fields: complete ? [] : missing,
    customer_profile_completed_at: complete ? new Date().toISOString() : null,
    customer_profile_updated_at: new Date().toISOString(),
    customer_profile_completion_source: complete ? "client_self_service" : null,
    profile_update_count: complete ? 1 : 0,
    linked_auth_user_count: user.customerId ? 1 : 0,
    legal_documents: complete ? mockCustomerLegalDocuments(user, profile) : []
  };
}

function mockCustomerLegalDocuments(
  user: AppUser,
  profile: CustomerProfileUpdate
): CustomerLegalDocument[] {
  const baseId = user.customerId ?? user.id;
  const filePrefix = (profile.full_name ?? user.fullName)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "customer";
  const documents: CustomerLegalDocument[] = [];

  if (profile.type === "individual" && profile.national_id) {
    documents.push({
      id: `${baseId}-id-document`,
      label: "ID document",
      document_type: "ID document",
      file_name: `${filePrefix}-id-document.pdf`,
      content_type: "application/pdf",
      source: "client_profile",
      extracted_fields: {
        full_name: profile.full_name,
        national_id: profile.national_id
      }
    });
  }

  if (profile.type === "company" && profile.company_id) {
    documents.push({
      id: `${baseId}-company-registration`,
      label: "Company registration document",
      document_type: "Company registration document",
      file_name: `${filePrefix}-company-registration.pdf`,
      content_type: "application/pdf",
      source: "client_profile",
      extracted_fields: {
        company_name: profile.full_name,
        company_id: profile.company_id
      }
    });
  }

  documents.push({
    id: `${baseId}-terms-consent`,
    label: "Terms / consent document",
    document_type: "Terms / consent document",
    file_name: `${filePrefix}-terms-consent.pdf`,
    content_type: "application/pdf",
    source: "client_profile",
    extracted_fields: {
      full_name: profile.full_name,
      email: profile.email
    }
  });

  return documents;
}

function missingFields(profile: CustomerProfileUpdate, user: AppUser) {
  const missing: string[] = [];
  const address = profile.address ?? {};
  if (!profile.type) missing.push("type");
  if (!present(profile.full_name ?? user.fullName)) missing.push("full_name");
  if (!present(profile.email ?? user.email)) missing.push("email");
  if (!present(profile.phone ?? user.phone)) missing.push("phone");
  if (profile.type === "individual" && !present(profile.national_id ?? user.nationalId)) {
    missing.push("national_id");
  }
  if (profile.type === "company" && !present(profile.company_id)) {
    missing.push("company_id");
  }
  for (const field of ["country", "county", "city", "street", "number", "postal_code"] as const) {
    if (!present(address[field])) missing.push(`address.${field}`);
  }
  return missing;
}

function parseAddress(address?: string) {
  return address ? { full_text: address } : undefined;
}

function formatAddress(address?: CustomerProfileUpdate["address"]) {
  if (!address) return "";
  return (
    address.full_text ||
    [
      `${address.street ?? ""} ${address.number ?? ""}`.trim(),
      address.city,
      address.county,
      address.country,
      address.postal_code
    ].filter(Boolean).join(", ")
  );
}

function present(value?: string | null) {
  return Boolean(value?.trim());
}


