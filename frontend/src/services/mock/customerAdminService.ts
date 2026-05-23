import { mockUsers } from "../../data/mockUsers";
import type {
  AppUser,
  CustomerAuthUserRelinkResult,
  CustomerAdminSummary,
  CustomerLinkedAuthUser,
  CustomerProfile,
  CustomerProfileDetail
} from "../../types";
import { delay, readStored, writeStored } from "../storage";
import { authUserSearchId } from "./authUserAdminService";
import { getCustomerProfiles } from "./customerProfileService";

const usersKey = "ultrasafe_users_v4";

const incompleteCustomer: CustomerProfile = {
  customer_id: 2002,
  status: "incomplete",
  requires_customer_profile_completion: true,
  type: "company",
  full_name: "ZeroRisk Property SRL",
  company_id: null,
  email: "office@zerorisk-property.example",
  phone: "0722000000",
  address: {
    country: "Romania",
    county: "Cluj",
    city: "Cluj-Napoca",
    street: "Str. Fabricii",
    number: "",
    postal_code: "",
    full_text: "Str. Fabricii, Cluj-Napoca, Cluj, Romania"
  },
  missing_fields: ["company_id", "address.number", "address.postal_code"],
  customer_profile_completed_at: null,
  customer_profile_updated_at: new Date().toISOString(),
  customer_profile_completion_source: "employee_link",
  profile_update_count: 2,
  linked_auth_user_count: 0
};

export async function listCustomers(): Promise<CustomerAdminSummary[]> {
  const profiles = await getCustomerProfiles();
  return delay([...profiles, incompleteCustomer].map(toCustomerSummary));
}

export async function getCustomerProfile(customerId: string): Promise<CustomerProfileDetail> {
  const profile = await findCustomerProfile(customerId);
  if (!profile) throw new Error("Customer profile not found.");
  return delay(toCustomerDetail(profile));
}

export async function getCustomerAuthUsers(customerId: string): Promise<CustomerLinkedAuthUser[]> {
  const users = readStored(usersKey, mockUsers);
  return delay(
    users
      .filter((user) => user.customerId === customerId)
      .map(toLinkedAuthUser)
  );
}

export async function linkAuthUserToCustomer(
  customerId: string,
  authUserId: string
): Promise<CustomerLinkedAuthUser> {
  const users = readStored(usersKey, mockUsers);
  const user = users.find((item) => matchesAuthUser(item, authUserId));
  if (!user) throw new Error("Auth user not found.");
  if (user.role !== "client") throw new Error("Only client users can be linked.");
  if (user.customerId && user.customerId !== customerId) {
    throw new Error("Auth user is already linked to another customer.");
  }

  const updated = { ...user, customerId, customerProfileStatus: "complete" };
  writeStored(usersKey, users.map((item) => (item.id === user.id ? updated : item)));
  return delay(toLinkedAuthUser(updated));
}

export async function unlinkAuthUserFromCustomer(
  customerId: string,
  authUserId: string
): Promise<CustomerLinkedAuthUser> {
  const users = readStored(usersKey, mockUsers);
  const user = users.find(
    (item) => item.customerId === customerId && matchesAuthUser(item, authUserId)
  );
  if (!user) throw new Error("Auth user not found.");

  const updated = {
    ...user,
    customerId: undefined,
    customerProfileStatus: "pending_customer_link",
    requiresCustomerProfileCompletion: true
  };
  writeStored(usersKey, users.map((item) => (item.id === user.id ? updated : item)));
  return delay(toLinkedAuthUser(updated));
}

export async function relinkAuthUserToCustomer(
  customerId: string,
  authUserId: string,
  reason: string
): Promise<CustomerAuthUserRelinkResult> {
  const cleanReason = reason.trim();
  if (cleanReason.length < 10) {
    throw new Error("A relink reason of at least 10 characters is required.");
  }

  const users = readStored(usersKey, mockUsers);
  const user = users.find((item) => matchesAuthUser(item, authUserId));
  if (!user) throw new Error("Auth user not found.");
  if (user.role !== "client") throw new Error("Only client users can be linked.");
  if (!user.customerId) throw new Error("Auth user is not linked.");

  const oldCustomerId = user.customerId;
  const oldProfile = await findCustomerProfile(oldCustomerId);
  const newProfile = await findCustomerProfile(customerId);
  if (!newProfile) throw new Error("Customer profile not found.");

  if (oldCustomerId !== customerId) {
    const updated = { ...user, customerId };
    writeStored(usersKey, users.map((item) => (item.id === user.id ? updated : item)));
  }

  return delay({
    auth_user_id: authUserSearchId(user),
    auth_user_email: user.email,
    old_customer_id: Number.parseInt(oldCustomerId, 10) || null,
    old_customer_name: oldProfile?.full_name ?? null,
    new_customer_id: Number.parseInt(customerId, 10) || 0,
    new_customer_name: newProfile.full_name ?? null,
    reason: cleanReason,
    changed_by_auth_user_id: null,
    changed_at: new Date().toISOString()
  });
}

function matchesAuthUser(user: AppUser, authUserId: string) {
  return user.id === authUserId || user.email === authUserId || String(authUserSearchId(user)) === authUserId;
}

async function findCustomerProfile(customerId: string) {
  const profiles = await getCustomerProfiles();
  const users = readStored(usersKey, mockUsers);
  const matchingUser = users.find((user) => user.id === customerId);
  const normalizedCustomerId = matchingUser?.customerId ?? customerId;
  return [...profiles, incompleteCustomer].find(
    (profile) => String(profile.customer_id ?? "") === customerId
      || String(profile.customer_id ?? "") === normalizedCustomerId
  );
}

function toCustomerSummary(profile: CustomerProfile): CustomerAdminSummary {
  return {
    ...profile,
    id: String(profile.customer_id ?? profile.email ?? profile.full_name ?? "unknown"),
    profile_status: profile.status,
    legal_name: profile.full_name,
    customer_type: profile.type
  };
}

function toCustomerDetail(profile: CustomerProfile): CustomerProfileDetail {
  return {
    ...profile,
    id: String(profile.customer_id ?? profile.email ?? profile.full_name ?? "unknown"),
    profile_status: profile.status
  };
}

function toLinkedAuthUser(user: AppUser): CustomerLinkedAuthUser {
  const parsedId = Number.parseInt(user.id, 10);
  const userId = Number.isFinite(parsedId) ? parsedId : null;
  return {
    id: String(userId ?? user.email),
    user_id: userId,
    auth_user_id: userId,
    email: user.email,
    role: user.role,
    full_name: user.fullName,
    client_id: user.customerId ? Number.parseInt(user.customerId, 10) || null : null,
    customer_profile_status: user.customerProfileStatus ?? null,
    requires_customer_profile_completion: Boolean(user.requiresCustomerProfileCompletion),
    status: user.requiresCustomerProfileCompletion ? "pending" : "active"
  };
}


