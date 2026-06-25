#include "image_preprocessor.h"

#include <algorithm>

namespace fever {

bool IsValidRoi(const ImageView& image, const Roi& roi) {
    if (image.pixels == nullptr || image.width == 0U || image.height == 0U || image.stride < image.width) {
        return false;
    }
    if (roi.width == 0U || roi.height == 0U) {
        return false;
    }
    return roi.x <= image.width && roi.y <= image.height && roi.width <= image.width - roi.x &&
           roi.height <= image.height - roi.y;
}

std::vector<uint8_t> CropGrayscale(const ImageView& image, const Roi& roi) {
    if (!IsValidRoi(image, roi)) {
        return {};
    }

    std::vector<uint8_t> crop;
    crop.reserve(roi.width * roi.height);
    for (std::size_t y = 0; y < roi.height; ++y) {
        const uint8_t* row = image.pixels + ((roi.y + y) * image.stride) + roi.x;
        for (std::size_t x = 0; x < roi.width; ++x) {
            crop.push_back(row[x]);
        }
    }
    return crop;
}

std::vector<uint8_t> Threshold(const std::vector<uint8_t>& grayscale, uint8_t threshold) {
    std::vector<uint8_t> binary(grayscale.size());
    std::transform(grayscale.begin(), grayscale.end(), binary.begin(),
                   [threshold](uint8_t pixel) { return pixel >= threshold ? 255U : 0U; });
    return binary;
}

}  // namespace fever
