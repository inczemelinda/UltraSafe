from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


ModuleStatus = Literal["success", "failed"]


class ModuleResult(BaseModel):
    """Lean receipt returned by Underwright workflow modules.

    The CaseContext remains the source of truth for module outputs. This model
    only records where a module result came from, its status, a short summary,
    and the context fields the module read.
    """

    module_name: str
    status: ModuleStatus
    summary: str
    source_fields_used: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_utc_now)


__all__ = ["ModuleResult", "ModuleStatus"]
