import type { AppUser } from "../types";

export const mockUsers: AppUser[] = [
  {
    id: "client-001",
    role: "client",
    fullName: "Ana Popescu",
    email: "ana.popescu@client.com",
    password: "client123",
    customerId: "1001",
    customerProfileStatus: "complete",
    requiresCustomerProfileCompletion: false,
    phone: "+40 721 000 111",
    address: "Str. Aviatorilor 12, București",
    nationalId: "2900101123456"
  },
  {
    id: "client-002",
    role: "client",
    fullName: "Mihai Ionescu",
    email: "mihai.ionescu@client.com",
    password: "client123",
    customerId: "1002",
    customerProfileStatus: "complete",
    requiresCustomerProfileCompletion: false,
    phone: "+40 722 000 222",
    address: "Str. Ficusului 18, București",
    nationalId: "1860315123456"
  },
  {
    id: "employee-001",
    role: "employee",
    fullName: "Ioana Poliță",
    email: "ioana.polita@ultrasafe.ro",
    password: "employee123",
    title: "Underwriter"
  }
];

