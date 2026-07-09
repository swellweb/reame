// Sovrano entry point. For this first step it only loads the configuration
// and sets up logging; engine/server wiring lands in later steps.

#include <csignal>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <memory>
#include <string>

#include "sovrano/cache/cache_manager.hpp"
#include "sovrano/core/engine.hpp"
#include "sovrano/speculative/speculative_decoder.hpp"
#include "sovrano/utils/config.hpp"
#include "sovrano/utils/logger.hpp"

#ifdef SOVRANO_WITH_SERVER
#include <condition_variable>
#include <mutex>

#include "sovrano/server/http_server.hpp"
#endif

namespace {

constexpr const char* kVersion = "0.1.0";

void print_usage(const char* argv0) {
    std::cerr << "Usage: " << argv0
              << " [--config <path>] [--prompt <text>] [--max-tokens <n>]"
                 " [--serve] [--help] [--version]\n";
}

#ifdef SOVRANO_WITH_SERVER
std::condition_variable g_shutdown_cv;
std::mutex g_shutdown_mutex;
bool g_shutdown = false;

void request_shutdown(int) {
    {
        std::lock_guard<std::mutex> lock(g_shutdown_mutex);
        g_shutdown = true;
    }
    g_shutdown_cv.notify_all();
}
#endif

}  // namespace

int main(int argc, char** argv) {
    std::string config_path = "config/sovrano.conf";
    std::string prompt;
    int max_tokens = 128;
    bool serve = false;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            return EXIT_SUCCESS;
        }
        if (arg == "--serve" || arg == "-s") {
            serve = true;
            continue;
        }
        if (arg == "--version" || arg == "-v") {
            std::cout << "sovrano " << kVersion << "\n";
            return EXIT_SUCCESS;
        }
        if (arg == "--config" || arg == "-c" || arg == "--prompt" ||
            arg == "-p" || arg == "--max-tokens") {
            if (i + 1 >= argc) {
                std::cerr << "error: " << arg << " requires an argument\n";
                return EXIT_FAILURE;
            }
            const std::string value = argv[++i];
            if (arg == "--config" || arg == "-c") config_path = value;
            else if (arg == "--max-tokens") max_tokens = std::stoi(value);
            else prompt = value;
            continue;
        }
        std::cerr << "error: unknown argument '" << arg << "'\n";
        print_usage(argv[0]);
        return EXIT_FAILURE;
    }

    try {
        const auto cfg = sovrano::Config::load(config_path);

        const auto level =
            sovrano::Logger::level_from_string(cfg.get_string("logging.level", "info"));
        sovrano::Logger log(std::cout, level);

        log.info("sovrano " + std::string(kVersion) + " starting");
        log.info("config loaded from " + config_path +
                 " (" + std::to_string(cfg.size()) + " keys)");
        log.info("model path: " + cfg.get_string("model.path", "<unset>"));
#ifdef SOVRANO_WITH_SERVER
        log.info("server: enabled (port " +
                 std::to_string(cfg.get_int("server.port", 8080)) + ")");
#else
        log.info("server: disabled in this build");
#endif

        if (prompt.empty() && !serve) {
            log.info("nothing to do: pass --prompt <text> or --serve");
            return EXIT_SUCCESS;
        }

        sovrano::core::SovranoEngine::Config engine_cfg;
        engine_cfg.model_path = cfg.get_string("model.path");
        engine_cfg.n_ctx =
            static_cast<int>(cfg.get_int("model.context_length", 4096));
        engine_cfg.n_threads = static_cast<int>(cfg.get_int("model.threads", 4));
        engine_cfg.use_mmap = cfg.get_bool("memory.use_mmap", true);
        engine_cfg.use_mlock = cfg.get_bool("memory.use_mlock", false);
        engine_cfg.kv_cache_type =
            cfg.get_string("memory.kv_cache_type", "f16");
        engine_cfg.use_speculative = cfg.get_bool("speculative.enabled", true);
        // mode: model (default, needs draft_model_path) | lookup (n-gram
        // proposals from the prompt itself, no second model)
        engine_cfg.use_prompt_lookup =
            cfg.get_string("speculative.mode", "model") == "lookup";
        engine_cfg.draft_model_path =
            cfg.get_string("speculative.draft_model_path", "");
        engine_cfg.draft_tokens =
            static_cast<int>(cfg.get_int("speculative.draft_tokens", 16));
        engine_cfg.cache_dir = cfg.get_string("cache.directory", "");
        engine_cfg.cache_max_mb = static_cast<std::uint64_t>(
            cfg.get_int("cache.max_size_mb", 512));
        engine_cfg.cache_compress = cfg.get_bool("cache.compress", true);
        engine_cfg.cache_block_tokens =
            static_cast<int>(cfg.get_int("cache.block_tokens", 256));

        log.info("loading model...");
        auto engine =
            std::make_shared<sovrano::core::SovranoEngine>(engine_cfg);
        log.info("model loaded (vocab " +
                 std::to_string(engine->vocab_size()) + ", ctx " +
                 std::to_string(engine->context_size()) + ")");
        if (engine->speculative_metrics() != nullptr)
            log.info("speculative decoding: on (draft " +
                     engine_cfg.draft_model_path + ")");

        if (serve) {
#ifdef SOVRANO_WITH_SERVER
            sovrano::server::HttpServer::Config sc;
            sc.host = cfg.get_string("server.host", "0.0.0.0");
            sc.port = static_cast<int>(cfg.get_int("server.port", 8080));
            sc.threads =
                static_cast<int>(cfg.get_int("server.threads", 2));
            sc.max_concurrent_requests = static_cast<int>(
                cfg.get_int("server.max_concurrent_requests", 10));
            sc.timeout_seconds = static_cast<int>(
                cfg.get_int("server.timeout_seconds", 300));
            sc.max_request_size_mb = static_cast<std::size_t>(
                cfg.get_int("server.max_request_size_mb", 10));
            sc.enable_cors = cfg.get_bool("server.enable_cors", true);
            sc.enable_metrics = cfg.get_bool("server.enable_metrics", true);
            sc.enable_request_logging =
                cfg.get_bool("server.enable_request_logging", true);
            sc.api_key = cfg.get_string("server.api_key", "");
            sc.model_id = cfg.get_string("server.model_id", "sovrano");

            sovrano::server::HttpServer server(sc, engine);
            server.start();

            std::signal(SIGINT, request_shutdown);
            std::signal(SIGTERM, request_shutdown);
            {
                std::unique_lock<std::mutex> lock(g_shutdown_mutex);
                g_shutdown_cv.wait(lock, [] { return g_shutdown; });
            }
            log.info("shutting down");
            server.stop();
            return EXIT_SUCCESS;
#else
            std::cerr << "error: sovrano was built without server support "
                         "(Boost/nlohmann-json missing at configure time)\n";
            return EXIT_FAILURE;
#endif
        }

        sovrano::core::GenerationConfig gen;
        gen.max_tokens = max_tokens;
        engine->generate_stream(prompt, [](const std::string& piece) {
            std::cout << piece << std::flush;
            return true;
        }, gen);
        std::cout << "\n";

        if (const auto* c = engine->cache_stats()) {
            log.info("cache: " + std::to_string(c->hits) + " hits, " +
                     std::to_string(c->misses) + " misses, " +
                     std::to_string(c->stores) + " stores");
        }
        if (const auto* m = engine->speculative_metrics()) {
            log.info("speculative metrics: acceptance " +
                     std::to_string(m->acceptance_rate()) + ", overall " +
                     std::to_string(m->overall_speed()) + " tok/s (draft " +
                     std::to_string(m->total_draft_tokens) + ", accepted " +
                     std::to_string(m->total_accepted_tokens) + ", rejected " +
                     std::to_string(m->total_rejected_tokens) + ")");
        }
        return EXIT_SUCCESS;
    } catch (const sovrano::core::EngineError& e) {
        std::cerr << "engine error: " << e.what() << "\n";
        return EXIT_FAILURE;
    } catch (const sovrano::ConfigError& e) {
        std::cerr << "config error";
        if (e.line() != 0) std::cerr << " (line " << e.line() << ")";
        std::cerr << ": " << e.what() << "\n";
        return EXIT_FAILURE;
    } catch (const std::exception& e) {
        std::cerr << "fatal: " << e.what() << "\n";
        return EXIT_FAILURE;
    }
}
