from __future__ import annotations


class TemplateReviewQueryService:
    def __init__(self, candidate_repository) -> None:
        self.candidate_repository = candidate_repository

    def list_candidates(
        self,
        status: str | None = "candidate",
        limit: int = 50,
    ):
        return self.candidate_repository.list_candidates(status=status, limit=limit)
