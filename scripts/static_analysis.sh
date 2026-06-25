#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v shellcheck >/dev/null 2>&1; then
    shellcheck "${ROOT_DIR}"/scripts/*.sh
fi

if command -v cppcheck >/dev/null 2>&1; then
    cppcheck --enable=warning,style,performance,portability \
        --suppressions-list="${ROOT_DIR}/.cppcheck-suppress" \
        --error-exitcode=1 \
        -I "${ROOT_DIR}/firmware/include" \
        "${ROOT_DIR}/firmware" "${ROOT_DIR}/tests"
fi

if command -v clang-tidy >/dev/null 2>&1 && [[ -f "${ROOT_DIR}/build-host/compile_commands.json" ]]; then
    find "${ROOT_DIR}/firmware/src" "${ROOT_DIR}/tests" -name '*.cpp' -print \
        | sort \
        | xargs -r clang-tidy -p "${ROOT_DIR}/build-host" --warnings-as-errors='*'
fi
