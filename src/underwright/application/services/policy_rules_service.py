from __future__ import annotations

from datetime import datetime, timezone

from underwright.domain.contract_case_context import ContractCaseContext


class PolicyRulesService:
    """Attaches minimal deterministic policy rules metadata to a case context."""

    RULE_VERSION = "v1"
    RULE_SOURCE = "static_mvp_policy_rules"

    def attach_policy_rules(
        self,
        case_context: ContractCaseContext,
    ) -> ContractCaseContext:
        case_context.reference_data.policy_rules = {
            "version": self.RULE_VERSION,
            "source": self.RULE_SOURCE,
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "rules": {
                "document_type": "PAD",
                "jurisdiction": "RO",
                "requires_client_profile": True,
                "requires_property_profile": True,
                "requires_risk_profile": True,
            },
            "metadata": {
                "description": "Minimal static policy rules for MVP architecture plumbing",
                "is_rules_engine": False,
            },
        }

        return case_context
