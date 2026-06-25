#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABELS=""
REPORT_JSON="${ROOT_DIR}/reports/model_training_audit.json"
REPORT_MD="${ROOT_DIR}/reports/model_training_audit.md"

usage() {
    cat <<'USAGE'
Usage:
  scripts/train_model.sh --labels PATH [options]

Options:
  --labels PATH       Label CSV generated from a capture batch.
  --json-out PATH     Audit JSON output. Default: reports/model_training_audit.json.
  --markdown-out PATH Audit Markdown output. Default: reports/model_training_audit.md.

The command audits dataset readiness before TinyML training. It refuses datasets
that cannot train a real digit recognizer.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --labels)
            LABELS="$2"
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

if [[ -z "${LABELS}" ]]; then
    printf '[ERROR] --labels is required\n' >&2
    usage >&2
    exit 2
fi

if ! python3 "${ROOT_DIR}/tools/model_training/audit_dataset.py" \
    --labels "${LABELS}" \
    --json-out "${REPORT_JSON}" \
    --markdown-out "${REPORT_MD}" \
    --strict; then
    printf '[ERROR] TinyML training blocked by dataset audit. See %s\n' "${REPORT_MD}" >&2
    exit 2
fi

python3 - <<'PY'
try:
    import tensorflow  # noqa: F401
except Exception as exc:
    raise SystemExit(f"TensorFlow is required after the dataset audit passes: {exc}")
PY

printf '[ERROR] Dataset audit passed, but the digit-crop trainer is not implemented yet.\n' >&2
printf '[ERROR] Implement tools/model_training/train_digit_classifier.py before producing a TFLite artifact.\n' >&2
exit 2
