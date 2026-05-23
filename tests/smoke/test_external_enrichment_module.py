from underwright.application.modules.external_enrichment_module import ExternalEnrichmentModule
from underwright.domain.contract_case_context import ContractCaseContext


def test_external_enrichment_is_deterministic():
    module = ExternalEnrichmentModule()

    context1 = ContractCaseContext()
    context2 = ContractCaseContext()

    result1 = module.run(context1)
    module.run(context2)

    # basic checks
    assert result1.status == "success"
    assert result1.module_name == "external_enrichment"

    # ModuleResult is a receipt; context keeps the state.
    assert isinstance(context1, ContractCaseContext)

    signals1 = context1.external_signals
    signals2 = context2.external_signals

    # structure checks
    assert isinstance(signals1.location_signals, dict)
    assert isinstance(signals1.property_signals, dict)
    assert isinstance(signals1.regulatory_signals, dict)

    # deterministic values
    assert signals1.location_signals["risk_level"] == "medium"
    assert signals1.location_signals["flood_zone"] is False

    assert signals1.property_signals["property_age_risk"] == "low"

    assert signals1.regulatory_signals["compliant"] is True

    # determinism check
    assert signals1 == signals2
