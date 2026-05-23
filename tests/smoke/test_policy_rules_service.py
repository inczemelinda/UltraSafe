from underwright.application.services.policy_rules_service import PolicyRulesService
from underwright.domain.contract_case_context import ContractCaseContext


def test_policy_rules_service_attaches_rules_to_context():
    service = PolicyRulesService()
    context = ContractCaseContext()

    result = service.attach_policy_rules(context)

    policy_rules = result.reference_data.policy_rules

    assert policy_rules["version"] == "v1"
    assert policy_rules["source"] == "static_mvp_policy_rules"
    assert policy_rules["rules"]["document_type"] == "PAD"
    assert policy_rules["rules"]["jurisdiction"] == "RO"
    assert policy_rules["rules"]["requires_client_profile"] is True
    assert policy_rules["rules"]["requires_property_profile"] is True
    assert policy_rules["metadata"]["is_rules_engine"] is False