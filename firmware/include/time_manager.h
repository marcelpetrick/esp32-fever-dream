#pragma once

#include <cstdint>

namespace fever {

/** Current timestamp plus whether that timestamp is externally synchronized. */
struct TimestampState {
    /** Unix timestamp in seconds. */
    uint32_t timestamp_s;
    /** True when set from a synchronized source such as NTP. */
    bool synced;
};

/** Minimal timestamp state manager with synchronized and estimated modes. */
class TimeManager {
   public:
    /** Set the current time from a synchronized source. */
    void SetSynchronizedTime(uint32_t timestamp_s);
    /** Advance time using elapsed seconds and mark it as estimated. */
    void AdvanceEstimated(uint32_t elapsed_s);
    /** Return the current timestamp state. */
    [[nodiscard]] TimestampState Now() const;

   private:
    TimestampState state_{0U, false};
};

}  // namespace fever
