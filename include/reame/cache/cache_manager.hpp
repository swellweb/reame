#pragma once

#include <cstdint>
#include <filesystem>
#include <list>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include "reame/cache/disk_cache_store.hpp"
#include "reame/core/llama_backend.hpp"

namespace reame::cache {

struct CacheStats {
    std::uint64_t hits = 0;
    std::uint64_t misses = 0;
    std::uint64_t stores = 0;
};

// Ties serializer + disk store together: named KV-cache snapshots that
// survive the process. Entry layout (inside the store's payload):
//   "SVK1" magic | u64 checksum(compressed) | u32 n_past | compressed blob
// Corrupt entries fail the checksum and are evicted on load.
class CacheManager {
public:
    struct Config {
        std::filesystem::path directory;
        std::uint64_t max_bytes = 0;  // 0 = unlimited
        bool compress = true;
        // RAM budget of the prefetch staging area (decompressed payloads
        // waiting for their request's turn at the engine). 0 disables it.
        std::uint64_t staging_bytes = 256ull * 1024 * 1024;
    };

    explicit CacheManager(const Config& cfg);

    // Deterministic key for a token prefix under a given model.
    static std::string make_key(const std::string& model_tag,
                                const std::vector<TokenId>& tokens);

    // Snapshot the backend state under `key`. `n_past` = positions the
    // snapshot represents. Returns false if the entry cannot be stored
    // (e.g. larger than the whole budget).
    bool store_state(const std::string& key, LlamaBackend& backend,
                     std::uint32_t n_past);

    // Restores the snapshot into the backend. False on miss or corruption
    // (corrupt entries are removed). Consumes the staged copy when the key
    // was prefetched.
    bool load_state(const std::string& key, LlamaBackend& backend);

    // Pays disk read + checksum + decompression NOW, on the caller's
    // thread, staging the ready-to-apply payload in RAM — so a request can
    // do this work while it waits its turn at the engine (the SGLang
    // HiCache idea, one level down). False on miss/corruption/disabled.
    bool prefetch(const std::string& key);

    const CacheStats& stats() const { return stats_; }

private:
    DiskCacheStore store_;
    bool compress_;
    std::uint64_t staging_budget_;
    CacheStats stats_;

    struct Pronta {
        std::vector<char> stato;   // decompressed, checksum already passed
        std::uint32_t n_past = 0;
    };
    std::mutex staging_mutex_;
    std::unordered_map<std::string, Pronta> staging_;
    std::list<std::string> staging_lru_;   // front = oldest
    std::uint64_t staging_usati_ = 0;

    bool preleva_staging(const std::string& key, Pronta& fuori);
};

}  // namespace reame::cache
