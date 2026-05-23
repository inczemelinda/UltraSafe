import type {
  CustomerAuthUserRelinkResult,
  CustomerAdminSummary,
  CustomerLinkedAuthUser,
  CustomerProfile,
  CustomerProfileDetail
} from "../../types";
import { apiRequest } from "./http";

export async function listCustomers(): Promise<CustomerAdminSummary[]> {
  const profiles = await apiRequest<CustomerProfile[]>("/customers");
  return profiles.map(toCustomerSummary);
}

export async function getCustomerProfile(customerId: string): Promise<CustomerProfileDetail> {
  const profile = await apiRequest<CustomerProfile>(
    `/customers/${encodeURIComponent(customerId)}/profile`
  );
  return toCustomerDetail(profile);
}

export async function getCustomerAuthUsers(customerId: string): Promise<CustomerLinkedAuthUser[]> {
  const users = await apiRequest<CustomerLinkedAuthUser[]>(
    `/customers/${encodeURIComponent(customerId)}/auth-users`
  );
  return users.map(toLinkedAuthUser);
}

export async function linkAuthUserToCustomer(
  customerId: string,
  authUserId: string
): Promise<CustomerLinkedAuthUser> {
  const user = await apiRequest<CustomerLinkedAuthUser>(
    `/customers/${encodeURIComponent(customerId)}/auth-users/${encodeURIComponent(authUserId)}/link`,
    { method: "POST" }
  );
  return toLinkedAuthUser(user);
}

export async function unlinkAuthUserFromCustomer(
  customerId: string,
  authUserId: string
): Promise<CustomerLinkedAuthUser> {
  const user = await apiRequest<CustomerLinkedAuthUser>(
    `/customers/${encodeURIComponent(customerId)}/auth-users/${encodeURIComponent(authUserId)}/link`,
    { method: "DELETE" }
  );
  return toLinkedAuthUser(user);
}

export async function relinkAuthUserToCustomer(
  customerId: string,
  authUserId: string,
  reason: string
): Promise<CustomerAuthUserRelinkResult> {
  return apiRequest<CustomerAuthUserRelinkResult>(
    `/customers/${encodeURIComponent(customerId)}/auth-users/${encodeURIComponent(authUserId)}/relink`,
    {
      method: "POST",
      body: JSON.stringify({ reason })
    }
  );
}

function toCustomerSummary(profile: CustomerProfile): CustomerAdminSummary {
  return {
    ...profile,
    id: customerProfileId(profile),
    profile_status: profile.status,
    legal_name: profile.full_name,
    customer_type: profile.type
  };
}

function toCustomerDetail(profile: CustomerProfile): CustomerProfileDetail {
  return {
    ...profile,
    id: customerProfileId(profile),
    profile_status: profile.status
  };
}

function toLinkedAuthUser(user: CustomerLinkedAuthUser): CustomerLinkedAuthUser {
  const authUserId = user.auth_user_id ?? user.user_id ?? null;
  return {
    ...user,
    auth_user_id: authUserId,
    id: String(authUserId ?? user.email)
  };
}

function customerProfileId(profile: CustomerProfile) {
  return String(profile.customer_id ?? profile.email ?? profile.full_name ?? "unknown");
}

