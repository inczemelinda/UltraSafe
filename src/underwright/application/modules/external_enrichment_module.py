from underwright.domain.contract_case_context import ContractCaseContext
from underwright.domain.module_result import ModuleResult


class ExternalEnrichmentModule:

    def run(self, case_context: ContractCaseContext) -> ModuleResult:
        # deterministic stub data
        case_context.external_signals.location_signals = {
            "risk_level": "medium",
            "flood_zone": False,
        }

        case_context.external_signals.property_signals = {
            "property_age_risk": "low",
        }

        case_context.external_signals.regulatory_signals = {
            "compliant": True,
        }

        return ModuleResult(
            module_name="external_enrichment",
            status="success",
            summary="External signals attached.",
            source_fields_used=["external_signals"],
        )
