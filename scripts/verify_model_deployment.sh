#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
if [[ -x "${ROOT_DIR}/.venv-ml/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv-ml/bin/python"
fi

cd "${ROOT_DIR}"
"${PYTHON_BIN}" tools/model_training/verify_deployment_gate.py \
    --model-eval models/generated/digit_classifier_eval.json \
    --reading-eval models/generated/digit_model_predictions_summary.json \
    --model models/generated/digit_classifier_int8.tflite \
    --firmware-config firmware/include/app_config.h \
    --recognizer-source firmware/src/tinyml_display_recognizer.cpp \
    --json-out reports/model_deployment_gate.json \
    --strict
