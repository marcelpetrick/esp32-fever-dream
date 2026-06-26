#include "api_router.h"
#include "test_support.h"

void TestApiRouter() {
    fever::StorageRingBuffer storage(3);
    fever::Diagnostics diagnostics;
    diagnostics.RecordBoot();
    REQUIRE(storage.Append(fever::ReadingRecord::Success(10U, {728U, 57U, 159U, 2100, 44U}, fever::ConfidencePercent{95U},
                                                         fever::ReadingFlags::kRecognitionRuleBased)));
    REQUIRE(storage.Append(fever::ReadingRecord::Failure(20U, fever::ReadingStatus::kRecognitionFailed,
                                                         fever::ConfidencePercent{22U},
                                                         fever::ReadingFlags::kRecognitionRuleBased)));

    const fever::ApiRouter router(storage, diagnostics);

    const fever::ApiResponse status = router.Handle({fever::ApiMethod::kGet, "/api/v1/status"});
    REQUIRE(status.status_code == 200);
    REQUIRE(status.body.find("\"boot_count\":1") != std::string::npos);
    REQUIRE(status.body.find("\"storage_record_size_bytes\":") != std::string::npos);

    const fever::ApiResponse current = router.Handle({fever::ApiMethod::kGet, "/api/v1/current"});
    REQUIRE(current.status_code == 200);
    REQUIRE(current.body.find("\"status\":\"recognition_failed\"") != std::string::npos);

    const fever::ApiResponse latest = router.Handle({fever::ApiMethod::kGet, "/api/v1/readings/latest?count=1"});
    REQUIRE(latest.status_code == 200);
    REQUIRE(latest.body.find("\"timestamp\":20") != std::string::npos);
    REQUIRE(latest.body.find("\"timestamp\":10") == std::string::npos);

    const fever::ApiResponse ignored_similar_name =
        router.Handle({fever::ApiMethod::kGet, "/api/v1/readings/latest?xcount=1"});
    REQUIRE(ignored_similar_name.status_code == 200);
    REQUIRE(ignored_similar_name.body.find("\"timestamp\":20") != std::string::npos);
    REQUIRE(ignored_similar_name.body.find("\"timestamp\":10") != std::string::npos);

    const fever::ApiResponse bad_limit = router.Handle({fever::ApiMethod::kGet, "/api/v1/readings/latest?count=0"});
    REQUIRE(bad_limit.status_code == 400);

    const fever::ApiResponse missing = router.Handle({fever::ApiMethod::kGet, "/api/v1/nope"});
    REQUIRE(missing.status_code == 404);
}
