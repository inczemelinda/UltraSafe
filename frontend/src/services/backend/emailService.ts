import type { CustomerEmailMessage } from "../../types";
import { apiRequest } from "./http";

export async function getCustomerEmailHistory(
  customerId: string,
): Promise<CustomerEmailMessage[]> {
  return apiRequest<CustomerEmailMessage[]>(
    `/emails/customer/${encodeURIComponent(customerId)}`,
  );
}

