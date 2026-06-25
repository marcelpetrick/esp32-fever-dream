#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABELS=()
REPORT_JSON="${ROOT_DIR}/reports/model_training_audit.json"
REPORT_MD="${ROOT_DIR}/reports/model_training_audit.md"
ALLOW_SYNTHETIC_PROTOTYPE="0"
DIGIT_DATASET_DIR="${ROOT_DIR}/models/generated/digit_dataset"
MODEL_OUTPUT_DIR="${ROOT_DIR}/models/generated"
SYNTHETIC_PER_DIGIT="250"
EPOCHS="12"
PYTHON_BIN="${PYTHON:-python3}"

if [[ -x "${ROOT_DIR}/.venv-ml/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv-ml/bin/python"
fi

usage() {
    cat <<'USAGE'
Usage:
  scripts/train_model.sh --labels PATH [options]

Options:
  --labels PATH       Label CSV generated from a capture batch. May be repeated.
  --json-out PATH     Audit JSON output. Default: reports/model_training_audit.json.
  --markdown-out PATH Audit Markdown output. Default: reports/model_training_audit.md.
  --allow-synthetic-prototype
                      Continue after the real-reading audit and train a clearly
                      marked prototype using synthetic digit crops.
  --digit-dataset DIR Digit crop dataset output. Default: models/generated/digit_dataset.
  --model-output DIR  Model artifact output. Default: models/generated.
  --synthetic-per-digit N
                      Synthetic crops per digit. Default: 250.
  --epochs N          Training epochs. Default: 12.

The command audits dataset readiness before TinyML training. It refuses datasets
that cannot train a real digit recognizer unless --allow-synthetic-prototype is
set for a local prototype.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --labels)
            LABELS+=("$2")
            shift 2
            ;;
        --json-out)
            REPORT_JSON="$2"
            shift 2
            ;;
        --markdown-out)
            REPORT_MD="$2"
            shift 2
            ;;
        --allow-synthetic-prototype)
            ALLOW_SYNTHETIC_PROTOTYPE="1"
            shift
            ;;
        --digit-dataset)
            DIGIT_DATASET_DIR="$2"
            shift 2
            ;;
        --model-output)
            MODEL_OUTPUT_DIR="$2"
            shift 2
            ;;
        --synthetic-per-digit)
            SYNTHETIC_PER_DIGIT="$2"
            shift 2
            ;;
        --epochs)
            EPOCHS="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            printf '[ERROR] unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ "${#LABELS[@]}" -eq 0 ]]; then
    printf '[ERROR] --labels is required\n' >&2
    usage >&2
    exit 2
fi

if [[ "${#LABELS[@]}" -eq 1 ]]; then
    AUDIT_LABELS="${LABELS[0]}"
else
    AUDIT_LABELS="${DIGIT_DATASET_DIR}/merged_labels.csv"
    merge_args=(--output "${AUDIT_LABELS}")
    for labels_path in "${LABELS[@]}"; do
        merge_args+=(--labels "${labels_path}")
    done
    "${PYTHON_BIN}" "${ROOT_DIR}/tools/dataset/merge_label_csv.py" "${merge_args[@]}"
fi

audit_args=(
    --labels "${AUDIT_LABELS}"
    --json-out "${REPORT_JSON}"
    --markdown-out "${REPORT_MD}"
)
if [[ "${ALLOW_SYNTHETIC_PROTOTYPE}" != "1" ]]; then
    audit_args+=(--strict)
fi

if ! "${PYTHON_BIN}" "${ROOT_DIR}/tools/model_training/audit_dataset.py" "${audit_args[@]}"; then
    printf '[ERROR] TinyML training blocked by dataset audit. See %s\n' "${REPORT_MD}" >&2
    exit 2
fi

if [[ "${ALLOW_SYNTHETIC_PROTOTYPE}" == "1" ]]; then
    printf '[WARN] continuing with synthetic prototype training; final validation is still blocked by %s\n' "${REPORT_MD}" >&2
else
    printf '[INFO] dataset audit passed\n'
fi

dataset_args=(--output-dir "${DIGIT_DATASET_DIR}" --synthetic-per-digit "${SYNTHETIC_PER_DIGIT}")
for labels_path in "${LABELS[@]}"; do
    dataset_args+=(--labels "${labels_path}")
done
"${PYTHON_BIN}" "${ROOT_DIR}/tools/model_training/build_digit_dataset.py" "${dataset_args[@]}"

"${PYTHON_BIN}" "${ROOT_DIR}/tools/model_training/train_digit_classifier.py" \
    --digit-labels "${DIGIT_DATASET_DIR}/digit_labels.csv" \
    --output-dir "${MODEL_OUTPUT_DIR}" \
    --epochs "${EPOCHS}"
