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
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

ESP_COMPONENTS = (
    "espressif/esp32-camera",
    "espressif/esp-tflite-micro",
    "espressif/esp-nn",
    "espressif/esp_jpeg",
)
PYTHON_PACKAGES = ("tensorflow", "numpy", "pillow")


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
    idf_match = re.search(r"^  idf:\n(?:    .*\n)*?    version: ['\"]?([^'\"\n]+)['\"]?", lock_path.read_text(encoding="utf-8"), re.MULTILINE)
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


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "esp32-fever-dream-dependency-audit"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


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


def installed_python_packages() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in PYTHON_PACKAGES:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "missing"
    return result


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
    py_installed = installed_python_packages()
    py_constraints = configured_python_constraints(REPO_ROOT / "scripts/setup_ml_env.sh")

    dependencies: list[DependencyStatus] = []
    for component in ESP_COMPONENTS:
        latest = None if offline else latest_esp_component(component)
        dependencies.append(status_for(component, lock_versions.get(component), latest, "ESP Component Registry"))
    dependencies.append(status_for("idf", lock_versions.get("idf"), lock_versions.get("idf"), "dependencies.lock", "IDF lock version"))

    for package in PYTHON_PACKAGES:
        latest = None if offline else latest_pypi(package)
        note = f"setup constraint: {py_constraints.get(package, 'not pinned in setup script')}"
        dependencies.append(status_for(package, py_installed.get(package), latest, "PyPI", note))

    return {
        "dependencies": [dependency.__dict__ for dependency in dependencies],
        "ollama": ollama_inventory(),
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
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
    lines.extend(["", "## Ollama", "", f"- Available: `{ollama['available']}`", f"- Version: `{ollama.get('version')}`", ""])
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
