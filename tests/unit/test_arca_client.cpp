// Integration tests for the ARCA RESP client: it talks to a real
// ArcaServer over a loopback socket, and — critically — degrades to a
// silent no-op when the archive is unreachable, so a down ARCA never
// breaks the engine that depends on it.

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <unistd.h>

#include "reame/arca/client.hpp"
#include "reame/arca/server.hpp"

using reame::arca::ArcaClient;
using reame::arca::ArcaServer;

namespace {

struct TempDir {
    std::filesystem::path path;
    TempDir() {
        path = std::filesystem::temp_directory_path() /
               ("arca-cli-" + std::to_string(::getpid()) + "-" +
                std::to_string(counter++));
        std::filesystem::create_directories(path);
    }
    ~TempDir() { std::filesystem::remove_all(path); }
    static inline int counter = 0;
};

}  // namespace

TEST_CASE("[integration] arca client: set then get round-trips via the daemon") {
    TempDir dir;
    ArcaServer::Config sc;
    sc.port = 0;
    sc.directory = dir.path;
    ArcaServer server(sc);
    server.start();

    ArcaClient client({"127.0.0.1", server.port()});
    client.set("k", "hello");
    const auto got = client.get("k");
    REQUIRE(got.has_value());
    CHECK(*got == "hello");

    // A miss is nullopt, not an error.
    CHECK_FALSE(client.get("ghost").has_value());

    server.stop();
}

TEST_CASE("[integration] arca client: binary-safe values") {
    TempDir dir;
    ArcaServer::Config sc;
    sc.port = 0;
    sc.directory = dir.path;
    ArcaServer server(sc);
    server.start();

    ArcaClient client({"127.0.0.1", server.port()});
    const std::string v = "line1\r\nline2\0tail";
    const std::string val(v.data(), 17);
    client.set("bin", val);
    const auto got = client.get("bin");
    REQUIRE(got.has_value());
    CHECK(*got == val);

    server.stop();
}

TEST_CASE("[integration] arca client: an unreachable archive degrades quietly") {
    // Nothing is listening here. get() must return nullopt and set() must
    // not throw — the engine keeps working without the cache.
    ArcaClient client({"127.0.0.1", 1});  // port 1: connection refused
    CHECK_FALSE(client.get("anything").has_value());
    CHECK_NOTHROW(client.set("k", "v"));
    // Still nullopt on the next call — no half-open state left behind.
    CHECK_FALSE(client.get("k").has_value());
}
