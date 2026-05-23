from __future__ import annotations


class FakeInsightRepository:
    def __init__(self) -> None:
        self.params = None

    def list_cards(
        self,
        country=None,
        source_id=None,
        line_of_business=None,
        topic=None,
        event_type=None,
        severity=None,
        limit=50,
    ):
        self.params = {
            "country": country,
            "source_id": source_id,
            "line_of_business": line_of_business,
            "topic": topic,
            "event_type": event_type,
            "severity": severity,
            "limit": limit,
        }
        return ["card"]


def test_list_insight_cards_delegates_to_repository() -> None:
    from underwright.application.services.intelligence_insight_query_service import (
        IntelligenceInsightQueryService,
    )

    repo = FakeInsightRepository()
    service = IntelligenceInsightQueryService(repo)

    cards = service.list_insight_cards(
        country="RO",
        source_id="asf_ro",
        line_of_business="property",
        topic="earthquake",
        event_type="public_warning",
        severity="high",
        limit=7,
    )

    assert cards == ["card"]
    assert repo.params == {
        "country": "RO",
        "source_id": "asf_ro",
        "line_of_business": "property",
        "topic": "earthquake",
        "event_type": "public_warning",
        "severity": "high",
        "limit": 7,
    }
