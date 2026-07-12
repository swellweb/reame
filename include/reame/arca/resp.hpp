#pragma once

#include <cstddef>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace reame::arca {

// ARCA speaks RESP2 — the Redis wire protocol — so every language's
// existing Redis client can talk to the realm's archive with zero SDK.
// This layer is pure byte logic: no sockets, no storage.

class RespError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

// Incremental request parser. TCP delivers arbitrary slices; feed() them
// as they arrive and take() whole commands (each a vector of strings).
// Accepts multibulk requests (*N of $L bulks — what clients send) and
// inline commands ("PING\r\n" — what humans type into netcat).
// Malformed or absurdly oversized input throws RespError.
class RespParser {
public:
    void feed(std::string_view bytes);
    std::vector<std::vector<std::string>> take();

private:
    // Attempts to parse ONE command from buf_ at offset; returns true and
    // advances `offset` past it when complete, false when more bytes are
    // needed. Throws on malformed input.
    bool parse_one(std::size_t& offset, std::vector<std::string>& out);

    std::string buf_;
    std::vector<std::vector<std::string>> ready_;
};

// Reply serializers (byte-exact, see tests).
std::string resp_simple(const std::string& s);
std::string resp_error(const std::string& s);
std::string resp_integer(long long v);
std::string resp_bulk(const std::string& s);
std::string resp_nil();

}  // namespace reame::arca
