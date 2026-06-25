#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-/dev/ttyUSB0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=scripts/idf_env.sh
source "${ROOT_DIR}/scripts/idf_env.sh"
source_idf_environment

idf.py -p "${PORT}" flash
