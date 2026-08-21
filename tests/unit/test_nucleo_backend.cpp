// Il backend nucleo del server, sui punti che Bonsai ha insegnato a botte:
// i token di controllo fuori dal pattern <|...|> (v7), il blocco di
// ragionamento nel template, gli stop token verificati e non presunti.
//
// I modelli sono i giocattoli di nucleo-dev, convertiti al volo: piccoli
// abbastanza da stare in un test, veri abbastanza da esercitare l'intera
// catena GGUF -> .nuc -> backend.

#include <catch2/catch_test_macros.hpp>

#if defined(REAME_HAS_NUCLEO)

#include <cstdio>
#include <string>

#include "nucleo/formato.hpp"
#include "reame/core/model.hpp"
#include "reame/core/nucleo_backend.hpp"

namespace {

// Il giocattolo qwen35 (Bonsai in miniatura): ha <think> e </think> come
// token di CONTROLLO nel vocabolario. Convertito una volta per la suite.
const std::string& bonsai_nuc() {
    static const std::string percorso = [] {
        const std::string dest = "/tmp/reame_test_bonsai.nuc";
        nucleo::converti(std::string(TEST_NUCLEO_DIR) +
                             "/tests/dati/bonsai_finto.gguf",
                         dest);
        return dest;
    }();
    return percorso;
}

reame::ModelParams parametri(const std::string& percorso) {
    reame::ModelParams p;
    p.path = percorso;
    p.context_length = 64;
    p.threads = 2;
    return p;
}

}  // namespace

TEST_CASE("il backend nucleo inietta il blocco think per i modelli thinking",
          "[nucleo_backend]") {
    auto backend = reame::make_nucleo_backend(parametri(bonsai_nuc()));
    const auto testo = backend->format_chat({{"user", "ciao"}});
    // Il template ufficiale di Bonsai: assistant apre e CHIUDE il
    // ragionamento (thinking spento) — senza questo prefisso il modello
    // parte orfano e la generazione degenera.
    const std::string coda = "<|im_start|>assistant\n<think>\n\n</think>\n\n";
    REQUIRE(testo.size() >= coda.size());
    CHECK(testo.compare(testo.size() - coda.size(), coda.size(), coda) == 0);
}

TEST_CASE("il backend nucleo codifica <think> come UN token (v7)",
          "[nucleo_backend]") {
    auto backend = reame::make_nucleo_backend(parametri(bonsai_nuc()));
    // Nel giocattolo <think> e' il token 30 e </think> il 31: se il
    // tokenizzatore del server non ricevesse i tipi, uscirebbero frammenti.
    const auto ids = backend->tokenize("<think>", false);
    REQUIRE(ids.size() == 1);
    CHECK(ids[0] == 30);
}

TEST_CASE("senza marcatori di fine il backend rifiuta di partire",
          "[nucleo_backend]") {
    // Il giocattolo MoE v5 (fixture congelata di nucleo-dev) non ha
    // <|im_end|> ne' <|endoftext|> nel suo vocabolario finto (t0..t31):
    // una generazione che non sa fermarsi e' un server che scrive
    // all'infinito — meglio un errore chiaro all'avvio.
    CHECK_THROWS(reame::make_nucleo_backend(
        parametri(std::string(TEST_NUCLEO_DIR) + "/tests/dati/moe_v5.nuc")));
}

#else

TEST_CASE("backend nucleo assente: il test non ha niente da dire",
          "[nucleo_backend]") {
    SKIP("compilato senza REAME_HAS_NUCLEO");
}

#endif
