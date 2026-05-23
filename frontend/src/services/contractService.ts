import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendContractService from "./backend/contractService";
import * as mockContractService from "./mock/contractService";

const contractService = USE_MOCK_DATA ? mockContractService : backendContractService;

export const getClientContracts = contractService.getClientContracts;
export const getAllContracts = contractService.getAllContracts;
export const getContractById = contractService.getContractById;
export const getContracts = contractService.getContracts;
export const getMyContracts = contractService.getMyContracts;
export const getClaimableContracts = contractService.getClaimableContracts;
export const getContract = contractService.getContract;
export const getMyContract = contractService.getMyContract;
export const declineMyContract = contractService.declineMyContract;
export const resolveQuoteContract = contractService.resolveQuoteContract;
export const convertQuoteToContract = contractService.convertQuoteToContract;
export const generateContractDocument = contractService.generateContractDocument;
export const getLatestContractDocument = contractService.getLatestContractDocument;
export const getLatestMyContractDocument = contractService.getLatestMyContractDocument;
export const getGeneratedDocument = contractService.getGeneratedDocument;
export const createGeneratedDocumentPdf = contractService.createGeneratedDocumentPdf;
export const getGeneratedDocumentPdfUrl = contractService.getGeneratedDocumentPdfUrl;
export const downloadGeneratedDocumentPdf = contractService.downloadGeneratedDocumentPdf;

