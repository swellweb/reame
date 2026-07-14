#include "reame/arca/archive.hpp"

#include <algorithm>
#include <cctype>

#include "reame/arca/resp.hpp"

namespace reame::arca {

namespace {

std::string upper(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) {
        return static_cast<char>(std::toupper(c));
    });
    return s;
}

std::string err_arity(const std::string& name) {
    return resp_error("ERR wrong number of arguments for '" + name + "'");
}

// Token ids on the wire: little-endian u32 packed into the bulk body.
std::string pack_tokens(const std::vector<TokenId>& toks) {
    std::string s;
    s.reserve(toks.size() * 4);
    for (TokenId t : toks) {
        const auto u = static_cast<std::uint32_t>(t);
        s.push_back(static_cast<char>(u & 0xff));
        s.push_back(static_cast<char>((u >> 8) & 0xff));
        s.push_back(static_cast<char>((u >> 16) & 0xff));
        s.push_back(static_cast<char>((u >> 24) & 0xff));
    }
    return s;
}

// Unpacks; returns false when the payload is not a whole number of u32s.
bool unpack_tokens(const std::string& s, std::vector<TokenId>& out) {
    if (s.size() % 4 != 0) return false;
    out.clear();
    out.reserve(s.size() / 4);
    for (std::size_t i = 0; i < s.size(); i += 4) {
        const std::uint32_t u =
            static_cast<unsigned char>(s[i]) |
            (static_cast<std::uint32_t>(static_cast<unsigned char>(s[i + 1]))
             << 8) |
            (static_cast<std::uint32_t>(static_cast<unsigned char>(s[i + 2]))
             << 16) |
            (static_cast<std::uint32_t>(static_cast<unsigned char>(s[i + 3]))
             << 24);
        out.push_back(static_cast<TokenId>(u));
    }
    return true;
}

}  // namespace

Archive::Archive(const Config& cfg)
    : store_({cfg.directory, cfg.max_bytes}),
      corpus_([&cfg] {
          palimpsest::CorpusIndex::Config cc;
          cc.directory = cfg.directory / "corpus";
          cc.ngram = cfg.corpus_ngram;
          return cc;
      }()) {}

std::string Archive::dispatch(const std::vector<std::string>& cmd) {
    if (cmd.empty()) return resp_error("ERR empty command");

    const std::string name = upper(cmd[0]);
    std::lock_guard<std::mutex> lock(mutex_);

    if (name == "PING") return resp_simple("PONG");

    if (name == "SET") {
        if (cmd.size() != 3) return err_arity("set");
        const std::vector<char> data(cmd[2].begin(), cmd[2].end());
        if (!store_.put(cmd[1], data))
            return resp_error("ERR value larger than the archive budget");
        return resp_simple("OK");
    }

    if (name == "GET") {
        if (cmd.size() != 2) return err_arity("get");
        const auto data = store_.get(cmd[1]);
        if (!data.has_value()) return resp_nil();
        return resp_bulk(std::string(data->begin(), data->end()));
    }

    if (name == "DEL") {
        if (cmd.size() != 2) return err_arity("del");
        return resp_integer(store_.remove(cmd[1]) ? 1 : 0);
    }

    if (name == "EXISTS") {
        if (cmd.size() != 2) return err_arity("exists");
        return resp_integer(store_.contains(cmd[1]) ? 1 : 0);
    }

    if (name == "DBSIZE") {
        if (cmd.size() != 1) return err_arity("dbsize");
        return resp_integer(static_cast<long long>(store_.count()));
    }

    // L4: the shared generation corpus.
    if (name == "ARCA.OBSERVE") {
        if (cmd.size() != 2) return err_arity("arca.observe");
        std::vector<TokenId> toks;
        if (!unpack_tokens(cmd[1], toks))
            return resp_error("ERR token payload must be whole u32s");
        corpus_.observe(toks);
        return resp_simple("OK");
    }

    if (name == "ARCA.DRAFT") {
        if (cmd.size() != 3) return err_arity("arca.draft");
        std::vector<TokenId> tail;
        if (!unpack_tokens(cmd[1], tail))
            return resp_error("ERR token payload must be whole u32s");
        int k = 0;
        try {
            k = std::stoi(cmd[2]);
        } catch (...) {
            return resp_error("ERR draft length is not an integer");
        }
        if (k <= 0) return resp_error("ERR draft length must be positive");
        const auto draft = corpus_.draft(tail, k);
        if (draft.empty()) return resp_nil();
        return resp_bulk(pack_tokens(draft));
    }

    return resp_error("ERR unknown command '" + cmd[0] + "'");
}

}  // namespace reame::arca
