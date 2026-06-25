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

printf '[INFO] web asset check\n'
"${ROOT_DIR}/scripts/package_web_assets.sh"

printf '[INFO] documentation check\n'
doxygen "${ROOT_DIR}/Doxyfile" >/dev/null

printf '[INFO] pipeline passed\n'
