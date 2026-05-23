import type { AppUser } from "../../types";
import { ApiError, apiRequest } from "./http";

interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: number | null;
  email: string;
  role: "client" | "employee" | "underwriter" | "admin";
  client_id: number | null;
  full_name: string;
  phone?: string | null;
  customer_profile_status?: string | null;
  requires_customer_profile_completion?: boolean;
}

export async function signIn(email: string, password: string): Promise<AppUser | null> {
  try {
    const response = await apiRequest<AuthResponse>("/auth/login", {
      method: "POST",
      body: { email, password }
    });
    return toAppUser(response, password);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}

export async function registerClient(data: {
  fullName: string;
  email: string;
  phone: string;
  password: string;
}): Promise<AppUser> {
  const response = await apiRequest<AuthResponse>("/auth/client/register", {
    method: "POST",
    body: {
      email: data.email,
      password: data.password,
      full_name: data.fullName,
      phone: data.phone
    }
  });
  return toAppUser(response, data.password);
}

export async function updateUserProfile(user: AppUser): Promise<AppUser> {
  return user;
}

function toAppUser(response: AuthResponse, password = ""): AppUser {
  const isEmployeeUser = ["employee", "underwriter", "admin"].includes(response.role);
  return {
    id: String(response.client_id ?? response.user_id ?? response.email),
    role: isEmployeeUser ? "employee" : "client",
    fullName: response.full_name,
    email: response.email,
    password,
    accessToken: response.access_token,
    customerId: response.client_id === null ? undefined : String(response.client_id),
    customerProfileStatus: response.customer_profile_status ?? null,
    requiresCustomerProfileCompletion: Boolean(response.requires_customer_profile_completion),
    phone: response.phone ?? undefined,
    title: isEmployeeUser ? employeeTitle(response.role) : undefined
  };
}

function employeeTitle(role: AuthResponse["role"]) {
  if (role === "admin") return "Admin";
  if (role === "employee") return "Employee";
  return "Underwriter";
}

