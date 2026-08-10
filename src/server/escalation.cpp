#include "reame/server/escalation.hpp"

#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cctype>
#include <cstring>
#include <regex>
#include <sstream>

namespace reame::server {

bool Escalation::dovrebbe(const std::string& risposta,
                          const std::string& trigger) {
    if (trigger.empty()) return false;
    const bool vuota =
        risposta.find_first_not_of(" \t\r\n") == std::string::npos;
    if (vuota) return true;
    try {
        const std::regex re(trigger, std::regex::icase);
        return std::regex_search(risposta, re);
    } catch (const std::regex_error&) {
        return false;  // a broken trigger must not break generation
    }
}

Escalation::Url Escalation::analizza(const std::string& endpoint) {
    Url u;
    static const std::string schema = "http://";
    if (endpoint.rfind(schema, 0) != 0) return u;
    const std::string resto = endpoint.substr(schema.size());
    if (resto.empty()) return u;

    const auto slash = resto.find('/');
    const std::string autorita =
        slash == std::string::npos ? resto : resto.substr(0, slash);
    u.path = slash == std::string::npos ? "/" : resto.substr(slash);

    const auto due_punti = autorita.find(':');
    if (due_punti == std::string::npos) {
        u.host = autorita;
    } else {
        u.host = autorita.substr(0, due_punti);
        const std::string porta = autorita.substr(due_punti + 1);
        if (porta.empty() ||
            porta.find_first_not_of("0123456789") != std::string::npos)
            return u;
        u.port = std::stoi(porta);
    }
    if (u.host.empty()) return u;
    u.valida = true;
    return u;
}

namespace {

// Blocking HTTP/1.1 POST over a plain socket: the deep lane lives on the
// loopback or the LAN, so a minimal client beats a dependency.
std::optional<std::string> http_post(const Escalation::Url& u,
                                     const std::string& body,
                                     int timeout_ms) {
    addrinfo hints{};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    addrinfo* res = nullptr;
    const std::string porta = std::to_string(u.port);
    if (getaddrinfo(u.host.c_str(), porta.c_str(), &hints, &res) != 0)
        return std::nullopt;

    int fd = -1;
    for (addrinfo* a = res; a; a = a->ai_next) {
        fd = socket(a->ai_family, a->ai_socktype, a->ai_protocol);
        if (fd < 0) continue;
        if (connect(fd, a->ai_addr, a->ai_addrlen) == 0) break;
        close(fd);
        fd = -1;
    }
    freeaddrinfo(res);
    if (fd < 0) return std::nullopt;

    timeval tv{timeout_ms / 1000, (timeout_ms % 1000) * 1000};
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

    std::ostringstream richiesta;
    richiesta << "POST " << u.path << " HTTP/1.1\r\n"
              << "Host: " << u.host << "\r\n"
              << "Content-Type: application/json\r\n"
              << "Content-Length: " << body.size() << "\r\n"
              << "Connection: close\r\n\r\n"
              << body;
    const std::string dati = richiesta.str();
    std::size_t inviati = 0;
    while (inviati < dati.size()) {
        const ssize_t n = send(fd, dati.data() + inviati,
                               dati.size() - inviati, 0);
        if (n <= 0) {
            close(fd);
            return std::nullopt;
        }
        inviati += static_cast<std::size_t>(n);
    }

    std::string risposta;
    char buffer[4096];
    ssize_t n;
    while ((n = recv(fd, buffer, sizeof(buffer), 0)) > 0)
        risposta.append(buffer, static_cast<std::size_t>(n));
    close(fd);

    const auto fine_testa = risposta.find("\r\n\r\n");
    if (fine_testa == std::string::npos) return std::nullopt;
    if (risposta.rfind("HTTP/1.1 200", 0) != 0 &&
        risposta.rfind("HTTP/1.0 200", 0) != 0)
        return std::nullopt;
    std::string corpo = risposta.substr(fine_testa + 4);

    // Connection: close usually yields a plain body, but a server that
    // answers chunked anyway must still be readable.
    if (risposta.substr(0, fine_testa).find("chunked") != std::string::npos) {
        std::string piano;
        std::size_t pos = 0;
        while (pos < corpo.size()) {
            const auto riga = corpo.find("\r\n", pos);
            if (riga == std::string::npos) break;
            const std::size_t lunghezza =
                std::strtoul(corpo.substr(pos, riga - pos).c_str(), nullptr, 16);
            if (lunghezza == 0) break;
            piano += corpo.substr(riga + 2, lunghezza);
            pos = riga + 2 + lunghezza + 2;
        }
        corpo = piano;
    }
    return corpo;
}

}  // namespace

EscalationClient make_http_escalation_client(int timeout_ms) {
    return [timeout_ms](const std::string& endpoint,
                        const std::string& body) -> std::optional<std::string> {
        const auto u = Escalation::analizza(endpoint);
        if (!u.valida) return std::nullopt;
        return http_post(u, body, timeout_ms);
    };
}

}  // namespace reame::server
