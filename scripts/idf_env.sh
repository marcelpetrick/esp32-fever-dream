#!/usr/bin/env bash

IDF_VERSION="v6.0.1"
IDF_PATH_ROOT="${IDF_PATH_ROOT:-/home/mpetrick/.local/opt/esp-idf-${IDF_VERSION}}"

source_idf_environment() {
    if command -v idf.py >/dev/null 2>&1; then
        return 0
    fi

    if [[ ! -f "${IDF_PATH_ROOT}/export.sh" ]]; then
        printf '[ERROR] ESP-IDF %s export.sh not found at %s/export.sh\n' "${IDF_VERSION}" "${IDF_PATH_ROOT}" >&2
        return 1
    fi

    # ESP-IDF export scripts read some unset variables under set -u.
    set +u
    # shellcheck source=/dev/null
    source "${IDF_PATH_ROOT}/export.sh" >/dev/null
    set -u
}
