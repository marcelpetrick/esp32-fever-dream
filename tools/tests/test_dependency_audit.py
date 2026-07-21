import tempfile
import unittest
from pathlib import Path

from tools.dependency_audit import configured_python_constraints, locked_esp_versions, status_for


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


if __name__ == "__main__":
    unittest.main()
