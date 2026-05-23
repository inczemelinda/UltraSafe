import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendCustomerProfileService from "./backend/customerProfileService";
import * as mockCustomerProfileService from "./mock/customerProfileService";

const customerProfileService = USE_MOCK_DATA
  ? mockCustomerProfileService
  : backendCustomerProfileService;

export const getMyCustomerProfile = customerProfileService.getMyCustomerProfile;
export const updateMyCustomerProfile = customerProfileService.updateMyCustomerProfile;
export const getCustomerProfiles = customerProfileService.getCustomerProfiles;

