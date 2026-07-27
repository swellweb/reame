#pragma once

namespace reame {

// The single source of truth is CMake's project(VERSION ...), passed in as
// REAME_VERSION. Never write the number here.
const char* version();

}  // namespace reame
