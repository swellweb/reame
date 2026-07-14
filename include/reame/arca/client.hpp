#pragma once

#include <memory>
#include <optional>
#include <string>

#include "reame/core/arca_cache.hpp"

namespace reame::arca {

// A thin RESP client for a remote ARCA daemon, implementing the engine's
// ArcaCache interface. Every operation is best-effort: an unreachable or
// slow archive makes get() return nullopt and set() a no-op, never an
// exception — a down ARCA must only remove the speedup, not break Reame.
// A short socket timeout keeps a hung remote from stalling generation.
class ArcaClient : public core::ArcaCache {
public:
    struct Config {
        std::string host = "127.0.0.1";
        int port = 6420;
        int timeout_ms = 200;  // per-operation cap; a slow ARCA is skipped
    };

    explicit ArcaClient(const Config& cfg);
    ~ArcaClient() override;

    std::optional<std::string> get(const std::string& key) override;
    void set(const std::string& key, const std::string& value) override;

private:
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
};

}  // namespace reame::arca
