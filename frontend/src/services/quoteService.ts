import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendQuoteService from "./backend/quoteService";
import * as mockQuoteService from "./mock/quoteService";

const quoteService = USE_MOCK_DATA ? mockQuoteService : backendQuoteService;

export const getClientQuotes = quoteService.getClientQuotes;
export const getAllQuotes = quoteService.getAllQuotes;
export const getQuoteById = quoteService.getQuoteById;
export const getMyQuoteById = quoteService.getMyQuoteById;
export const getQuoteAcceptance = quoteService.getQuoteAcceptance;
export const getMyQuoteAcceptance = quoteService.getMyQuoteAcceptance;
export const getQuoteDecisionAudit = quoteService.getQuoteDecisionAudit;
export const createQuote = quoteService.createQuote;
export const acceptQuote = quoteService.acceptQuote;
export const declineQuote = quoteService.declineQuote;
export const employeeApproveQuote = quoteService.employeeApproveQuote;
export const employeeRejectQuote = quoteService.employeeRejectQuote;
export const updateQuoteStatus = quoteService.updateQuoteStatus;

