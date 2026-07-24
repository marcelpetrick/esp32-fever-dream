import tempfile
import unittest
from pathlib import Path

from tools.dependency_audit import (
    configured_python_constraints,
    installed_ollama_version,
    locked_esp_versions,
    release_version,
    status_for,
    venv_site_packages,
)


class DependencyAuditTest(unittest.TestCase):
    def test_reads_esp_lock_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dependencies.lock"
            path.write_text(
                "\n".join(
                    [
                        "dependencies:",
                        "  espressif/esp-nn:",
                        "    source:",
                        "      type: service",
                        "    version: 1.2.4",
                        "  idf:",
                        "    source:",
                        "      type: idf",
                        "    version: 6.0.1",
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                locked_esp_versions(path),
                {"espressif/esp-nn": "1.2.4", "idf": "6.0.1"},
            )

    def test_reads_python_setup_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "setup_ml_env.sh"
            path.write_text(
                'uv pip install --python "${VENV_DIR}/bin/python" "tensorflow>=2.16,<2.19" pillow numpy\n',
                encoding="utf-8",
            )

            self.assertEqual(
                configured_python_constraints(path),
                {
                    "tensorflow": "tensorflow>=2.16,<2.19",
                    "pillow": "pillow",
                    "numpy": "numpy",
                },
            )

    def test_marks_status(self) -> None:
        self.assertEqual(status_for("x", "1", "1", "src").status, "current")
        self.assertEqual(status_for("x", "1", "2", "src").status, "stale")
        self.assertEqual(status_for("x", "missing", "2", "src").status, "missing")
        self.assertEqual(status_for("x", "1", None, "src").status, "unknown")

    def test_parses_stable_release_tags_only(self) -> None:
        self.assertEqual(release_version("v6.0.2"), (6, 0, 2))
        self.assertEqual(release_version("6.0"), (6, 0))
        self.assertIsNone(release_version("v6.1-beta1"))
        self.assertIsNone(release_version("v6.0-rc1"))

    def test_orders_releases_by_version_not_by_date(self) -> None:
        # Espressif backports to LTS branches, so v5.5.5 can be published after v6.0.2.
        tags = ["v5.5.5", "v6.0.2", "v6.0.1", "v5.2.7"]
        highest = max((release_version(tag), tag) for tag in tags)  # type: ignore[type-var]
        self.assertEqual(highest[1], "v6.0.2")

    def test_extracts_ollama_version(self) -> None:
        self.assertEqual(installed_ollama_version("ollama version is 0.31.2"), "0.31.2")
        self.assertIsNone(installed_ollama_version(""))
        self.assertIsNone(installed_ollama_version(None))

    def test_finds_venv_site_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            venv_dir = Path(temp_dir) / ".venv-ml"
            site_packages = venv_dir / "lib" / "python3.13" / "site-packages"
            site_packages.mkdir(parents=True)

            self.assertEqual(venv_site_packages(venv_dir), [str(site_packages)])
            self.assertEqual(venv_site_packages(Path(temp_dir) / "absent"), [])


if __name__ == "__main__":
    unittest.main()
