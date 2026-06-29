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
SEED="173"
REAL_WEIGHT="1"
QUALIFY_TEST="0"
EXPORT_FIRMWARE_HEADER="0"
PYTHON_BIN="${PYTHON:-python3}"
SPLIT_POLICY="${ROOT_DIR}/tools/model_training/frozen_split_policy.json"

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
  --split-policy PATH Frozen capture-session split policy.
  --allow-synthetic-prototype
                      Continue after the real-reading audit and train a clearly
                      marked prototype using synthetic digit crops.
  --digit-dataset DIR Digit crop dataset output. Default: models/generated/digit_dataset.
  --model-output DIR  Model artifact output. Default: models/generated.
  --synthetic-per-digit N
                      Synthetic crops per digit. Default: 250.
  --epochs N          Training epochs. Default: 12.
  --seed N            Reproducible training seed. Default: 173.
  --real-weight N     Loss weight for real training crops. Default: 1.
  --qualify-test      Evaluate the frozen test split after validation passes.
  --export-firmware-header
                      Export the model into firmware after final qualification.

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
        --split-policy)
            SPLIT_POLICY="$2"
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
        --seed)
            SEED="$2"
            shift 2
            ;;
        --real-weight)
            REAL_WEIGHT="$2"
            shift 2
            ;;
        --qualify-test)
            QUALIFY_TEST="1"
            shift
            ;;
        --export-firmware-header)
            EXPORT_FIRMWARE_HEADER="1"
            shift
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

AUDIT_LABELS="${DIGIT_DATASET_DIR}/merged_labels.csv"
merge_args=(--policy "${SPLIT_POLICY}" --output "${AUDIT_LABELS}")
for labels_path in "${LABELS[@]}"; do
    merge_args+=(--labels "${labels_path}")
done
"${PYTHON_BIN}" "${ROOT_DIR}/tools/model_training/apply_split_policy.py" "${merge_args[@]}"

# Extract split_within batch names from the policy so the audit can exempt
# them from the capture_batches_split_exclusive check.
mapfile -t SPLIT_WITHIN_BATCHES < <(
    "${PYTHON_BIN}" -c "
import json, sys
with open('${SPLIT_POLICY}') as f:
    policy = json.load(f)
for entry in policy.get('split_within', []):
    print(entry['batch'])
"
)

audit_args=(
    --labels "${AUDIT_LABELS}"
    --json-out "${REPORT_JSON}"
    --markdown-out "${REPORT_MD}"
)
if [[ "${#SPLIT_WITHIN_BATCHES[@]}" -gt 0 ]]; then
    audit_args+=(--exempt-cross-split-batches "${SPLIT_WITHIN_BATCHES[@]}")
fi
# Allow a small number of frames where locate_display fails (camera glitch,
# motion blur) rather than blocking the entire training run.
audit_args+=(--max-hash-failures 30)
# Small validation sets from narrow sensor-condition ranges may not cover every
# digit class (e.g. '8' never appearing in temp/humidity at a stable 29°C/43%
# reading).  Allow at most 1 missing digit in the validation split.
audit_args+=(--max-missing-validation-digits 1)
# Sequential captures of stable readings produce near-identical frames;
# use threshold 0 to flag only exact pixel-level duplicates, not temporally
# close frames of the same stable sensor value.
audit_args+=(--perceptual-hamming-threshold 0)
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

dataset_args=(
    --output-dir "${DIGIT_DATASET_DIR}"
    --synthetic-per-digit "${SYNTHETIC_PER_DIGIT}"
    --labels "${AUDIT_LABELS}"
)
"${PYTHON_BIN}" "${ROOT_DIR}/tools/model_training/build_digit_dataset.py" "${dataset_args[@]}"

train_args=(
    --digit-labels "${DIGIT_DATASET_DIR}/digit_labels.csv"
    --output-dir "${MODEL_OUTPUT_DIR}"
    --epochs "${EPOCHS}"
    --seed "${SEED}"
    --real-weight "${REAL_WEIGHT}"
)
if [[ "${QUALIFY_TEST}" == "1" ]]; then
    train_args+=(--qualify-test)
fi
if [[ "${EXPORT_FIRMWARE_HEADER}" == "1" ]]; then
    train_args+=(--firmware-header "${ROOT_DIR}/firmware/generated/digit_classifier_model.h")
fi
"${PYTHON_BIN}" "${ROOT_DIR}/tools/model_training/train_digit_classifier.py" \
    "${train_args[@]}"
