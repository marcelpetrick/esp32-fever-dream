#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL=""
COUNT="100"
INTERVAL_SECONDS="1"
RETRIES="3"
CONNECT_TIMEOUT_SECONDS="5"
MAX_TIME_SECONDS="20"
FRAME_SIZE="vga"
QUALITY="12"
BRIGHTNESS=""
CONTRAST=""
SATURATION=""
AEC=""
AGC=""
AWB=""
LIGHTING_LABEL="unspecified"
OUTPUT_DIR="${ROOT_DIR}/tools/dataset/captures/$(date -u +%Y%m%dT%H%M%SZ)"

usage() {
    cat <<'USAGE'
Usage:
  scripts/collect_dataset.sh --base-url http://DEVICE_IP [options]

Options:
  --count N                 Number of images to capture. Default: 100.
  --interval SECONDS        Delay between captures. Default: 1.
  --retries N               Attempts per image before marking failure. Default: 3.
  --connect-timeout SECONDS Curl connect timeout. Default: 5.
  --max-time SECONDS        Curl total request timeout. Default: 20.
  --output DIR              Output directory. Default: tools/dataset/captures/<utc>.
  --lighting-label LABEL    Label written to the manifest. Default: unspecified.
  --framesize qvga|vga|svga Camera frame size. Default: vga.
  --quality N               OV2640 JPEG quality, lower is better. Default: 12.
  --brightness -2..2        Optional camera brightness.
  --contrast -2..2          Optional camera contrast.
  --saturation -2..2        Optional camera saturation.
  --aec 0|1                 Optional auto exposure control.
  --agc 0|1                 Optional auto gain control.
  --awb 0|1                 Optional auto white balance.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        --count)
            COUNT="$2"
            shift 2
            ;;
        --interval)
            INTERVAL_SECONDS="$2"
            shift 2
            ;;
        --retries)
            RETRIES="$2"
            shift 2
            ;;
        --connect-timeout)
            CONNECT_TIMEOUT_SECONDS="$2"
            shift 2
            ;;
        --max-time)
            MAX_TIME_SECONDS="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --lighting-label)
            LIGHTING_LABEL="$2"
            shift 2
            ;;
        --framesize)
            FRAME_SIZE="$2"
            shift 2
            ;;
        --quality)
            QUALITY="$2"
            shift 2
            ;;
        --brightness)
            BRIGHTNESS="$2"
            shift 2
            ;;
        --contrast)
            CONTRAST="$2"
            shift 2
            ;;
        --saturation)
            SATURATION="$2"
            shift 2
            ;;
        --aec)
            AEC="$2"
            shift 2
            ;;
        --agc)
            AGC="$2"
            shift 2
            ;;
        --awb)
            AWB="$2"
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

if [[ -z "${BASE_URL}" ]]; then
    printf '[ERROR] --base-url is required\n' >&2
    usage >&2
    exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
    printf '[ERROR] curl is required\n' >&2
    exit 1
fi

BASE_URL="${BASE_URL%/}"
mkdir -p "${OUTPUT_DIR}"
MANIFEST="${OUTPUT_DIR}/manifest.csv"
printf 'sample_id,image_path,lighting_label,framesize,quality,brightness,contrast,saturation,aec,agc,awb,http_code,bytes,captured_at_utc,display_text,notes\n' >"${MANIFEST}"

query="framesize=${FRAME_SIZE}&quality=${QUALITY}"
[[ -n "${BRIGHTNESS}" ]] && query="${query}&brightness=${BRIGHTNESS}"
[[ -n "${CONTRAST}" ]] && query="${query}&contrast=${CONTRAST}"
[[ -n "${SATURATION}" ]] && query="${query}&saturation=${SATURATION}"
[[ -n "${AEC}" ]] && query="${query}&aec=${AEC}"
[[ -n "${AGC}" ]] && query="${query}&agc=${AGC}"
[[ -n "${AWB}" ]] && query="${query}&awb=${AWB}"

printf '[INFO] health check %s/debug/health\n' "${BASE_URL}"
curl --fail --silent --show-error "${BASE_URL}/debug/health" >/dev/null

for index in $(seq 1 "${COUNT}"); do
    sample_id="$(printf 'capture_%04d' "${index}")"
    image_path="${OUTPUT_DIR}/${sample_id}.jpg"
    captured_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    url="${BASE_URL}/debug/capture.jpg?${query}&sample=${sample_id}"
    http_code="000"
    curl_status="0"
    for attempt in $(seq 1 "${RETRIES}"); do
        curl_status="0"
        http_code="$(curl \
            --silent \
            --show-error \
            --connect-timeout "${CONNECT_TIMEOUT_SECONDS}" \
            --max-time "${MAX_TIME_SECONDS}" \
            --output "${image_path}" \
            --write-out '%{http_code}' \
            "${url}")" || curl_status="$?"
        if [[ "${curl_status}" == "0" && "${http_code}" == "200" ]]; then
            break
        fi
        printf '[WARN] %s attempt %s/%s failed: curl=%s http=%s\n' \
            "${sample_id}" "${attempt}" "${RETRIES}" "${curl_status}" "${http_code}" >&2
        sleep "${INTERVAL_SECONDS}"
    done
    if [[ -f "${image_path}" ]]; then
        bytes="$(wc -c <"${image_path}" | tr -d ' ')"
    else
        bytes="0"
    fi

    if [[ "${curl_status}" != "0" || "${http_code}" != "200" ]]; then
        printf '[WARN] %s failed: curl=%s http=%s\n' "${sample_id}" "${curl_status}" "${http_code}" >&2
    else
        printf '[INFO] %s %s bytes\n' "${sample_id}" "${bytes}"
    fi

    printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,,\n' \
        "${sample_id}" "${image_path}" "${LIGHTING_LABEL}" "${FRAME_SIZE}" "${QUALITY}" "${BRIGHTNESS}" \
        "${CONTRAST}" "${SATURATION}" "${AEC}" "${AGC}" "${AWB}" "${http_code}" "${bytes}" "${captured_at}" \
        >>"${MANIFEST}"

    sleep "${INTERVAL_SECONDS}"
done

printf '[INFO] dataset written to %s\n' "${OUTPUT_DIR}"
