#pragma once

// Mock LlamaBackend for isolated LlamaModel tests: canned return values,
// recorded calls, no llama.cpp involved. The interface shape mirrors the
// real backend (llama_backend_real.cpp), which was written against the
// actual llama.h of the pinned submodule.

#include <cstdint>
#include <string>
#include <vector>

#include "sovrano/core/llama_backend.hpp"

namespace sovrano::test {

class MockBackend : public LlamaBackend {
public:
    // Canned responses (set from the test before use).
    std::vector<TokenId> tokenize_result;
    std::string detokenize_result;
    std::vector<float> decode_result;
    std::int32_t vocab_size_value = 32000;
    std::uint32_t context_length_value = 2048;

    // Recorded calls.
    std::vector<std::pair<std::string, bool>> tokenize_calls;
    std::vector<std::vector<TokenId>> detokenize_calls;
    std::vector<std::vector<TokenId>> decode_calls;

    std::vector<TokenId> tokenize(const std::string& text,
                                  bool add_special) override {
        tokenize_calls.emplace_back(text, add_special);
        return tokenize_result;
    }

    std::string detokenize(const std::vector<TokenId>& tokens) override {
        detokenize_calls.push_back(tokens);
        return detokenize_result;
    }

    std::vector<float> decode(const std::vector<TokenId>& tokens) override {
        decode_calls.push_back(tokens);
        return decode_result;
    }

    std::int32_t vocab_size() const override { return vocab_size_value; }
    std::uint32_t context_length() const override { return context_length_value; }
};

}  // namespace sovrano::test
