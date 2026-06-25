#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-/dev/ttyUSB0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLASH_BAUD="${FEVER_FLASH_BAUD:-115200}"
ROM_FALLBACK="${FEVER_FLASH_ROM_FALLBACK:-1}"
ROM_BAUD="${FEVER_FLASH_ROM_BAUD:-57600}"

# shellcheck source=scripts/idf_env.sh
source "${ROOT_DIR}/scripts/idf_env.sh"
source_idf_environment

"${ROOT_DIR}/scripts/generate_wifi_config.sh"

if idf.py -p "${PORT}" -b "${FLASH_BAUD}" flash; then
    exit 0
fi

if [[ "${ROM_FALLBACK}" != "1" ]]; then
    exit 1
fi

printf '[WARN] idf.py flash failed; retrying via ROM loader without stub at %s baud\n' "${ROM_BAUD}" >&2
idf.py build

APP_BIN="$(python3 - "${ROOT_DIR}/build/project_description.json" <<'PY'
import json
import sys
from pathlib import Path

description = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(description["app_bin"])
PY
)"

(
    cd "${ROOT_DIR}/build"
    python -m esptool \
        --chip esp32 \
        -p "${PORT}" \
        -b "${ROM_BAUD}" \
        --before default-reset \
        --after hard-reset \
        --no-stub \
        write-flash \
        --flash-mode dio \
        --flash-freq 40m \
        --flash-size 4MB \
        0x1000 bootloader/bootloader.bin \
        0x8000 partition_table/partition-table.bin \
        0x10000 "${APP_BIN}"
)
