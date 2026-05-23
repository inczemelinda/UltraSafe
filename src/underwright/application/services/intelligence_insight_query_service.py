from __future__ import annotations


class IntelligenceInsightQueryService:
    def __init__(self, insight_repository) -> None:
        self.insight_repository = insight_repository

    def list_insight_cards(
        self,
        country: str | None = None,
        source_id: str | None = None,
        line_of_business: str | None = None,
        topic: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        status: str | None = "classified",
        limit: int = 50,
    ):
        params = {
            "country": country,
            "source_id": source_id,
            "line_of_business": line_of_business,
            "topic": topic,
            "event_type": event_type,
            "severity": severity,
            "limit": limit,
        }
        if status != "classified":
            params["status"] = status
        return self.insight_repository.list_cards(**params)
