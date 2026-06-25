#include "measurement_scheduler.h"

namespace fever {

MeasurementScheduler::MeasurementScheduler(MeasurementScheduleConfig config)
    : interval_s_(config.interval_s == 0U ? 1U : config.interval_s), next_due_s_(config.start_time_s) {}

bool MeasurementScheduler::Due(uint32_t now_s) const { return now_s >= next_due_s_; }

void MeasurementScheduler::MarkCompleted(uint32_t now_s) {
    do {
        next_due_s_ += interval_s_;
    } while (next_due_s_ <= now_s);
}

uint32_t MeasurementScheduler::SecondsUntilDue(uint32_t now_s) const {
    if (Due(now_s)) {
        return 0U;
    }
    return next_due_s_ - now_s;
}

uint32_t MeasurementScheduler::NextDueTime() const { return next_due_s_; }

}  // namespace fever
