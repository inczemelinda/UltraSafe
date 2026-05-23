import type { CustomerProfileDocument } from "../../types";
import { readStoredAuthUser } from "../authSession";
import { delay } from "../storage";

const documentsByUser = new Map<string, CustomerProfileDocument[]>();

export async function listMyProfileDocuments(): Promise<CustomerProfileDocument[]> {
  const user = readStoredAuthUser();
  return delay([...(documentsByUser.get(user?.id ?? "anonymous") ?? [])]);
}

export async function uploadMyProfileDocument({
  label,
  documentType,
  file
}: {
  label: string;
  documentType?: string;
  file: File;
}): Promise<CustomerProfileDocument> {
  const user = readStoredAuthUser();
  const userId = user?.id ?? "anonymous";
  const now = new Date().toISOString();
  const document: CustomerProfileDocument = {
    id: `${userId}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${Date.now()}`,
    customer_id: Number.parseInt(user?.customerId ?? userId, 10) || 0,
    label,
    document_type: documentType || label,
    file_name: file.name,
    content_type: file.type || "application/octet-stream",
    size_bytes: file.size,
    storage_key: `${userId}-${Date.now()}`,
    file_url: null,
    metadata: { label, source: "client_profile" },
    created_at: now,
    updated_at: now
  };
  const existing = documentsByUser.get(userId) ?? [];
  documentsByUser.set(userId, [
    document,
    ...existing.filter((item) => item.label !== label)
  ]);
  return delay(document);
}

export async function deleteMyProfileDocument(documentId: string): Promise<void> {
  const user = readStoredAuthUser();
  const userId = user?.id ?? "anonymous";
  documentsByUser.set(
    userId,
    (documentsByUser.get(userId) ?? []).filter((item) => item.id !== documentId)
  );
  await delay(null);
}

