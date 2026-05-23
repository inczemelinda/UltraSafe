#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "${script_dir}/../sql" ]]; then
  project_root="$(cd -- "${script_dir}/.." && pwd)"
else
  project_root="$script_dir"
fi
cd "$project_root"

if [[ -z "${DATABASE_URL:-}" && -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

psql_connection_args=("-v" "ON_ERROR_STOP=1")

if [[ -n "${DATABASE_URL:-}" ]]; then
  psql_connection_args+=("$DATABASE_URL")
else
  : "${POSTGRES_USER:?POSTGRES_USER or DATABASE_URL is required}"
  : "${POSTGRES_DB:?POSTGRES_DB or DATABASE_URL is required}"

  if [[ "$project_root" == "/docker-entrypoint-initdb.d" ]]; then
    psql_connection_args+=("-U" "$POSTGRES_USER" "-d" "$POSTGRES_DB")
  else
    : "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD or DATABASE_URL is required}"

    postgres_host="${POSTGRES_HOST:-127.0.0.1}"
    if [[ "$postgres_host" == "0.0.0.0" ]]; then
      postgres_host="127.0.0.1"
    fi

    DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${postgres_host}:${POSTGRES_PORT:-5432}/${POSTGRES_DB}"
    psql_connection_args+=("$DATABASE_URL")
  fi
fi

psql "${psql_connection_args[@]}" -f sql/001_init_schema.sql
psql "${psql_connection_args[@]}" -f sql/003_claim_requests.sql
psql "${psql_connection_args[@]}" -f sql/004_quote_requests.sql
psql "${psql_connection_args[@]}" -f sql/005_quote_documents.sql
psql "${psql_connection_args[@]}" -f sql/006_intelligence_schema.sql
psql "${psql_connection_args[@]}" -f sql/007_intelligence_template_review_candidates.sql
psql "${psql_connection_args[@]}" -f sql/010_legal_document_sources.sql
psql "${psql_connection_args[@]}" -f sql/011_normalized_legal_documents.sql
psql "${psql_connection_args[@]}" -f sql/012_legal_demo_template_metadata.sql
psql "${psql_connection_args[@]}" -f sql/013_legal_document_template_review_candidates.sql
psql "${psql_connection_args[@]}" -f sql/014_template_change_suggestions.sql
psql "${psql_connection_args[@]}" -f sql/015_template_draft_revisions.sql
psql "${psql_connection_args[@]}" -f sql/016_claim_precheck_statuses.sql
psql "${psql_connection_args[@]}" -f sql/017_contract_quote_lifecycle.sql
psql "${psql_connection_args[@]}" -f sql/017_underwriting_rules.sql
psql "${psql_connection_args[@]}" -f sql/018_generated_document_metadata.sql
psql "${psql_connection_args[@]}" -f sql/019_generated_document_pdf_metadata.sql
psql "${psql_connection_args[@]}" -f sql/020_template_change_suggestion_hunk_context.sql
psql "${psql_connection_args[@]}" -f sql/022_customer_profile_audit.sql
psql "${psql_connection_args[@]}" -f sql/025_customer_auth_user_link_audit.sql
psql "${psql_connection_args[@]}" -f sql/026_quote_acceptance.sql
psql "${psql_connection_args[@]}" -f sql/027_contract_source_quote_one_to_one.sql
psql "${psql_connection_args[@]}" -f sql/028_wording_documents.sql
psql "${psql_connection_args[@]}" -f sql/029_quote_document_cascade.sql
psql "${psql_connection_args[@]}" -f sql/030_email_messages.sql
psql "${psql_connection_args[@]}" -f sql/029_contract_bullet_points.sql
psql "${psql_connection_args[@]}" -f sql/030_contract_document_text_formatting.sql
psql "${psql_connection_args[@]}" -f sql/031_contract_coverage_placeholders.sql
psql "${psql_connection_args[@]}" -f sql/032_contract_ascii_table_cleanup.sql
psql "${psql_connection_args[@]}" -f sql/033_raw_source_item_metadata.sql
psql "${psql_connection_args[@]}" -f sql/034_normalized_legal_document_structured_clauses.sql
psql "${psql_connection_args[@]}" -f sql/035_quote_decision_audit.sql
psql "${psql_connection_args[@]}" -f sql/036_template_draft_revision_approval_submission.sql
psql "${psql_connection_args[@]}" -f sql/037_customer_profile_documents.sql
psql "${psql_connection_args[@]}" -f sql/038_contract_decline.sql
