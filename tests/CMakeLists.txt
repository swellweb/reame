include(FetchContent)

FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG        v3.5.4
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(Catch2)

add_executable(reame_tests
    unit/test_config.cpp
    unit/test_logger.cpp
    unit/test_version.cpp
    unit/test_model.cpp
    unit/test_sampler.cpp
    unit/test_engine.cpp
    unit/test_scheduler.cpp
    unit/test_autoconfig.cpp
    unit/test_conclave.cpp
    unit/test_resp.cpp
    unit/test_arca.cpp
    unit/test_arca_server.cpp
    unit/test_arca_client.cpp
    unit/test_speculative.cpp
    unit/test_prompt_lookup.cpp
    unit/test_form_draft.cpp
    unit/test_cache.cpp
    unit/test_prefix_cache.cpp
    unit/test_corpus_index.cpp
    unit/test_nucleo_backend.cpp
)

# Il test del backend nucleo esercita la catena vera (GGUF giocattolo ->
# convertitore -> backend): serve la libreria e il percorso dei dati.
if(EXISTS "${REAME_NUCLEO_DIR}/include/nucleo/motore.hpp")
    target_compile_definitions(reame_tests PRIVATE REAME_HAS_NUCLEO=1
        TEST_NUCLEO_DIR="${REAME_NUCLEO_DIR}")
    target_link_libraries(reame_tests PRIVATE nucleo_motore)
endif()

if(REAME_BUILD_SERVER)
    target_sources(reame_tests PRIVATE
        unit/test_http_parser.cpp
        unit/test_api_handler.cpp
        unit/test_http_server.cpp
        unit/test_escalation.cpp
    )
    target_link_libraries(reame_tests PRIVATE reame_server)
endif()
target_link_libraries(reame_tests PRIVATE
    reame_core
    reame_utils
    Catch2::Catch2WithMain
)

list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
include(Catch)
# Catch2 exits with 4 when a test SKIPs (e.g. integration test without a
# downloaded model); tell ctest that means "skipped", not "failed".
# TIMEOUT turns a hang (e.g. a stuck socket test) into a failure instead
# of blocking the suite indefinitely.
catch_discover_tests(reame_tests PROPERTIES SKIP_RETURN_CODE 4 TIMEOUT 300)
