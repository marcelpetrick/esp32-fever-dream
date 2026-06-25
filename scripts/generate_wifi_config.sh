#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/wifi.env"
OUTPUT_FILE="${ROOT_DIR}/main/config.local.h"

usage() {
    cat <<'USAGE'
Usage:
  scripts/generate_wifi_config.sh

Reads ignored wifi.env and writes ignored main/config.local.h for ESP-IDF builds.

Accepted wifi.env keys:
  ssid: your-ssid
  pw: your-password

Also accepted:
  FEVER_WIFI_SSID=your-ssid
  FEVER_WIFI_PASSWORD=your-password
  FEVER_DEVICE_HOSTNAME=esp32-fever-dream
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

if [[ ! -f "${ENV_FILE}" ]]; then
    printf '[WARN] %s not found; keeping existing config.local.h if present\n' "${ENV_FILE}" >&2
    exit 0
fi

python3 - "${ENV_FILE}" "${OUTPUT_FILE}" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

values: dict[str, str] = {}
for raw_line in env_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue

    if "=" in line:
        key, value = line.split("=", 1)
    elif ":" in line:
        key, value = line.split(":", 1)
    else:
        continue

    normalized_key = re.sub(r"[^A-Za-z0-9]+", "_", key.strip()).strip("_").lower()
    values[normalized_key] = value.strip().strip('"').strip("'")

ssid = (
    values.get("fever_wifi_ssid")
    or values.get("wifi_ssid")
    or values.get("ssid")
)
password = (
    values.get("fever_wifi_password")
    or values.get("wifi_password")
    or values.get("password")
    or values.get("pw")
)
hostname = (
    values.get("fever_device_hostname")
    or values.get("device_hostname")
    or values.get("hostname")
    or "esp32-fever-dream"
)

if not ssid:
    raise SystemExit(f"{env_path} does not define a Wi-Fi SSID")
if password is None:
    raise SystemExit(f"{env_path} does not define a Wi-Fi password")

def c_string(value: str) -> str:
    return json.dumps(value)

output_path.write_text(
    "\n".join(
        [
            "#pragma once",
            "",
            "// Generated from ignored wifi.env by scripts/generate_wifi_config.sh.",
            "// Do not commit this file.",
            "",
            f"#define FEVER_WIFI_SSID {c_string(ssid)}",
            f"#define FEVER_WIFI_PASSWORD {c_string(password)}",
            f"#define FEVER_DEVICE_HOSTNAME {c_string(hostname)}",
            "",
        ]
    ),
    encoding="utf-8",
)
print(f"[INFO] wrote {output_path}")
PY
