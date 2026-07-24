#!/usr/bin/env bash
# Local pipeline gate. This is the script that must pass before committing.
#
# Every stage is mandatory. Tools are version-pinned in scripts/tool_versions.sh
# and verified up front, so the pipeline cannot quietly report success while a
# missing tool skips a check. Formatting is verified, not applied: run
# ./scripts/format_all.sh to fix drift.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build-host"

# shellcheck source=scripts/tool_versions.sh
source "${ROOT_DIR}/scripts/tool_versions.sh"

printf '[INFO] verifying pinned toolchain\n'
fever_require_tool clang-format "${FEVER_CLANG_FORMAT_VERSION}"
fever_require_tool clang-tidy "${FEVER_CLANG_TIDY_VERSION}"
fever_require_tool cppcheck "${FEVER_CPPCHECK_VERSION}"
fever_require_tool shellcheck "${FEVER_SHELLCHECK_VERSION}"
fever_require_tool doxygen "${FEVER_DOXYGEN_VERSION}"
fever_require_python_tools "${ROOT_DIR}"

TOOLS_VENV="$(fever_tools_venv "${ROOT_DIR}")"

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
python3 -m compileall -q "${ROOT_DIR}/tools"
"${TOOLS_VENV}/bin/ruff" check "${ROOT_DIR}/tools"
"${TOOLS_VENV}/bin/black" --check "${ROOT_DIR}/tools"

printf '[INFO] python tooling tests\n'
python3 -m pytest "${ROOT_DIR}/tools" -q

printf '[INFO] documentation check\n'
doxygen "${ROOT_DIR}/Doxyfile" >/dev/null

printf '[INFO] pipeline passed\n'
