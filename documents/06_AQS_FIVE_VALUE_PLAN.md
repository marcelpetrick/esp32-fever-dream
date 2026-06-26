# AQS Five-Value Readout Plan

Last updated: 2026-06-26.

## Scope

The target display is now the air quality sensor, abbreviated `AQS` in project
documentation and code comments when a short name is needed.

The mounted AQS screen contains five values:

1. `CO2` on the first row.
2. `HCHO` on the second row.
3. `TVOC` on the third row.
4. Temperature on the lower combined row.
5. Relative humidity on the same lower combined row as temperature.

The next product target is to read all five values from one camera capture,
store them as one record, expose them through the ESP32 API, and show current
values plus history charts in the web UI.

## Constraints

- The ESP32-CAM currently has a working VGA JPEG capture path.
- Wi-Fi may be unavailable during dataset collection, so USB serial capture is
  now a required fallback.
- The existing TinyML model recognizes single digits in fixed ROIs. It can be
  extended to more fixed digit boxes, but the current model was only validated
  for temperature and humidity geometry.
- The current storage is an in-memory ring buffer of 240 records. It resets on
  reboot.
- Future flash persistence needs a versioned binary format; JSON is fine for
  API output but too bulky for flash storage.

## Data Model

Use a single compact reading record with nullable/sentinel fields:

| Field | Type | Sentinel | Notes |
| --- | --- | --- | --- |
| Timestamp | `uint32_t` | none | Seconds since epoch or boot-estimated time. |
| CO2 | `uint16_t` ppm | `65535` | Expected AQS range usually fits below 9999 ppm. |
| HCHO | `uint16_t` scaled | `65535` | Store as integer display units until exact decimal placement is confirmed. |
| TVOC | `uint16_t` scaled | `65535` | Store as integer display units until exact decimal placement is confirmed. |
| Temperature | `int16_t` centi-C | `INT16_MIN` | Existing format can stay. |
| Humidity | `uint8_t` percent | `255` | Existing format can stay. |
| Confidence | `uint8_t` percent | none | Minimum confidence across accepted fields. |
| Recognition duration | `uint16_t` ms | capped | Existing UI/API field remains useful. |
| Status | `uint8_t` enum | none | One status for the whole capture. |
| Flags | `uint8_t` bitset | none | Existing source/time metadata. |

For API readability, emit:

```json
{
  "co2_ppm": 728,
  "hcho": 0.03,
  "tvoc": 0.11,
  "temperature_c": 24.50,
  "humidity_percent": 43,
  "status": "ok",
  "confidence": 0.91,
  "recognition_duration_ms": 180
}
```

The exact HCHO/TVOC units and decimal placement must be confirmed from the AQS
display face or manual. Until confirmed, firmware should store integer scaled
values and documentation should avoid pretending the unit is known.

## Storage Capacity

Current RAM storage:

- Capacity configured in `main/app_main.cpp`: 240 records.
- Old two-value record is roughly 16 bytes after normal C++ alignment on ESP32.
- Five-value record is expected to be roughly 24 bytes after alignment.
- 240 records therefore cost about 5.6 KiB plus vector overhead, which is fine
  for RAM.

Practical maximum:

- Keeping 240 records is conservative and safe.
- 1,440 records, one day at one-minute cadence, would likely cost about
  35 KiB RAM plus overhead. This is possible on some ESP32-CAM builds but should
  not be the default until heap pressure is measured with camera, Wi-Fi, and
  TFLite active.
- For durable history, use flash-backed fixed records instead of increasing RAM
  indefinitely.

Planned persistent binary record:

| Byte range | Content |
| --- | --- |
| 0 | Record schema version. |
| 1 | Status. |
| 2 | Flags. |
| 3 | Confidence percent. |
| 4-7 | Timestamp seconds, little-endian. |
| 8-9 | CO2 ppm. |
| 10-11 | HCHO scaled integer. |
| 12-13 | TVOC scaled integer. |
| 14-15 | Temperature centi-C. |
| 16 | Humidity percent. |
| 17-18 | Recognition duration ms. |
| 19-20 | Checksum. |

That format is 21 bytes before padding. A 64 KiB flash partition could hold
roughly 3,000 records before metadata and wear strategy, which is about two days
at one-minute cadence. A 256 KiB partition could hold roughly 12,000 records,
or about eight days.

## Recognition Plan

1. Keep the current fixed-display OCR path.
2. Add fixed digit boxes for all AQS rows.
3. Decode each numeric field from its digit sequence.
4. Apply per-field plausibility checks:
   - CO2: reject unavailable or impossible values above the display range.
   - HCHO: accept only non-negative scaled values.
   - TVOC: accept only non-negative scaled values.
   - Temperature: reuse configured temperature range.
   - Humidity: `0..100`.
5. Compute full-reading confidence as the minimum digit confidence.
6. Continue to reject the full reading below the configured confidence
   threshold.

The first implementation can wire the data model, API, UI, and placeholder
fixed boxes. The real OCR accuracy will still need new labeled AQS captures.

## Dataset Plan

Use Wi-Fi HTTP capture when available:

```sh
./scripts/collect_dataset.sh \
  --base-url http://DEVICE_IP \
  --count 30 \
  --lighting-label aqs_daylight
```

Use USB serial capture when Wi-Fi is unavailable:

```sh
./scripts/collect_serial_dataset.sh \
  --port /dev/ttyUSB0 \
  --count 30 \
  --lighting-label aqs_usb_daylight \
  --framesize vga \
  --quality 12
```

Store human labels for all five values in the capture manifest or a derived
label CSV:

```csv
sample_id,image_path,co2_ppm,hcho,tvoc,temperature_c,humidity_percent,valid,notes
capture_0001,tools/dataset/captures/aqs_usb_daylight/capture_0001.jpg,728,0.03,0.11,24.5,43,true,baseline
```

## Implementation Steps

1. Add the USB serial capture fallback and dataset script.
2. Extend `ReadingRecord`, `RecognitionResult`, API serialization, and host
   tests to include five AQS values.
3. Extend the web dashboard current panel and chart renderer to show CO2, HCHO,
   TVOC, temperature, humidity, confidence, and status.
4. Extend the TinyML recognizer to produce all five values from fixed boxes.
5. Update documentation and storage-capacity notes.
6. Run host tests, web asset packaging, static checks where available, and an
   ESP-IDF build.

## Acceptance

- `/api/v1/current` contains all five value fields.
- `/api/v1/readings/latest` returns history with all five value fields.
- `/api/v1/status` reports storage capacity and record byte estimates.
- Web UI displays all five current values and charts historical progress.
- USB serial dataset capture works without Wi-Fi after firmware with the serial
  protocol is flashed.
- The implementation builds locally without embedding secrets.
