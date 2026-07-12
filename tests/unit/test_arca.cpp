// Isolated tests for the ARCA L1 archive: parsed RESP commands in,
// byte-exact RESP replies out, entries persisted on disk. Every expected
// reply is hand-derived from the Redis protocol conventions.

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <unistd.h>

#include "reame/arca/archive.hpp"

using reame::arca::Archive;

namespace {

// Fresh temp directory per test case (removed on destruction).
struct TempDir {
    std::filesystem::path path;
    TempDir() {
        path = std::filesystem::temp_directory_path() /
               ("arca-test-" + std::to_string(::getpid()) + "-" +
                std::to_string(counter++));
        std::filesystem::create_directories(path);
    }
    ~TempDir() { std::filesystem::remove_all(path); }
    static inline int counter = 0;
};

Archive make(const TempDir& dir) {
    Archive::Config c;
    c.directory = dir.path;
    return Archive(c);
}

}  // namespace

TEST_CASE("arca: PING answers PONG") {
    TempDir dir;
    auto a = make(dir);
    CHECK(a.dispatch({"PING"}) == "+PONG\r\n");
    // redis-cli sends lowercase sometimes; commands are case-insensitive.
    CHECK(a.dispatch({"ping"}) == "+PONG\r\n");
}

TEST_CASE("arca: SET then GET round-trips the value") {
    TempDir dir;
    auto a = make(dir);
    CHECK(a.dispatch({"SET", "k", "hello"}) == "+OK\r\n");
    CHECK(a.dispatch({"GET", "k"}) == "$5\r\nhello\r\n");
}

TEST_CASE("arca: GET of a missing key is nil") {
    TempDir dir;
    auto a = make(dir);
    CHECK(a.dispatch({"GET", "ghost"}) == "$-1\r\n");
}

TEST_CASE("arca: binary-safe values (CRLF inside the payload)") {
    TempDir dir;
    auto a = make(dir);
    const std::string v = "a\r\nb";
    CHECK(a.dispatch({"SET", "k", v}) == "+OK\r\n");
    CHECK(a.dispatch({"GET", "k"}) == "$4\r\na\r\nb\r\n");
}

TEST_CASE("arca: DEL reports how many keys existed") {
    TempDir dir;
    auto a = make(dir);
    a.dispatch({"SET", "k", "v"});
    CHECK(a.dispatch({"DEL", "k"}) == ":1\r\n");
    CHECK(a.dispatch({"DEL", "k"}) == ":0\r\n");
    CHECK(a.dispatch({"GET", "k"}) == "$-1\r\n");
}

TEST_CASE("arca: EXISTS and DBSIZE") {
    TempDir dir;
    auto a = make(dir);
    CHECK(a.dispatch({"EXISTS", "k"}) == ":0\r\n");
    a.dispatch({"SET", "k", "v"});
    CHECK(a.dispatch({"EXISTS", "k"}) == ":1\r\n");
    a.dispatch({"SET", "j", "w"});
    CHECK(a.dispatch({"DBSIZE"}) == ":2\r\n");
}

TEST_CASE("arca: entries survive a restart — that is the whole point") {
    TempDir dir;
    {
        auto a = make(dir);
        a.dispatch({"SET", "answer", "42"});
    }
    auto b = make(dir);
    CHECK(b.dispatch({"GET", "answer"}) == "$2\r\n42\r\n");
}

TEST_CASE("arca: errors are RESP errors, not crashes") {
    TempDir dir;
    auto a = make(dir);
    // Unknown command.
    CHECK(a.dispatch({"FLY"}).rfind("-ERR", 0) == 0);
    // Wrong arity.
    CHECK(a.dispatch({"SET", "k"}).rfind("-ERR", 0) == 0);
    CHECK(a.dispatch({"GET"}).rfind("-ERR", 0) == 0);
    // Empty command (inline blank line tolerated upstream, but guard).
    CHECK(a.dispatch({}).rfind("-ERR", 0) == 0);
}
