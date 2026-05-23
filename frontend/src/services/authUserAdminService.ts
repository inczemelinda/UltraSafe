import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendAuthUserAdminService from "./backend/authUserAdminService";
import * as mockAuthUserAdminService from "./mock/authUserAdminService";

const authUserAdminService = USE_MOCK_DATA
  ? mockAuthUserAdminService
  : backendAuthUserAdminService;

export const searchAuthUsers = authUserAdminService.searchAuthUsers;

