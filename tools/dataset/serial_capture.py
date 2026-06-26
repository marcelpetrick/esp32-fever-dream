#!/usr/bin/env python3
"""Collect ESP32-CAM JPEG captures through the USB serial fallback protocol."""

from __future__ import annotations

import argparse
import array
import base64
import csv
import fcntl
import os
import select
import sys
import termios
import time
import tty
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


BAUD_RATES = {
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
    230400: termios.B230400,
    460800: termios.B460800,
    921600: termios.B921600,
}


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(description="Capture JPEG training images over /dev/ttyUSB0 without Wi-Fi.")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial device. Default: /dev/ttyUSB0.")
    parser.add_argument("--baud", type=int, default=115200, choices=sorted(BAUD_RATES), help="UART baud rate.")
    parser.add_argument("--count", type=int, default=10, help="Number of images to capture.")
    parser.add_argument("--interval", type=float, default=1.0, help="Delay between captures in seconds.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tools/dataset/captures") / f"serial_{timestamp}",
        help="Directory for JPEGs and manifest.",
    )
    parser.add_argument("--lighting-label", default="serial_usb", help="Manifest lighting label.")
    parser.add_argument("--framesize", default="vga", choices=["qvga", "vga", "svga"], help="Camera frame size.")
    parser.add_argument("--quality", type=int, default=12, help="JPEG quality, lower is better. Firmware clamps 4..63.")
    parser.add_argument("--brightness", type=int, help="OV2640 brightness, -2..2.")
    parser.add_argument("--contrast", type=int, help="OV2640 contrast, -2..2.")
    parser.add_argument("--saturation", type=int, help="OV2640 saturation, -2..2.")
    parser.add_argument("--aec", type=int, choices=[0, 1], help="Auto exposure control.")
    parser.add_argument("--agc", type=int, choices=[0, 1], help="Auto gain control.")
    parser.add_argument("--awb", type=int, choices=[0, 1], help="Auto white balance.")
    parser.add_argument("--timeout", type=float, default=20.0, help="Seconds to wait for each serial response.")
    parser.add_argument(
        "--startup-wait",
        type=float,
        default=8.0,
        help="Seconds to drain boot logs and wait for FEVER_SERIAL_CAPTURE_READY after opening the port.",
    )
    parser.add_argument("--no-reset", action="store_true", help="Do not toggle RTS/DTR to reset the board on open.")
    return parser.parse_args(list(argv))


class SerialPort:
    def __init__(self, path: str, baud: int) -> None:
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)
        attrs = termios.tcgetattr(self.fd)
        attrs[4] = BAUD_RATES[baud]
        attrs[5] = BAUD_RATES[baud]
        attrs[2] |= termios.CLOCAL | termios.CREAD
        attrs[2] &= ~termios.CSTOPB
        attrs[2] &= ~termios.PARENB
        attrs[2] &= ~termios.CSIZE
        attrs[2] |= termios.CS8
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        termios.tcflush(self.fd, termios.TCIOFLUSH)
        self.buffer = bytearray()

    def close(self) -> None:
        os.close(self.fd)

    def write_line(self, line: str) -> None:
        os.write(self.fd, line.encode("ascii") + b"\n")

    def reset_board(self) -> None:
        bits = array.array("i", [0])
        fcntl.ioctl(self.fd, termios.TIOCMGET, bits, True)
        bits[0] |= termios.TIOCM_RTS
        bits[0] &= ~termios.TIOCM_DTR
        fcntl.ioctl(self.fd, termios.TIOCMSET, bits)
        time.sleep(0.1)
        bits[0] &= ~termios.TIOCM_RTS
        fcntl.ioctl(self.fd, termios.TIOCMSET, bits)

    def read_line(self, timeout_s: float) -> str | None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                raw = bytes(self.buffer[:newline])
                del self.buffer[: newline + 1]
                return raw.decode("ascii", errors="replace").strip()

            remaining = max(0.0, deadline - time.monotonic())
            readable, _, _ = select.select([self.fd], [], [], min(0.25, remaining))
            if not readable:
                continue
            try:
                chunk = os.read(self.fd, 4096)
            except BlockingIOError:
                continue
            if chunk:
                self.buffer.extend(chunk)
        return None


def camera_settings(args: argparse.Namespace) -> list[str]:
    settings = [f"framesize={args.framesize}", f"quality={args.quality}"]
    for name in ["brightness", "contrast", "saturation", "aec", "agc", "awb"]:
        value = getattr(args, name)
        if value is not None:
            settings.append(f"{name}={value}")
    return settings


def parse_begin(line: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for token in line.split()[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            values[key] = value
    return values


def request_capture(serial: SerialPort, command: str, timeout_s: float) -> tuple[bytes, dict[str, str]]:
    serial.write_line(command)

    begin: dict[str, str] | None = None
    while begin is None:
        line = serial.read_line(timeout_s)
        if line is None:
            raise TimeoutError("timed out waiting for FEVER_JPEG_BEGIN")
        if line.startswith("FEVER_CAPTURE_ERROR"):
            raise RuntimeError(line)
        if line.startswith("FEVER_JPEG_BEGIN"):
            begin = parse_begin(line)

    chunks: list[str] = []
    while True:
        line = serial.read_line(timeout_s)
        if line is None:
            raise TimeoutError("timed out waiting for FEVER_JPEG_END")
        if line.startswith("FEVER_CAPTURE_ERROR"):
            raise RuntimeError(line)
        if line == "FEVER_JPEG_END":
            break
        if line and not line.startswith(("I ", "W ", "E ", "FEVER_SERIAL_CAPTURE_READY")):
            chunks.append(line)

    data = base64.b64decode("".join(chunks), validate=True)
    expected_bytes = int(begin.get("bytes", "0"))
    if expected_bytes and len(data) != expected_bytes:
        raise RuntimeError(f"decoded {len(data)} bytes, expected {expected_bytes}")
    if not data.startswith(b"\xff\xd8"):
        raise RuntimeError("decoded payload is not a JPEG")
    return data, begin


def wait_for_serial_capture_ready(serial: SerialPort, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    saw_ready = False
    while time.monotonic() < deadline:
        line = serial.read_line(max(0.1, min(0.5, deadline - time.monotonic())))
        if line is None:
            continue
        if line.startswith("FEVER_SERIAL_CAPTURE_READY"):
            saw_ready = True
            break
    return saw_ready


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.csv"
    command = "CAPTURE_JPEG " + " ".join(camera_settings(args))

    with manifest_path.open("w", encoding="utf-8", newline="") as manifest_file:
        writer = csv.DictWriter(
            manifest_file,
            fieldnames=[
                "sample_id",
                "image_path",
                "lighting_label",
                "framesize",
                "quality",
                "brightness",
                "contrast",
                "saturation",
                "aec",
                "agc",
                "awb",
                "serial_status",
                "bytes",
                "width",
                "height",
                "captured_at_utc",
                "display_text",
                "notes",
            ],
        )
        writer.writeheader()

        serial = SerialPort(args.port, args.baud)
        try:
            if not args.no_reset:
                serial.reset_board()
            if args.startup_wait > 0:
                if wait_for_serial_capture_ready(serial, args.startup_wait):
                    print("[INFO] serial capture task is ready")
                else:
                    print("[WARN] did not see FEVER_SERIAL_CAPTURE_READY before first request", file=sys.stderr)
            for index in range(1, args.count + 1):
                sample_id = f"capture_{index:04d}"
                image_path = args.output_dir / f"{sample_id}.jpg"
                captured_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                try:
                    data, metadata = request_capture(serial, command, args.timeout)
                    image_path.write_bytes(data)
                    status = "ok"
                    notes = "serial_capture"
                    print(f"[INFO] {sample_id}: wrote {image_path} ({len(data)} bytes)")
                except Exception as exc:
                    data = b""
                    metadata = {}
                    status = "failed"
                    notes = str(exc)
                    print(f"[WARN] {sample_id}: {exc}", file=sys.stderr)

                writer.writerow(
                    {
                        "sample_id": sample_id,
                        "image_path": image_path,
                        "lighting_label": args.lighting_label,
                        "framesize": args.framesize,
                        "quality": args.quality,
                        "brightness": args.brightness if args.brightness is not None else "",
                        "contrast": args.contrast if args.contrast is not None else "",
                        "saturation": args.saturation if args.saturation is not None else "",
                        "aec": args.aec if args.aec is not None else "",
                        "agc": args.agc if args.agc is not None else "",
                        "awb": args.awb if args.awb is not None else "",
                        "serial_status": status,
                        "bytes": len(data),
                        "width": metadata.get("width", ""),
                        "height": metadata.get("height", ""),
                        "captured_at_utc": captured_at,
                        "display_text": "",
                        "notes": notes,
                    }
                )
                manifest_file.flush()
                if index < args.count:
                    time.sleep(args.interval)
        finally:
            serial.close()

    print(f"[INFO] wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
