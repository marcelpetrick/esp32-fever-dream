#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-/dev/ttyUSB0}"

if ! command -v idf.py >/dev/null 2>&1; then
    printf '[ERROR] idf.py not found. Source ESP-IDF v6.0.1 export.sh first.\n' >&2
    exit 1
fi

idf.py -p "${PORT}" monitor
