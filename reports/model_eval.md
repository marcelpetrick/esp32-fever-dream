# Recognition Evaluation

No real thermometer dataset has been captured yet.

Planned acceptance thresholds:

- Per-digit accuracy: at least 99% on controlled validation images.
- Full-reading accuracy: at least 98%.
- Invalid or ambiguous images must be rejected explicitly.

Current implementation status:

- Rule-based seven-segment digit decoding is available as a host-tested primitive.
- Display text parsing validates confidence and plausible temperature range.
- Image ROI crop and threshold primitives are available for desktop and firmware integration.
