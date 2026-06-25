#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${ROOT_DIR}/tools/dataset/raw" "${ROOT_DIR}/tools/dataset/labeled" "${ROOT_DIR}/tools/dataset/crops"
printf '[INFO] dataset directories ready under tools/dataset\n'
