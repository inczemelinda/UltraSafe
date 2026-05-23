from __future__ import annotations

import shutil
import subprocess
import json
import os
from hashlib import md5, sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE_DEMO_SEED = ROOT / "sql/002_seed_demo_data.sql"
BACKEND_DEMO_SEED = ROOT / "sql/023_backend_demo_dataset.sql"
CONTRACT_ONE_TO_ONE_MIGRATION = ROOT / "sql/027_contract_source_quote_one_to_one.sql"
WORDING_DOCUMENTS_MIGRATION = ROOT / "sql/028_wording_documents.sql"
CONTRACT_BULLET_POINTS_MIGRATION = ROOT / "sql/029_contract_bullet_points.sql"
CONTRACT_DOCUMENT_TEXT_FORMATTING_MIGRATION = (
    ROOT / "sql/030_contract_document_text_formatting.sql"
)
CONTRACT_COVERAGE_PLACEHOLDERS_MIGRATION = (
    ROOT / "sql/031_contract_coverage_placeholders.sql"
)
CONTRACT_ASCII_TABLE_CLEANUP_MIGRATION = (
    ROOT / "sql/032_contract_ascii_table_cleanup.sql"
)
LEGAL_REVIEW_DEMO_SEED = ROOT / "sql/024_legal_review_demo_dataset.sql"
QUOTE_DECISION_AUDIT_MIGRATION = ROOT / "sql/035_quote_decision_audit.sql"
CUSTOMER_PROFILE_DOCUMENTS_MIGRATION = (
    ROOT / "sql/037_customer_profile_documents.sql"
)
GENERATED_PROPERTY_UNSIGNED_MIGRATION = (
    ROOT / "sql/038_generated_property_contract_unsigned_state.sql"
)
DEMO_CONTRACT_PDFS = [
    ROOT / "generated/pdfs/demo-contract-pad-risk.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-property.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-maria.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-andrei.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-ioana.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-carpatica.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-elena.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-george.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-vlad.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-simona.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-radu.pdf",
    ROOT / "generated/pdfs/demo-contract-pad-alex.pdf",
]
DEMO_ARTIFACT_INSTALLER = ROOT / "scripts/install_demo_artifacts.sh"
DEMO_CLAIM_ARTIFACTS = ROOT / "demo_artifacts/claim_attachments"
DEMO_PROFILE_ARTIFACTS = ROOT / "demo_artifacts/profile_documents"


def test_backend_demo_seed_runs_after_backend_schema_migrations() -> None:
    sql_files = sorted(path.name for path in (ROOT / "sql").glob("*.sql"))

    assert "004_quote_requests.sql" < BACKEND_DEMO_SEED.name
    assert "005_quote_documents.sql" < BACKEND_DEMO_SEED.name
    assert "019_generated_document_pdf_metadata.sql" < BACKEND_DEMO_SEED.name
    assert sql_files.index(BACKEND_DEMO_SEED.name) > sql_files.index(
        "019_generated_document_pdf_metadata.sql"
    )
    assert CONTRACT_ONE_TO_ONE_MIGRATION.name in sql_files
    assert WORDING_DOCUMENTS_MIGRATION.name in sql_files
    assert CONTRACT_BULLET_POINTS_MIGRATION.name in sql_files
    assert CONTRACT_DOCUMENT_TEXT_FORMATTING_MIGRATION.name in sql_files
    assert CONTRACT_COVERAGE_PLACEHOLDERS_MIGRATION.name in sql_files
    assert CONTRACT_ASCII_TABLE_CLEANUP_MIGRATION.name in sql_files
    assert QUOTE_DECISION_AUDIT_MIGRATION.name in sql_files
    assert CUSTOMER_PROFILE_DOCUMENTS_MIGRATION.name in sql_files
    assert GENERATED_PROPERTY_UNSIGNED_MIGRATION.name in sql_files


def test_backend_demo_seed_populates_frontend_backend_tables() -> None:
    seed_sql = BACKEND_DEMO_SEED.read_text(encoding="utf-8")

    assert "DELETE FROM claim_request;" in seed_sql
    assert "ON CONFLICT (request_id) DO UPDATE" in seed_sql

    for table_name in [
        "customer",
        "auth_user",
        "quote_request",
        "claim_request",
        "email_messages",
        "quote_document",
        "quote_acceptance",
        "quote_decision_audit",
        "generated_document",
        "customer_profile_document",
    ]:
        assert f"INSERT INTO {table_name}" in seed_sql

    assert "Maria Ionescu" in seed_sql
    assert "Alex Vulcu" in seed_sql
    assert "alex.vulcu@ultrasafe.ro" in seed_sql
    assert "CLM-DEMO-ALEX-001" in seed_sql
    assert "'decision', CASE" in seed_sql
    assert "THEN 'approved'" in seed_sql
    assert "'decision_status'" in seed_sql
    assert "'decision_justification'" in seed_sql
    assert "'decided_by'" in seed_sql
    assert "'decided_at'" in seed_sql
    assert "Carpatica Retail SRL" in seed_sql
    assert "000000000032" in seed_sql

    for quote_status in [
        "draft",
        "pricing_in_progress",
        "quote_ready",
        "auto_accepted",
        "underwriter_review",
        "approved",
        "disapproved",
        "field_review_required",
        "failed",
    ]:
        assert f"'{quote_status}'" in seed_sql

    for claim_status in [
        "submitted",
        "screening",
        "needs_underwriter_review",
        "coverage_review_required",
        "in_review",
        "completed",
        "failed",
    ]:
        assert f"'{claim_status}'" in seed_sql

    assert "source_quote_request_id" in seed_sql
    assert "source_quote_document_id" in seed_sql
    assert "source_quote_acceptance_id" in seed_sql
    assert "SET source_quote_request_id = NULL" not in seed_sql
    assert "DELETE FROM quote_request;" not in seed_sql
    assert "33333333-3333-4333-8333-000000000101" in seed_sql
    assert "demo-seeded-outbound-alex-001" in seed_sql
    assert "demo-seeded-inbound-alex-001" in seed_sql
    for pdf_path in DEMO_CONTRACT_PDFS:
        assert pdf_path.name in seed_sql
    assert "Demo generated property contract document" not in seed_sql
    assert "Document generated from approved demo quote" not in seed_sql
    assert "PAD-PROPERTY-2026-000150" in seed_sql
    assert "source_quote_acceptance_id = NULL" in seed_sql
    assert "Quote approved and contract generated for client signature" in seed_sql
    assert "demo-quote-content-hash-1002" not in seed_sql
    assert "PAD-MARIA-2026-000201" in seed_sql
    assert "PAD-ANDREI-2026-000202" in seed_sql
    assert "PAD-IOANA-2026-000203" in seed_sql
    assert "PAD-CARPATICA-2026-000204" in seed_sql
    assert "PAD-DEMO-ELENA-2026-000301" in seed_sql
    assert "PAD-DEMO-GEORGE-2026-000302" in seed_sql
    assert "PAD-DEMO-VLAD-2026-000303" in seed_sql
    assert "PAD-DEMO-SIMONA-2026-000304" in seed_sql
    assert "PAD-DEMO-RADU-2026-000305" in seed_sql
    assert "PAD-DEMO-ALEX-2026-000401" in seed_sql
    assert "11111111-1111-4111-8111-000000000007" in seed_sql
    assert "field_review_required" in seed_sql
    assert "Coastal wind exposure requires local inspection" in seed_sql
    assert "array_to_string(ARRAY[" in seed_sql
    assert "concat_ws(chr(10)" not in seed_sql
    assert "application/zip" not in seed_sql
    assert "pg_temp.demo_claim_attachment" in seed_sql
    assert "'storage_key', md5('claim:'" in seed_sql
    assert "'extraction_status', 'completed'" in seed_sql
    assert "metadata ->> 'generation_mode' = 'demo_seed'" in seed_sql
    assert "NULL, 'PAD-DEMO-" not in seed_sql


def test_backend_demo_contract_pdfs_are_full_policy_artifacts() -> None:
    seed_sql = BACKEND_DEMO_SEED.read_text(encoding="utf-8")

    for pdf_path in DEMO_CONTRACT_PDFS:
        pdf_bytes = pdf_path.read_bytes()

        assert len(pdf_bytes) > 100_000
        assert b"Demo generated property contract document" not in pdf_bytes
        assert sha256(pdf_bytes).hexdigest() in seed_sql


def test_backend_demo_contract_pdfs_do_not_include_demo_cover_headers() -> None:
    pdftotext = shutil.which("pdftotext")
    if pdftotext is None:
        return

    for pdf_path in DEMO_CONTRACT_PDFS:
        extracted = subprocess.run(
            [pdftotext, str(pdf_path), "-"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout

        assert extracted.startswith("POLIȚĂ DE ASIGURARE")
        assert "Document: Contract PAD demo" not in extracted
        assert "\nAsigurat: " not in extracted


def test_demo_client_auth_user_matches_seeded_customer_profile() -> None:
    base_seed_sql = BASE_DEMO_SEED.read_text(encoding="utf-8")
    backend_seed_sql = BACKEND_DEMO_SEED.read_text(encoding="utf-8")

    assert "'Vasile Valoare'" in base_seed_sql
    assert "'vasile.valoare@client.com'" in base_seed_sql
    assert "'vasile.valoare@client.com'" in backend_seed_sql
    assert "'ioana.polita@underwright.com'" in backend_seed_sql
    assert "'Ioana Poliță'" in base_seed_sql
    assert "'Ioana Poliță'" in backend_seed_sql
    assert "Ioana Polita" not in base_seed_sql
    assert "Ioana Polita" not in backend_seed_sql
    assert "'underwriter'" in backend_seed_sql
    assert "(SELECT id FROM customer WHERE full_name = 'Vasile Valoare' LIMIT 1)" in base_seed_sql
    assert "(SELECT id FROM customer WHERE email = 'vasile.valoare@client.com' LIMIT 1)" in backend_seed_sql
    assert "ion.popescu@example.test" not in base_seed_sql
    assert "ion.popescu@example.test" not in backend_seed_sql
    assert "Ion Popescu" not in backend_seed_sql


def test_base_demo_seed_creates_contracts_from_source_quotes() -> None:
    seed_sql = BASE_DEMO_SEED.read_text(encoding="utf-8")

    assert "INSERT INTO quote_request" in seed_sql
    assert "INSERT INTO quote_document" in seed_sql
    assert "source_quote_request_id" in seed_sql
    assert "source_quote_document_id = quote_document.id" in seed_sql
    assert "\N{BULLET} tip imobil" in seed_sql
    assert "* tip imobil" not in seed_sql
    assert "| Categoria" not in seed_sql
    assert "Suma asigurată totală este de {{coverage.total_sum_insured}} RON." in (
        seed_sql
    )
    assert "{{coverage.building_sum_insured}} RON" in seed_sql
    assert "{{coverage.contents_sum_insured}} RON" in seed_sql


def test_backend_demo_seed_is_wired_into_manual_seed_script() -> None:
    seed_script = (ROOT / "scripts/db_seed_demo.sh").read_text(encoding="utf-8")

    assert "source .env" in seed_script
    assert "DATABASE_URL=\"postgresql://" in seed_script
    assert "POSTGRES_HOST" in seed_script
    assert "sql/002_seed_demo_data.sql" in seed_script
    assert "sql/023_backend_demo_dataset.sql" in seed_script
    assert "scripts/install_demo_artifacts.sh" in seed_script


def test_demo_claim_and_profile_artifacts_are_real_pdfs() -> None:
    claim_artifacts = sorted(DEMO_CLAIM_ARTIFACTS.glob("*/*.pdf"))
    profile_artifacts = sorted(DEMO_PROFILE_ARTIFACTS.glob("*/*.pdf"))

    assert len(claim_artifacts) >= 30
    assert len(profile_artifacts) >= 20

    for artifact in [*claim_artifacts, *profile_artifacts]:
        pdf_bytes = artifact.read_bytes()

        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 700


def test_demo_artifact_installer_materializes_seed_storage_keys(tmp_path) -> None:
    claim_upload_dir = tmp_path / "claim-uploads"
    pdf_storage_dir = tmp_path / "pdfs"
    env = {
        **os.environ,
        "UNDERWRIGHT_CLAIM_UPLOAD_DIR": str(claim_upload_dir),
        "UNDERWRIGHT_PDF_STORAGE_DIR": str(pdf_storage_dir),
    }

    subprocess.run([str(DEMO_ARTIFACT_INSTALLER)], check=True, env=env)

    for source in DEMO_CLAIM_ARTIFACTS.glob("*/*.pdf"):
        owner = source.parent.name
        storage_key = md5(f"claim:{owner}:{source.name}".encode()).hexdigest()
        stored = claim_upload_dir / storage_key
        metadata = json.loads((claim_upload_dir / f"{storage_key}.json").read_text())

        assert stored.read_bytes() == source.read_bytes()
        assert metadata["file_name"] == source.name
        assert metadata["content_type"] == "application/pdf"
        assert metadata["size_bytes"] == source.stat().st_size

    for source in DEMO_PROFILE_ARTIFACTS.glob("*/*.pdf"):
        owner = source.parent.name
        storage_key = md5(f"profile:{owner}:{source.name}".encode()).hexdigest()
        stored = claim_upload_dir / storage_key
        metadata = json.loads((claim_upload_dir / f"{storage_key}.json").read_text())

        assert stored.read_bytes() == source.read_bytes()
        assert metadata["file_name"] == source.name
        assert metadata["content_type"] == "application/pdf"
        assert metadata["size_bytes"] == source.stat().st_size

    for pdf_path in DEMO_CONTRACT_PDFS:
        assert (pdf_storage_dir / pdf_path.name).read_bytes() == pdf_path.read_bytes()


def test_docker_postgres_init_runs_migration_and_seed_scripts() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "COPY sql/ /docker-entrypoint-initdb.d/sql/" in dockerfile
    assert "COPY scripts/db_migrate.sh /docker-entrypoint-initdb.d/001_db_migrate.sh" in dockerfile
    assert "COPY scripts/db_seed_demo.sh /docker-entrypoint-initdb.d/002_db_seed_demo.sh" in dockerfile
    assert "/docker-entrypoint-initdb.d/001_db_migrate.sh" in dockerfile
    assert "/docker-entrypoint-initdb.d/002_db_seed_demo.sh" in dockerfile
    assert "COPY sql/*.sql /docker-entrypoint-initdb.d/" not in dockerfile
    assert "!scripts/" in dockerignore
    assert "!scripts/db_migrate.sh" in dockerignore
    assert "!scripts/db_seed_demo.sh" in dockerignore


def test_database_scripts_resolve_repo_or_docker_init_root() -> None:
    for script_name in ["db_migrate.sh", "db_seed_demo.sh"]:
        script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")

        assert 'script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"' in script
        assert 'if [[ -d "${script_dir}/../sql" ]]' in script
        assert 'project_root="$script_dir"' in script
        assert 'cd "$project_root"' in script


def test_database_scripts_build_database_url_from_env_file() -> None:
    for script_name in ["db_migrate.sh", "db_seed_demo.sh"]:
        script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")

        assert "source .env" in script
        assert "DATABASE_URL=\"postgresql://" in script
        assert 'postgres_host="${POSTGRES_HOST:-127.0.0.1}"' in script
        assert 'if [[ "$postgres_host" == "0.0.0.0" ]]' in script


def test_database_scripts_use_postgres_socket_during_docker_init() -> None:
    for script_name in ["db_migrate.sh", "db_seed_demo.sh"]:
        script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")

        assert 'if [[ "$project_root" == "/docker-entrypoint-initdb.d" ]]' in script
        assert 'psql_connection_args+=("-U" "$POSTGRES_USER" "-d" "$POSTGRES_DB")' in script
        assert 'psql "${psql_connection_args[@]}" -f' in script
        assert 'psql -v ON_ERROR_STOP=1 "$DATABASE_URL"' not in script


def test_migrate_script_creates_quote_decision_audit_table_for_docker_init() -> None:
    migration_sql = QUOTE_DECISION_AUDIT_MIGRATION.read_text(encoding="utf-8")
    migrate_script = (ROOT / "scripts/db_migrate.sh").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS quote_decision_audit" in migration_sql
    assert "idx_quote_decision_audit_quote_request" in migration_sql
    assert "sql/035_quote_decision_audit.sql" in migrate_script
    assert migrate_script.index("sql/034_normalized_legal_document_structured_clauses.sql") < (
        migrate_script.index("sql/035_quote_decision_audit.sql")
    )


def test_migrate_script_creates_customer_profile_documents_table_for_docker_init() -> None:
    migration_sql = CUSTOMER_PROFILE_DOCUMENTS_MIGRATION.read_text(encoding="utf-8")
    migrate_script = (ROOT / "scripts/db_migrate.sh").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS customer_profile_document" in migration_sql
    assert "REFERENCES customer(id) ON DELETE CASCADE" in migration_sql
    assert "idx_customer_profile_document_customer" in migration_sql
    assert "idx_customer_profile_document_active_label" in migration_sql
    assert "sql/037_customer_profile_documents.sql" in migrate_script
    assert migrate_script.index("sql/036_template_draft_revision_approval_submission.sql") < (
        migrate_script.index("sql/037_customer_profile_documents.sql")
    )
    assert migrate_script.index("sql/035_quote_decision_audit.sql") < (
        migrate_script.index("sql/036_template_draft_revision_approval_submission.sql")
    )


def test_contract_one_to_one_migration_documents_validation_queries() -> None:
    migration_sql = CONTRACT_ONE_TO_ONE_MIGRATION.read_text(encoding="utf-8")

    assert "ALTER COLUMN source_quote_request_id SET NOT NULL" in migration_sql
    assert "idx_contract_source_quote_request_id" in migration_sql
    assert "fk_contract_source_quote_document_request" in migration_sql
    assert "Quotes with no contract, informational only" in migration_sql
    assert "WHERE source_quote_request_id IS NULL" in migration_sql


def test_wording_documents_migration_adds_first_class_wording_seed() -> None:
    migration_sql = WORDING_DOCUMENTS_MIGRATION.read_text(encoding="utf-8")
    migrate_script = (ROOT / "scripts/db_migrate.sh").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS wording_document" in migration_sql
    assert "CREATE TABLE IF NOT EXISTS wording_document_version" in migration_sql
    assert "UNIQUE (wording_document_id, version)" in migration_sql
    assert "code TEXT NOT NULL UNIQUE" in migration_sql
    assert "DEMO_PAD_POLICY_WORDING_RO" in migration_sql
    assert "2a9480a11038b3b86218dc2e2d93e0d76fbc4d8399839f13a3f6b464d53d22ca" in (
        migration_sql
    )
    assert "Document demonstrativ utilizat exclusiv pentru testare" in migration_sql
    assert "CAPITOLUL I - DEFINIȚII" in migration_sql
    assert "CAPITOLUL XIII - STABILIREA ȘI PLATA DESPĂGUBIRILOR" in migration_sql
    assert "Asiguratul trebuie să notifice dauna în termen de 10 zile calendaristice" in (
        migration_sql
    )
    assert "ON CONFLICT (wording_document_id, version) DO NOTHING" in migration_sql
    assert "sql/028_wording_documents.sql" in migrate_script
    assert "sql/028_wording_documents.sql" in (
        ROOT / "scripts/db_seed_demo.sh"
    ).read_text(encoding="utf-8")


def test_contract_bullet_points_migration_normalizes_existing_contract_text() -> None:
    migration_sql = CONTRACT_BULLET_POINTS_MIGRATION.read_text(encoding="utf-8")
    migrate_script = (ROOT / "scripts/db_migrate.sh").read_text(encoding="utf-8")

    assert "regexp_replace" in migration_sql
    assert "chr(8226)" in migration_sql
    assert "UPDATE template" in migration_sql
    assert "UPDATE quote_document" in migration_sql
    assert "UPDATE generated_document" in migration_sql
    assert "sql/029_contract_bullet_points.sql" in migrate_script


def test_contract_document_text_formatting_migration_removes_ascii_tables() -> None:
    migration_sql = CONTRACT_DOCUMENT_TEXT_FORMATTING_MIGRATION.read_text(
        encoding="utf-8"
    )
    migrate_script = (ROOT / "scripts/db_migrate.sh").read_text(encoding="utf-8")

    assert "regexp_replace" in migration_sql
    assert "Suma asigurată totală este de" in migration_sql
    assert "UPDATE template" in migration_sql
    assert "UPDATE quote_document" in migration_sql
    assert "UPDATE generated_document" in migration_sql
    assert "sql/030_contract_document_text_formatting.sql" in migrate_script


def test_contract_coverage_placeholders_migration_updates_existing_templates() -> None:
    migration_sql = CONTRACT_COVERAGE_PLACEHOLDERS_MIGRATION.read_text(
        encoding="utf-8"
    )
    migrate_script = (ROOT / "scripts/db_migrate.sh").read_text(encoding="utf-8")

    assert "{{coverage.total_sum_insured}} RON" in migration_sql
    assert "{{coverage.building_sum_insured}} RON" in migration_sql
    assert "{{coverage.contents_sum_insured}} RON" in migration_sql
    assert "{{insured_asset.declared_value}} {{contract_meta.currency}}" in (
        migration_sql
    )
    assert "sql/031_contract_coverage_placeholders.sql" in migrate_script


def test_contract_ascii_table_cleanup_migration_updates_persisted_documents() -> None:
    migration_sql = CONTRACT_ASCII_TABLE_CLEANUP_MIGRATION.read_text(
        encoding="utf-8"
    )
    migrate_script = (ROOT / "scripts/db_migrate.sh").read_text(encoding="utf-8")

    assert "UPDATE template" in migration_sql
    assert "UPDATE generated_document" in migration_sql
    assert "UPDATE quote_document" in migration_sql
    assert "Suma asigurată totală este de" in migration_sql
    assert "{{coverage.total_sum_insured}} RON" in migration_sql
    assert "\\\\r?\\\\n" in migration_sql
    assert "sql/032_contract_ascii_table_cleanup.sql" in migrate_script


def test_legal_review_demo_seed_populates_review_queue_tables() -> None:
    sql_files = sorted(path.name for path in (ROOT / "sql").glob("*.sql"))
    seed_sql = LEGAL_REVIEW_DEMO_SEED.read_text(encoding="utf-8")
    seed_script = (ROOT / "scripts/db_seed_demo.sh").read_text(encoding="utf-8")

    assert sql_files.index(LEGAL_REVIEW_DEMO_SEED.name) > sql_files.index(
        "020_template_change_suggestion_hunk_context.sql"
    )
    assert "sql/024_legal_review_demo_dataset.sql" in seed_script

    for table_name in [
        "raw_source_item",
        "normalized_legal_document",
        "legal_document_normalization_result",
        "legal_document_template_review_candidate",
        "template_change_suggestion",
        "template_change_suggestion_hunk",
    ]:
        assert f"INSERT INTO {table_name}" in seed_sql

    assert seed_sql.count("'needs_review'") >= 10
    assert "'accepted'" in seed_sql
    assert "'dismissed'" in seed_sql
    assert "DEMO_PAD_POLICY_WORDING_RO" in seed_sql
    assert "SELECT version.full_text" in seed_sql
    assert "3ea24a1263372c20d2511cad4df06c7fca6cbe2c2e1b082934c72296df7310d5" in seed_sql
    assert "10 zile calendaristice" in seed_sql
    assert "5 zile calendaristice" in seed_sql
