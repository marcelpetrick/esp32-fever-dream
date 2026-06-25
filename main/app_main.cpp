#include "app_config.h"
#include "camera_manager.h"
#include "debug_capture_server.h"
#include "diagnostics.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_netif_ip_addr.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "nvs_flash.h"
#include "storage_ring_buffer.h"
#include "version.h"

#if __has_include("config.local.h")
#include "config.local.h"
#else
#include "config.example.h"
#endif

namespace {
constexpr const char* kTag = "fever_dream";
constexpr int kWifiConnectedBit = BIT0;
EventGroupHandle_t g_wifi_events = nullptr;

const char* WifiDisconnectReasonName(uint8_t reason) {
    switch (reason) {
        case WIFI_REASON_AUTH_EXPIRE:
            return "auth_expire";
        case WIFI_REASON_AUTH_FAIL:
            return "auth_fail";
        case WIFI_REASON_NO_AP_FOUND:
            return "no_ap_found";
        case WIFI_REASON_ASSOC_FAIL:
            return "assoc_fail";
        case WIFI_REASON_HANDSHAKE_TIMEOUT:
            return "handshake_timeout";
        case WIFI_REASON_BEACON_TIMEOUT:
            return "beacon_timeout";
        default:
            return "other";
    }
}

void WifiEventHandler(void*, esp_event_base_t event_base, int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
        return;
    }
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        const auto* event = static_cast<wifi_event_sta_disconnected_t*>(event_data);
        xEventGroupClearBits(g_wifi_events, kWifiConnectedBit);
        esp_wifi_connect();
        ESP_LOGW(kTag, "wifi disconnected, reconnecting: reason=%u (%s)", event->reason,
                 WifiDisconnectReasonName(event->reason));
        return;
    }
    if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        const auto* event = static_cast<ip_event_got_ip_t*>(event_data);
        xEventGroupSetBits(g_wifi_events, kWifiConnectedBit);
        ESP_LOGI(kTag, "wifi connected, ip=" IPSTR, IP2STR(&event->ip_info.ip));
        ESP_LOGI(kTag, "debug capture endpoint: http://" IPSTR "/debug/capture.jpg", IP2STR(&event->ip_info.ip));
    }
}

bool InitializeWifi() {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    if (err != ESP_OK) {
        ESP_LOGE(kTag, "nvs init failed: 0x%x", static_cast<unsigned int>(err));
        return false;
    }

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_t* netif = esp_netif_create_default_wifi_sta();
    ESP_ERROR_CHECK(esp_netif_set_hostname(netif, FEVER_DEVICE_HOSTNAME));
    g_wifi_events = xEventGroupCreate();

    wifi_init_config_t init_config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_config));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &WifiEventHandler, nullptr));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &WifiEventHandler, nullptr));

    wifi_config_t wifi_config = {};
    snprintf(reinterpret_cast<char*>(wifi_config.sta.ssid), sizeof(wifi_config.sta.ssid), "%s", FEVER_WIFI_SSID);
    snprintf(reinterpret_cast<char*>(wifi_config.sta.password), sizeof(wifi_config.sta.password), "%s",
             FEVER_WIFI_PASSWORD);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    return true;
}
}  // namespace

extern "C" void app_main(void) {
    fever::Diagnostics diagnostics;
    diagnostics.RecordBoot();

    ESP_LOGI(kTag, "ESP32 Fever Dream firmware %s", fever::version::ProjectVersion());
    ESP_LOGI(kTag, "measurement interval: %u seconds", fever::config::kMeasurementIntervalSeconds);
    ESP_LOGI(kTag, "target board: AI-Thinker ESP32-CAM / OV2640");

    fever::CameraManager camera;
    const bool camera_ready = camera.Initialize();
    ESP_LOGI(kTag, "camera ready: %s", camera_ready ? "yes" : camera.LastError().c_str());

    const bool wifi_ready = InitializeWifi();
    ESP_LOGI(kTag, "wifi startup: %s", wifi_ready ? "started" : "failed");
    if (camera_ready && wifi_ready) {
        const bool debug_server_ready = fever::StartDebugCaptureServer(camera);
        ESP_LOGI(kTag, "debug capture server: %s", debug_server_ready ? "started" : "failed");
        ESP_LOGI(kTag, "dataset endpoint: http://<device-ip>/debug/capture.jpg");
    }

    fever::StorageRingBuffer readings(16);
    const fever::ReadingRecord boot_record = fever::ReadingRecord::Failure(
        0U, fever::ReadingStatus::kTimeUnknown, fever::ConfidencePercent{0U}, fever::ReadingFlags::kTimeEstimated);
    const bool stored = readings.Append(boot_record);
    ESP_LOGI(kTag, "boot diagnostic record stored: %s", stored ? "yes" : "no");
}
