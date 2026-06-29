#include "flash_persistence.h"

#include <array>
#include <vector>

#include "app_config.h"
#include "record_codec.h"

#ifdef ESP_PLATFORM
#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"
#endif

namespace fever {
namespace FlashPersistence {

namespace {
#ifdef ESP_PLATFORM
constexpr const char* kTag = "flash_persist";
#endif
constexpr const char* kNvsNamespace = "fever";
constexpr const char* kNvsKey = "ring_tail";
}  // namespace

void Save(const StorageRingBuffer& storage) {
#ifdef ESP_PLATFORM
    const auto records = storage.ReadChronological(config::kPersistenceRecords);
    if (records.empty()) {
        return;
    }

    const std::size_t blob_size = records.size() * RecordCodec::kEncodedSize;
    std::vector<uint8_t> blob;
    blob.reserve(blob_size);
    for (const auto& record : records) {
        const auto encoded = RecordCodec::Encode(record);
        blob.insert(blob.end(), encoded.begin(), encoded.end());
    }

    nvs_handle_t handle;
    esp_err_t err = nvs_open(kNvsNamespace, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGW(kTag, "nvs_open failed: %s", esp_err_to_name(err));
        return;
    }

    err = nvs_set_blob(handle, kNvsKey, blob.data(), blob.size());
    if (err == ESP_OK) {
        err = nvs_commit(handle);
    }
    if (err != ESP_OK) {
        ESP_LOGW(kTag, "save failed: %s", esp_err_to_name(err));
    } else {
        ESP_LOGI(kTag, "saved %zu records (%zu B) to NVS", records.size(), blob.size());
    }
    nvs_close(handle);
#endif
}

std::size_t Restore(StorageRingBuffer& storage) {
#ifdef ESP_PLATFORM
    nvs_handle_t handle;
    esp_err_t err = nvs_open(kNvsNamespace, NVS_READONLY, &handle);
    if (err != ESP_OK) {
        ESP_LOGI(kTag, "no persisted data (%s)", esp_err_to_name(err));
        return 0;
    }

    size_t blob_size = 0;
    err = nvs_get_blob(handle, kNvsKey, nullptr, &blob_size);
    if (err != ESP_OK || blob_size == 0 || blob_size % RecordCodec::kEncodedSize != 0) {
        nvs_close(handle);
        return 0;
    }

    std::vector<uint8_t> blob(blob_size);
    err = nvs_get_blob(handle, kNvsKey, blob.data(), &blob_size);
    nvs_close(handle);

    if (err != ESP_OK) {
        ESP_LOGW(kTag, "restore read failed: %s", esp_err_to_name(err));
        return 0;
    }

    const std::size_t record_count = blob_size / RecordCodec::kEncodedSize;
    std::size_t restored = 0;
    for (std::size_t i = 0; i < record_count; ++i) {
        std::array<uint8_t, RecordCodec::kEncodedSize> encoded{};
        const std::size_t offset = i * RecordCodec::kEncodedSize;
        std::copy(blob.begin() + static_cast<std::ptrdiff_t>(offset),
                  blob.begin() + static_cast<std::ptrdiff_t>(offset + RecordCodec::kEncodedSize),
                  encoded.begin());
        const auto record = RecordCodec::Decode(encoded);
        if (record && storage.Append(*record)) {
            ++restored;
        }
    }

    ESP_LOGI(kTag, "restored %zu records from NVS", restored);
    return restored;
#else
    (void)storage;
    return 0;
#endif
}

}  // namespace FlashPersistence
}  // namespace fever
