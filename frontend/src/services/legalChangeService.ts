import { USE_MOCK_LEGAL_REVIEW_DATA } from "../config/dataSource";
import * as backendLegalChangeService from "./backend/legalChangeService";
import * as mockLegalChangeService from "./mock/legalChangeService";

const legalChangeService = USE_MOCK_LEGAL_REVIEW_DATA
  ? mockLegalChangeService
  : backendLegalChangeService;

export const getLegalChanges = legalChangeService.getLegalChanges;
export const createTemplateChangeSuggestion =
  legalChangeService.createTemplateChangeSuggestion;
export const getTemplateChangeSuggestion =
  legalChangeService.getTemplateChangeSuggestion;
export const updateTemplateChangeSuggestionHunk =
  legalChangeService.updateTemplateChangeSuggestionHunk;
export const acceptTemplateChangeSuggestionHunk =
  legalChangeService.acceptTemplateChangeSuggestionHunk;
export const rejectTemplateChangeSuggestionHunk =
  legalChangeService.rejectTemplateChangeSuggestionHunk;
export const createDraftRevisionFromSuggestion =
  legalChangeService.createDraftRevisionFromSuggestion;
export const submitDraftRevisionForApproval =
  legalChangeService.submitDraftRevisionForApproval;

