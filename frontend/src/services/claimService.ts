import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendClaimService from "./backend/claimService";
import * as mockClaimService from "./mock/claimService";

const claimService = USE_MOCK_DATA ? mockClaimService : backendClaimService;

export const getClientClaims = claimService.getClientClaims;
export const getAllClaims = claimService.getAllClaims;
export const getClaimById = claimService.getClaimById;
export const getMyClaimById = claimService.getMyClaimById;
export const getLatestClaimReview = claimService.getLatestClaimReview;
export const startClaimReview = claimService.startClaimReview;
export const createClaim = claimService.createClaim;
export const uploadClaimAttachments = claimService.uploadClaimAttachments;
export const startClaimAnalysis = claimService.startClaimAnalysis;
export const refreshClaimAttachmentAnalysis = claimService.refreshClaimAttachmentAnalysis;
export const generateEvidenceRequestDraft = claimService.generateEvidenceRequestDraft;
export const updateEvidenceRequestDraft = claimService.updateEvidenceRequestDraft;
export const sendEvidenceRequestDraft = claimService.sendEvidenceRequestDraft;
export const sendDemoInboundClaimEmail = claimService.sendDemoInboundClaimEmail;
export const dismissClaimAiSuggestion = claimService.dismissClaimAiSuggestion;
export const sendClaimDecisionEmail = claimService.sendClaimDecisionEmail;
export const rewordClaimDecisionJustification = claimService.rewordClaimDecisionJustification;
export const approveClaim = claimService.approveClaim;
export const rejectClaim = claimService.rejectClaim;
export const requestOnPremisesInspection = claimService.requestOnPremisesInspection;

