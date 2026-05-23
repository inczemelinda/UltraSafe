from __future__ import annotations

from typing import Protocol

from underwright.domain.intelligence import (
    ClassificationInput,
    ClassificationOutput,
    ExternalEvent,
    RawSourceItem,
    Source,
    TemplateReviewCandidate,
)
from underwright.domain.models import Template


class SourceConnector(Protocol):
    def fetch_items(
        self,
        source: Source,
        limit: int | None = None,
    ) -> list[RawSourceItem]: ...


class EventClassifier(Protocol):
    model_name: str
    model_version: str
    prompt_version: str | None

    def classify(
        self,
        classification_input: ClassificationInput,
    ) -> ClassificationOutput: ...


class EventSummaryWriter(Protocol):
    model_name: str
    model_version: str
    prompt_version: str | None

    def summarize(
        self,
        classification_input: ClassificationInput,
        classification: ClassificationOutput,
    ) -> ClassificationOutput: ...


class TemplateCandidateExplainer(Protocol):
    model_name: str
    model_version: str
    prompt_version: str | None

    def explain(
        self,
        event: ExternalEvent,
        template: Template,
        candidate: TemplateReviewCandidate,
    ) -> TemplateReviewCandidate: ...
