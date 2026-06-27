(function () {
    "use strict";

    var ENDPOINTS = {
        status: "/api/v1/status",
        current: "/api/v1/current",
        latest: "/api/v1/readings/latest?count=1440"
    };
    var STORAGE_KEY = "esp32-fever-dream-ui";
    var DEFAULT_MEASUREMENT_INTERVAL_SECONDS = 10;
    var SERIES = [
        { key: "co2", label: "CO2", unit: "ppm", color: "#b84222", decimals: 0 },
        { key: "hcho", label: "HCHO", unit: "", color: "#2e6f46", decimals: 3 },
        { key: "tvoc", label: "TVOC", unit: "", color: "#6f4fb5", decimals: 3 },
        { key: "temperature", label: "Temp", unit: "°C", color: "#1f6fb2", decimals: 1 },
        { key: "humidity", label: "Humidity", unit: "%", color: "#9a6500", decimals: 0 }
    ];
    var state = {
        status: null,
        current: null,
        readings: [],
        loading: false,
        lastUpdated: null,
        lastReadingKey: null,
        lastReadingSeenAt: null,
        refreshTimer: null,
        countdownTimer: null,
        pipelineTimer: null,
        pipelineLoading: false,
        lastError: null,
        streamBase: "",
        streamTimer: null,
        streamFrames: 0,
        streamLastLoaded: null
    };

    var el = {};

    document.addEventListener("DOMContentLoaded", function () {
        el = {
            modeSelect: document.getElementById("modeSelect"),
            themeSelect: document.getElementById("themeSelect"),
            firmwareVersion: document.getElementById("firmwareVersion"),
            currentCo2: document.getElementById("currentCo2"),
            currentHcho: document.getElementById("currentHcho"),
            currentTvoc: document.getElementById("currentTvoc"),
            currentTemp: document.getElementById("currentTemp"),
            currentHumidity: document.getElementById("currentHumidity"),
            currentConfidence: document.getElementById("currentConfidence"),
            confidenceRule: document.getElementById("confidenceRule"),
            currentMeta: document.getElementById("currentMeta"),
            statusBadge: document.getElementById("statusBadge"),
            chartGrid: document.getElementById("chartGrid"),
            chartSummary: document.getElementById("chartSummary"),
            captureCountdown: document.getElementById("captureCountdown"),
            captureInterval: document.getElementById("captureInterval"),
            captureProgress: document.getElementById("captureProgress"),
            pipelineSteps: document.getElementById("pipelineSteps"),
            statusList: document.getElementById("statusList"),
            diagnosticsList: document.getElementById("diagnosticsList"),
            refreshButton: document.getElementById("refreshButton"),
            apiState: document.getElementById("apiState"),
            deviceInput: document.getElementById("deviceInput"),
            connectButton: document.getElementById("connectButton"),
            snapshotButton: document.getElementById("snapshotButton"),
            liveImage: document.getElementById("liveImage"),
            streamState: document.getElementById("streamState"),
            streamMeta: document.getElementById("streamMeta")
        };

        loadPreferences();
        bindControls();
        setupStreamFromLocation();
        refreshAll();
        scheduleRefresh();
        state.countdownTimer = window.setInterval(renderCaptureCountdown, 250);
        state.pipelineTimer = window.setInterval(refreshPipelineStatus, 400);
        window.addEventListener("resize", debounce(drawChart, 120));
        window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", drawChart);
    });

    function bindControls() {
        el.modeSelect.addEventListener("change", function () {
            document.documentElement.dataset.mode = el.modeSelect.value;
            savePreferences();
            drawChart();
        });
        el.themeSelect.addEventListener("change", function () {
            document.documentElement.dataset.theme = el.themeSelect.value;
            savePreferences();
            drawChart();
        });
        el.refreshButton.addEventListener("click", refreshAll);
        el.connectButton.addEventListener("click", connectStream);
        el.snapshotButton.addEventListener("click", loadStreamFrame);
        el.liveImage.addEventListener("load", function () {
            state.streamFrames += 1;
            state.streamLastLoaded = new Date();
            setStreamState("Live");
            renderStreamMeta();
        });
        el.liveImage.addEventListener("error", function () {
            setStreamState("Offline");
            renderStreamMeta("capture failed");
        });
    }

    function loadPreferences() {
        var prefs = {};
        try {
            prefs = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
        } catch (error) {
            prefs = {};
        }
        var mode = ["auto", "light", "dark"].indexOf(prefs.mode) >= 0 ? prefs.mode : "auto";
        var theme = ["ember", "forest", "mono"].indexOf(prefs.theme) >= 0 ? prefs.theme : "ember";
        document.documentElement.dataset.mode = mode;
        document.documentElement.dataset.theme = theme;
        el.modeSelect.value = mode;
        el.themeSelect.value = theme;
    }

    function savePreferences() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
            mode: el.modeSelect.value,
            theme: el.themeSelect.value
        }));
    }

    function refreshAll() {
        if (state.loading) {
            return;
        }
        state.loading = true;
        el.refreshButton.disabled = true;
        setApiState("Loading");

        Promise.all([
            getJson(apiUrl(ENDPOINTS.status)),
            getJson(apiUrl(ENDPOINTS.current)),
            getJson(apiUrl(ENDPOINTS.latest))
        ]).then(function (responses) {
            state.status = newerPipelineStatus(state.status, responses[0]);
            state.current = normalizeCurrent(responses[1]);
            state.readings = normalizeReadings(responses[2]);
            rememberCurrentSample(state.current);
            state.lastUpdated = new Date();
            state.lastError = null;
            render();
            syncStreamTimer();
            setApiState("Live");
        }).catch(function (error) {
            state.lastError = error;
            render();
            setApiState("Offline");
        }).finally(function () {
            state.loading = false;
            el.refreshButton.disabled = false;
            scheduleRefresh();
        });
    }

    function scheduleRefresh() {
        window.clearTimeout(state.refreshTimer);
        state.refreshTimer = window.setTimeout(refreshAll, measurementIntervalSeconds() * 1000);
    }

    function refreshPipelineStatus() {
        if (!state.streamBase || state.pipelineLoading) {
            return;
        }
        state.pipelineLoading = true;
        getJson(apiUrl(ENDPOINTS.status)).then(function (status) {
            state.status = newerPipelineStatus(state.status, status);
            renderHeader();
            renderPipeline();
        }).catch(function () {
            // The full refresh owns user-visible connection errors.
        }).finally(function () {
            state.pipelineLoading = false;
        });
    }

    function syncStreamTimer() {
        if (!state.streamBase) {
            return;
        }
        window.clearInterval(state.streamTimer);
        state.streamTimer = window.setInterval(loadStreamFrame, measurementIntervalSeconds() * 1000);
    }

    function setupStreamFromLocation() {
        var params = new URLSearchParams(window.location.search);
        var device = params.get("device") || localStorage.getItem(STORAGE_KEY + "-device") || "";
        if (!device && window.location.protocol.indexOf("http") === 0 && window.location.hostname) {
            device = window.location.origin;
        }
        el.deviceInput.value = device.replace(/^https?:\/\//, "");
        if (device) {
            connectStream();
        }
    }

    function connectStream() {
        var raw = el.deviceInput.value.trim();
        if (!raw) {
            setStreamState("Unknown");
            renderStreamMeta("device missing");
            return;
        }
        state.streamBase = normalizeDeviceBase(raw);
        localStorage.setItem(STORAGE_KEY + "-device", state.streamBase);
        state.streamFrames = 0;
        setStreamState("Loading");
        loadStreamFrame();
        syncStreamTimer();
    }

    function normalizeDeviceBase(raw) {
        if (/^https?:\/\//.test(raw)) {
            return raw.replace(/\/+$/, "");
        }
        return "http" + "://" + raw.replace(/\/+$/, "");
    }

    function streamCaptureUrl() {
        var params = [
            "framesize=vga",
            "quality=12",
            "brightness=2",
            "contrast=2",
            "awb=0",
            "aec=0",
            "agc=0",
            "ui_ts=" + Date.now()
        ];
        return state.streamBase + "/debug/capture.jpg?" + params.join("&");
    }

    function apiUrl(path) {
        return state.streamBase ? state.streamBase + path : path;
    }

    function loadStreamFrame() {
        if (!state.streamBase) {
            return;
        }
        setStreamState("Loading");
        el.liveImage.src = streamCaptureUrl();
    }

    function setStreamState(text) {
        el.streamState.textContent = text;
        el.streamState.className = "api-state " + statusClass(text);
    }

    function renderStreamMeta(extra) {
        var parts = [];
        if (state.streamBase) {
            parts.push(state.streamBase);
        }
        if (state.streamLastLoaded) {
            parts.push("frame " + state.streamFrames + " at " + formatTime(state.streamLastLoaded));
        }
        if (extra) {
            parts.push(extra);
        }
        el.streamMeta.textContent = parts.join(" · ") || "No live stream connected";
    }

    function getJson(url) {
        return fetch(url, {
            cache: "no-store",
            headers: { "Accept": "application/json" }
        }).then(function (response) {
            if (!response.ok) {
                throw new Error(url + " returned HTTP " + response.status);
            }
            return response.json();
        });
    }

    function normalizeCurrent(payload) {
        var reading = payload && (payload.reading || payload.current || payload.latest || payload);
        return normalizeReading(reading || {});
    }

    function normalizeReadings(payload) {
        var raw = [];
        if (Array.isArray(payload)) {
            raw = payload;
        } else if (payload && Array.isArray(payload.readings)) {
            raw = payload.readings;
        } else if (payload && Array.isArray(payload.items)) {
            raw = payload.items;
        } else if (payload && Array.isArray(payload.data)) {
            raw = payload.data;
        }
        return raw.map(normalizeReading).filter(function (reading) {
            return reading.timestamp || hasAnyValue(reading) || reading.status !== "unknown";
        });
    }

    function normalizeReading(raw) {
        var timestamp = pick(raw, ["timestamp", "time", "ts", "created_at"]);
        var co2 = pick(raw, ["co2_ppm", "co2", "co2ppm"]);
        var hcho = pick(raw, ["hcho", "hcho_value"]);
        var tvoc = pick(raw, ["tvoc", "tvoc_value"]);
        var temperature = pick(raw, ["temperature_c", "temperature", "temp_c", "value"]);
        var confidence = pick(raw, ["confidence", "quality", "score"]);
        var humidity = pick(raw, ["humidity_percent", "humidity", "rh_percent"]);
        var duration = pick(raw, ["recognition_duration_ms", "ocr_duration_ms", "duration_ms"]);
        return {
            timestampRaw: timestamp,
            timestamp: normalizeTimestamp(timestamp),
            co2: toNumberOrNull(co2),
            hcho: toNumberOrNull(hcho),
            tvoc: toNumberOrNull(tvoc),
            temperature: toNumberOrNull(temperature),
            humidity: toNumberOrNull(humidity),
            status: String(pick(raw, ["status", "state"], "unknown") || "unknown"),
            confidence: toNumberOrNull(confidence),
            recognitionDurationMs: toNumberOrNull(duration),
            source: pick(raw, ["source", "recognition_source"], ""),
            error: pick(raw, ["error", "message"], "")
        };
    }

    function hasAnyValue(reading) {
        return SERIES.some(function (series) {
            return reading[series.key] !== null;
        });
    }

    function rememberCurrentSample(reading) {
        if (!reading) {
            return;
        }
        var key = sampleKey(reading);
        if (key && key !== state.lastReadingKey) {
            state.lastReadingKey = key;
            state.lastReadingSeenAt = new Date();
        } else if (key && !state.lastReadingSeenAt) {
            state.lastReadingSeenAt = new Date();
        }
    }

    function sampleKey(reading) {
        if (!reading) {
            return "";
        }
        if (reading.timestampRaw !== null && reading.timestampRaw !== undefined && reading.timestampRaw !== "") {
            return String(reading.timestampRaw);
        }
        return [
            reading.status,
            reading.co2,
            reading.hcho,
            reading.tvoc,
            reading.temperature,
            reading.humidity,
            reading.confidence
        ].join("|");
    }

    function measurementIntervalSeconds() {
        var direct = state.status && pick(state.status, ["measurement_interval_seconds", "measurementIntervalSeconds"]);
        var interval = toNumberOrNull(direct);
        if (interval !== null && interval > 0) {
            return Math.max(1, interval);
        }
        var capacity = state.status && toNumberOrNull(pick(state.status, ["storage_capacity_records"]));
        var retention = state.status && toNumberOrNull(pick(state.status, ["storage_retention_minutes"]));
        if (capacity && retention) {
            return Math.max(1, Math.round((retention * 60) / capacity));
        }
        return DEFAULT_MEASUREMENT_INTERVAL_SECONDS;
    }

    function newerPipelineStatus(current, incoming) {
        if (!current) {
            return incoming;
        }
        var currentCycle = toNumberOrNull(current.pipeline_cycle) || 0;
        var incomingCycle = toNumberOrNull(incoming && incoming.pipeline_cycle) || 0;
        if (incomingCycle !== currentCycle) {
            return incomingCycle > currentCycle ? incoming : current;
        }
        var currentStage = toNumberOrNull(current.pipeline_stage_index) || 0;
        var incomingStage = toNumberOrNull(incoming && incoming.pipeline_stage_index) || 0;
        var currentOrder = currentStage === 0 && currentCycle > 0 ? 6 : currentStage;
        var incomingOrder = incomingStage === 0 && incomingCycle > 0 ? 6 : incomingStage;
        return incomingOrder >= currentOrder ? incoming : current;
    }

    function renderCaptureCountdown() {
        if (!el.captureCountdown || !el.captureInterval || !el.captureProgress) {
            return;
        }
        var interval = measurementIntervalSeconds();
        el.captureInterval.textContent = "Interval " + interval.toFixed(0) + "s";
        if (!state.lastReadingSeenAt) {
            el.captureCountdown.textContent = "Next OCR sample in --s";
            el.captureProgress.style.width = "0%";
            return;
        }
        var elapsed = Math.max(0, (Date.now() - state.lastReadingSeenAt.getTime()) / 1000);
        var remaining = Math.max(0, interval - elapsed);
        var progress = Math.min(100, (elapsed / interval) * 100);
        el.captureCountdown.textContent = remaining <= 0.3 ? "Waiting for new OCR sample" : "Next OCR sample in " + Math.ceil(remaining) + "s";
        el.captureProgress.style.width = progress.toFixed(1) + "%";
    }

    function renderPipeline() {
        if (!el.pipelineSteps) {
            return;
        }
        var stage = toNumberOrNull(state.status && state.status.pipeline_stage_index);
        var cycle = toNumberOrNull(state.status && state.status.pipeline_cycle) || 0;
        var active = stage !== null && stage >= 1 && stage <= 5 ? stage : 0;
        Array.prototype.forEach.call(el.pipelineSteps.querySelectorAll("[data-stage-index]"), function (item) {
            var itemStage = Number(item.dataset.stageIndex);
            item.classList.toggle("is-active", itemStage === active);
            item.classList.toggle("is-complete", active > 0 ? itemStage < active : cycle > 0);
        });
    }

    function normalizeTimestamp(value) {
        if (value === null || value === undefined || value === "") {
            return null;
        }
        if (typeof value === "number") {
            return new Date(value < 100000000000 ? value * 1000 : value);
        }
        var parsed = new Date(value);
        return Number.isNaN(parsed.getTime()) ? null : parsed;
    }

    function pick(source, keys, fallback) {
        var target = source || {};
        for (var index = 0; index < keys.length; index += 1) {
            if (Object.prototype.hasOwnProperty.call(target, keys[index]) && target[keys[index]] !== undefined) {
                return target[keys[index]];
            }
        }
        return fallback === undefined ? null : fallback;
    }

    function toNumberOrNull(value) {
        var number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function render() {
        renderHeader();
        renderCurrent();
        renderDetails();
        renderPipeline();
        drawChart();
    }

    function renderHeader() {
        if (!el.firmwareVersion) {
            return;
        }
        var version = state.status && pick(state.status, ["firmware_version", "firmwareVersion"]);
        el.firmwareVersion.textContent = version ? "v" + String(version).replace(/^v/, "") : "v...";
    }

    function renderCurrent() {
        var reading = state.current;
        el.currentCo2.textContent = formatMetric(reading, "co2", "----");
        el.currentHcho.textContent = formatMetric(reading, "hcho", "-.---");
        el.currentTvoc.textContent = formatMetric(reading, "tvoc", "-.---");
        el.currentTemp.textContent = formatMetric(reading, "temperature", "--.-");
        el.currentHumidity.textContent = formatMetric(reading, "humidity", "--");
        if (reading && reading.confidence !== null) {
            el.currentConfidence.textContent = String(Math.round(normalizeConfidencePercent(reading.confidence)));
        } else {
            el.currentConfidence.textContent = "--";
        }

        var threshold = recognitionThresholdPercent();
        el.confidenceRule.textContent =
            "OCR accepted at " + threshold.toFixed(0) + "% confidence or higher; below that it is rejected.";

        var parts = [];
        if (reading && reading.timestamp) {
            parts.push("Measured " + formatSampleTimestamp(reading));
        }
        if (reading && reading.confidence !== null) {
            parts.push("confidence " + formatConfidence(reading.confidence));
        }
        if (reading && reading.co2 !== null) {
            parts.push("CO2 " + reading.co2.toFixed(0) + " ppm");
        }
        if (reading && reading.hcho !== null) {
            parts.push("HCHO " + reading.hcho.toFixed(3));
        }
        if (reading && reading.tvoc !== null) {
            parts.push("TVOC " + reading.tvoc.toFixed(3));
        }
        if (reading && reading.humidity !== null) {
            parts.push("humidity " + reading.humidity.toFixed(0) + "%");
        }
        if (reading && reading.recognitionDurationMs !== null) {
            parts.push("OCR " + reading.recognitionDurationMs.toFixed(0) + " ms");
        }
        if (reading && reading.error) {
            parts.push(reading.error);
        }
        if (state.lastError) {
            parts.push(state.lastError.message);
        }
        el.currentMeta.textContent = parts.join(" · ") || "Waiting for first reading";

        var status = reading ? reading.status : "unknown";
        el.statusBadge.textContent = humanize(status);
        el.statusBadge.className = "status-badge " + statusClass(status);
        renderCaptureCountdown();
    }

    function renderDetails() {
        var statusRows = flattenObject(state.status || {});
        if (state.lastUpdated) {
            statusRows.unshift(["Dashboard updated", formatDateTime(state.lastUpdated)]);
        }
        if (!statusRows.length) {
            statusRows = [["Device", state.lastError ? "Unavailable" : "No status yet"]];
        }
        renderDefinitionList(el.statusList, statusRows.slice(0, 12));

        var diagnostics = collectDiagnostics();
        renderDefinitionList(el.diagnosticsList, diagnostics);
    }

    function collectDiagnostics() {
        var valid = state.readings.filter(function (reading) {
            return hasAnyValue(reading);
        });
        var failed = state.readings.length - valid.length;
        var rows = [
            ["Samples loaded", String(state.readings.length)],
            ["Valid readings", String(valid.length)],
            ["Failed readings", String(failed)]
        ];
        SERIES.forEach(function (series) {
            var values = metricValues(series.key);
            if (values.length) {
                rows.push([series.label + " avg", formatSeriesValue(average(values), series)]);
                rows.push([series.label + " range", formatSeriesValue(Math.min.apply(null, values), series) + " to " + formatSeriesValue(Math.max.apply(null, values), series)]);
            }
        });
        var durations = state.readings.map(function (reading) {
            return reading.recognitionDurationMs;
        }).filter(function (value) {
            return value !== null;
        });
        if (durations.length) {
            rows.push(["Average OCR runtime", average(durations).toFixed(0) + " ms"]);
        }
        if (state.lastError) {
            rows.push(["API error", state.lastError.message]);
        }
        return rows;
    }

    function renderDefinitionList(target, rows) {
        target.textContent = "";
        rows.forEach(function (row) {
            var term = document.createElement("dt");
            var detail = document.createElement("dd");
            term.textContent = row[0];
            detail.textContent = row[1] === null || row[1] === undefined || row[1] === "" ? "N/A" : String(row[1]);
            target.appendChild(term);
            target.appendChild(detail);
        });
    }

    function flattenObject(source, prefix) {
        var rows = [];
        Object.keys(source || {}).forEach(function (key) {
            var value = source[key];
            var label = prefix ? prefix + " " + humanize(key) : humanize(key);
            if (value && typeof value === "object" && !Array.isArray(value)) {
                rows = rows.concat(flattenObject(value, label));
            } else if (!Array.isArray(value)) {
                rows.push([label, formatValue(value)]);
            }
        });
        return rows;
    }

    function drawChart() {
        if (!el.chartGrid) {
            return;
        }
        ensureMetricCanvases();
        var valid = state.readings.filter(function (reading) {
            return hasAnyValue(reading);
        });
        SERIES.forEach(function (series) {
            var canvas = document.getElementById("chart-" + series.key);
            if (canvas) {
                drawMetricChart(canvas, valid, series);
            }
        });
        if (!valid.length) {
            el.chartSummary.textContent = state.lastError ? "API unavailable" : "No valid samples";
            return;
        }
        el.chartSummary.textContent = valid.length + " valid · five independent scales";
    }

    function ensureMetricCanvases() {
        SERIES.forEach(function (series) {
            if (document.getElementById("chart-" + series.key)) {
                return;
            }
            var card = document.createElement("article");
            var canvas = document.createElement("canvas");
            card.className = "metric-chart";
            canvas.id = "chart-" + series.key;
            canvas.width = 520;
            canvas.height = 220;
            canvas.setAttribute("aria-label", series.label + " history chart");
            card.appendChild(canvas);
            el.chartGrid.appendChild(card);
        });
    }

    function drawMetricChart(canvas, readings, series) {
        var ctx = canvas.getContext("2d");
        var rect = canvas.getBoundingClientRect();
        var ratio = window.devicePixelRatio || 1;
        canvas.width = Math.max(280, Math.floor(rect.width * ratio));
        canvas.height = Math.max(180, Math.floor(rect.height * ratio));
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

        var width = rect.width;
        var height = rect.height;
        var styles = getComputedStyle(document.documentElement);
        var surface = styles.getPropertyValue("--surface-strong").trim();
        var text = styles.getPropertyValue("--text").trim();
        var muted = styles.getPropertyValue("--muted").trim();
        var line = styles.getPropertyValue("--line").trim();

        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = surface;
        ctx.fillRect(0, 0, width, height);

        var values = readings.map(function (reading) {
            return reading[series.key];
        }).filter(function (value) {
            return value !== null;
        });

        var padding = { top: 30, right: 18, bottom: 30, left: 58 };
        var plotW = Math.max(1, width - padding.left - padding.right);
        var plotH = Math.max(1, height - padding.top - padding.bottom);

        ctx.fillStyle = text;
        ctx.font = "800 13px system-ui, sans-serif";
        ctx.textAlign = "left";
        ctx.fillText(series.label, padding.left, 18);

        if (!values.length) {
            ctx.fillStyle = muted;
            ctx.font = "700 13px system-ui, sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("No samples", width / 2, height / 2);
            return;
        }

        var range = paddedRange(values);
        drawMetricGrid(ctx, series, range, padding, plotW, plotH, line, muted);
        drawMetricLine(ctx, readings, series, range, padding, plotW, plotH);
        drawMetricMarkers(ctx, readings, series, range, padding, plotW, plotH);

        ctx.fillStyle = muted;
        ctx.font = "11px system-ui, sans-serif";
        ctx.textAlign = "left";
        ctx.fillText(sampleLabel(readings[0]), padding.left, height - 9);
        ctx.textAlign = "right";
        ctx.fillText(sampleLabel(readings[readings.length - 1]), width - padding.right, height - 9);
    }

    function drawMetricGrid(ctx, series, range, padding, plotW, plotH, line, muted) {
        ctx.strokeStyle = line;
        ctx.lineWidth = 1;
        ctx.fillStyle = muted;
        ctx.font = "11px system-ui, sans-serif";
        ctx.textAlign = "right";
        for (var tick = 0; tick <= 3; tick += 1) {
            var ratio = tick / 3;
            var y = padding.top + (plotH * ratio);
            var value = range.max - ((range.max - range.min) * ratio);
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(padding.left + plotW, y);
            ctx.stroke();
            ctx.fillText(formatSeriesValue(value, series), padding.left - 8, y + 4);
        }
    }

    function drawMetricLine(ctx, readings, series, range, padding, plotW, plotH) {
        var started = false;
        ctx.strokeStyle = colorWithAlpha(series.color, 0.5);
        ctx.lineWidth = 2;
        ctx.beginPath();
        readings.forEach(function (reading, index) {
            var point = metricPoint(reading, index, readings.length, series, range, padding, plotW, plotH);
            if (!point) {
                started = false;
                return;
            }
            if (!started) {
                ctx.moveTo(point.x, point.y);
                started = true;
            } else {
                ctx.lineTo(point.x, point.y);
            }
        });
        ctx.stroke();
    }

    function drawMetricMarkers(ctx, readings, series, range, padding, plotW, plotH) {
        ctx.strokeStyle = series.color;
        ctx.lineWidth = 1.3;
        readings.forEach(function (reading, index) {
            var point = metricPoint(reading, index, readings.length, series, range, padding, plotW, plotH);
            if (!point) {
                return;
            }
            ctx.beginPath();
            ctx.moveTo(point.x - 3, point.y - 3);
            ctx.lineTo(point.x + 3, point.y + 3);
            ctx.moveTo(point.x + 3, point.y - 3);
            ctx.lineTo(point.x - 3, point.y + 3);
            ctx.stroke();
        });
    }

    function metricPoint(reading, index, total, series, range, padding, plotW, plotH) {
        var value = reading[series.key];
        if (value === null) {
            return null;
        }
        var x = padding.left + (total === 1 ? plotW : plotW * index / (total - 1));
        var y = padding.top + plotH - ((value - range.min) / (range.max - range.min)) * plotH;
        return { x: x, y: y };
    }

    function paddedRange(values) {
        var min = Math.min.apply(null, values);
        var max = Math.max.apply(null, values);
        var span = max - min;
        var pad = span <= 0 ? Math.max(1, Math.abs(max) * 0.08) : span * 0.12;
        return { min: min - pad, max: max + pad };
    }

    function statusClass(status) {
        var normalized = String(status || "").toLowerCase();
        if (normalized === "ok" || normalized === "ready" || normalized === "live") {
            return "status-ok";
        }
        if (normalized.indexOf("fail") >= 0 || normalized.indexOf("error") >= 0) {
            return "status-bad";
        }
        if (normalized.indexOf("warn") >= 0 || normalized.indexOf("stale") >= 0) {
            return "status-warn";
        }
        return "status-unknown";
    }

    function setApiState(text) {
        el.apiState.textContent = text;
        el.apiState.className = "api-state " + statusClass(text);
    }

    function humanize(value) {
        return String(value || "unknown").replace(/[_-]+/g, " ").replace(/\b\w/g, function (match) {
            return match.toUpperCase();
        });
    }

    function formatValue(value) {
        if (value === null || value === undefined) {
            return "N/A";
        }
        if (typeof value === "number") {
            return Number.isInteger(value) ? String(value) : value.toFixed(2);
        }
        if (typeof value === "boolean") {
            return value ? "Yes" : "No";
        }
        return String(value);
    }

    function formatDateTime(date) {
        return new Intl.DateTimeFormat(undefined, {
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit"
        }).format(date);
    }

    function formatSampleTimestamp(reading) {
        if (reading && typeof reading.timestampRaw === "number" && reading.timestampRaw < 1000000000) {
            return "t+" + Math.round(reading.timestampRaw) + "s";
        }
        return reading && reading.timestamp ? formatDateTime(reading.timestamp) : "unknown time";
    }

    function formatTime(date) {
        return new Intl.DateTimeFormat(undefined, {
            hour: "2-digit",
            minute: "2-digit"
        }).format(date);
    }

    function sampleLabel(reading) {
        if (!reading) {
            return "";
        }
        if (typeof reading.timestampRaw === "number" && reading.timestampRaw < 1000000000) {
            return "t+" + Math.round(reading.timestampRaw) + "s";
        }
        return reading.timestamp ? formatTime(reading.timestamp) : "";
    }

    function normalizeConfidencePercent(value) {
        return value <= 1 ? value * 100 : value;
    }

    function recognitionThresholdPercent() {
        var raw = state.status && pick(state.status, ["recognition_min_confidence_percent", "recognition_min_confidence"]);
        var value = toNumberOrNull(raw);
        if (value === null) {
            return 60;
        }
        return normalizeConfidencePercent(value);
    }

    function formatConfidence(value) {
        return Math.round(normalizeConfidencePercent(value)) + "%";
    }

    function formatMetric(reading, key, fallback) {
        if (!reading || reading[key] === null) {
            return fallback;
        }
        var series = SERIES.filter(function (item) {
            return item.key === key;
        })[0];
        return reading[key].toFixed(series ? series.decimals : 1);
    }

    function metricValues(key) {
        return state.readings.map(function (reading) {
            return reading[key];
        }).filter(function (value) {
            return value !== null;
        });
    }

    function formatSeriesValue(value, series) {
        var formatted = value.toFixed(series.decimals);
        return series.unit ? formatted + " " + series.unit : formatted;
    }

    function average(values) {
        return values.reduce(function (sum, value) {
            return sum + value;
        }, 0) / values.length;
    }

    function colorWithAlpha(hex, alpha) {
        var match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        if (!match) {
            return hex;
        }
        return "rgba(" + parseInt(match[1], 16) + "," + parseInt(match[2], 16) + "," + parseInt(match[3], 16) + "," + alpha + ")";
    }

    function debounce(fn, delay) {
        var timer = null;
        return function () {
            window.clearTimeout(timer);
            timer = window.setTimeout(fn, delay);
        };
    }
}());
