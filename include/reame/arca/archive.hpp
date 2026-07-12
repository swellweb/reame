#pragma once

#include <cstdint>
#include <filesystem>
#include <mutex>
#include <string>
#include <vector>

#include "reame/cache/disk_cache_store.hpp"

namespace reame::arca {

// ARCA L1: the exact-response archive. Parsed RESP commands in,
// byte-exact RESP replies out; entries live on disk under an LRU byte
// budget and survive restarts. No sockets here — the daemon feeds it.
// Thread-safe: the daemon serves many connections against one archive.
class Archive {
public:
    struct Config {
        std::filesystem::path directory;
        std::uint64_t max_bytes = 0;  // 0 = unlimited
    };

    explicit Archive(const Config& cfg);

    // Executes one command (SET/GET/DEL/EXISTS/DBSIZE/PING, names
    // case-insensitive) and returns the RESP-encoded reply. Unknown
    // commands and wrong arities come back as RESP errors — a bad
    // client must never take the archive down.
    std::string dispatch(const std::vector<std::string>& cmd);

private:
    cache::DiskCacheStore store_;
    std::mutex mutex_;
};

}  // namespace reame::arca
