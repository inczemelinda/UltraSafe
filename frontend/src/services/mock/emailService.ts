import type { CustomerEmailMessage } from "../../types";
import { delay } from "../storage";

const mockCustomerEmails: CustomerEmailMessage[] = [
  {
    id: "email-1001-2",
    customer_id: 1001,
    case_id: "11111111-1111-4111-8111-000000000001",
    case_reference: "Quote 11111111",
    direction: "OUTBOUND",
    status: "SENT",
    to_email: "vasile.valoare@client.com",
    from_email: "claims@ultrasafe.example",
    subject: "Quote document available",
    body_preview: "Your quote document is ready for review in the client portal.",
    body_text: "Your quote document is ready for review in the client portal.\n\nRegards,\nUltraSafe Team",
    body_html: null,
    provider_message_id: "mock-message-2",
    created_at: "2026-05-15T08:45:00.000Z",
    sent_at: "2026-05-15T08:45:00.000Z",
  },
  {
    id: "email-1001-1",
    customer_id: 1001,
    case_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    case_reference: "Claim aaaaaaaa",
    direction: "OUTBOUND",
    status: "FAILED",
    to_email: "vasile.valoare@client.com",
    from_email: "claims@ultrasafe.example",
    subject: "Evidence request",
    body_preview: "Please upload photos and repair invoices for the water damage claim.",
    body_text: "Please upload photos and repair invoices for the water damage claim.\n\nRegards,\nUltraSafe Claims Team",
    body_html: null,
    error_message: "Mailbox unavailable in mock delivery.",
    created_at: "2026-05-14T12:30:00.000Z",
  },
];

export async function getCustomerEmailHistory(
  customerId: string,
): Promise<CustomerEmailMessage[]> {
  return delay(
    mockCustomerEmails.filter(
      (email) => String(email.customer_id) === String(customerId),
    ),
  );
}


