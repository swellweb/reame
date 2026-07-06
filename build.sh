#!/usr/bin/env bash
# Sovrano build script.
#   ./build.sh              Release build + tests
#   ./build.sh --debug      Debug build
#   ./build.sh --clean      remove build dir first
#   ./build.sh --no-tests   skip building/running tests
#   ./build.sh --avx512     enable AVX-512 (VPS with capable CPU)
#   ./build.sh --no-server  skip server target and its dependencies
set -euo pipefail

cd "$(dirname "$0")"

BUILD_DIR="build"
BUILD_TYPE="Release"
RUN_TESTS=1
CMAKE_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --debug)     BUILD_TYPE="Debug" ;;
        --clean)     rm -rf "$BUILD_DIR" ;;
        --no-tests)  RUN_TESTS=0; CMAKE_ARGS+=(-DSOVRANO_BUILD_TESTS=OFF) ;;
        --avx512)    CMAKE_ARGS+=(-DSOVRANO_ENABLE_AVX512=ON) ;;
        --no-server) CMAKE_ARGS+=(-DSOVRANO_BUILD_SERVER=OFF) ;;
        --help|-h)   grep '^#   ' "$0" | sed 's/^#   //'; exit 0 ;;
        *) echo "unknown option: $arg (see --help)" >&2; exit 1 ;;
    esac
done

if command -v nproc >/dev/null 2>&1; then
    JOBS="$(nproc)"
else
    JOBS="$(sysctl -n hw.ncpu)"
fi

echo "== Configuring (${BUILD_TYPE}) =="
cmake -S . -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
    "${CMAKE_ARGS[@]+"${CMAKE_ARGS[@]}"}"

echo "== Building with ${JOBS} jobs =="
cmake --build "$BUILD_DIR" --parallel "$JOBS"

if [[ "$RUN_TESTS" -eq 1 ]]; then
    echo "== Running tests =="
    ctest --test-dir "$BUILD_DIR" --output-on-failure
fi

echo "== Done: ${BUILD_DIR}/src/sovrano =="
