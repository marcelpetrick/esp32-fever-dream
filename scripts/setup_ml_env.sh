#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-ml"
PYTHON_VERSION="3.13"
PYTHON_EXACT="3.13.14"

if ! command -v uv >/dev/null 2>&1; then
    printf '[ERROR] uv is required to create the ML environment on this host\n' >&2
    exit 1
fi

uv python install "${PYTHON_VERSION}"
if [[ -x "${VENV_DIR}/bin/python" ]]; then
    CURRENT_VERSION="$("${VENV_DIR}/bin/python" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
else
    CURRENT_VERSION=""
fi
if [[ "${CURRENT_VERSION}" != "${PYTHON_EXACT}" ]]; then
    printf '[INFO] recreating ML environment for Python %s (was: %s)\n' "${PYTHON_EXACT}" "${CURRENT_VERSION:-missing}"
    rm -rf "${VENV_DIR}"
    uv venv --python "${PYTHON_VERSION}" "${VENV_DIR}"
fi
uv pip install --python "${VENV_DIR}/bin/python" "tensorflow==2.21.0" "numpy==2.5.1" "pillow==12.3.0"

printf '[INFO] ML environment ready: %s\n' "${VENV_DIR}"
printf '[INFO] activate with: . .venv-ml/bin/activate\n'
