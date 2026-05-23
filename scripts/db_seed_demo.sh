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

psql "${psql_connection_args[@]}" -f sql/002_seed_demo_data.sql
psql "${psql_connection_args[@]}" -f sql/028_wording_documents.sql
psql "${psql_connection_args[@]}" -f sql/008_intelligence_sources.sql
psql "${psql_connection_args[@]}" -f sql/010_legal_document_sources.sql
psql "${psql_connection_args[@]}" -f sql/009_demo_intelligence_events.sql
psql "${psql_connection_args[@]}" -f sql/023_backend_demo_dataset.sql
psql "${psql_connection_args[@]}" -f sql/024_legal_review_demo_dataset.sql

if [[ -x "${project_root}/scripts/install_demo_artifacts.sh" ]]; then
  "${project_root}/scripts/install_demo_artifacts.sh"
fi
