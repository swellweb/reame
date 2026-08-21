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
          // I tipi dei token (formato v7) fanno riconoscere interi i token
          // di controllo che NON rispettano il pattern <|...|> — <think>
          // in testa. Senza, la codifica li spezza in frammenti mai visti
          // in addestramento e il modello risponde frammenti in ciclo:
          // successo davvero, con Bonsai. Sui .nuc vecchi il campo e'
          // vuoto e non cambia niente.
          tokenizzatore_(modello_.vocabolario, modello_.fusioni,
                         modello_.tipi_token),
          motore_(modello_, static_cast<std::uint32_t>(params.context_length),
                  params.threads) {
        if (!modello_.vocab_uscita.empty())
            throw ModelError(
                "il server richiede un .nuc a testa piena: quello potato "
                "emette solo il vocabolario del suo corpus");
        fine_turno_ = token_unico("<|im_end|>");
        fine_testo_ = token_unico("<|endoftext|>");
        if (fine_turno_ < 0 && fine_testo_ < 0)
            throw ModelError(
                "il vocabolario non ha ne' <|im_end|> ne' <|endoftext|>: "
                "senza un token di fine la generazione non sa fermarsi");
        // La famiglia thinking (Bonsai/Qwen3.6): se <think> e' un token di
        // controllo, il template DEVE aprire il blocco di ragionamento —
        // il modello e' addestrato cosi'. Il server lo chiude subito
        // (thinking spento): a pochi token al secondo, i token di pensiero
        // sono un lusso che una risposta HTTP non puo' pagare.
        pensa_ = token_unico("<think>") >= 0 && token_unico("</think>") >= 0;
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
        // La verifica speculativa: i logit di OGNI posizione, coi pesi
        // letti una volta per lotto (avanza_lotto, al massimo 8 posizioni
        // per volta). E' cio' che rende la speculazione conveniente anche
        // su questo backend.
        std::vector<std::vector<float>> tutti;
        tutti.reserve(tokens.size());
        std::vector<float> logit_tutti;
        std::size_t da = 0;
        while (da < tokens.size()) {
            const std::size_t quanti =
                std::min<std::size_t>(8, tokens.size() - da);
            const std::vector<int> lotto(tokens.begin() + da,
                                         tokens.begin() + da + quanti);
            motore_.continua_lotto(lotto, logit_tutti);
            const std::size_t n_logit = logit_tutti.size() / quanti;
            for (std::size_t t = 0; t < quanti; ++t)
                tutti.emplace_back(
                    logit_tutti.begin() + t * n_logit,
                    logit_tutti.begin() + (t + 1) * n_logit);
            da += quanti;
        }
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
        // Il blocco di ragionamento chiuso subito: la forma "thinking
        // spento" del template ufficiale (pinnata dal tokenizer.chat_template
        // del GGUF di Bonsai). Senza questo prefisso il modello parte
        // orfano e la generazione degenera.
        if (pensa_) testo += "<think>\n\n</think>\n\n";
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

    TokenId eos_token() const override {
        return fine_testo_ >= 0 ? fine_testo_ : fine_turno_;
    }

    bool is_eog(TokenId token) const override {
        return token == fine_turno_ || token == fine_testo_;
    }

    bool supports_rollback() const override { return true; }

private:
    // L'id del marcatore se il vocabolario lo codifica come UN token; -1
    // altrimenti. La vecchia codifica(...)[0] prendeva il primo frammento
    // BPE e lo stop diventava un token qualunque, in silenzio.
    int token_unico(const std::string& testo) const {
        const auto ids = tokenizzatore_.codifica(testo);
        return ids.size() == 1 ? ids[0] : -1;
    }

    nucleo::Modello modello_;
    nucleo::Tokenizzatore tokenizzatore_;
    nucleo::Motore motore_;
    TokenId fine_turno_ = -1;
    TokenId fine_testo_ = -1;
    bool pensa_ = false;
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
