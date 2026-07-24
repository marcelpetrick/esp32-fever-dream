#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=scripts/tool_versions.sh
source "${ROOT_DIR}/scripts/tool_versions.sh"

CHECK=false

if [[ "${1:-}" == "--check" ]]; then
    CHECK=true
fi

fever_require_tool clang-format "${FEVER_CLANG_FORMAT_VERSION}"

# Generated artifacts (model byte arrays) are excluded: reformatting them produces
# thousands of lines of churn whenever the local clang-format version changes.
mapfile -t FILES < <(find "${ROOT_DIR}/firmware" "${ROOT_DIR}/main" "${ROOT_DIR}/tests" \
    -path "${ROOT_DIR}/firmware/generated" -prune -o \
    \( -name '*.h' -o -name '*.cpp' -o -name '*.c' \) -print | sort)

if [[ "${#FILES[@]}" -eq 0 ]]; then
    exit 0
fi

if [[ "${CHECK}" == true ]]; then
    clang-format --dry-run --Werror "${FILES[@]}"
else
    clang-format -i "${FILES[@]}"
fi
