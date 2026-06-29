#pragma once

#include <cstddef>

#include "storage_ring_buffer.h"

namespace fever {

/**
 * NVS-backed persistence for the ring-buffer tail.
 *
 * Save() encodes the last kPersistenceRecords records as a binary blob in the
 * "fever" NVS namespace and commits.  Restore() reads that blob back into the
 * supplied ring buffer on boot.
 *
 * Flash write frequency is kept intentionally low (every kPersistenceIntervalCycles
 * measurements) to stay well within flash endurance limits.
 */
namespace FlashPersistence {

/** Write the most recent records from storage into NVS. */
void Save(const StorageRingBuffer& storage);

/** Populate storage from the NVS blob written by Save().
 *  Returns the number of records restored. */
std::size_t Restore(StorageRingBuffer& storage);

}  // namespace FlashPersistence

}  // namespace fever
