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

bool NormalizeResizeNearest(const uint8_t* source, std::size_t source_width, std::size_t source_height,
                            uint8_t* destination, std::size_t destination_width, std::size_t destination_height) {
    if (source == nullptr || destination == nullptr || source_width == 0U || source_height == 0U ||
        destination_width == 0U || destination_height == 0U) {
        return false;
    }
    const std::size_t source_size = source_width * source_height;
    const auto [minimum_it, maximum_it] = std::minmax_element(source, source + source_size);
    const int minimum = static_cast<int>(*minimum_it);
    const int range = std::max(1, static_cast<int>(*maximum_it) - minimum);
    for (std::size_t y = 0; y < destination_height; ++y) {
        const std::size_t source_y = (y * source_height) / destination_height;
        for (std::size_t x = 0; x < destination_width; ++x) {
            const std::size_t source_x = (x * source_width) / destination_width;
            const int value = static_cast<int>(source[(source_y * source_width) + source_x]);
            destination[(y * destination_width) + x] =
                static_cast<uint8_t>(((value - minimum) * 255) / range);
        }
    }
    return true;
}

}  // namespace fever
