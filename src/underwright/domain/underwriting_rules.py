from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RuleBlockKind = Literal["list", "notice", "table"]


class UnderwritingRuleBlock(BaseModel):
    id: str
    kind: RuleBlockKind
    text: str = ""
    items: list[str] = Field(default_factory=list)
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class UnderwritingRuleSection(BaseModel):
    id: str
    title: str
    blocks: list[UnderwritingRuleBlock] = Field(default_factory=list)


class UnderwritingRulesDocument(BaseModel):
    key: str = "employee_underwriting_rules"
    sections: list[UnderwritingRuleSection] = Field(default_factory=list)
    updated_at: datetime | None = None
    updated_by: str | None = None


__all__ = [
    "UnderwritingRuleBlock",
    "UnderwritingRuleSection",
    "UnderwritingRulesDocument",
]
