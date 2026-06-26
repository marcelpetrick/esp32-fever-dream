#include "recognition.h"
#include "test_support.h"

void TestRecognition() {
    const fever::DigitSegments eight{true, true, true, true, true, true, true};
    const auto decoded = fever::DecodeSevenSegmentDigit(eight);
    REQUIRE(decoded.has_value());
    REQUIRE(*decoded == 8U);

    const auto parsed = fever::ParseDisplayText("21.7", fever::ConfidencePercent{95U});
    REQUIRE(parsed.ok);
    REQUIRE(parsed.values.temperature_centi_c == 2170);

    const auto negative = fever::ParseDisplayText("-1.25", fever::ConfidencePercent{99U});
    REQUIRE(negative.ok);
    REQUIRE(negative.values.temperature_centi_c == -125);

    const auto low_confidence = fever::ParseDisplayText("21.7", fever::ConfidencePercent{10U});
    REQUIRE(!low_confidence.ok);
    REQUIRE(low_confidence.status == fever::ReadingStatus::kConfidenceTooLow);

    const auto out_of_range = fever::ParseDisplayText("99.9", fever::ConfidencePercent{99U});
    REQUIRE(!out_of_range.ok);
    REQUIRE(out_of_range.status == fever::ReadingStatus::kValueOutOfRange);
}
