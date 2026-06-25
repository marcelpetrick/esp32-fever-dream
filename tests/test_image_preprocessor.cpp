#include <array>

#include "image_preprocessor.h"
#include "test_support.h"

void TestImagePreprocessor() {
    const std::array<uint8_t, 9> pixels = {1U, 2U, 3U, 4U, 5U, 6U, 7U, 8U, 9U};
    const fever::ImageView image{pixels.data(), 3U, 3U, 3U};
    const fever::Roi roi{1U, 1U, 2U, 2U};

    REQUIRE(fever::IsValidRoi(image, roi));
    const auto crop = fever::CropGrayscale(image, roi);
    REQUIRE(crop.size() == 4U);
    REQUIRE(crop[0] == 5U);
    REQUIRE(crop[1] == 6U);
    REQUIRE(crop[2] == 8U);
    REQUIRE(crop[3] == 9U);

    const auto thresholded = fever::Threshold(crop, 7U);
    REQUIRE(thresholded[0] == 0U);
    REQUIRE(thresholded[1] == 0U);
    REQUIRE(thresholded[2] == 255U);
    REQUIRE(thresholded[3] == 255U);
}
