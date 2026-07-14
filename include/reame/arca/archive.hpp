#pragma once

#include <cstdint>
#include <filesystem>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "reame/cache/disk_cache_store.hpp"
#include "reame/palimpsest/corpus_index.hpp"

namespace reame::arca {

// The realm's archive behind the RESP daemon. Two layers today:
//   L1 — exact responses: SET/GET/DEL/EXISTS/DBSIZE on an LRU disk store.
//   L4 — the shared generation corpus: ARCA.OBSERVE feeds one node's
//        token stream to a fleet-wide Palimpsest, ARCA.DRAFT returns the
//        best historical continuation, so one node's speculation feeds
//        the others. Tokens travel as little-endian u32 in the bulk body.
// Entries live on disk and survive restarts. Thread-safe: the daemon
// serves many connections against one archive.
class Archive {
public:
    struct Config {
        std::filesystem::path directory;
        std::uint64_t max_bytes = 0;  // 0 = unlimited (L1 LRU budget)
        int corpus_ngram = 3;         // L4 index key length
    };

    explicit Archive(const Config& cfg);

    // Executes one command and returns the RESP-encoded reply. Commands
    // (case-insensitive): PING, SET, GET, DEL, EXISTS, DBSIZE,
    // ARCA.OBSERVE, ARCA.DRAFT. Unknown commands and wrong arities come
    // back as RESP errors — a bad client must never take the archive down.
    std::string dispatch(const std::vector<std::string>& cmd);

private:
    cache::DiskCacheStore store_;
    palimpsest::CorpusIndex corpus_;
    std::mutex mutex_;
};

}  // namespace reame::arca
