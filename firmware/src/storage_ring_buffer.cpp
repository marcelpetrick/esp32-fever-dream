#include "storage_ring_buffer.h"

#include <algorithm>

namespace fever {

StorageRingBuffer::StorageRingBuffer(std::size_t capacity) : records_(capacity) {}

std::size_t StorageRingBuffer::Capacity() const { return records_.size(); }

std::size_t StorageRingBuffer::Count() const { return count_; }

std::size_t StorageRingBuffer::CapacityBytes() const { return records_.size() * RecordSizeBytes(); }

std::size_t StorageRingBuffer::UsedBytes() const { return count_ * RecordSizeBytes(); }

bool StorageRingBuffer::Empty() const { return count_ == 0U; }

bool StorageRingBuffer::Full() const { return count_ == records_.size() && !records_.empty(); }

bool StorageRingBuffer::Append(const ReadingRecord& record) {
    if (records_.empty()) {
        return false;
    }

    records_[write_index_] = record;
    write_index_ = (write_index_ + 1U) % records_.size();
    count_ = std::min(count_ + 1U, records_.size());
    return true;
}

std::optional<ReadingRecord> StorageRingBuffer::Latest() const {
    if (Empty()) {
        return std::nullopt;
    }
    const std::size_t index = (write_index_ + records_.size() - 1U) % records_.size();
    return records_[index];
}

std::vector<ReadingRecord> StorageRingBuffer::ReadChronological(std::size_t limit) const {
    const std::size_t records_to_read = std::min(limit, count_);
    std::vector<ReadingRecord> result;
    result.reserve(records_to_read);

    const std::size_t skipped = count_ - records_to_read;
    for (std::size_t i = skipped; i < count_; ++i) {
        result.push_back(records_[PhysicalIndex(i)]);
    }
    return result;
}

void StorageRingBuffer::Clear() {
    write_index_ = 0U;
    count_ = 0U;
}

std::size_t StorageRingBuffer::PhysicalIndex(std::size_t chronological_index) const {
    const std::size_t start = Full() ? write_index_ : 0U;
    return (start + chronological_index) % records_.size();
}

}  // namespace fever
