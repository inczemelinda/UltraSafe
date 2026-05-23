#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "${script_dir}/../sql" ]]; then
  project_root="$(cd -- "${script_dir}/.." && pwd)"
else
  project_root="$script_dir"
fi
cd "$project_root"

claim_source_dir="${project_root}/demo_artifacts/claim_attachments"
profile_source_dir="${project_root}/demo_artifacts/profile_documents"
pdf_source_dir="${project_root}/generated/pdfs"

claim_upload_dir="${UNDERWRIGHT_CLAIM_UPLOAD_DIR:-/tmp/underwright-claim-uploads}"
pdf_storage_dir="${UNDERWRIGHT_PDF_STORAGE_DIR:-${project_root}/generated/pdfs}"

content_type_for_file() {
  case "${1,,}" in
    *.pdf) printf '%s\n' "application/pdf" ;;
    *.png) printf '%s\n' "image/png" ;;
    *.jpg|*.jpeg) printf '%s\n' "image/jpeg" ;;
    *.docx) printf '%s\n' "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ;;
    *) printf '%s\n' "application/octet-stream" ;;
  esac
}

install_storage_tree() {
  local prefix="$1"
  local source_dir="$2"
  local destination_dir="$3"

  [[ -d "$source_dir" ]] || return 0
  mkdir -p "$destination_dir"

  local owner_dir
  while IFS= read -r -d '' owner_dir; do
    local owner
    owner="$(basename "$owner_dir")"

    local source_file
    while IFS= read -r -d '' source_file; do
      local file_name
      local storage_key
      local destination_file
      local metadata_file
      local content_type
      local size_bytes

      file_name="$(basename "$source_file")"
      storage_key="$(printf '%s' "${prefix}:${owner}:${file_name}" | md5sum | awk '{print $1}')"
      destination_file="${destination_dir}/${storage_key}"
      metadata_file="${destination_file}.json"
      content_type="$(content_type_for_file "$file_name")"
      size_bytes="$(stat -c '%s' "$source_file")"

      cp "$source_file" "$destination_file"
      printf '{"file_name":"%s","content_type":"%s","size_bytes":%s}\n' \
        "$file_name" \
        "$content_type" \
        "$size_bytes" \
        > "$metadata_file"
    done < <(find "$owner_dir" -maxdepth 1 -type f -print0 | sort -z)
  done < <(find "$source_dir" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
}

install_contract_pdfs() {
  [[ -d "$pdf_source_dir" ]] || return 0
  mkdir -p "$pdf_storage_dir"

  local source_real
  local destination_real
  source_real="$(cd "$pdf_source_dir" && pwd -P)"
  destination_real="$(cd "$pdf_storage_dir" && pwd -P)"

  [[ "$source_real" != "$destination_real" ]] || return 0

  find "$pdf_source_dir" -maxdepth 1 -type f -name 'demo-contract-pad-*.pdf' -print0 |
    while IFS= read -r -d '' pdf_file; do
      cp "$pdf_file" "${pdf_storage_dir}/$(basename "$pdf_file")"
    done
}

install_storage_tree "claim" "$claim_source_dir" "$claim_upload_dir"
install_storage_tree "profile" "$profile_source_dir" "$claim_upload_dir"
install_contract_pdfs
