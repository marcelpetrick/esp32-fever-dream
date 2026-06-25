#include "test_support.h"
#include "time_manager.h"

void TestTimeManager() {
    fever::TimeManager time;
    REQUIRE(!time.Now().synced);
    REQUIRE(time.Now().timestamp_s == 0U);

    time.SetSynchronizedTime(100U);
    REQUIRE(time.Now().synced);
    REQUIRE(time.Now().timestamp_s == 100U);

    time.AdvanceEstimated(60U);
    REQUIRE(!time.Now().synced);
    REQUIRE(time.Now().timestamp_s == 160U);
}
