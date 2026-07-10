#!/usr/bin/env bash
# Sartoria (experimental): re-cut the model against the server's OWN
# traffic. The generation archive (palimpsest corpus) becomes an imatrix
# calibration set; the model is re-quantized so that the weights your
# domain actually exercises keep precision and the rest slims down.
#
#   ./scripts/sartoria.sh <f16-master.gguf> <calibration.txt> <out.gguf> [QTYPE]
#
# STATUS — read before trusting this:
#   * Mechanism: proven end-to-end (runs in minutes on a laptop).
#   * Quality advantage: NOT yet demonstrated. With a small synthetic
#     calibration corpus (~1.4k words) the tailored Q3_K_M scored a
#     statistical TIE with the generic Q3_K_M on held-out domain text
#     (PPL 3.18±0.21 vs 3.14±0.20; Q4_K_M reference 3.02±0.19).
#     A thin imatrix is noise and can even hurt. The honest test needs
#     real production traffic at volume (>>10k tokens) exported from the
#     palimpsest corpus — if you run one, please report numbers.
set -euo pipefail

MASTER="${1:?usage: sartoria.sh <f16-master.gguf> <calibration.txt> <out.gguf> [QTYPE]}"
CALIB="${2:?missing calibration text}"
OUT="${3:?missing output path}"
QTYPE="${4:-Q3_K_M}"

TOOLS="${SOVRANO_LLAMA_TOOLS:-}"
if [[ -z "$TOOLS" ]]; then
    echo "Building llama.cpp tools (one-off)..."
    cmake -S "$(dirname "$0")/../third_party/llama.cpp" -B /tmp/sovrano-llama-tools \
        -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_TOOLS=ON \
        -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TESTS=OFF \
        -DGGML_METAL=OFF -DLLAMA_CURL=OFF > /dev/null
    cmake --build /tmp/sovrano-llama-tools --parallel \
        --target llama-imatrix llama-quantize > /dev/null
    TOOLS=/tmp/sovrano-llama-tools/bin
fi

IMATRIX="$(mktemp -t sartoria).imatrix"
echo "== 1/2 measuring weight importance on YOUR corpus =="
"$TOOLS/llama-imatrix" -m "$MASTER" -f "$CALIB" -o "$IMATRIX"

echo "== 2/2 cutting the tailored $QTYPE =="
"$TOOLS/llama-quantize" --imatrix "$IMATRIX" "$MASTER" "$OUT" "$QTYPE"

echo "Done: $OUT"
echo "Validate before deploying: llama-perplexity on HELD-OUT domain text,"
echo "against a generic $QTYPE cut of the same master."
