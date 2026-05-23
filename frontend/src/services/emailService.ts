import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendEmailService from "./backend/emailService";
import * as mockEmailService from "./mock/emailService";

const emailService = USE_MOCK_DATA ? mockEmailService : backendEmailService;

export const getCustomerEmailHistory = emailService.getCustomerEmailHistory;

