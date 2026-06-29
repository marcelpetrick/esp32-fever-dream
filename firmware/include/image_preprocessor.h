#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace fever {

/** Borrowed grayscale image buffer. */
struct ImageView {
    /** Pointer to the first pixel. */
    const uint8_t* pixels;
    /** Image width in pixels. */
    std::size_t width;
    /** Image height in pixels. */
    std::size_t height;
    /** Bytes between the start of adjacent rows. */
    std::size_t stride;
};

/** Rectangular region of interest in image coordinates. */
struct Roi {
    /** Left coordinate in pixels. */
    std::size_t x;
    /** Top coordinate in pixels. */
    std::size_t y;
    /** Region width in pixels. */
    std::size_t width;
    /** Region height in pixels. */
    std::size_t height;
};

/** Return true when the ROI fits inside the image and the image buffer is usable. */
[[nodiscard]] bool IsValidRoi(const ImageView& image, const Roi& roi);
/** Copy a grayscale ROI into a compact row-major vector. */
[[nodiscard]] std::vector<uint8_t> CropGrayscale(const ImageView& image, const Roi& roi);
/** Convert grayscale pixels to 0 or 255 using the given threshold. */
[[nodiscard]] std::vector<uint8_t> Threshold(const std::vector<uint8_t>& grayscale, uint8_t threshold);
/** Min/max normalize and floor-sample a compact grayscale image, matching TinyML input. */
[[nodiscard]] bool NormalizeResizeNearest(const uint8_t* source, std::size_t source_width,
                                          std::size_t source_height, uint8_t* destination,
                                          std::size_t destination_width, std::size_t destination_height);

}  // namespace fever
