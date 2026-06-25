#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${1:-models/generated/thermometer_digit_model_int8.tflite}"

if [[ ! -f "${MODEL_PATH}" ]]; then
    printf '[ERROR] model artifact not found: %s\n' "${MODEL_PATH}" >&2
    printf '[ERROR] run scripts/train_model.sh after collecting a varied dataset.\n' >&2
    exit 2
fi

printf '[ERROR] firmware C-array export is not implemented yet for %s\n' "${MODEL_PATH}" >&2
exit 2
