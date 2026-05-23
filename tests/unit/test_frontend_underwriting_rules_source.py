from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_frontend_source(relative_path: str) -> str:
    return (ROOT / "frontend" / relative_path).read_text(encoding="utf-8")


def test_employee_rules_page_uses_backend_document_without_frontend_merging() -> None:
    source = read_frontend_source("src/pages/EmployeePages.tsx")
    rules_page = source.split("export function EmployeeRulesPage()", 1)[1].split(
        "function EditableRuleBlock",
        1,
    )[0]

    assert "buildFrontendRulesDocument" not in source
    assert "mergeRulesDocument" not in source
    assert "../data/rulesContent" not in source
    assert "setRules(fallback)" not in rules_page
    assert "Backend unavailable. Showing frontend defaults" not in source
    assert "setRules(document)" in rules_page
    assert "setRules(undefined)" in rules_page
    assert "No backend underwriting rules are configured yet." in rules_page
    assert "Could not load underwriting rules" in rules_page


def test_underwriting_rules_mock_data_is_explicitly_selected_and_labeled() -> None:
    page_source = read_frontend_source("src/pages/EmployeePages.tsx")
    service_source = read_frontend_source("src/services/rulesService.ts")
    mock_service_source = read_frontend_source("src/services/mock/rulesService.ts")
    backend_service_source = read_frontend_source("src/services/backend/rulesService.ts")

    assert 'DATA_SOURCE_MODE === "mock"' in page_source
    assert "Demo underwriting rules" in page_source
    assert "These local rules are for demos only" in page_source
    assert "USE_MOCK_DATA ? mockRulesService : backendRulesService" in service_source
    assert "buildMockUnderwritingRulesDocument" in mock_service_source
    assert "mockRulesService" not in backend_service_source
