#include "measurement_scheduler.h"
#include "test_support.h"

void TestMeasurementScheduler() {
    fever::MeasurementScheduler scheduler({60U, 100U});
    REQUIRE(!scheduler.Due(99U));
    REQUIRE(scheduler.SecondsUntilDue(90U) == 10U);
    REQUIRE(scheduler.Due(100U));

    scheduler.MarkCompleted(100U);
    REQUIRE(scheduler.NextDueTime() == 160U);
    REQUIRE(!scheduler.Due(159U));
    REQUIRE(scheduler.Due(160U));

    scheduler.MarkCompleted(245U);
    REQUIRE(scheduler.NextDueTime() == 280U);

    fever::MeasurementScheduler zero_interval({0U, 5U});
    REQUIRE(zero_interval.Due(5U));
    zero_interval.MarkCompleted(5U);
    REQUIRE(zero_interval.NextDueTime() == 6U);
}
