#pragma once

#include <optional>
#include <string>
#include <vector>

namespace reame::arca {

// Cosine similarity of two vectors in [-1, 1]: dot(a,b) / (|a| |b|).
// Returns 0 (not NaN) when either vector is zero-length or the dimensions
// differ — a degenerate input is "no match", never a crash.
float cosine_similarity(const std::vector<float>& a,
                        const std::vector<float>& b);

// The L2 semantic index: stores (embedding, value) pairs and answers
// "what stored value is closest in meaning to this query?" via cosine
// similarity. This is the pure search core of the semantic cache — no
// model here; an embedder turns text into the vectors it holds.
//
// nearest() returns a stored value only when its similarity clears
// min_similarity, the tunable that trades hit rate against the real risk
// of a semantic cache: serving the answer to a *different* question that
// merely embeds nearby. A high threshold is the safe default.
class SemanticIndex {
public:
    void add(const std::vector<float>& embedding, const std::string& value);

    std::optional<std::string> nearest(const std::vector<float>& query,
                                       float min_similarity) const;

    std::size_t size() const { return entries_.size(); }

private:
    struct Entry {
        std::vector<float> embedding;
        std::string value;
    };
    std::vector<Entry> entries_;
};

}  // namespace reame::arca
