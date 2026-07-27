#include <catch2/catch_test_macros.hpp>

#include <regex>
#include <string>

#include "reame/utils/version.hpp"

// v0.1.6 shipped with the version written by hand in main.cpp while
// CMakeLists said something else, so the released binary announced the
// previous release and anyone checking whether they had the fix concluded
// they didn't. REAME_VERSION comes from the build system: if the string ever
// goes back to being typed into a source file, the next bump breaks this.
TEST_CASE("the reported version comes from the build system", "[version]") {
    REQUIRE(std::string(reame::version()) == std::string(REAME_VERSION));
}

TEST_CASE("the reported version is semver", "[version]") {
    REQUIRE(std::regex_match(reame::version(), std::regex(R"(\d+\.\d+\.\d+)")));
}

TEST_CASE("the reported version is not empty", "[version]") {
    REQUIRE(reame::version() != nullptr);
    REQUIRE(std::string(reame::version()).length() >= 5);
}
