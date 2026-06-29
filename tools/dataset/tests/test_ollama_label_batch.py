from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from tools.dataset.ollama_label_batch import (
    assign_split,
    extract_json,
    load_existing_labels,
    parse_args,
    proposal_succeeded,
    query_ollama,
    response_socket,
    validate_values,
    write_proposals_atomic,
)


class ExtractJsonTest(unittest.TestCase):
    def test_extracts_bare_json(self) -> None:
        text = '{"co2_ppm":444,"hcho_raw":13,"tvoc_raw":36,"temperature_c":27,"humidity_percent":43,"valid":true}'
        result = extract_json(text)
        assert result is not None
        self.assertEqual(result["co2_ppm"], 444)
        self.assertEqual(result["valid"], True)

    def test_extracts_json_surrounded_by_prose(self) -> None:
        text = (
            "Here is the data you asked for:\n"
            '{"co2_ppm":720,"hcho_raw":5,"tvoc_raw":12,"temperature_c":28,"humidity_percent":47,"valid":true}\n'
            "Note that values are within range."
        )
        result = extract_json(text)
        assert result is not None
        self.assertEqual(result["co2_ppm"], 720)

    def test_returns_none_on_missing_json(self) -> None:
        self.assertIsNone(extract_json("No JSON object here at all."))

    def test_returns_none_on_malformed_json(self) -> None:
        self.assertIsNone(extract_json("{co2_ppm: 444}"))


class ValidateValuesTest(unittest.TestCase):
    def _good(self) -> dict:
        return {
            "co2_ppm": 600,
            "hcho_raw": 15,
            "tvoc_raw": 40,
            "temperature_c": 25,
            "humidity_percent": 50,
        }

    def test_accepts_valid_readings(self) -> None:
        self.assertTrue(validate_values(self._good()))

    def test_rejects_co2_out_of_range(self) -> None:
        d = self._good()
        d["co2_ppm"] = 99999
        self.assertFalse(validate_values(d))

    def test_rejects_temperature_out_of_range(self) -> None:
        d = self._good()
        d["temperature_c"] = -50
        self.assertFalse(validate_values(d))

    def test_rejects_humidity_over_100(self) -> None:
        d = self._good()
        d["humidity_percent"] = 101
        self.assertFalse(validate_values(d))

    def test_rejects_single_digit_humidity(self) -> None:
        d = self._good()
        d["humidity_percent"] = 6
        self.assertFalse(validate_values(d))

    def test_rejects_missing_key(self) -> None:
        d = self._good()
        del d["tvoc_raw"]
        self.assertFalse(validate_values(d))

    def test_rejects_sentinel_minus_one(self) -> None:
        d = self._good()
        d["co2_ppm"] = -1
        self.assertFalse(validate_values(d))


class AssignSplitTest(unittest.TestCase):
    def test_first_frame_is_train(self) -> None:
        self.assertEqual(assign_split(0, 100, 0.80, 0.10), "train")

    def test_last_train_frame(self) -> None:
        self.assertEqual(assign_split(79, 100, 0.80, 0.10), "train")

    def test_first_val_frame(self) -> None:
        self.assertEqual(assign_split(80, 100, 0.80, 0.10), "validation")

    def test_last_val_frame(self) -> None:
        self.assertEqual(assign_split(89, 100, 0.80, 0.10), "validation")

    def test_test_frame(self) -> None:
        self.assertEqual(assign_split(95, 100, 0.80, 0.10), "test")

    def test_single_frame_is_train(self) -> None:
        self.assertEqual(assign_split(0, 1, 0.80, 0.10), "train")


class ArgumentsTest(unittest.TestCase):
    def test_rejects_invalid_split_sum(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(
                [
                    "--dataset-dir",
                    ".",
                    "--train-fraction",
                    "0.9",
                    "--val-fraction",
                    "0.2",
                ]
            )

    def test_duplicate_policy_can_be_disabled(self) -> None:
        args = parse_args(["--dataset-dir", ".", "--no-skip-duplicates"])
        self.assertFalse(args.skip_duplicates)

    def test_limit_must_be_positive(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--dataset-dir", ".", "--limit", "0"])


class ProposalPersistenceTest(unittest.TestCase):
    def _row(self, status: str, valid: str) -> dict[str, object]:
        return {
            "sample_id": "capture_0001",
            "image_path": "capture_0001.jpg",
            "temperature_c": 27,
            "humidity_percent": 45,
            "co2_ppm": 600,
            "hcho_raw": 15,
            "tvoc_raw": 40,
            "valid": valid,
            "split": "train",
            "notes": "test",
            "proposal_status": status,
            "model": "test",
            "prompt_version": "test-v1",
            "labeled_at_utc": "2026-06-29T00:00:00+00:00",
            "attempts": 1,
            "duration_seconds": "1.0",
        }

    def test_atomic_write_replaces_failed_row_without_duplicates(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "proposals.csv"
            write_proposals_atomic({"capture_0001": self._row("error", "false")}, path)
            write_proposals_atomic({"capture_0001": self._row("accepted", "true")}, path)
            rows = load_existing_labels(path)
            self.assertEqual(list(rows), ["capture_0001"])
            self.assertTrue(proposal_succeeded(rows["capture_0001"]))

    def test_errors_are_not_complete_for_resume(self) -> None:
        self.assertFalse(proposal_succeeded(self._row("error", "false")))


class _FakeResponse:
    status = 200
    reason = "OK"

    def readline(self) -> bytes:
        return b'{"response":"x","done":false}\n'


class _FakeConnection:
    last_body = b""
    sock = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    def request(self, method, path, body, headers) -> None:
        self.__class__.last_body = body

    def getresponse(self) -> _FakeResponse:
        return _FakeResponse()

    def close(self) -> None:
        pass


class _FakeThinkingResponse:
    status = 200
    reason = "OK"

    def __init__(self) -> None:
        self.returned = False

    def readline(self) -> bytes:
        if self.returned:
            return b""
        self.returned = True
        return b'{"response":"","thinking":"{\\"valid\\":true}","done":true}\n'


class _FakeThinkingConnection(_FakeConnection):
    def getresponse(self) -> _FakeThinkingResponse:
        return _FakeThinkingResponse()


class _TransferredSocket:
    def __init__(self) -> None:
        self.timeout = None

    def settimeout(self, timeout) -> None:
        self.timeout = timeout


class _RawStream:
    def __init__(self, sock) -> None:
        self._sock = sock


class _ResponseStream:
    def __init__(self, sock) -> None:
        self.raw = _RawStream(sock)


class QueryOllamaTest(unittest.TestCase):
    def test_hard_deadline_and_bounded_structured_output(self) -> None:
        with (
            mock.patch(
                "tools.dataset.ollama_label_batch.http.client.HTTPConnection",
                _FakeConnection,
            ),
            mock.patch(
                "tools.dataset.ollama_label_batch.time.monotonic",
                side_effect=[0.0, 2.0],
            ),
        ):
            with self.assertRaises(TimeoutError):
                query_ollama(
                    "model",
                    "image",
                    "http://localhost/api/generate",
                    "prompt",
                    10,
                    total_timeout=1,
                    num_predict=96,
                )
        body = _FakeConnection.last_body.decode()
        self.assertIn('"num_predict": 96', body)
        self.assertIn('"format": {', body)
        self.assertIn('"think": false', body)

    def test_uses_structured_thinking_fallback_from_qwen(self) -> None:
        with (
            mock.patch(
                "tools.dataset.ollama_label_batch.http.client.HTTPConnection",
                _FakeThinkingConnection,
            ),
            mock.patch(
                "tools.dataset.ollama_label_batch.time.monotonic",
                side_effect=[0.0, 0.1],
            ),
        ):
            result = query_ollama(
                "model", "image", "http://localhost/api/generate", "prompt", 10
            )
        self.assertEqual(result, '{"valid":true}')

    def test_finds_socket_transferred_to_response(self) -> None:
        sock = _TransferredSocket()
        response = _FakeThinkingResponse()
        response.fp = _ResponseStream(sock)
        connection = _FakeConnection()
        connection.sock = None
        self.assertIs(response_socket(response, connection), sock)


if __name__ == "__main__":
    unittest.main()
