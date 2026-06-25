#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v idf.py >/dev/null 2>&1; then
    printf '[ERROR] idf.py not found. Source ESP-IDF v6.0.1 export.sh first.\n' >&2
    exit 1
fi

cd "${ROOT_DIR}"
idf.py set-target esp32
idf.py build
