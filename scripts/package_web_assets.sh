#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="${ROOT_DIR}/web"

if [[ ! -d "${WEB_DIR}" ]]; then
    printf '[INFO] web directory not present yet; skipping\n'
    exit 0
fi

find "${WEB_DIR}" -type f \( -name '*.html' -o -name '*.css' -o -name '*.js' \) -print0 \
    | while IFS= read -r -d '' file; do
        if grep -Eq 'https?://|cdn\\.' "${file}"; then
            printf '[ERROR] external dependency found in %s\n' "${file}" >&2
            exit 1
        fi
    done

if command -v node >/dev/null 2>&1 && [[ -f "${WEB_DIR}/app.js" ]]; then
    node --check "${WEB_DIR}/app.js"
fi

printf '[INFO] web assets are local-only\n'
