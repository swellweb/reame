#pragma once

// Il backend "nucleo": il motore di inferenza scritto in casa, al posto di
// llama.cpp, dietro la stessa interfaccia. Si attiva da solo quando
// model.path finisce in ".nuc" — il formato di esecuzione del nucleo,
// prodotto dal suo convertitore a partire da un GGUF.
//
// Perche' esiste: sul target di Reame (2-4 core ARM, classe 0.5-3B) il
// nucleo decodifica il 20-30% piu' veloce di llama.cpp, e il formato .nuc
// elimina il repack in RAM (misurati 4,2 GB risparmiati a ogni avvio).
//
// Limiti della v1, dichiarati invece che scoperti: una sola sequenza
// (niente multi-utente interlacciato ne' copy_seq), e la verifica
// speculativa per-posizione e' un ciclo lento — corretta, non veloce.

#include <memory>

#include "reame/core/llama_backend.hpp"

namespace reame {

// Compilato solo se il nucleo e' disponibile alla build (REAME_HAS_NUCLEO);
// altrimenti lancia ModelError con una spiegazione utile.
std::unique_ptr<LlamaBackend> make_nucleo_backend(const ModelParams& params);

}  // namespace reame
