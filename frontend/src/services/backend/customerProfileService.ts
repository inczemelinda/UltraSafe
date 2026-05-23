import type { CustomerProfile, CustomerProfileUpdate } from "../../types";
import { apiRequest } from "./http";

export async function getMyCustomerProfile(): Promise<CustomerProfile> {
  return apiRequest<CustomerProfile>("/me/customer-profile");
}

export async function updateMyCustomerProfile(
  profile: CustomerProfileUpdate
): Promise<CustomerProfile> {
  return apiRequest<CustomerProfile>("/me/customer-profile", {
    method: "PUT",
    body: { ...profile }
  });
}

export async function getCustomerProfiles(): Promise<CustomerProfile[]> {
  return apiRequest<CustomerProfile[]>("/customers");
}

