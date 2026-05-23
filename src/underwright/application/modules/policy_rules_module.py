from __future__ import annotations

from typing import Any

from underwright.domain.module_result import ModuleResult
from underwright.domain.policy_rules import PolicyRule, PolicyRuleOutcome
from underwright.domain.quote_case_context import QuoteCaseContext


class PolicyRulesModule:
    """Matches deterministic MVP quote rules against quote request data."""

    module_name = "PolicyRulesModule"
    RULE_VERSION = "mvp_quote_rules_v1"

    required_fields = [
        "client_data.full_name",
        "client_data.email",
        "client_data.phone",
        "asset_data.asset_type",
        "asset_data.usage_type",
        "asset_data.construction_type",
        "asset_data.year_built",
        "asset_data.area_sqm",
        "asset_data.declared_value",
        "asset_data.occupancy",
    ]
    positive_number_fields = {
        "asset_data.year_built",
        "asset_data.area_sqm",
        "asset_data.declared_value",
    }

    def evaluate(self, case_context: QuoteCaseContext) -> ModuleResult:
        quote_request = case_context.reference_data.quote_request
        if not quote_request:
            return ModuleResult(
                module_name=self.module_name,
                status="failed",
                summary="reference_data.quote_request is required before policy rules.",
            )

        client_data = self._object(quote_request.get("client_data"))
        asset_data = self._object(quote_request.get("asset_data"))

        outcome = PolicyRuleOutcome(
            rule_version=self.RULE_VERSION,
            missing_required_fields=self._missing_required_fields(
                client_data,
                asset_data,
            ),
        )

        outcome.matched_rules.append(
            self._rule(
                "quote_required_fields_present",
                "data_completion",
                "Required client and asset fields are present.",
                "standard",
                "Required quote fields were checked.",
            )
        )

        year_built = self._number(asset_data.get("year_built"))
        previous_claims = self._number(asset_data.get("previous_claims_count"))
        usage_type = self._usage_type(
            asset_data.get("usage_type") or asset_data.get("occupancy")
        )
        construction_type = self._construction_type(
            asset_data.get("construction_type")
        )
        declared_value = self._number(asset_data.get("declared_value"))
        property_country = self._country(
            asset_data.get("address"),
            fallback=client_data.get("address"),
        )

        if declared_value <= 0:
            outcome.coverage_flags.append("declared_value_missing_or_zero")

        if property_country and property_country not in {"romania", "ro"}:
            outcome.exclusion_flags.append("unsupported_property_country")
            outcome.failed_rules.append(
                self._rule(
                    "unsupported_property_country",
                    "eligibility",
                    "asset_data.address.country must be Romania",
                    "disapproved",
                    "Property must be located in Romania for this product.",
                    severity="hard",
                )
            )

        if year_built and year_built < 1975:
            outcome.nonstandard_rules.append(
                self._rule(
                    "property_built_before_1975",
                    "property_age",
                    "asset_data.year_built < 1975",
                    "underwriter_review",
                    "Property built before 1975 requires underwriting review.",
                    severity="medium",
                )
            )
        else:
            outcome.matched_rules.append(
                self._rule(
                    "property_age_standard",
                    "property_age",
                    "asset_data.year_built >= 1975 or missing for preview",
                    "standard",
                    "Property age does not trigger nonstandard review.",
                )
            )

        if previous_claims > 5:
            outcome.nonstandard_rules.append(
                self._rule(
                    "property_claims_gt_5",
                    "claims_history",
                    "asset_data.previous_claims_count > 5",
                    "underwriter_review",
                    "More than 5 property claims requires underwriting review.",
                    severity="high",
                )
            )
        else:
            outcome.matched_rules.append(
                self._rule(
                    "property_claims_standard",
                    "claims_history",
                    "asset_data.previous_claims_count <= 5",
                    "standard",
                    "Claims history is within standard quote bounds.",
                )
            )

        if usage_type == "vacant":
            outcome.nonstandard_rules.append(
                self._rule(
                    "vacant_property_use",
                    "property_use",
                    "asset_data.usage_type == vacant",
                    "underwriter_review",
                    "Vacant property use increases exposure and requires review.",
                    severity="medium",
                )
            )
        else:
            outcome.matched_rules.append(
                self._rule(
                    "property_use_standard",
                    "property_use",
                    "asset_data.usage_type is not vacant",
                    "standard",
                    "Property use is inside standard MVP bounds.",
                )
            )

        if construction_type == "wood":
            outcome.nonstandard_rules.append(
                self._rule(
                    "wood_construction",
                    "construction",
                    "asset_data.construction_type == wood",
                    "underwriter_review",
                    "Wood construction adds fire and structural risk.",
                    severity="medium",
                )
            )
        else:
            outcome.matched_rules.append(
                self._rule(
                    "construction_standard",
                    "construction",
                    "asset_data.construction_type is not wood",
                    "standard",
                    "Construction type is inside standard MVP bounds.",
                )
            )

        if outcome.missing_required_fields:
            outcome.failed_rules.append(
                self._rule(
                    "quote_required_fields_missing",
                    "data_completion",
                    "One or more required quote fields are missing.",
                    "pricing_in_progress",
                    "Missing required quote data prevents final quote evaluation.",
                    severity="high",
                )
            )

        if outcome.exclusion_flags:
            outcome.recommended_actions = ["auto_reject"]
        elif not outcome.is_standard:
            outcome.recommended_actions = ["underwriter_review"]
        else:
            outcome.recommended_actions = ["auto_accept"]

        outcome_data = outcome.model_dump(mode="json")
        case_context.domain_payload.rule_outcomes = outcome_data
        case_context.domain_payload.quote_evaluation["policy_rule_outcome"] = (
            outcome_data
        )
        case_context.reference_data.policy_rules = {
            "rule_version": self.RULE_VERSION,
            "source": "static_mvp_policy_rules",
            "is_rules_engine": True,
            "rules": [
                rule.model_dump(mode="json")
                for rule in outcome.matched_rules
                + outcome.failed_rules
                + outcome.nonstandard_rules
            ],
        }
        case_context.checks_and_warnings.rule_warnings = [
            rule.explanation for rule in outcome.nonstandard_rules
        ] + [
            f"Missing required field: {field}"
            for field in outcome.missing_required_fields
        ]

        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary=(
                "Policy rules matched with nonstandard review triggers."
                if outcome.nonstandard_rules
                else "Policy rules matched standard quote conditions."
            ),
            source_fields_used=[
                "reference_data.quote_request",
                "domain_payload.rule_outcomes",
            ],
        )

    def _missing_required_fields(
        self,
        client_data: dict[str, Any],
        asset_data: dict[str, Any],
    ) -> list[str]:
        sections = {
            "client_data": client_data,
            "asset_data": asset_data,
        }
        missing_fields: list[str] = []
        for field_path in self.required_fields:
            section_name, field_name = field_path.split(".", 1)
            value = sections[section_name].get(field_name)
            if not self._has_value(value):
                missing_fields.append(field_path)
                continue
            if field_path in self.positive_number_fields and self._number(value) <= 0:
                missing_fields.append(field_path)
        return missing_fields

    def _rule(
        self,
        policy_rule_id: str,
        category: str,
        condition: str,
        outcome: str,
        explanation: str,
        *,
        severity: str = "info",
    ) -> PolicyRule:
        return PolicyRule(
            policy_rule_id=policy_rule_id,
            version=self.RULE_VERSION,
            category=category,
            condition=condition,
            outcome=outcome,
            severity=severity,
            explanation=explanation,
        )

    def _usage_type(self, value: Any) -> str:
        normalized = self._text(value)
        if normalized in {"vacant"}:
            return "vacant"
        if normalized in {"commercial use", "commercial", "business"}:
            return "commercial use"
        if normalized in {"rented", "rental"}:
            return "rented"
        if normalized in {"holiday home", "holiday"}:
            return "holiday home"
        return "owner occupied"

    def _construction_type(self, value: Any) -> str:
        normalized = self._text(value)
        if normalized in {"wood", "timber"}:
            return "wood"
        if normalized in {"brick"}:
            return "brick"
        if normalized in {"steel"}:
            return "steel"
        return "concrete"

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _number(self, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return number if number > 0 else 0.0

    def _text(self, value: Any) -> str:
        return str(value or "").strip().replace("_", " ").lower()

    def _country(self, value: Any, *, fallback: Any = None) -> str:
        for candidate in (value, fallback):
            if isinstance(candidate, dict):
                country = self._text(candidate.get("country"))
                if country:
                    return country
        return ""

    def _has_value(self, value: Any) -> bool:
        return value is not None and value != "" and value != [] and value != {}


__all__ = ["PolicyRulesModule"]
