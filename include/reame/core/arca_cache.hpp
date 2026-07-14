#pragma once

#include <optional>
#include <string>

namespace reame::core {

// The engine's view of ARCA: an exact-response cache it can consult before
// generating and populate after. Kept as a pure interface here so
// reame_core carries no socket dependency — the real RESP client lives in
// reame_server, a mock drives the tests.
//
// Every method must degrade gracefully: if the remote archive is
// unreachable or slow, get() returns nullopt and set() is a silent no-op.
// A down ARCA must never break generation — it only removes the speedup.
class ArcaCache {
public:
    virtual ~ArcaCache() = default;

    // Cached completion for `key`, or nullopt on miss / any failure.
    virtual std::optional<std::string> get(const std::string& key) = 0;

    // Best-effort store. Failures are swallowed.
    virtual void set(const std::string& key, const std::string& value) = 0;
};

}  // namespace reame::core
