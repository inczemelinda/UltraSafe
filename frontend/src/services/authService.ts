import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendAuthService from "./backend/authService";
import * as mockAuthService from "./mock/authService";

const authService = USE_MOCK_DATA ? mockAuthService : backendAuthService;

export const signIn = authService.signIn;
export const registerClient = authService.registerClient;
export const updateUserProfile = authService.updateUserProfile;

