import { USE_MOCK_DATA } from "../config/dataSource";
import * as backendNewsService from "./backend/newsService";
import * as mockNewsService from "./mock/newsService";

const newsService = USE_MOCK_DATA ? mockNewsService : backendNewsService;

export const getNewsStories = newsService.getNewsStories;

