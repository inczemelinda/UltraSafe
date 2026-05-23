from underwright.domain.case_context_base import PersistedCaseContext
from uuid import UUID

CASE_ID = UUID("00000000-0000-0000-0000-000000000123")
CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000001")


def test_persisted_case_context_shape():
    context = PersistedCaseContext(
        id=1,
        case_id=CASE_ID,
        domain="contracts",
        workflow_name="contract_drafting",
        status="draft",
        context_json={
                "case_metadata": {
                    "case_id": str(CASE_ID),
                    "domain": "contracts",
                },
                "domain_payload": {
                    "contract_generation_payload": {
                        "contract_id": str(CONTRACT_ID),
                    }
                },
            },
        )

    assert context.id == 1
    assert context.case_id == CASE_ID
    assert context.domain == "contracts"
    assert context.workflow_name == "contract_drafting"
    assert context.status == "draft"
    assert isinstance(context.context_json, dict)
    assert context.context_json["domain_payload"]["contract_generation_payload"]["contract_id"] == str(CONTRACT_ID)
