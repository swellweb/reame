// Isolated tests for the interleaved scheduler. step() is driven directly
// (no threads); the mock's per-sequence queues script each request's
// token trajectory, so every expectation is hand-derived.

#include <catch2/catch_test_macros.hpp>

#include <vector>

#include "../mock/llama_mock.hpp"
#include "sovrano/core/scheduler.hpp"

using sovrano::SeqSlice;
using sovrano::TokenId;
using sovrano::test::MockBackend;
using sovrano::core::EngineError;
using sovrano::core::GenerationConfig;
using sovrano::core::Scheduler;

namespace {

GenerationConfig greedy(int max_tokens = 16) {
    GenerationConfig g;
    g.temperature = 0.0f;
    g.repeat_penalty = 1.0f;
    g.max_tokens = max_tokens;
    return g;
}

std::vector<float> peak(std::size_t n, std::size_t idx) {
    std::vector<float> v(n, 0.0f);
    v[idx] = 10.0f;
    return v;
}

constexpr std::size_t kVocab = 6;
constexpr TokenId kEos = 5;

void setup(MockBackend& m) {
    m.vocab_size_value = kVocab;
    m.eos_token_value = kEos;
    m.context_length_value = 256;
}

struct Collector {
    std::vector<TokenId> tokens;
    Scheduler::TokenCallback cb() {
        return [this](TokenId t) {
            tokens.push_back(t);
            return true;
        };
    }
};

}  // namespace

TEST_CASE("two requests interleave in shared batches and both complete") {
    MockBackend backend;
    setup(backend);
    // seq 0 (request A): tokens 1, 2, then EOS.  seq 1 (B): token 3, EOS.
    backend.seq_decode_queues[0] = {peak(kVocab, 1), peak(kVocab, 2),
                                    peak(kVocab, kEos)};
    backend.seq_decode_queues[1] = {peak(kVocab, 3), peak(kVocab, kEos)};

    Scheduler sched(backend, {/*n_parallel=*/2});
    Collector a, b;
    const auto ra = sched.submit({10, 11}, greedy(), a.cb());
    const auto rb = sched.submit({20}, greedy(), b.cb());

    sched.run_until_idle();

    CHECK(a.tokens == std::vector<TokenId>{1, 2});
    CHECK(b.tokens == std::vector<TokenId>{3});
    CHECK(sched.finished(ra));
    CHECK(sched.finished(rb));
    CHECK(sched.error(ra) == nullptr);

    // First batch: both prefills together, at position 0 of their seqs.
    REQUIRE_FALSE(backend.decode_seqs_calls.empty());
    const auto& first = backend.decode_seqs_calls[0];
    REQUIRE(first.size() == 2);
    CHECK(first[0].tokens == std::vector<TokenId>{10, 11});
    CHECK(first[0].pos_start == 0);
    CHECK(first[1].tokens == std::vector<TokenId>{20});
    CHECK(first[1].seq_id != first[0].seq_id);

    // Second batch: one generated token per request, positions advanced.
    const auto& second = backend.decode_seqs_calls[1];
    REQUIRE(second.size() == 2);
    CHECK(second[0].tokens == std::vector<TokenId>{1});
    CHECK(second[0].pos_start == 2);
    CHECK(second[1].tokens == std::vector<TokenId>{3});
    CHECK(second[1].pos_start == 1);

    // Both sequences were released.
    CHECK(backend.clear_seq_calls.size() == 2);
}

TEST_CASE("requests beyond n_parallel wait and run after a slot frees") {
    MockBackend backend;
    setup(backend);
    backend.seq_decode_queues[0] = {peak(kVocab, 1), peak(kVocab, kEos),
                                    // reused by the queued request:
                                    peak(kVocab, 2), peak(kVocab, kEos)};

    Scheduler sched(backend, {/*n_parallel=*/1});
    Collector a, b;
    sched.submit({10}, greedy(), a.cb());
    sched.submit({20}, greedy(), b.cb());

    CHECK(sched.step());          // prefill A only: one slice
    CHECK(backend.decode_seqs_calls[0].size() == 1);

    sched.run_until_idle();

    CHECK(a.tokens == std::vector<TokenId>{1});
    CHECK(b.tokens == std::vector<TokenId>{2});
}

TEST_CASE("a callback returning false ends that request but not the others") {
    MockBackend backend;
    setup(backend);
    backend.seq_decode_queues[0] = {peak(kVocab, 1), peak(kVocab, 2),
                                    peak(kVocab, 3), peak(kVocab, kEos)};
    backend.seq_decode_queues[1] = {peak(kVocab, 4), peak(kVocab, kEos)};

    Scheduler sched(backend, {2});
    Collector b;
    std::vector<TokenId> a_tokens;
    const auto ra = sched.submit({10}, greedy(), [&](TokenId t) {
        a_tokens.push_back(t);
        return false;  // stop A immediately
    });
    const auto rb = sched.submit({20}, greedy(), b.cb());

    sched.run_until_idle();

    CHECK(a_tokens == std::vector<TokenId>{1});
    CHECK(b.tokens == std::vector<TokenId>{4});
    CHECK(sched.finished(ra));
    CHECK(sched.finished(rb));
}

TEST_CASE("max_tokens is enforced per request") {
    MockBackend backend;
    setup(backend);
    backend.decode_result = peak(kVocab, 2);  // token 2 forever

    Scheduler sched(backend, {1});
    Collector a;
    sched.submit({10}, greedy(/*max_tokens=*/3), a.cb());
    sched.run_until_idle();

    CHECK(a.tokens == std::vector<TokenId>{2, 2, 2});
}

TEST_CASE("a prompt that can never fit is rejected at submit") {
    MockBackend backend;
    setup(backend);
    backend.context_length_value = 4;

    Scheduler sched(backend, {2});
    CHECK_THROWS_AS(
        sched.submit({1, 2, 3, 4, 5}, greedy(), [](TokenId) { return true; }),
        EngineError);
}

TEST_CASE("a backend failure fails in-flight requests, scheduler survives") {
    MockBackend backend;
    setup(backend);

    Scheduler sched(backend, {2});
    Collector a;
    const auto ra = sched.submit({10}, greedy(), a.cb());

    backend.fail_decodes = true;
    sched.run_until_idle();

    CHECK(sched.finished(ra));
    CHECK(sched.error(ra) != nullptr);

    // Recovered: a new request completes normally.
    backend.fail_decodes = false;
    backend.seq_decode_queues.clear();
    backend.seq_decode_queues[0] = {peak(kVocab, 1), peak(kVocab, kEos)};
    Collector c;
    const auto rc = sched.submit({30}, greedy(), c.cb());
    sched.run_until_idle();

    CHECK(sched.finished(rc));
    CHECK(sched.error(rc) == nullptr);
    CHECK(c.tokens == std::vector<TokenId>{1});
}

TEST_CASE("idle scheduler reports no work") {
    MockBackend backend;
    setup(backend);
    Scheduler sched(backend, {2});
    CHECK_FALSE(sched.step());
    CHECK(sched.active_count() == 0);
}
