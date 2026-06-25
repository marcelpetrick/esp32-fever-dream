#pragma once

#include <cstdint>

namespace fever {

/** Configuration for a fixed-interval measurement scheduler. */
struct MeasurementScheduleConfig {
    /** Desired measurement interval in seconds. */
    uint32_t interval_s;
    /** Initial monotonic timestamp for the first due measurement. */
    uint32_t start_time_s;
};

/** Drift-corrected fixed-interval scheduler state. */
class MeasurementScheduler {
   public:
    /** Create a scheduler with an interval and starting monotonic time. */
    explicit MeasurementScheduler(MeasurementScheduleConfig config);

    /** Return true when a measurement is due at `now_s`. */
    [[nodiscard]] bool Due(uint32_t now_s) const;
    /** Mark a measurement attempt complete and advance to the next scheduled slot. */
    void MarkCompleted(uint32_t now_s);
    /** Return seconds until the next scheduled measurement. */
    [[nodiscard]] uint32_t SecondsUntilDue(uint32_t now_s) const;
    /** Return the next scheduled monotonic timestamp. */
    [[nodiscard]] uint32_t NextDueTime() const;

   private:
    uint32_t interval_s_;
    uint32_t next_due_s_;
};

}  // namespace fever
