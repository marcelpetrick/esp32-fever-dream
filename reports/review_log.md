# Review Log

Review findings are tracked here by severity. High findings must be fixed immediately.

## 2026-06-25 Bootstrap Review

### High

- [x] Local pipeline did not run the ESP-IDF firmware build; install ESP-IDF v6.0.1 and add firmware build to `scripts/check_all.sh`.

### Medium

- [x] `RecordCodec::Decode` accepted checksum-valid bytes with invalid status, confidence, flags, or reserved byte.
- [x] API query parsing matched `count=` inside unrelated parameter names such as `xcount`.
- [x] Doxygen warnings were visible but not fatal.

### Low

- [ ] Firmware HTTP handlers are still not wired to ESP-IDF `esp_http_server`; the host router defines the contract first.
