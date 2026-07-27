#include "reame/utils/version.hpp"

#ifndef REAME_VERSION
#error "REAME_VERSION must be provided by the build system"
#endif

namespace reame {

const char* version() {
    return REAME_VERSION;
}

}  // namespace reame
