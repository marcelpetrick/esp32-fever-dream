#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-ml"

if ! command -v uv >/dev/null 2>&1; then
    printf '[ERROR] uv is required to create the ML environment on this host\n' >&2
    exit 1
fi

uv python install 3.11
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    uv venv --python 3.11 "${VENV_DIR}"
fi
uv pip install --python "${VENV_DIR}/bin/python" "tensorflow>=2.16,<2.19" pillow numpy

printf '[INFO] ML environment ready: %s\n' "${VENV_DIR}"
printf '[INFO] activate with: . .venv-ml/bin/activate\n'
