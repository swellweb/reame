// Isolated tests for the escalation policy: when the fast lane's answer is a
// refusal, the request is retried on the deep lane. The policy is pure
// (string in, verdict out) and the URL parser feeds the HTTP client; both are
// testable without sockets, and every expected value here is derived from the
// rules by hand.

#include <catch2/catch_test_macros.hpp>

#include "reame/server/escalation.hpp"

using reame::server::Escalation;

// ---------------------------------------------------------------------------
// the decision
// ---------------------------------------------------------------------------

TEST_CASE("il rifiuto letterale scala") {
    CHECK(Escalation::dovrebbe("NON PRESENTE", "NON PRESENTE"));
}

TEST_CASE("il rifiuto scala anche minuscolo e dentro una frase") {
    CHECK(Escalation::dovrebbe("Mi spiace, non presente nel documento.",
                               "NON PRESENTE"));
}

TEST_CASE("una risposta vera non scala") {
    CHECK_FALSE(Escalation::dovrebbe("35,00 € al metro quadro",
                                     "NON PRESENTE"));
}

TEST_CASE("la risposta vuota e' un fallimento della corsia rapida e scala") {
    CHECK(Escalation::dovrebbe("", "NON PRESENTE"));
    CHECK(Escalation::dovrebbe("   \n", "NON PRESENTE"));
}

TEST_CASE("trigger vuoto significa escalation spenta") {
    CHECK_FALSE(Escalation::dovrebbe("NON PRESENTE", ""));
    CHECK_FALSE(Escalation::dovrebbe("", ""));
}

TEST_CASE("il trigger e' una regex con alternative") {
    CHECK(Escalation::dovrebbe("boh, non saprei dirti",
                               "NON PRESENTE|non saprei"));
}

// ---------------------------------------------------------------------------
// the endpoint URL
// ---------------------------------------------------------------------------

TEST_CASE("un endpoint completo si scompone in host porta e percorso") {
    const auto u = Escalation::analizza("http://127.0.0.1:8080/v1/chat/completions");
    CHECK(u.valida);
    CHECK(u.host == "127.0.0.1");
    CHECK(u.port == 8080);
    CHECK(u.path == "/v1/chat/completions");
}

TEST_CASE("la porta assente vale 80 e il percorso assente vale slash") {
    const auto u = Escalation::analizza("http://box2");
    CHECK(u.valida);
    CHECK(u.host == "box2");
    CHECK(u.port == 80);
    CHECK(u.path == "/");
}

TEST_CASE("schemi diversi da http vengono rifiutati") {
    CHECK_FALSE(Escalation::analizza("ftp://x/y").valida);
    CHECK_FALSE(Escalation::analizza("non-un-url").valida);
}

TEST_CASE("la porta non numerica invalida l'endpoint") {
    CHECK_FALSE(Escalation::analizza("http://host:porta/x").valida);
}
