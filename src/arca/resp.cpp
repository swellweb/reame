#include "reame/arca/resp.hpp"

#include <cctype>

namespace reame::arca {

namespace {

// Guards against a hostile "*2147483647" allocating the moon: no single
// command or bulk this daemon serves legitimately approaches this.
constexpr long kMaxElements = 1024;
constexpr long kMaxBulkBytes = 64 * 1024 * 1024;  // 64 MB (a KV block fits)

// Parses the integer after a type marker, up to CRLF. Returns false when
// the CRLF has not arrived yet; throws when the digits are not digits.
bool parse_number_line(const std::string& buf, std::size_t& pos, long& out) {
    const auto crlf = buf.find("\r\n", pos);
    if (crlf == std::string::npos) return false;
    const std::string digits = buf.substr(pos, crlf - pos);
    if (digits.empty()) throw RespError("empty length in RESP input");
    std::size_t i = digits[0] == '-' ? 1 : 0;
    if (i == digits.size()) throw RespError("bare minus in RESP length");
    for (; i < digits.size(); ++i)
        if (!std::isdigit(static_cast<unsigned char>(digits[i])))
            throw RespError("non-numeric RESP length: " + digits);
    out = std::stol(digits);
    pos = crlf + 2;
    return true;
}

}  // namespace

void RespParser::feed(std::string_view bytes) {
    buf_.append(bytes.data(), bytes.size());
    std::size_t offset = 0;
    std::vector<std::string> cmd;
    while (parse_one(offset, cmd)) {
        if (!cmd.empty()) ready_.push_back(std::move(cmd));
        cmd.clear();
    }
    buf_.erase(0, offset);
}

std::vector<std::vector<std::string>> RespParser::take() {
    auto out = std::move(ready_);
    ready_.clear();
    return out;
}

bool RespParser::parse_one(std::size_t& offset, std::vector<std::string>& out) {
    if (offset >= buf_.size()) return false;

    if (buf_[offset] != '*') {
        // Inline command: a plain line, words split on spaces.
        const auto crlf = buf_.find("\r\n", offset);
        if (crlf == std::string::npos) return false;
        std::string word;
        for (std::size_t i = offset; i < crlf; ++i) {
            if (buf_[i] == ' ') {
                if (!word.empty()) out.push_back(std::move(word));
                word.clear();
            } else {
                word.push_back(buf_[i]);
            }
        }
        if (!word.empty()) out.push_back(std::move(word));
        offset = crlf + 2;
        return true;
    }

    // Multibulk: *N, then N bulks of $L bytes each.
    std::size_t pos = offset + 1;
    long n = 0;
    if (!parse_number_line(buf_, pos, n)) return false;
    if (n < 0 || n > kMaxElements)
        throw RespError("unreasonable RESP array size: " + std::to_string(n));

    std::vector<std::string> parts;
    parts.reserve(static_cast<std::size_t>(n));
    for (long i = 0; i < n; ++i) {
        if (pos >= buf_.size()) return false;
        if (buf_[pos] != '$')
            throw RespError("expected bulk string marker '$'");
        ++pos;
        long len = 0;
        if (!parse_number_line(buf_, pos, len)) return false;
        if (len < 0 || len > kMaxBulkBytes)
            throw RespError("unreasonable RESP bulk length: " +
                            std::to_string(len));
        if (buf_.size() < pos + static_cast<std::size_t>(len) + 2)
            return false;  // payload (+ its CRLF) not fully arrived
        parts.emplace_back(buf_, pos, static_cast<std::size_t>(len));
        pos += static_cast<std::size_t>(len);
        if (buf_.compare(pos, 2, "\r\n") != 0)
            throw RespError("bulk payload not terminated by CRLF");
        pos += 2;
    }
    out = std::move(parts);
    offset = pos;
    return true;
}

std::string resp_simple(const std::string& s) { return "+" + s + "\r\n"; }
std::string resp_error(const std::string& s) { return "-" + s + "\r\n"; }
std::string resp_integer(long long v) {
    return ":" + std::to_string(v) + "\r\n";
}
std::string resp_bulk(const std::string& s) {
    return "$" + std::to_string(s.size()) + "\r\n" + s + "\r\n";
}
std::string resp_nil() { return "$-1\r\n"; }

}  // namespace reame::arca
