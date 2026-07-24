#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=scripts/tool_versions.sh
source "${ROOT_DIR}/scripts/tool_versions.sh"

# Every analyzer is mandatory and version-pinned. These tools change their
# findings between releases, so silently skipping a missing one would let the
# pipeline report success while checking less than it did the day before.
fever_require_tool shellcheck "${FEVER_SHELLCHECK_VERSION}"
fever_require_tool cppcheck "${FEVER_CPPCHECK_VERSION}"
fever_require_tool clang-tidy "${FEVER_CLANG_TIDY_VERSION}"

shellcheck "${ROOT_DIR}"/scripts/*.sh

cppcheck --enable=warning,style,performance,portability \
    --suppressions-list="${ROOT_DIR}/.cppcheck-suppress" \
    --error-exitcode=1 \
    -I "${ROOT_DIR}/firmware/include" \
    "${ROOT_DIR}/firmware" "${ROOT_DIR}/tests"

if [[ ! -f "${ROOT_DIR}/build-host/compile_commands.json" ]]; then
    printf '[ERROR] build-host/compile_commands.json missing; configure the host build first\n' >&2
    exit 1
fi

find "${ROOT_DIR}/firmware/src" "${ROOT_DIR}/tests" -name '*.cpp' -print \
    | sort \
    | xargs -r clang-tidy -p "${ROOT_DIR}/build-host" --warnings-as-errors='*'
