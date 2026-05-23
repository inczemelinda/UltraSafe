import type { NewsStory, NewsStoryFilters } from "../../types";
import { apiRequest } from "./http";

interface InsightCard {
  event_id: string;
  title: string;
  paragraphs: string[];
  source_links: Array<{ label: string; url: string; content_type?: string | null }>;
  published_at?: string | null;
  source_name: string;
  country: string;
  line_of_business?: string | null;
  event_type: string;
  topics: string[];
  severity: string;
  confidence: number;
}

export async function getNewsStories(filters: NewsStoryFilters = {}): Promise<NewsStory[]> {
  const query = new URLSearchParams({ limit: "20" });
  if (filters.country) query.set("country", filters.country);
  if (filters.lineOfBusiness) query.set("line_of_business", filters.lineOfBusiness);

  const cards = await apiRequest<InsightCard[]>(`/intelligence/events?${query.toString()}`);
  return cards.map((card) => ({
    id: card.event_id,
    title: card.title,
    publishedAt: formatDate(card.published_at),
    sourceCount: card.source_links.length,
    coverageLabel: card.source_name,
    rightCoverage: severityWeight(card.severity, "high"),
    centerCoverage: severityWeight(card.severity, "medium"),
    leftCoverage: 0,
    summary: card.paragraphs,
    eventType: formatLabel(card.event_type),
    severity: formatLabel(card.severity),
    relevance: relevanceLabel(card.confidence),
    sourceName: card.source_name,
    country: card.country,
    lineOfBusiness: card.line_of_business,
    topics: card.topics,
    sourceLinks: card.source_links.map((link) => ({
      label: link.label,
      url: link.url,
      contentType: link.content_type
    }))
  }));
}

function formatDate(value?: string | null) {
  if (!value) return "Unknown date";
  return new Date(value).toLocaleDateString("ro-RO");
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function severityWeight(severity: string, expected: string) {
  return severity === expected ? 100 : 0;
}

function relevanceLabel(confidence: number) {
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.6) return "Medium";
  return "Low";
}

