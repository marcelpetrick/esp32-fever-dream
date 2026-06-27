from __future__ import annotations

import unittest

from tools.dataset.serial_capture import is_base64_payload_line, parse_begin


class SerialCaptureTest(unittest.TestCase):
    def test_accepts_only_base64_payload_lines(self) -> None:
        self.assertTrue(is_base64_payload_line("/9j/4AAQSkZJRgABAQ=="))
        self.assertFalse(is_base64_payload_line("I (1234) camera: periodic capture"))
        self.assertFalse(is_base64_payload_line("FEVER_SERIAL_CAPTURE_READY"))
        self.assertFalse(is_base64_payload_line(""))

    def test_parse_begin_extracts_frame_metadata(self) -> None:
        self.assertEqual(
            parse_begin("FEVER_JPEG_BEGIN bytes=123 width=640 height=480"),
            {"bytes": "123", "width": "640", "height": "480"},
        )


if __name__ == "__main__":
    unittest.main()
