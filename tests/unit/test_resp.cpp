// Isolated tests for the ARCA RESP2 protocol layer — pure byte logic,
// every expectation hand-derived from the RESP specification. The parser
// is incremental: TCP delivers arbitrary chunks, commands must assemble
// identically no matter where the cuts fall.

#include <catch2/catch_test_macros.hpp>

#include "reame/arca/resp.hpp"

using reame::arca::RespError;
using reame::arca::RespParser;

using Cmd = std::vector<std::string>;

TEST_CASE("resp: one whole multibulk command") {
    RespParser p;
    p.feed("*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n");
    const auto cmds = p.take();
    REQUIRE(cmds.size() == 1);
    CHECK(cmds[0] == Cmd{"GET", "foo"});
    CHECK(p.take().empty());  // drained
}

TEST_CASE("resp: command split at every possible byte boundary") {
    // The same command must assemble no matter how TCP slices it.
    const std::string wire = "*3\r\n$3\r\nSET\r\n$1\r\nk\r\n$5\r\nhello\r\n";
    for (std::size_t cut = 1; cut < wire.size(); ++cut) {
        RespParser p;
        p.feed(wire.substr(0, cut));
        CHECK(p.take().empty());  // incomplete: nothing to harvest yet
        p.feed(wire.substr(cut));
        const auto cmds = p.take();
        REQUIRE(cmds.size() == 1);
        CHECK(cmds[0] == Cmd{"SET", "k", "hello"});
    }
}

TEST_CASE("resp: two commands in one chunk") {
    RespParser p;
    p.feed("*1\r\n$4\r\nPING\r\n*2\r\n$3\r\nGET\r\n$1\r\na\r\n");
    const auto cmds = p.take();
    REQUIRE(cmds.size() == 2);
    CHECK(cmds[0] == Cmd{"PING"});
    CHECK(cmds[1] == Cmd{"GET", "a"});
}

TEST_CASE("resp: inline command (redis-cli handshake style)") {
    RespParser p;
    p.feed("PING\r\n");
    const auto cmds = p.take();
    REQUIRE(cmds.size() == 1);
    CHECK(cmds[0] == Cmd{"PING"});

    // Inline with arguments, split across feeds.
    p.feed("GET fo");
    CHECK(p.take().empty());
    p.feed("o\r\n");
    const auto more = p.take();
    REQUIRE(more.size() == 1);
    CHECK(more[0] == Cmd{"GET", "foo"});
}

TEST_CASE("resp: binary-safe bulk payload") {
    // A bulk string carries raw bytes, CRLF included: length rules, not
    // delimiters.
    RespParser p;
    const std::string payload = "a\r\nb\0c";  // careful: contains NUL
    const std::string data(payload.data(), 6);
    p.feed("*2\r\n$3\r\nSET\r\n$6\r\n" + data + "\r\n");
    const auto cmds = p.take();
    REQUIRE(cmds.size() == 1);
    REQUIRE(cmds[0].size() == 2);
    CHECK(cmds[0][1] == data);
}

TEST_CASE("resp: malformed input throws") {
    SECTION("array count not a number") {
        RespParser p;
        CHECK_THROWS_AS(p.feed("*x\r\n"), RespError);
    }
    SECTION("bulk without dollar") {
        RespParser p;
        CHECK_THROWS_AS(p.feed("*1\r\n#4\r\nPING\r\n"), RespError);
    }
    SECTION("negative bulk length inside a command") {
        RespParser p;
        CHECK_THROWS_AS(p.feed("*1\r\n$-2\r\nxx\r\n"), RespError);
    }
    SECTION("oversized declared lengths are rejected, not allocated") {
        RespParser p;
        CHECK_THROWS_AS(p.feed("*1\r\n$999999999\r\n"), RespError);
    }
}

TEST_CASE("resp: reply serializers, byte-exact") {
    CHECK(reame::arca::resp_simple("OK") == "+OK\r\n");
    CHECK(reame::arca::resp_error("ERR boom") == "-ERR boom\r\n");
    CHECK(reame::arca::resp_integer(42) == ":42\r\n");
    CHECK(reame::arca::resp_integer(-1) == ":-1\r\n");
    CHECK(reame::arca::resp_bulk("hello") == "$5\r\nhello\r\n");
    CHECK(reame::arca::resp_bulk("") == "$0\r\n\r\n");
    CHECK(reame::arca::resp_nil() == "$-1\r\n");
}
