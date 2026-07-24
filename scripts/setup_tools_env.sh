#!/usr/bin/env bash
# Create the pinned Python formatting/linting environment used by the pipeline.
#
# This is separate from .venv-ml on purpose: the training stack is heavy and tied
# to a TensorFlow-supported interpreter, while the formatters must be installable
# and identical everywhere. Pinning them here keeps formatting reproducible
# regardless of what the host happens to have installed.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=scripts/tool_versions.sh
source "${ROOT_DIR}/scripts/tool_versions.sh"

VENV_DIR="$(fever_tools_venv "${ROOT_DIR}")"

if ! command -v uv >/dev/null 2>&1; then
    printf '[ERROR] uv is required to create the pinned tool environment\n' >&2
    exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    uv venv "${VENV_DIR}"
fi

uv pip install --python "${VENV_DIR}/bin/python" \
    "black==${FEVER_BLACK_VERSION}" \
    "ruff==${FEVER_RUFF_VERSION}"

printf '[INFO] pinned tools ready: black %s, ruff %s in %s\n' \
    "${FEVER_BLACK_VERSION}" "${FEVER_RUFF_VERSION}" "${VENV_DIR}"
