#include "version.h"

#ifndef FEVER_DREAM_VERSION
#define FEVER_DREAM_VERSION "0.0.0-dev"
#endif

namespace fever::version {

const char* ProjectVersion() { return FEVER_DREAM_VERSION; }

}  // namespace fever::version
