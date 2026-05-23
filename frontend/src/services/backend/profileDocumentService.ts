import type { CustomerProfileDocument } from "../../types";
import { apiRequest } from "./http";

export async function listMyProfileDocuments(): Promise<CustomerProfileDocument[]> {
  return apiRequest<CustomerProfileDocument[]>("/me/customer-profile/documents");
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
  const formData = new FormData();
  formData.append("label", label);
  if (documentType) formData.append("document_type", documentType);
  formData.append("file", file);

  return apiRequest<CustomerProfileDocument>("/me/customer-profile/documents", {
    method: "POST",
    body: formData
  });
}

export async function deleteMyProfileDocument(documentId: string): Promise<void> {
  await apiRequest<null>(`/me/customer-profile/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE"
  });
}

