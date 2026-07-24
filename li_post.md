# LinkedIn Post — Data Collection

Working file for a LinkedIn post about the `esp32-fever-dream` project.
Status: **collection phase** — raw input first, drafting later.

---

## 1. Source brief (verbatim, as given by Marcel Petrick, 2026-07-24)

> first and foremost. check all dependencies of the project and check if there are more recent and stable ones. if yes, update. make sure everything is green. follow this projects guide lines. // get this done. handle this as plan. i will add more tassks. // review what was done in the past commit. is the model now more "fit" and better at recognition than before? tell me // then: extract all the interesting aspects about this project for a linkedin post. for professionals. i want to show off. use those two images i have in the readme too. make it baiting. like the idea "just wanted to read out the values from a co2 sensor" (predictive maintenance is a close one), instead of hooking sensor to the esp32. web-interface on the esp32: easy; rest api: easy; tflite model: easy. ersulting recognition of the camera output: hard. very hard. and challengeing. and time consuming. sampling, then doing ocr via other model. then the model training and checks. 80% of the effort. surprise to my initial expectation. burned tons of tokens. make the linkedin article data collection in this style. collect my input here verbatim first. call the file li_post.md, root dir. now go

---

## 2. Extracted intent / angle (derived from the brief above)

- **Audience:** professionals (embedded, ML, IoT, engineering leadership).
- **Tone:** show off, "baiting" hook — an honest effort-distribution reveal.
- **Core hook:** *"I just wanted to read the values off a CO2 sensor."*
  - Adjacent framing: predictive maintenance — reading a device that offers no data interface.
  - The twist: instead of wiring a sensor to the ESP32, point a **camera** at the existing display.
- **The effort inversion (the actual story):**
  | Part | Expected difficulty | Actual |
  | --- | --- | --- |
  | Web interface on the ESP32 | — | easy |
  | REST API | — | easy |
  | TFLite model | — | easy |
  | **Recognition of the camera output** | assumed easy | **hard. very hard. challenging. time-consuming.** |
- **Where the 80% went:** sampling → OCR via another (larger) model for label proposals → model training → checks/validation.
- **Surprise vs. initial expectation** is the emotional core of the post.
- **Cost note:** burned tons of tokens.
- **Images to use:** the two already in `README.md`:
  - `media/esp32cam_c0_sensor.png` (set-up, idealized)
  - `media/currentStateWebUi.png` (web UI view)

---

## 2b. THE HOOK (lead with this)

Two facts carry the entire post. Everything else is supporting material.
Open with them — do not bury them under setup.

### Hook A — the line-count inversion

> I built an ESP32 that reads a CO2 sensor's display with a camera.
>
> The embedded firmware: **3,002 lines**.
> The code to figure out *what the digits actually were*: **7,431 lines**.
>
> I expected that ratio to be the other way around.

**Why this works:** it's one comparison, no jargon, and it inverts the reader's
assumption in two numbers. Every engineer instinctively believes the embedded
part is the hard part. The repo says otherwise, and it says it in a metric
nobody can argue with.

**The reasoning behind it — this is the actual insight:**
The firmware is *bounded*. Capture a frame, crop a ROI, run inference, serve
JSON. You know when it's done, because it either compiles and runs or it
doesn't. The recognition problem is *unbounded* — it isn't "write the code," it's
"establish what the truth is, at scale, without a human labeling 3,083 frames by
hand." That's not an engineering task with a definition of done. That's a
measurement problem wearing an engineering costume. The line count is just where
that difference finally became visible.

### Hook B — the money slide (the agreement collapse)

> I asked two independent vision models to read the same 460 frames of the same
> display.
>
> | Field | Do they agree? |
> | --- | ---: |
> | CO2 | **100.0%** |
> | Temperature | **99.8%** |
> | Humidity | **99.1%** |
> | HCHO | **11.1%** |
> | TVOC | **13.7%** |
>
> Same display. Same frames. Same models. The big digits are solved. On the small
> ones, the models don't even agree with *each other*.

**Why this works:** it's a single table where the numbers fall off a cliff
mid-column. The reader's eye does the work — no explanation needed to feel that
something broke.

**The reasoning behind it — why this is the whole project in one table:**
The instinctive read is "the model is bad, train it more." That read is wrong,
and being able to say *why* is what makes this post worth writing.

Those two rows aren't measuring my model at all. They're measuring **whether a
ground truth exists**. When two independent labelers agree 100% of the time, you
have labels and training is a solved exercise. When they agree 11% of the time,
you have *noise* — and every epoch you train on it teaches the network to
reproduce a coin flip with increasing confidence.

That reframes the whole effort. It wasn't "the model underperformed." It was
**I could not tell the model what the right answer was**, because I didn't
reliably know. Accuracy was never the bottleneck. Ground truth was.

And the proof is in the failure: a retrain on those labels moved full-reading
accuracy 12.78% → 29.05% while per-digit accuracy *dropped* 86.68% → 82.05%,
with a 5.83% false-accept rate. It got better and worse simultaneously, which is
the signature of learning noise. It was rejected by an automated gate. It is not
on the device.

### How A and B fit together

A is the setup, B is the payoff, and the causal link between them is the post:

**7,431 lines of tooling exist *because* of that 11%.**

Multi-model consensus, temporal consistency checks, display-locator quality
gates, generated negative examples, a frozen test split, a deployment gate —
none of that is model code. It is all machinery built for one purpose: to
manufacture a trustworthy answer key. That is where the 80% went, and that is
the part nobody budgets for.

Closing line candidate:

> The neural network was the easy part. Knowing what it was supposed to say was
> the project.

---

## 3. Raw material

### 3.1 The one-line pitch

An ESP32-CAM stares at the LCD of an air-quality monitor and reads the numbers off it
with an on-device int8 TinyML digit classifier — because the sensor has no data
interface. No wires into the device, no protocol, no teardown. Just a camera and OCR.

Five values per frame: **CO2, HCHO, TVOC, temperature, humidity.**
Everything — dashboard, REST API, storage, inference — runs on the ESP32 itself.
No cloud, no CDN, no internet dependency.

### 3.2 The effort inversion (the actual hook — hard numbers)

The parts everyone assumes are the project:

| Part | Reality | Evidence |
| --- | --- | --- |
| Web dashboard on the ESP32 | easy | ~52 KB HTML/CSS/JS embedded as C string literals in flash |
| REST API | easy | 3 endpoints: `/api/v1/status`, `/current`, `/readings/latest` |
| TFLite Micro on device | easy | int8, 24×32 input, ~83 KB model, 96 KB tensor arena |
| **Getting correct numbers out of the camera image** | **the whole project** | see below |

**The code split tells the story on its own:**

- Firmware (C++, the "hard embedded part"): **3,002 lines**
- Data/ML/labeling tooling (Python): **7,431 lines** — **2.5× the firmware**

That ratio *is* the post. The embedded system was the easy part.

### 3.3 What "hard" actually meant

- **3,083 captured frames** across **29 distinct capture batches** — different
  lighting, angles, camera settings, day vs. night, upright vs. rotated.
- Batches that had to be thrown out entirely because the display locator failed on them.
- Labeling could not be done by hand at that volume → labels were generated by
  running **local vision LLMs via Ollama** over the captures (`qwen3-vl:4b`,
  `llama3.2-vision:11b`, `minicpm-v`, `moondream`).
- **One model alone is not ground truth.** So: multi-model consensus + temporal
  consistency checks + display-locator quality gates + plausibility ranges.
- Consensus is brutal. Strict two-model exact agreement over 520 rows promoted
  **12 rows**. Twelve.

### 3.4 The single best chart/table for the post — where OCR agreement collapses

Two independent vision models (`qwen3-vl:4b` vs `minicpm-v`), 460 commonly accepted frames:

| Field | Exact agreement |
| --- | ---: |
| CO2 | **100.00%** (460/460) |
| Temperature | **99.78%** (459/460) |
| Humidity | **99.13%** (456/460) |
| HCHO | **11.09%** (51/460) |
| TVOC | **13.70%** (63/460) |

Same display. Same frame. Same models. Big digits: essentially solved.
Small pollutant rows: the models don't even agree with *each other*.

**This is the money slide.** It shows the problem is not "the model is bad" —
it's that *the ground truth itself is unreliable* for the small text, and you
cannot train your way out of bad labels.

### 3.5 The honest part (good for credibility, very LinkedIn-rare)

The current on-device model is **not** production-trustworthy, and the project
says so out loud. There is an automated **deployment gate** that a model must
pass before it is allowed to replace the checked-in one. It currently **fails**:

| Gate check | Status |
| --- | --- |
| Test digit accuracy | ✗ 86.68% |
| Full-reading exact accuracy | ✗ 12.78% |
| Worst-digit accuracy | ✗ |
| False-accept rate | ✗ (no negative set at gate time) |
| Confidence threshold ≥85% | ✗ (still at prototype 30%) |
| Model size | ✓ |
| Frozen test split present | ✓ |
| All digits present in test set | ✓ |

A 60-epoch retrain on the new consensus labels was run, measured, and **rejected**:
full-reading accuracy improved 12.78% → 29.05%, but per-digit accuracy *dropped*
86.68% → 82.05% and it produced a 5.83% false-accept rate on generated negatives.
Not deployed. The gate did its job.

Per-field accuracy of that rejected model shows exactly the same shape as the
agreement table above:

| Field | Accuracy |
| --- | ---: |
| Temperature | 98.17% |
| Humidity | 87.07% |
| HCHO | 66.92% |
| TVOC | 66.39% |
| CO2 | 34.75% |

### 3.6 Engineering-discipline angle (for the "professionals" audience)

Hobby scope, production habits:

- Conventional commits, SemVer bumped every commit, signed off, GPLv3.
- One gate script: `check_all.sh` = clang-format → host build (`-Werror`) →
  host unit tests → cppcheck + clang-tidy (`--warnings-as-errors=*`) →
  firmware build → web asset check → ruff + black → Doxygen.
- A **frozen test split policy** so results stay comparable across retrains.
- **Generated negative/ambiguous examples** so "confidently wrong" is measurable,
  not just accuracy on clean frames.
- A reproducible **dependency audit** tool that checks ESP-IDF, ESP components,
  and the pinned Python ML stack against upstream registries.
- 86 commits.

### 3.7 Punchlines / candidate hooks

- "I just wanted to read the CO2 value off a sensor."
- "Hooking a sensor to an ESP32 is a weekend. Reading a sensor that refuses to
  talk to you is a research project."
- "The ESP32 part was done in days. The 'just read the digits' part ate 80% of it."
- "Web UI: easy. REST API: easy. TFLite model: easy. Recognition: *very* hard."
- "Turns out the bottleneck wasn't the neural network. It was knowing what the
  right answer was supposed to be."
- "I asked four vision models what the display said. On the big digits they agreed
  100% of the time. On the small ones, 11%."
- "Labeling is the product. The model is a side effect."
- Predictive-maintenance framing: this is the *exact* problem in the field —
  legacy equipment with a display and no data interface. A camera is the retrofit.
- Cost note: burned tons of tokens. (Honest and relatable — the multi-model
  labeling loop is the expensive part, not the training.)

### 3.8 Images (both already in README.md)

1. `media/esp32cam_c0_sensor.png` — the idealized setup: ESP32-CAM pointed at the
   AQS display. Use as the **lead image**; it makes the premise instantly legible.
2. `media/currentStateWebUi.png` — the dashboard served straight off the ESP32.
   Use as the **second image**; it's the "and it actually works" payoff.
3. (optional third, not in README) `media/labelling_run.png` — the labeling run.
   Would support the "80% of the effort was here" claim visually.

### 3.9 Tone notes for drafting

- Lead with the naive expectation, then the reveal. Don't bury the inversion.
- Keep the honesty about the failing gate — it is the most credible thing in the
  whole post and separates it from the usual "I built an AI thing 🚀" genre.
- The HCHO/TVOC agreement collapse is the single most shareable fact.
- End on the generalizable lesson (label quality > model architecture), not on
  the gadget.
