#include "reame/arca/semantic_index.hpp"

#include <cmath>

namespace reame::arca {

float cosine_similarity(const std::vector<float>& a,
                        const std::vector<float>& b) {
    if (a.size() != b.size() || a.empty()) return 0.0f;
    double dot = 0.0, na = 0.0, nb = 0.0;
    for (std::size_t i = 0; i < a.size(); ++i) {
        dot += static_cast<double>(a[i]) * b[i];
        na += static_cast<double>(a[i]) * a[i];
        nb += static_cast<double>(b[i]) * b[i];
    }
    if (na == 0.0 || nb == 0.0) return 0.0f;  // zero vector: no direction
    return static_cast<float>(dot / (std::sqrt(na) * std::sqrt(nb)));
}

void SemanticIndex::add(const std::vector<float>& embedding,
                        const std::string& value) {
    entries_.push_back({embedding, value});
}

std::optional<std::string> SemanticIndex::nearest(
    const std::vector<float>& query, float min_similarity) const {
    const std::string* best = nullptr;
    float best_sim = min_similarity;  // must strictly clear the threshold
    for (const auto& e : entries_) {
        const float sim = cosine_similarity(query, e.embedding);
        if (sim >= best_sim) {
            best_sim = sim;
            best = &e.value;
        }
    }
    if (best == nullptr) return std::nullopt;
    return *best;
}

}  // namespace reame::arca
