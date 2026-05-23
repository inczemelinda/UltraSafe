import { mockUsers } from "../../data/mockUsers";
import type { AppUser } from "../../types";
import { delay, readStored, writeStored } from "../storage";

const usersKey = "ultrasafe_users_v4";

export async function signIn(email: string, password: string): Promise<AppUser | null> {
  const users = readStored(usersKey, mockUsers);
  const found = users.find((user) => user.email === email && user.password === password);
  return delay(found ?? null);
}

export async function registerClient(data: {
  fullName: string;
  email: string;
  phone: string;
  password: string;
}): Promise<AppUser> {
  const users = readStored(usersKey, mockUsers);
  const newUser: AppUser = {
    id: `client-${Date.now()}`,
    role: "client",
    fullName: data.fullName,
    email: data.email,
    phone: data.phone,
    password: data.password,
    customerProfileStatus: "pending_customer_link",
    requiresCustomerProfileCompletion: true
  };
  writeStored(usersKey, [newUser, ...users.filter((user) => user.email !== data.email)]);
  return delay(newUser);
}

export async function updateUserProfile(user: AppUser): Promise<AppUser> {
  const users = readStored(usersKey, mockUsers);
  writeStored(
    usersKey,
    users.map((item) => (item.id === user.id ? user : item))
  );
  return delay(user);
}


