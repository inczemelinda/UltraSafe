from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_frontend_source(relative_path: str) -> str:
    return (ROOT / "frontend" / relative_path).read_text(encoding="utf-8")


def test_employee_sidebar_has_only_bottom_account_navigation_button() -> None:
    sidebar = read_frontend_source("src/components/navigation/AppSidebar.tsx")
    navigation = read_frontend_source("src/config/navigation.ts")

    assert sidebar.count('to="/employee/account"') == 1
    assert sidebar.count('aria-label="Employee account"') == 1
    assert 'id: "employee-account"' not in navigation
    assert 'href: "/employee/account"' not in navigation
