#include "reame/cache/cache_manager.hpp"

#include <cstring>

#include "reame/cache/cache_serializer.hpp"

namespace reame::cache {

namespace {

constexpr char kMagic[4] = {'S', 'V', 'K', '1'};

void append_u32(std::vector<char>& out, std::uint32_t v) {
    for (int i = 0; i < 4; ++i)
        out.push_back(static_cast<char>((v >> (8 * i)) & 0xFF));
}

void append_u64(std::vector<char>& out, std::uint64_t v) {
    for (int i = 0; i < 8; ++i)
        out.push_back(static_cast<char>((v >> (8 * i)) & 0xFF));
}

std::uint32_t read_u32(const char* p) {
    std::uint32_t v = 0;
    for (int i = 3; i >= 0; --i)
        v = (v << 8) | static_cast<unsigned char>(p[i]);
    return v;
}

std::uint64_t read_u64(const char* p) {
    std::uint64_t v = 0;
    for (int i = 7; i >= 0; --i)
        v = (v << 8) | static_cast<unsigned char>(p[i]);
    return v;
}

constexpr std::size_t kEnvelopeHeader = 4 + 8 + 4;  // magic + checksum + n_past

}  // namespace

CacheManager::CacheManager(const Config& cfg)
    : store_({cfg.directory, cfg.max_bytes}),
      compress_(cfg.compress),
      staging_budget_(cfg.staging_bytes) {}

std::string CacheManager::make_key(const std::string& model_tag,
                                   const std::vector<TokenId>& tokens) {
    // Two decorrelated FNV hashes over tag + tokens keep the key compact
    // while making cross-prompt collisions negligible; the store verifies
    // the full key string anyway.
    std::vector<char> raw(model_tag.begin(), model_tag.end());
    raw.push_back('\0');
    for (const TokenId t : tokens) {
        for (int i = 0; i < 4; ++i)
            raw.push_back(static_cast<char>((static_cast<std::uint32_t>(t) >>
                                             (8 * i)) &
                                            0xFF));
    }
    const std::uint64_t h1 = KVCacheSerializer::checksum(raw);
    raw.push_back('x');  // perturb for the second hash
    const std::uint64_t h2 = KVCacheSerializer::checksum(raw);
    return "kv-" + std::to_string(h1) + "-" + std::to_string(h2) + "-n" +
           std::to_string(tokens.size());
}

bool CacheManager::store_state(const std::string& key, LlamaBackend& backend,
                               std::uint32_t n_past) {
    const auto raw = KVCacheSerializer::serialize(backend);
    const auto packed = compress_
                            ? KVCacheSerializer::compress(raw)
                            : [&raw] {
                                  std::vector<char> out{'R'};
                                  out.insert(out.end(), raw.begin(), raw.end());
                                  return out;
                              }();

    std::vector<char> entry;
    entry.reserve(kEnvelopeHeader + packed.size());
    entry.insert(entry.end(), kMagic, kMagic + 4);
    append_u64(entry, KVCacheSerializer::checksum(packed));
    append_u32(entry, n_past);
    entry.insert(entry.end(), packed.begin(), packed.end());

    if (!store_.put(key, entry)) return false;
    ++stats_.stores;
    return true;
}

bool CacheManager::prefetch(const std::string& key) {
    if (staging_budget_ == 0) return false;
    {
        std::lock_guard<std::mutex> lock(staging_mutex_);
        if (staging_.count(key)) return true;   // gia' pronta
    }

    const auto entry = store_.get(key);
    if (!entry.has_value()) return false;
    if (entry->size() < kEnvelopeHeader ||
        std::memcmp(entry->data(), kMagic, 4) != 0) {
        store_.remove(key);
        return false;
    }
    const std::uint64_t expected = read_u64(entry->data() + 4);
    Pronta pronta;
    pronta.n_past = read_u32(entry->data() + 12);
    const std::vector<char> packed(entry->begin() + kEnvelopeHeader,
                                   entry->end());
    if (KVCacheSerializer::checksum(packed) != expected) {
        store_.remove(key);
        return false;
    }
    try {
        pronta.stato = KVCacheSerializer::decompress(packed);
    } catch (const std::exception&) {
        store_.remove(key);
        return false;
    }

    std::lock_guard<std::mutex> lock(staging_mutex_);
    staging_usati_ += pronta.stato.size();
    staging_[key] = std::move(pronta);
    staging_lru_.push_back(key);
    // LRU sul budget: si sfratta il piu' vecchio, mai l'appena entrato.
    while (staging_usati_ > staging_budget_ && staging_lru_.size() > 1) {
        const std::string vecchia = staging_lru_.front();
        staging_lru_.pop_front();
        auto it = staging_.find(vecchia);
        if (it != staging_.end()) {
            staging_usati_ -= it->second.stato.size();
            staging_.erase(it);
        }
    }
    return true;
}

bool CacheManager::preleva_staging(const std::string& key, Pronta& fuori) {
    std::lock_guard<std::mutex> lock(staging_mutex_);
    auto it = staging_.find(key);
    if (it == staging_.end()) return false;
    fuori = std::move(it->second);
    staging_usati_ -= fuori.stato.size();
    staging_.erase(it);
    staging_lru_.remove(key);
    return true;
}

bool CacheManager::load_state(const std::string& key, LlamaBackend& backend) {
    // A prefetched entry already paid disk, checksum and decompression on
    // the requester's thread: apply it and it is spent.
    Pronta pronta;
    if (preleva_staging(key, pronta)) {
        try {
            KVCacheSerializer::deserialize(backend, pronta.stato,
                                           pronta.n_past);
            ++stats_.hits;
            return true;
        } catch (const std::exception&) {
            store_.remove(key);
            ++stats_.misses;
            return false;
        }
    }

    const auto entry = store_.get(key);
    if (!entry.has_value()) {
        ++stats_.misses;
        return false;
    }

    if (entry->size() < kEnvelopeHeader ||
        std::memcmp(entry->data(), kMagic, 4) != 0) {
        store_.remove(key);
        ++stats_.misses;
        return false;
    }

    const std::uint64_t expected = read_u64(entry->data() + 4);
    const std::uint32_t n_past = read_u32(entry->data() + 12);
    const std::vector<char> packed(entry->begin() + kEnvelopeHeader,
                                   entry->end());

    if (KVCacheSerializer::checksum(packed) != expected) {
        store_.remove(key);  // corrupt on disk
        ++stats_.misses;
        return false;
    }

    try {
        KVCacheSerializer::deserialize(
            backend, KVCacheSerializer::decompress(packed), n_past);
    } catch (const std::exception&) {
        store_.remove(key);
        ++stats_.misses;
        return false;
    }

    ++stats_.hits;
    return true;
}

}  // namespace reame::cache
