#!/usr/bin/env bash
# Format every source file in the repository in place.
#
# C/C++ : clang-format, Google style with 4-space indent and a 120-column limit
#         (see .clang-format). Generated artifacts are skipped.
# Python: black for formatting and ruff for lint autofixes, both pinned to 120
#         columns (see pyproject.toml).
#
# Run this before committing. scripts/check_all.sh runs the same tools in
# --check mode and fails the pipeline when anything is unformatted.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

printf '[INFO] formatting C/C++\n'
"${ROOT_DIR}/scripts/format_cpp.sh"

if [[ -d "${ROOT_DIR}/tools" ]]; then
    if command -v ruff >/dev/null 2>&1; then
        printf '[INFO] applying ruff autofixes\n'
        ruff check --fix "${ROOT_DIR}/tools"
    else
        printf '[WARN] ruff not found, skipping Python lint autofixes\n' >&2
    fi

    if command -v black >/dev/null 2>&1; then
        printf '[INFO] formatting Python\n'
        black "${ROOT_DIR}/tools"
    else
        printf '[WARN] black not found, skipping Python formatting\n' >&2
    fi
fi

printf '[INFO] formatting complete\n'
