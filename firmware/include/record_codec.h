#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

#include "reading_record.h"

namespace fever {

/** Fixed binary storage codec for one reading record. */
class RecordCodec {
   public:
    /** Serialized record size in bytes. */
    static constexpr std::size_t kEncodedSize = 22U;
    /** Serialized record schema version. */
    static constexpr uint8_t kSchemaVersion = 2U;

    /** Encode a reading record into a fixed-size little-endian byte array. */
    [[nodiscard]] static std::array<uint8_t, kEncodedSize> Encode(const ReadingRecord& record);
    /** Decode a fixed-size byte array into a reading record, validating checksum. */
    [[nodiscard]] static std::optional<ReadingRecord> Decode(const std::array<uint8_t, kEncodedSize>& encoded);

   private:
    [[nodiscard]] static uint16_t Checksum(const std::array<uint8_t, kEncodedSize>& encoded);
};

/** Persistent ring-buffer metadata kept separately from records. */
struct StorageMetadata {
    /** Metadata schema version. */
    uint16_t schema_version;
    /** Physical write index for the next appended record. */
    uint32_t write_index;
    /** Number of valid records currently stored. */
    uint32_t record_count;
    /** Maximum record capacity. */
    uint32_t capacity;
};

}  // namespace fever
