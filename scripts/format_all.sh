#!/usr/bin/env bash
# Format every source file in the repository in place.
#
# C/C++ : clang-format, Google style with 4-space indent and a 120-column limit
#         (see .clang-format). Generated artifacts are skipped.
# Python: black for formatting and ruff for lint autofixes, both pinned to 120
#         columns (see pyproject.toml).
#
# All tools are version-pinned in scripts/tool_versions.sh and are mandatory: a
# missing or mismatched tool fails instead of being silently skipped.
#
# Run this before committing. scripts/check_all.sh runs the same tools in
# --check mode and fails the pipeline when anything is unformatted.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=scripts/tool_versions.sh
source "${ROOT_DIR}/scripts/tool_versions.sh"

VENV_DIR="$(fever_tools_venv "${ROOT_DIR}")"

printf '[INFO] formatting C/C++\n'
"${ROOT_DIR}/scripts/format_cpp.sh"

fever_require_python_tools "${ROOT_DIR}"

printf '[INFO] applying ruff autofixes\n'
"${VENV_DIR}/bin/ruff" check --fix "${ROOT_DIR}/tools"

printf '[INFO] formatting Python\n'
"${VENV_DIR}/bin/black" "${ROOT_DIR}/tools"

printf '[INFO] formatting complete\n'
