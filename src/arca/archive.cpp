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

}  // namespace

Archive::Archive(const Config& cfg)
    : store_({cfg.directory, cfg.max_bytes}) {}

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

    return resp_error("ERR unknown command '" + cmd[0] + "'");
}

}  // namespace reame::arca
