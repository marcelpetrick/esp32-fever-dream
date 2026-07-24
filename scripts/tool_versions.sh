#!/usr/bin/env bash
# Single source of truth for the toolchain the local pipeline is pinned to.
#
# Formatters and analyzers change their output between releases. On a rolling
# distribution an unpinned upgrade silently rewrites the whole tree or raises new
# findings on code that was clean, which is indistinguishable from a real
# regression. Every tool the pipeline depends on is therefore pinned here and
# verified before use.
#
# Python tools are pinned hard: setup_tools_env.sh installs the exact versions
# into .venv-tools and the scripts call that venv, so the host environment cannot
# influence formatting.
#
# System tools (clang-format, clang-tidy, cppcheck, shellcheck, doxygen) cannot be
# installed per project, so they are version-checked instead. A mismatch is a hard
# error. To upgrade deliberately, bump the value here, re-run the pipeline, and
# commit the resulting churn as a standalone style/chore commit.
#
# Escape hatch for a one-off run against a different toolchain:
#   FEVER_ALLOW_TOOL_DRIFT=1 ./scripts/check_all.sh

# These are consumed by the scripts that source this file, not by this file.
# shellcheck disable=SC2034
FEVER_CLANG_FORMAT_VERSION="22.1.8"
FEVER_CLANG_TIDY_VERSION="22.1.8"
FEVER_CPPCHECK_VERSION="2.21.1"
FEVER_SHELLCHECK_VERSION="0.11.0"
FEVER_DOXYGEN_VERSION="1.16.1"

FEVER_BLACK_VERSION="26.5.1"
FEVER_RUFF_VERSION="0.15.20"
FEVER_TOOLS_VENV_NAME=".venv-tools"

# Print the first version-looking token in a tool's --version output.
fever_tool_version() {
    local command_name="$1"
    "${command_name}" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1
}

# Fail unless the tool exists and reports the pinned version.
fever_require_tool() {
    local command_name="$1"
    local expected="$2"

    if ! command -v "${command_name}" >/dev/null 2>&1; then
        printf '[ERROR] %s is required but not installed (pinned version %s)\n' "${command_name}" "${expected}" >&2
        return 1
    fi

    local actual
    actual="$(fever_tool_version "${command_name}")"
    if [[ "${actual}" == "${expected}" ]]; then
        return 0
    fi

    if [[ "${FEVER_ALLOW_TOOL_DRIFT:-0}" == "1" ]]; then
        printf '[WARN] %s is %s but the project pins %s (FEVER_ALLOW_TOOL_DRIFT=1)\n' \
            "${command_name}" "${actual:-unknown}" "${expected}" >&2
        return 0
    fi

    printf '[ERROR] %s is %s but the project pins %s\n' "${command_name}" "${actual:-unknown}" "${expected}" >&2
    printf '[ERROR] update scripts/tool_versions.sh deliberately, or re-run with FEVER_ALLOW_TOOL_DRIFT=1\n' >&2
    return 1
}

# Absolute path to the pinned Python tool environment.
fever_tools_venv() {
    local root_dir="$1"
    printf '%s/%s' "${root_dir}" "${FEVER_TOOLS_VENV_NAME}"
}

# Fail unless .venv-tools exists with the pinned black and ruff installed.
fever_require_python_tools() {
    local root_dir="$1"
    local venv_dir
    venv_dir="$(fever_tools_venv "${root_dir}")"

    if [[ ! -x "${venv_dir}/bin/black" || ! -x "${venv_dir}/bin/ruff" ]]; then
        printf '[ERROR] pinned Python tools missing; run ./scripts/setup_tools_env.sh\n' >&2
        return 1
    fi

    local black_actual ruff_actual
    black_actual="$("${venv_dir}/bin/black" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)"
    ruff_actual="$("${venv_dir}/bin/ruff" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)"

    if [[ "${black_actual}" != "${FEVER_BLACK_VERSION}" || "${ruff_actual}" != "${FEVER_RUFF_VERSION}" ]]; then
        printf '[ERROR] .venv-tools has black %s / ruff %s but the project pins %s / %s\n' \
            "${black_actual:-unknown}" "${ruff_actual:-unknown}" "${FEVER_BLACK_VERSION}" "${FEVER_RUFF_VERSION}" >&2
        printf '[ERROR] re-run ./scripts/setup_tools_env.sh\n' >&2
        return 1
    fi
}
