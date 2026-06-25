#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=scripts/idf_env.sh
source "${ROOT_DIR}/scripts/idf_env.sh"
source_idf_environment

"${ROOT_DIR}/scripts/generate_wifi_config.sh"

cd "${ROOT_DIR}"
idf.py set-target esp32
idf.py build
