// Isolated tests for the L2 semantic index — pure cosine-similarity vector
// search. Every expected similarity is computed by hand so a wrong answer
// (the real risk of a semantic cache) can never hide behind a fuzzy test.

#include <catch2/catch_test_macros.hpp>
#include <catch2/matchers/catch_matchers_floating_point.hpp>

#include "reame/arca/semantic_index.hpp"

using Catch::Matchers::WithinAbs;
using reame::arca::cosine_similarity;
using reame::arca::SemanticIndex;

TEST_CASE("cosine: identical, orthogonal, and 45 degrees") {
    CHECK_THAT(cosine_similarity({1, 0}, {1, 0}), WithinAbs(1.0, 1e-6));
    CHECK_THAT(cosine_similarity({1, 0}, {0, 1}), WithinAbs(0.0, 1e-6));
    // {1,0} vs {1,1}: dot 1, norms 1 and sqrt(2) -> 1/sqrt(2).
    CHECK_THAT(cosine_similarity({1, 0}, {1, 1}),
               WithinAbs(0.70710678, 1e-6));
    // Magnitude does not matter, only direction: {2,0} ~ {5,0} -> 1.
    CHECK_THAT(cosine_similarity({2, 0}, {5, 0}), WithinAbs(1.0, 1e-6));
    // Opposite direction -> -1.
    CHECK_THAT(cosine_similarity({1, 0}, {-1, 0}), WithinAbs(-1.0, 1e-6));
}

TEST_CASE("cosine: degenerate vectors are zero similarity, never NaN") {
    CHECK_THAT(cosine_similarity({0, 0}, {1, 0}), WithinAbs(0.0, 1e-9));
    CHECK_THAT(cosine_similarity({}, {}), WithinAbs(0.0, 1e-9));
    // Mismatched dimensions: treated as no match, not a crash.
    CHECK_THAT(cosine_similarity({1, 0}, {1, 0, 0}), WithinAbs(0.0, 1e-9));
}

TEST_CASE("index: an exact-direction query returns the stored value") {
    SemanticIndex idx;
    idx.add({1, 0, 0}, "france");
    const auto hit = idx.nearest({2, 0, 0}, /*min_similarity=*/0.9f);
    REQUIRE(hit.has_value());
    CHECK(*hit == "france");
}

TEST_CASE("index: below the threshold is a miss") {
    SemanticIndex idx;
    idx.add({1, 0}, "france");
    // {1,0} vs {1,1} = 0.707 < 0.9 -> miss.
    CHECK_FALSE(idx.nearest({1, 1}, 0.9f).has_value());
    // Same query, looser threshold -> hit.
    CHECK(idx.nearest({1, 1}, 0.7f).has_value());
}

TEST_CASE("index: returns the closest of several") {
    SemanticIndex idx;
    idx.add({1, 0}, "france");
    idx.add({0, 1}, "germany");
    idx.add({1, 1}, "europe");
    // Query {0.9, 0.1}: closest to {1,0} (france).
    const auto hit = idx.nearest({0.9f, 0.1f}, 0.5f);
    REQUIRE(hit.has_value());
    CHECK(*hit == "france");
}

TEST_CASE("index: empty index and degenerate query miss cleanly") {
    SemanticIndex idx;
    CHECK_FALSE(idx.nearest({1, 0}, 0.5f).has_value());
    idx.add({1, 0}, "x");
    CHECK_FALSE(idx.nearest({0, 0}, 0.5f).has_value());  // zero query
    CHECK(idx.size() == 1);
}
