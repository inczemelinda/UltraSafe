from __future__ import annotations

from underwright.domain.module_result import ModuleResult
from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.quote_request import QuoteRequest


class QuoteApprovalModule:
    """Routes complete quotes from deterministic policy rule outcomes."""

    module_name = "QuoteApprovalModule"

    def evaluate(
        self,
        quote_request: QuoteRequest,
        case_context: QuoteCaseContext,
    ) -> ModuleResult:
        rule_outcomes = case_context.domain_payload.rule_outcomes
        nonstandard_rules = rule_outcomes.get("nonstandard_rules", [])
        failed_rules = rule_outcomes.get("failed_rules", [])
        missing_required_fields = rule_outcomes.get("missing_required_fields", [])
        exclusion_flags = rule_outcomes.get("exclusion_flags", [])
        hard_failed_rules = [
            rule
            for rule in failed_rules
            if str(rule.get("severity") or "").lower() == "hard"
        ]

        is_standard = not (
            nonstandard_rules
            or failed_rules
            or missing_required_fields
            or exclusion_flags
        )
        if quote_request.request_status in {"approved", "auto_accepted", "disapproved"}:
            status = quote_request.request_status
            decision_source = (
                "underwriter_decision"
                if status in {"approved", "disapproved"}
                else "existing_quote_status"
            )
            reasons = [f"preserved_{status}_status"]
        elif exclusion_flags or hard_failed_rules:
            status = "disapproved"
            decision_source = "policy_rules_module"
            reasons = [
                str(rule.get("policy_rule_id", "hard_rule"))
                for rule in hard_failed_rules
            ] or [str(flag) for flag in exclusion_flags]
        else:
            status = "auto_accepted" if is_standard else "underwriter_review"
            decision_source = "policy_rules_module"
            reasons = (
                ["standard_quote_rules_matched"]
                if is_standard
                else [
                    str(rule.get("policy_rule_id", "nonstandard_rule"))
                    for rule in nonstandard_rules or failed_rules
                ]
            )
        decision = {
            "status": status,
            "decision_source": decision_source,
            "reasons": reasons,
            "rule_version": rule_outcomes.get("rule_version"),
            "nonstandard_rules": nonstandard_rules,
            "exclusion_flags": exclusion_flags,
        }
        case_context.domain_payload.approval_decision = decision
        case_context.domain_payload.quote_evaluation["approval_decision"] = decision
        case_context.case_metadata.status = status
        quote_request.request_status = status

        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary=(
                "Quote approval status preserved for document generation."
                if decision_source != "policy_rules_module"
                else (
                    "Quote disapproved by hard deterministic policy rules."
                    if status == "disapproved"
                    else "Quote auto-accepted by deterministic policy rules."
                    if is_standard
                    else "Quote routed to underwriter review by policy rules."
                )
            ),
            source_fields_used=[
                "quote_request.mandatory_data_status",
                "quote_case_context.domain_payload.rule_outcomes",
                "quote_case_context.domain_payload.approval_decision",
            ],
        )


__all__ = ["QuoteApprovalModule"]
