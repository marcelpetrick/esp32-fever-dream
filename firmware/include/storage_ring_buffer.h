#pragma once

#include <cstddef>
#include <optional>
#include <vector>

#include "reading_record.h"

namespace fever {

/** Bounded chronological ring buffer for reading records. */
class StorageRingBuffer {
   public:
    /** Create a ring buffer with fixed record capacity. */
    explicit StorageRingBuffer(std::size_t capacity);

    /** Return maximum number of stored records. */
    [[nodiscard]] std::size_t Capacity() const;
    /** Return current number of stored records. */
    [[nodiscard]] std::size_t Count() const;
    /** Return true when no records are stored. */
    [[nodiscard]] bool Empty() const;
    /** Return true when the next append overwrites the oldest record. */
    [[nodiscard]] bool Full() const;

    /** Append one record, overwriting the oldest record when full. */
    bool Append(const ReadingRecord& record);
    /** Return the newest record, if one exists. */
    [[nodiscard]] std::optional<ReadingRecord> Latest() const;
    /** Return up to `limit` records in chronological order. */
    [[nodiscard]] std::vector<ReadingRecord> ReadChronological(std::size_t limit) const;
    /** Remove all records while keeping the configured capacity. */
    void Clear();

   private:
    [[nodiscard]] std::size_t PhysicalIndex(std::size_t chronological_index) const;

    std::vector<ReadingRecord> records_;
    std::size_t write_index_ = 0U;
    std::size_t count_ = 0U;
};

}  // namespace fever
