#pragma once

#include <cstdlib>
#include <iostream>

#define REQUIRE(condition)                                                                               \
    do {                                                                                                 \
        if (!(condition)) {                                                                              \
            std::cerr << "REQUIRE failed at " << __FILE__ << ':' << __LINE__ << ": " #condition << '\n'; \
            std::exit(1);                                                                                \
        }                                                                                                \
    } while (false)
