import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendCustomerAdminService from "./backend/customerAdminService";
import * as mockCustomerAdminService from "./mock/customerAdminService";

const customerAdminService = USE_MOCK_DATA
  ? mockCustomerAdminService
  : backendCustomerAdminService;

export const listCustomers = customerAdminService.listCustomers;
export const getCustomerProfile = customerAdminService.getCustomerProfile;
export const getCustomerAuthUsers = customerAdminService.getCustomerAuthUsers;
export const linkAuthUserToCustomer = customerAdminService.linkAuthUserToCustomer;
export const unlinkAuthUserFromCustomer = customerAdminService.unlinkAuthUserFromCustomer;
export const relinkAuthUserToCustomer = customerAdminService.relinkAuthUserToCustomer;

