from __future__ import annotations


class FakeCandidateRepository:
    def __init__(self) -> None:
        self.status = None
        self.limit = None

    def list_candidates(self, status="candidate", limit=50):
        self.status = status
        self.limit = limit
        return ["candidate"]


def test_list_candidates_delegates_to_repository() -> None:
    from underwright.application.services.template_review_query_service import (
        TemplateReviewQueryService,
    )

    repo = FakeCandidateRepository()
    service = TemplateReviewQueryService(repo)

    candidates = service.list_candidates(status="dismissed", limit=7)

    assert candidates == ["candidate"]
    assert repo.status == "dismissed"
    assert repo.limit == 7
