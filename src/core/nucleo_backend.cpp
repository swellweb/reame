#include "reame/core/nucleo_backend.hpp"

#include <algorithm>
#include <stdexcept>

#include "reame/core/model.hpp"

#if defined(REAME_HAS_NUCLEO)

#include "nucleo/campionatore.hpp"
#include "nucleo/formato.hpp"
#include "nucleo/motore.hpp"
#include "nucleo/tokenizzatore.hpp"

namespace reame {
namespace {

class NucleoBackend final : public LlamaBackend {
public:
    explicit NucleoBackend(const ModelParams& params)
        : modello_(params.path),
          tokenizzatore_(modello_.vocabolario, modello_.fusioni),
          motore_(modello_, static_cast<std::uint32_t>(params.context_length),
                  params.threads) {
        if (!modello_.vocab_uscita.empty())
            throw ModelError(
                "il server richiede un .nuc a testa piena: quello potato "
                "emette solo il vocabolario del suo corpus");
        fine_turno_ = tokenizzatore_.codifica("<|im_end|>")[0];
        fine_testo_ = tokenizzatore_.codifica("<|endoftext|>")[0];
    }

    std::vector<TokenId> tokenize(const std::string& text,
                                  bool /*add_special*/) override {
        const auto ids = tokenizzatore_.codifica(text);
        return {ids.begin(), ids.end()};
    }

    std::string detokenize(const std::vector<TokenId>& tokens) override {
        return tokenizzatore_.decodifica({tokens.begin(), tokens.end()});
    }

    std::string token_piece(TokenId token) override {
        return tokenizzatore_.decodifica({static_cast<int>(token)});
    }

    std::vector<float> decode(const std::vector<TokenId>& tokens) override {
        motore_.riparti();
        return decode_append(tokens);
    }

    std::vector<float> decode_append(
        const std::vector<TokenId>& tokens) override {
        const auto& logit =
            motore_.continua({tokens.begin(), tokens.end()});
        return {logit.begin(), logit.end()};
    }

    std::vector<std::vector<float>> decode_batch(
        const std::vector<TokenId>& tokens) override {
        // Corretta ma lenta: un forward per posizione. La verifica
        // speculativa la usa; su questo backend la speculazione non
        // conviene finche' il motore non restituisce i logit di ogni
        // posizione in un passaggio solo.
        std::vector<std::vector<float>> tutti;
        tutti.reserve(tokens.size());
        for (const TokenId t : tokens)
            tutti.push_back(decode_append({t}));
        return tutti;
    }

    void truncate_to(std::uint32_t n_tokens) override {
        motore_.tronca(n_tokens);
    }

    std::vector<std::vector<float>> decode_seqs(
        const std::vector<SeqSlice>& slices) override {
        if (slices.size() != 1)
            throw ModelError(
                "backend nucleo v1: una sola sequenza (multi-utente "
                "interlacciato non ancora supportato)");
        return {decode_append(slices[0].tokens)};
    }

    std::string format_chat(const std::string& user_message) override {
        return format_chat(
            std::vector<ChatMessage>{{"user", user_message}});
    }

    std::string format_chat(
        const std::vector<ChatMessage>& messages) override {
        // ChatML: il template della famiglia Qwen, l'unica che il nucleo
        // esegue oggi.
        std::string testo;
        for (const auto& m : messages)
            testo += "<|im_start|>" + m.role + "\n" + m.content +
                     "<|im_end|>\n";
        testo += "<|im_start|>assistant\n";
        return testo;
    }

    void clear_seq(std::int32_t /*seq_id*/) override { motore_.riparti(); }

    void copy_seq(std::int32_t, std::int32_t, std::uint32_t) override {
        throw ModelError("backend nucleo v1: copy_seq non supportata");
    }

    void reset() override { motore_.riparti(); }

    std::vector<char> state_data() override { return motore_.stato(); }

    void set_state(const std::vector<char>& data,
                   std::uint32_t n_past) override {
        motore_.carica_stato(data, n_past);
    }

    std::uint32_t n_past() const override { return motore_.posizioni(); }

    std::int32_t vocab_size() const override {
        return static_cast<std::int32_t>(modello_.p.n_vocab);
    }

    std::uint32_t context_length() const override {
        return motore_.configurazione().n_ctx;
    }

    TokenId eos_token() const override { return fine_testo_; }

    bool is_eog(TokenId token) const override {
        return token == fine_turno_ || token == fine_testo_;
    }

    bool supports_rollback() const override { return true; }

private:
    nucleo::Modello modello_;
    nucleo::Tokenizzatore tokenizzatore_;
    nucleo::Motore motore_;
    TokenId fine_turno_ = 0;
    TokenId fine_testo_ = 0;
};

}  // namespace

std::unique_ptr<LlamaBackend> make_nucleo_backend(const ModelParams& params) {
    return std::make_unique<NucleoBackend>(params);
}

}  // namespace reame

#else  // il nucleo non era disponibile alla build

namespace reame {
std::unique_ptr<LlamaBackend> make_nucleo_backend(const ModelParams&) {
    throw ModelError(
        "questo binario e' stato compilato senza il motore nucleo: "
        "ricompila con -DREAME_NUCLEO_DIR=<percorso di nucleo-dev>");
}
}  // namespace reame

#endif
