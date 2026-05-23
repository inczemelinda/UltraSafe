from __future__ import annotations

from typing import Any

from underwright.application.ports import TemplateRenderer, TemplateRepository
from underwright.domain.models import Template


class TemplateService:
    """Loads and renders document templates."""

    def __init__(
        self,
        template_repository: TemplateRepository,
        template_renderer: TemplateRenderer,
    ) -> None:
        self.template_repository = template_repository
        self.template_renderer = template_renderer

    def get_contract_template(self, template_code: str) -> Template:
        return self.template_repository.get_active_template(template_code)

    def get_template(self, template_code: str) -> Template:
        return self.template_repository.get_active_template(template_code)

    def render(self, template_content: str, context: dict[str, Any]) -> str:
        return self.template_renderer.render(template_content, context)

    def get_template_metadata(self, template: Template) -> dict[str, Any]:
        return {
            "template_id": template.id,
            "template_code": template.template_code,
            "template_name": template.name,
            "template_version": template.version,
        }


__all__ = ["TemplateService"]
