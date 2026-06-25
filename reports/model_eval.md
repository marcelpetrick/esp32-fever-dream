# Recognition Evaluation

A first real ESP32-CAM capture batch has been acquired locally under the ignored
dataset tree. The display is an air quality monitor with a fixed bottom row for
temperature and humidity.

Initial local baseline:

- Capture directory: `tools/dataset/captures/baseline_20260625T182331Z`
- Successful captures: 100 / 100
- Resolution: VGA JPEG, 640x480
- Confirmed temperature label: `30C`
- Confirmed humidity label: `44%`
- Temperature unit: Celsius
- Local labels: `labels_environment.csv` in the capture directory
- Local report: `fixed_display_report.md` in the capture directory

The initial baseline proved acquisition and labeling, but default camera
settings produced low bottom-row contrast.

Tuned local training baseline:

- Capture directory: `tools/dataset/captures/training_baseline_manual_20260625T183552Z`
- Successful captures: 100 / 100
- HTTP retries: 1 recovered retry
- Resolution: VGA JPEG, 640x480
- Camera settings: `quality=12 brightness=2 contrast=2 awb=0 aec=0 agc=0`
- Confirmed temperature label: `29C`
- Confirmed humidity label: `43%`
- Temperature unit: Celsius
- Train/validation/test split: 80/10/10
- Median ROI confidence: 0.5219
- P10 ROI confidence: 0.5127
- Low-quality samples: 1 / 100
- Local labels: `labels_environment.csv` in the capture directory
- Local report: `fixed_display_report.md` in the capture directory

This tuned baseline is useful for acquisition, ROI, and benchmark plumbing. It
is not yet enough to train or validate a digit model because all temperature and
humidity labels are the same.

Planned acceptance thresholds:

- Per-digit accuracy: at least 99% on controlled validation images.
- Full-reading accuracy: at least 98%.
- Invalid or ambiguous images must be rejected explicitly.

Current implementation status:

- Rule-based seven-segment digit decoding is available as a host-tested primitive.
- Display text parsing validates confidence and plausible temperature range.
- Image ROI crop and threshold primitives are available for desktop and firmware integration.
- A fixed-layout local labeler exists for temperature/humidity capture batches.
- The debug capture endpoint streams JPEGs directly from the camera frame buffer
  to improve repeated-capture stability.
