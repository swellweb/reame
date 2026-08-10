#pragma once

// The escalation lane: when the fast model's answer is a refusal, the same
// request is retried on a deeper endpoint (the two-lane design: a small
// model answers instantly, a large pre-warmed one takes what it refuses).
//
// The decision is pure string logic and lives here so it can be pinned by
// unit tests; the HTTP client is a std::function so the handler can be
// tested with a fake and production can plug the socket implementation.

#include <functional>
#include <optional>
#include <string>

namespace reame::server {

struct Escalation {
    // True when the fast answer should be retried on the deep lane: the
    // trigger regex matches (case-insensitive), or the answer is blank —
    // an empty answer is a failure, not a success. An empty trigger
    // disables escalation entirely.
    static bool dovrebbe(const std::string& risposta,
                         const std::string& trigger);

    struct Url {
        std::string host;
        int port = 80;
        std::string path = "/";
        bool valida = false;
    };
    // Accepts http://host[:port][/path]; anything else is invalid.
    static Url analizza(const std::string& endpoint);
};

// POSTs `body` (application/json) to `endpoint`; returns the response body,
// or nullopt on any network or protocol failure — the caller keeps the fast
// answer, so escalation can never make a response worse than no escalation.
using EscalationClient = std::function<std::optional<std::string>(
    const std::string& endpoint, const std::string& body)>;

EscalationClient make_http_escalation_client(int timeout_ms);

}  // namespace reame::server
