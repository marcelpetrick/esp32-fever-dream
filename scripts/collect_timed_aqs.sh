#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ -x "${ROOT_DIR}/.venv-ml/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv-ml/bin/python"
fi

cd "${ROOT_DIR}"
exec "${PYTHON_BIN}" tools/dataset/collect_timed_aqs.py "$@"
