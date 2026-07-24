#!/usr/bin/env python3
"""Audit project dependency freshness and local ML/Ollama environment."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

ESP_COMPONENTS = (
    "espressif/esp32-camera",
    "espressif/esp-tflite-micro",
    "espressif/esp-nn",
    "espressif/esp_jpeg",
)
PYTHON_PACKAGES = ("tensorflow", "numpy", "pillow")
ML_VENV_DIR = REPO_ROOT / ".venv-ml"
IDF_RELEASES_URL = "https://api.github.com/repos/espressif/esp-idf/releases?per_page=100"
OLLAMA_RELEASE_URL = "https://api.github.com/repos/ollama/ollama/releases/latest"


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    current: str | None
    latest: str | None
    status: str
    source: str
    note: str = ""


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=REPO_ROOT / "reports/dependency_audit.json")
    parser.add_argument("--markdown-out", type=Path, default=REPO_ROOT / "reports/dependency_audit.md")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not query remote registries; report local versions only.",
    )
    return parser.parse_args(list(argv))


def _run(command: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)
    return completed.returncode, completed.stdout.strip()


def locked_esp_versions(lock_path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    current: str | None = None
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        component = re.match(r"^  (espressif/[^:]+):$", line)
        if component:
            current = component.group(1)
            continue
        if current:
            version = re.match(r"^    version: ['\"]?([^'\"]+)['\"]?$", line)
            if version:
                result[current] = version.group(1)
                current = None
    idf_match = re.search(
        r"^  idf:\n(?:    .*\n)*?    version: ['\"]?([^'\"\n]+)['\"]?",
        lock_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if idf_match:
        result["idf"] = idf_match.group(1)
    return result


def configured_python_constraints(setup_script: Path) -> dict[str, str]:
    text = setup_script.read_text(encoding="utf-8")
    match = re.search(r"uv pip install.*", text)
    if not match:
        return {}
    command = match.group(0)
    return {
        package.lower(): requirement
        for requirement in re.findall(r'"([^"]+)"|(\b[a-zA-Z][a-zA-Z0-9_-]+\b)', command)
        for requirement in [requirement[0] or requirement[1]]
        for package in [re.split(r"[<>=!~]", requirement, maxsplit=1)[0].lower()]
        if package not in {"uv", "pip", "install", "python"} and "/" not in package and "$" not in package
    }


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "esp32-fever-dream-dependency-audit"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def release_version(tag: str) -> tuple[int, ...] | None:
    """Parse a plain release tag such as ``v6.0.2`` into a comparable tuple.

    Pre-release tags (``v6.1-beta1``, ``v6.0-rc1``) return ``None`` so they are
    never proposed as the latest stable version.
    """
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", tag.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def latest_idf_release() -> str | None:
    """Return the highest stable ESP-IDF release, not merely the most recent one.

    Espressif backports to older LTS branches, so the newest release by date can
    be older by version than the current pin.
    """
    releases = fetch_json(IDF_RELEASES_URL)
    if not isinstance(releases, list):
        return None
    candidates: list[tuple[tuple[int, ...], str]] = []
    for release in releases:
        if not isinstance(release, dict) or release.get("prerelease") or release.get("draft"):
            continue
        tag = str(release.get("tag_name", ""))
        parsed = release_version(tag)
        if parsed is not None:
            candidates.append((parsed, tag.lstrip("v")))
    if not candidates:
        return None
    return max(candidates)[1]


def latest_ollama_release() -> str | None:
    release = fetch_json(OLLAMA_RELEASE_URL)
    if not isinstance(release, dict):
        return None
    tag = release.get("tag_name")
    return str(tag).lstrip("v") if tag else None


def latest_esp_component(component: str) -> str | None:
    namespace, name = component.split("/", 1)
    data = fetch_json(f"https://components.espressif.com/api/components/{namespace}/{name}")
    versions = data.get("versions", [])
    latest = next((item for item in versions if item.get("latest")), None)
    if latest is None and versions:
        latest = versions[0]
    return latest.get("version") if isinstance(latest, dict) else None


def latest_pypi(package: str) -> str | None:
    data = fetch_json(f"https://pypi.org/pypi/{package}/json")
    info = data.get("info", {})
    version = info.get("version")
    return str(version) if version else None


def venv_site_packages(venv_dir: Path) -> list[str]:
    return [str(path) for path in sorted(venv_dir.glob("lib/python*/site-packages")) if path.is_dir()]


def installed_python_packages(venv_dir: Path | None = None) -> dict[str, str]:
    """Report ML package versions from the project venv, not the running interpreter.

    The audit is normally launched with the system Python, which does not have the
    pinned training stack installed; reading it would report false ``missing``/``stale``.
    """
    search_path = venv_site_packages(venv_dir) if venv_dir is not None else []
    if search_path:
        found = {
            (distribution.metadata["Name"] or "").lower(): distribution.version
            for distribution in importlib.metadata.distributions(path=search_path)
        }
        return {package: found.get(package, "missing") for package in PYTHON_PACKAGES}

    result: dict[str, str] = {}
    for package in PYTHON_PACKAGES:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "missing"
    return result


def installed_ollama_version(version_output: str | None) -> str | None:
    if not version_output:
        return None
    match = re.search(r"(\d+(?:\.\d+)+)", version_output)
    return match.group(1) if match else None


def ollama_inventory() -> dict[str, object]:
    version_rc, version_out = _run(["ollama", "--version"])
    list_rc, list_out = _run(["ollama", "list"])
    models: list[dict[str, str]] = []
    if list_rc == 0:
        for line in list_out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 4:
                models.append({"name": parts[0], "id": parts[1], "size": parts[2]})
    return {
        "available": version_rc == 0,
        "version": version_out if version_rc == 0 else None,
        "models": models,
        "error": None if version_rc == 0 else version_out,
    }


def status_for(name: str, current: str | None, latest: str | None, source: str, note: str = "") -> DependencyStatus:
    if current in {None, "", "missing"}:
        status = "missing"
    elif latest is None:
        status = "unknown"
    elif current == latest:
        status = "current"
    else:
        status = "stale"
    return DependencyStatus(name, current, latest, status, source, note)


def build_report(offline: bool) -> dict[str, object]:
    lock_versions = locked_esp_versions(REPO_ROOT / "dependencies.lock")
    py_installed = installed_python_packages(ML_VENV_DIR)
    py_constraints = configured_python_constraints(REPO_ROOT / "scripts/setup_ml_env.sh")
    ollama = ollama_inventory()

    dependencies: list[DependencyStatus] = []
    for component in ESP_COMPONENTS:
        latest = None if offline else latest_esp_component(component)
        dependencies.append(status_for(component, lock_versions.get(component), latest, "ESP Component Registry"))

    idf_latest = lock_versions.get("idf") if offline else latest_idf_release()
    dependencies.append(
        status_for(
            "idf",
            lock_versions.get("idf"),
            idf_latest,
            "GitHub Releases",
            "highest stable esp-idf release; toolchain pin lives in scripts/idf_env.sh",
        )
    )

    for package in PYTHON_PACKAGES:
        latest = None if offline else latest_pypi(package)
        note = f"setup constraint: {py_constraints.get(package, 'not pinned in setup script')}"
        dependencies.append(status_for(package, py_installed.get(package), latest, "PyPI", note))

    ollama_current = installed_ollama_version(ollama.get("version"))  # type: ignore[arg-type]
    ollama_latest = None if offline else latest_ollama_release()
    dependencies.append(
        status_for(
            "ollama",
            ollama_current,
            ollama_latest,
            "GitHub Releases",
            "host tool, hand-installed in /usr/local/bin; upgrading it changes vision-model labeling output",
        )
    )

    return {
        "dependencies": [dependency.__dict__ for dependency in dependencies],
        "ollama": ollama,
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "ml_venv": str(ML_VENV_DIR),
            "ml_venv_present": bool(venv_site_packages(ML_VENV_DIR)),
        },
    }


def write_markdown(report: dict[str, object], output_path: Path) -> None:
    lines = [
        "# Dependency Audit",
        "",
        "## Dependencies",
        "",
        "| Name | Current | Latest | Status | Source | Note |",
        "|---|---:|---:|---|---|---|",
    ]
    for dependency in report["dependencies"]:  # type: ignore[index]
        lines.append(
            "| {name} | {current} | {latest} | {status} | {source} | {note} |".format(
                name=dependency["name"],
                current=dependency.get("current") or "",
                latest=dependency.get("latest") or "",
                status=dependency["status"],
                source=dependency["source"],
                note=dependency.get("note", ""),
            )
        )
    ollama = report["ollama"]  # type: ignore[index]
    lines.extend(
        ["", "## Ollama", "", f"- Available: `{ollama['available']}`", f"- Version: `{ollama.get('version')}`", ""]
    )
    lines.append("| Model | ID | Size |")
    lines.append("|---|---|---:|")
    for model in ollama.get("models", []):
        lines.append(f"| {model['name']} | {model['id']} | {model['size']} |")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    report = build_report(offline=args.offline)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown_out)
    stale = [item for item in report["dependencies"] if item["status"] == "stale"]
    print(f"[INFO] wrote {args.json_out}")
    print(f"[INFO] wrote {args.markdown_out}")
    if stale:
        print("[WARN] stale dependencies: " + ", ".join(item["name"] for item in stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
