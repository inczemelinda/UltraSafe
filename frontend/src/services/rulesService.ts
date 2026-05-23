import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendRulesService from "./backend/rulesService";
import * as mockRulesService from "./mock/rulesService";

const rulesService = USE_MOCK_DATA ? mockRulesService : backendRulesService;

export const getUnderwritingRules = rulesService.getUnderwritingRules;
export const updateUnderwritingRules = rulesService.updateUnderwritingRules;

