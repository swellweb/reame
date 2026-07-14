// Isolated tests for the ARCA L1 archive: parsed RESP commands in,
// byte-exact RESP replies out, entries persisted on disk. Every expected
// reply is hand-derived from the Redis protocol conventions.

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <filesystem>
#include <string>
#include <unistd.h>
#include <vector>

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

// --- L4: the shared generation corpus (Palimpsest over the network) ---

namespace {

// Token ids packed as little-endian u32, the wire form ARCA.OBSERVE /
// ARCA.DRAFT carry in their RESP bulk payload.
std::string pack(const std::vector<int>& toks) {
    std::string s;
    s.reserve(toks.size() * 4);
    for (int t : toks) {
        const auto u = static_cast<std::uint32_t>(t);
        s.push_back(static_cast<char>(u & 0xff));
        s.push_back(static_cast<char>((u >> 8) & 0xff));
        s.push_back(static_cast<char>((u >> 16) & 0xff));
        s.push_back(static_cast<char>((u >> 24) & 0xff));
    }
    return s;
}

std::vector<int> unpack(const std::string& s) {
    std::vector<int> out;
    for (std::size_t i = 0; i + 4 <= s.size(); i += 4) {
        std::uint32_t u = static_cast<unsigned char>(s[i]) |
                          (static_cast<unsigned char>(s[i + 1]) << 8) |
                          (static_cast<unsigned char>(s[i + 2]) << 16) |
                          (static_cast<unsigned char>(s[i + 3]) << 24);
        out.push_back(static_cast<int>(u));
    }
    return out;
}

// The bulk-string body of a "$N\r\n...\r\n" reply, or "" for nil.
std::string bulk_body(const std::string& reply) {
    if (reply.rfind("$-1", 0) == 0) return "";
    const auto crlf = reply.find("\r\n");
    const std::size_t start = crlf + 2;
    return reply.substr(start, reply.size() - start - 2);
}

}  // namespace

TEST_CASE("arca L4: OBSERVE a generation, then DRAFT its continuation") {
    TempDir dir;
    auto a = make(dir);
    // Teach the corpus: after (10, 11, 12) came (13, 14).
    CHECK(a.dispatch({"ARCA.OBSERVE", pack({10, 11, 12, 13, 14})}) ==
          "+OK\r\n");
    // A different node asks: I just produced (…, 10, 11, 12), what's next?
    const auto reply = a.dispatch({"ARCA.DRAFT", pack({10, 11, 12}), "4"});
    const auto draft = unpack(bulk_body(reply));
    REQUIRE(draft.size() >= 2);
    CHECK(draft[0] == 13);
    CHECK(draft[1] == 14);
}

TEST_CASE("arca L4: DRAFT on an unseen n-gram is nil") {
    TempDir dir;
    auto a = make(dir);
    CHECK(a.dispatch({"ARCA.DRAFT", pack({99, 98, 97}), "4"}) == "$-1\r\n");
}

TEST_CASE("arca L4: the corpus is shared across restarts (fleet memory)") {
    TempDir dir;
    {
        auto a = make(dir);
        a.dispatch({"ARCA.OBSERVE", pack({20, 21, 22, 23, 24})});
    }
    // A node that starts later inherits what the fleet has seen.
    auto b = make(dir);
    const auto reply = b.dispatch({"ARCA.DRAFT", pack({20, 21, 22}), "2"});
    const auto draft = unpack(bulk_body(reply));
    REQUIRE(draft.size() >= 1);
    CHECK(draft[0] == 23);
}

TEST_CASE("arca L4: arity and bad payloads are RESP errors") {
    TempDir dir;
    auto a = make(dir);
    CHECK(a.dispatch({"ARCA.OBSERVE"}).rfind("-ERR", 0) == 0);
    CHECK(a.dispatch({"ARCA.DRAFT", pack({1, 2, 3})}).rfind("-ERR", 0) == 0);
    // A payload whose length is not a multiple of 4 is malformed.
    CHECK(a.dispatch({"ARCA.OBSERVE", "abc"}).rfind("-ERR", 0) == 0);
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
