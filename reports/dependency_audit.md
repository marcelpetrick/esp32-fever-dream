# Dependency Audit

## Dependencies

| Name | Current | Latest | Status | Source | Note |
|---|---:|---:|---|---|---|
| espressif/esp32-camera | 2.1.7 | 2.1.7 | current | ESP Component Registry |  |
| espressif/esp-tflite-micro | 1.3.7 | 1.3.7 | current | ESP Component Registry |  |
| espressif/esp-nn | 1.2.4 | 1.2.4 | current | ESP Component Registry |  |
| espressif/esp_jpeg | 1.3.1 | 1.3.1 | current | ESP Component Registry |  |
| idf | 6.0.2 | 6.0.2 | current | GitHub Releases | highest stable esp-idf release; toolchain pin lives in scripts/idf_env.sh |
| tensorflow | 2.21.0 | 2.21.0 | current | PyPI | setup constraint: tensorflow==2.21.0 |
| numpy | 2.5.1 | 2.5.1 | current | PyPI | setup constraint: numpy==2.5.1 |
| pillow | 12.3.0 | 12.3.0 | current | PyPI | setup constraint: pillow==12.3.0 |
| ollama | 0.31.2 | 0.32.3 | stale | GitHub Releases | host tool, hand-installed in /usr/local/bin; upgrading it changes vision-model labeling output |

## Ollama

- Available: `True`
- Version: `ollama version is 0.31.2`

| Model | ID | Size |
|---|---|---:|
| qwen3.5:4b | 2a654d98e6fb | 3.4 |
| qwen3.5:4b-ctx54k | 32eb33b786c2 | 3.4 |
| llama3.2-vision:11b | 6f2f9757ae97 | 7.8 |
| minicpm-v:latest | c92bfad01205 | 5.5 |
| moondream:latest | 55fc3abd3867 | 1.7 |
| qwen3-vl:4b | 1343d82ebee3 | 3.3 |
| qwen3.5:4b-ctx32k | 0c8faadc50c2 | 3.4 |
