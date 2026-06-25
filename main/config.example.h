#pragma once

// This fallback is used only when ignored config.local.h has not been generated.
// Preferred local flow:
//
// 1. Put credentials in ignored wifi.env.
// 2. Run scripts/build_firmware.sh or scripts/flash_device.sh.
// 3. scripts/generate_wifi_config.sh writes ignored config.local.h.

#define FEVER_WIFI_SSID "your-local-ssid"
#define FEVER_WIFI_PASSWORD "your-local-password"
#define FEVER_DEVICE_HOSTNAME "esp32-fever-dream"
