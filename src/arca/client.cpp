#include "reame/arca/client.hpp"

#include <boost/asio.hpp>

#include <sys/socket.h>
#include <sys/time.h>

#include <chrono>
#include <optional>
#include <string>

#include "reame/arca/resp.hpp"

namespace reame::arca {

namespace asio = boost::asio;
using asio::ip::tcp;

struct ArcaClient::Impl {
    Config cfg;
    asio::io_context io;
    std::optional<tcp::socket> sock;

    explicit Impl(const Config& c) : cfg(c) {}

    // Puts a receive/send deadline on the raw fd so a synchronous read
    // against a hung archive returns instead of blocking generation.
    void arm_timeouts() {
        timeval tv{};
        tv.tv_sec = cfg.timeout_ms / 1000;
        tv.tv_usec = (cfg.timeout_ms % 1000) * 1000;
        const int fd = static_cast<int>(sock->native_handle());
        ::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        ::setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
    }

    // Lazily (re)connect with a deadline. False when the archive is down.
    bool connect() {
        if (sock && sock->is_open()) return true;
        try {
            sock.emplace(io);
            tcp::resolver resolver(io);
            const auto endpoints =
                resolver.resolve(cfg.host, std::to_string(cfg.port));
            bool done = false;
            boost::system::error_code cec = asio::error::would_block;
            asio::async_connect(
                *sock, endpoints,
                [&](const boost::system::error_code& ec, const tcp::endpoint&) {
                    done = true;
                    cec = ec;
                });
            io.restart();
            io.run_for(std::chrono::milliseconds(cfg.timeout_ms));
            if (!done || cec) {
                sock.reset();
                return false;
            }
            arm_timeouts();
            return true;
        } catch (...) {
            sock.reset();
            return false;
        }
    }

    void drop() { sock.reset(); }

    // Reads one RESP reply. `io_ok` is set false only on an I/O failure
    // (caller should drop the connection); a nil or error reply keeps the
    // connection healthy and returns nullopt. Value is "" for a simple
    // string (+OK), the payload for a bulk string.
    std::optional<std::string> read_reply(bool& io_ok) {
        io_ok = true;
        std::string buf;
        if (!fill_until_crlf(buf)) {
            io_ok = false;
            return std::nullopt;
        }
        const std::size_t eol = buf.find("\r\n");
        const char type = buf[0];
        const std::string head = buf.substr(1, eol - 1);

        if (type == '+') return std::string();          // +OK
        if (type == '-') return std::nullopt;            // error reply (healthy)
        if (type == '$') {
            const long n = std::stol(head);
            if (n < 0) return std::nullopt;              // $-1 nil (healthy)
            const std::size_t need = eol + 2 + static_cast<std::size_t>(n) + 2;
            while (buf.size() < need) {
                if (!recv_more(buf)) {
                    io_ok = false;
                    return std::nullopt;
                }
            }
            return buf.substr(eol + 2, static_cast<std::size_t>(n));
        }
        return std::nullopt;
    }

    bool fill_until_crlf(std::string& buf) {
        while (buf.find("\r\n") == std::string::npos)
            if (!recv_more(buf)) return false;
        return true;
    }

    bool recv_more(std::string& buf) {
        char tmp[4096];
        boost::system::error_code ec;
        const std::size_t n = sock->read_some(asio::buffer(tmp), ec);
        if (ec || n == 0) return false;
        buf.append(tmp, n);
        return true;
    }

    bool write_all(const std::string& data) {
        boost::system::error_code ec;
        asio::write(*sock, asio::buffer(data), ec);
        return !ec;
    }
};

ArcaClient::ArcaClient(const Config& cfg)
    : pimpl_(std::make_unique<Impl>(cfg)) {}

ArcaClient::~ArcaClient() = default;

std::optional<std::string> ArcaClient::get(const std::string& key) {
    auto& p = *pimpl_;
    try {
        if (!p.connect()) return std::nullopt;
        const std::string cmd =
            "*2\r\n$3\r\nGET\r\n" + resp_bulk(key);
        if (!p.write_all(cmd)) {
            p.drop();
            return std::nullopt;
        }
        bool io_ok = true;
        auto reply = p.read_reply(io_ok);
        if (!io_ok) p.drop();  // a miss keeps the connection; only I/O drops
        return reply;
    } catch (...) {
        p.drop();
        return std::nullopt;
    }
}

void ArcaClient::set(const std::string& key, const std::string& value) {
    auto& p = *pimpl_;
    try {
        if (!p.connect()) return;
        const std::string cmd =
            "*3\r\n$3\r\nSET\r\n" + resp_bulk(key) + resp_bulk(value);
        if (!p.write_all(cmd)) {
            p.drop();
            return;
        }
        bool io_ok = true;
        p.read_reply(io_ok);  // consume +OK
        if (!io_ok) p.drop();
    } catch (...) {
        p.drop();
    }
}

}  // namespace reame::arca
