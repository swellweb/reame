// Sovrano entry point. For this first step it only loads the configuration
// and sets up logging; engine/server wiring lands in later steps.

#include <cstdlib>
#include <exception>
#include <iostream>
#include <string>

#include "sovrano/utils/config.hpp"
#include "sovrano/utils/logger.hpp"

namespace {

constexpr const char* kVersion = "0.1.0";

void print_usage(const char* argv0) {
    std::cerr << "Usage: " << argv0 << " [--config <path>] [--help] [--version]\n";
}

}  // namespace

int main(int argc, char** argv) {
    std::string config_path = "config/sovrano.conf";

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            return EXIT_SUCCESS;
        }
        if (arg == "--version" || arg == "-v") {
            std::cout << "sovrano " << kVersion << "\n";
            return EXIT_SUCCESS;
        }
        if (arg == "--config" || arg == "-c") {
            if (i + 1 >= argc) {
                std::cerr << "error: " << arg << " requires a path argument\n";
                return EXIT_FAILURE;
            }
            config_path = argv[++i];
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
        log.info("engine wiring not implemented yet; exiting");
        return EXIT_SUCCESS;
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
