#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build-host"

printf '[INFO] formatting check\n'
"${ROOT_DIR}/scripts/format_cpp.sh" --check

printf '[INFO] host build\n'
cmake -S "${ROOT_DIR}" -B "${BUILD_DIR}" -G Ninja
cmake --build "${BUILD_DIR}"

printf '[INFO] host tests\n'
cmake --build "${BUILD_DIR}" --target check

printf '[INFO] static analysis\n'
"${ROOT_DIR}/scripts/static_analysis.sh"

printf '[INFO] firmware build\n'
"${ROOT_DIR}/scripts/build_firmware.sh"

printf '[INFO] web asset check\n'
"${ROOT_DIR}/scripts/package_web_assets.sh"

printf '[INFO] python tooling check\n'
if [[ -d "${ROOT_DIR}/tools" ]]; then
    python3 -m compileall -q "${ROOT_DIR}/tools"
    if command -v ruff >/dev/null 2>&1; then
        ruff check "${ROOT_DIR}/tools"
    fi
    if command -v black >/dev/null 2>&1; then
        black --check "${ROOT_DIR}/tools"
    fi
fi

printf '[INFO] documentation check\n'
doxygen "${ROOT_DIR}/Doxyfile" >/dev/null

printf '[INFO] pipeline passed\n'
