(function () {
    "use strict";

    var ENDPOINTS = {
        status: "/api/v1/status",
        current: "/api/v1/current",
        latest: "/api/v1/readings/latest?count=1440"
    };
    var STORAGE_KEY = "esp32-fever-dream-ui";
    var POLL_MS = 60000;
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
            currentCo2: document.getElementById("currentCo2"),
            currentHcho: document.getElementById("currentHcho"),
            currentTvoc: document.getElementById("currentTvoc"),
            currentTemp: document.getElementById("currentTemp"),
            currentHumidity: document.getElementById("currentHumidity"),
            currentConfidence: document.getElementById("currentConfidence"),
            confidenceRule: document.getElementById("confidenceRule"),
            currentMeta: document.getElementById("currentMeta"),
            statusBadge: document.getElementById("statusBadge"),
            chart: document.getElementById("historyChart"),
            chartSummary: document.getElementById("chartSummary"),
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
        window.setInterval(refreshAll, POLL_MS);
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
            state.status = responses[0];
            state.current = normalizeCurrent(responses[1]);
            state.readings = normalizeReadings(responses[2]);
            state.lastUpdated = new Date();
            state.lastError = null;
            render();
            setApiState("Live");
        }).catch(function (error) {
            state.lastError = error;
            render();
            setApiState("Offline");
        }).finally(function () {
            state.loading = false;
            el.refreshButton.disabled = false;
        });
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
        window.clearInterval(state.streamTimer);
        state.streamTimer = window.setInterval(loadStreamFrame, 5000);
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
        renderCurrent();
        renderDetails();
        drawChart();
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
            parts.push("Measured " + formatDateTime(reading.timestamp));
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
        if (!el.chart) {
            return;
        }
        var ctx = el.chart.getContext("2d");
        var rect = el.chart.getBoundingClientRect();
        var ratio = window.devicePixelRatio || 1;
        el.chart.width = Math.max(320, Math.floor(rect.width * ratio));
        el.chart.height = Math.max(220, Math.floor(rect.height * ratio));
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

        var width = rect.width;
        var height = rect.height;
        var styles = getComputedStyle(document.documentElement);
        var surface = styles.getPropertyValue("--surface-strong").trim();
        var text = styles.getPropertyValue("--text").trim();
        var muted = styles.getPropertyValue("--muted").trim();
        var line = styles.getPropertyValue("--line").trim();
        var accent = styles.getPropertyValue("--accent").trim();
        var bad = styles.getPropertyValue("--bad").trim();

        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = surface;
        ctx.fillRect(0, 0, width, height);

        var valid = state.readings.filter(function (reading) {
            return hasAnyValue(reading);
        });
        if (!valid.length) {
            ctx.fillStyle = muted;
            ctx.font = "700 15px system-ui, sans-serif";
            ctx.textAlign = "center";
            ctx.fillText(state.lastError ? "API unavailable" : "No history samples", width / 2, height / 2);
            el.chartSummary.textContent = "No valid samples";
            return;
        }

        var padding = { top: 28, right: 18, bottom: 34, left: 52 };
        var plotW = width - padding.left - padding.right;
        var plotH = height - padding.top - padding.bottom;

        ctx.strokeStyle = line;
        ctx.lineWidth = 1;
        ctx.fillStyle = muted;
        ctx.font = "12px system-ui, sans-serif";
        ctx.textAlign = "right";
        for (var tick = 0; tick <= 4; tick += 1) {
            var y = padding.top + (plotH * tick / 4);
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.stroke();
            ctx.fillText(String(100 - (tick * 25)) + "%", padding.left - 8, y + 4);
        }

        SERIES.forEach(function (series) {
            drawSeries(ctx, valid, series, padding, plotW, plotH);
        });

        ctx.fillStyle = bad;
        state.readings.forEach(function (reading, index) {
            if (!hasAnyValue(reading)) {
                var x = padding.left + (state.readings.length === 1 ? plotW : plotW * index / (state.readings.length - 1));
                ctx.fillRect(x - 1, padding.top, 2, plotH);
            }
        });

        drawLegend(ctx, padding.left, 14);

        ctx.fillStyle = text;
        ctx.textAlign = "left";
        var first = valid[0].timestamp ? formatTime(valid[0].timestamp) : "start";
        var last = valid[valid.length - 1].timestamp ? formatTime(valid[valid.length - 1].timestamp) : "latest";
        ctx.fillText(first, padding.left, height - 10);
        ctx.textAlign = "right";
        ctx.fillText(last, width - padding.right, height - 10);

        el.chartSummary.textContent = valid.length + " valid · normalized AQS trends";
    }

    function drawSeries(ctx, readings, series, padding, plotW, plotH) {
        var values = readings.map(function (reading) {
            return reading[series.key];
        }).filter(function (value) {
            return value !== null;
        });
        if (!values.length) {
            return;
        }
        var min = Math.min.apply(null, values);
        var max = Math.max.apply(null, values);
        var span = Math.max(1, max - min);
        var started = false;
        ctx.strokeStyle = series.color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        readings.forEach(function (reading, index) {
            var value = reading[series.key];
            if (value === null) {
                started = false;
                return;
            }
            var x = padding.left + (readings.length === 1 ? plotW : plotW * index / (readings.length - 1));
            var y = padding.top + plotH - ((value - min) / span) * plotH;
            if (!started) {
                ctx.moveTo(x, y);
                started = true;
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();
    }

    function drawLegend(ctx, x, y) {
        ctx.textAlign = "left";
        ctx.font = "700 12px system-ui, sans-serif";
        var offset = 0;
        SERIES.forEach(function (series) {
            ctx.fillStyle = series.color;
            ctx.fillRect(x + offset, y - 8, 10, 10);
            ctx.fillText(series.label, x + offset + 14, y);
            offset += 78;
        });
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

    function formatTime(date) {
        return new Intl.DateTimeFormat(undefined, {
            hour: "2-digit",
            minute: "2-digit"
        }).format(date);
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

    function debounce(fn, delay) {
        var timer = null;
        return function () {
            window.clearTimeout(timer);
            timer = window.setTimeout(fn, delay);
        };
    }
}());
