#include "time_manager.h"

namespace fever {

void TimeManager::SetSynchronizedTime(uint32_t timestamp_s) { state_ = TimestampState{timestamp_s, true}; }

void TimeManager::AdvanceEstimated(uint32_t elapsed_s) {
    state_.timestamp_s += elapsed_s;
    state_.synced = false;
}

TimestampState TimeManager::Now() const { return state_; }

}  // namespace fever
