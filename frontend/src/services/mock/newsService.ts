import { mockNews } from "../../data/mockNews";
import type { NewsStory, NewsStoryFilters } from "../../types";
import { delay } from "../storage";

export async function getNewsStories(filters: NewsStoryFilters = {}): Promise<NewsStory[]> {
  return delay(
    mockNews.filter((story) => {
      const countryMatches = !filters.country || story.country === filters.country;
      const domainMatches =
        !filters.lineOfBusiness || story.lineOfBusiness === filters.lineOfBusiness;
      return countryMatches && domainMatches;
    })
  );
}

