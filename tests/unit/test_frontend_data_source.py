import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend" / "src"


def read_frontend_source(relative_path: str) -> str:
    return (ROOT / "frontend" / relative_path).read_text(encoding="utf-8")


def test_mock_api_requires_explicit_true() -> None:
    source = read_frontend_source("src/config/dataSource.ts")

    assert 'export const USE_MOCK_DATA = envMockFlag === "true";' in source
    assert "envMockFlag == null ? true" not in source
    assert 'envMockFlag !== "false"' not in source


def test_mock_api_mode_has_development_indicator_and_warning() -> None:
    config_source = read_frontend_source("src/config/dataSource.ts")
    layout_source = read_frontend_source("src/layouts/AppLayouts.tsx")

    assert "SHOW_MOCK_DATA_INDICATOR" in config_source
    assert "console.warn" in config_source
    assert "Mock data mode is enabled" in config_source
    assert "MockDataIndicator" in layout_source
    assert "Mock data mode" in layout_source


def test_mock_local_storage_helpers_stay_inside_mock_services() -> None:
    offenders: list[str] = []
    for path in FRONTEND_SRC.rglob("*.ts*"):
        relative = path.relative_to(ROOT).as_posix()
        if relative == "frontend/src/services/storage.ts":
            continue
        source = path.read_text(encoding="utf-8")
        if "../storage" in source or "./storage" in source:
            if "/services/mock/" not in relative:
                offenders.append(relative)

    assert offenders == []


def test_direct_browser_storage_has_explicit_non_authoritative_allowlist() -> None:
    allowed = {
        "frontend/src/pages/ClientPages.tsx",  # local autosaved, unsubmitted form drafts
        "frontend/src/services/authSession.ts",  # backend-issued auth session cache
        "frontend/src/services/storage.ts",  # explicit mock service helper
    }
    offenders: list[str] = []
    for path in FRONTEND_SRC.rglob("*.ts*"):
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        if "window.localStorage" in source or "window.sessionStorage" in source:
            if relative not in allowed and "/services/mock/" not in relative:
                offenders.append(relative)

    assert offenders == []


def test_mock_data_fixtures_are_not_imported_by_backend_or_pages() -> None:
    offenders: list[str] = []
    for path in FRONTEND_SRC.rglob("*.ts*"):
        relative = path.relative_to(ROOT).as_posix()
        if "/data/" in relative:
            continue
        source = path.read_text(encoding="utf-8")
        if "../data/mock" in source or "../../data/mock" in source:
            if "/services/mock/" not in relative:
                offenders.append(relative)

    assert offenders == []


def test_domain_facades_select_mock_only_from_explicit_flag() -> None:
    domain_facades = [
        "src/services/authService.ts",
        "src/services/customerProfileService.ts",
        "src/services/profileDocumentService.ts",
        "src/services/emailService.ts",
        "src/services/newsService.ts",
        "src/services/contractService.ts",
        "src/services/quoteService.ts",
        "src/services/claimService.ts",
    ]

    for facade_path in domain_facades:
        source = read_frontend_source(facade_path)

        assert 'import { USE_MOCK_DATA } from "../config/dataSource";' in source
        assert re.search(r"USE_MOCK_DATA\s*\?\s*mock", source)
        assert "catch" not in source
        assert "localStorage" not in source
        assert "sessionStorage" not in source


def test_backend_readers_do_not_silently_hide_non_404_failures() -> None:
    quote_source = read_frontend_source("src/services/backend/quoteService.ts")
    claim_source = read_frontend_source("src/services/backend/claimService.ts")

    assert "catch {\n    return undefined;" not in quote_source
    assert "catch {\n    return undefined;" not in claim_source
    assert "if (isNotFoundApiError(error)) return undefined;" in quote_source
    assert "if (isNotFoundApiError(error)) return undefined;" in claim_source
