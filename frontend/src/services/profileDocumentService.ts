import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendProfileDocumentService from "./backend/profileDocumentService";
import * as mockProfileDocumentService from "./mock/profileDocumentService";

const profileDocumentService = USE_MOCK_DATA
  ? mockProfileDocumentService
  : backendProfileDocumentService;

export const listMyProfileDocuments = profileDocumentService.listMyProfileDocuments;
export const uploadMyProfileDocument = profileDocumentService.uploadMyProfileDocument;
export const deleteMyProfileDocument = profileDocumentService.deleteMyProfileDocument;

