> ⚠️ Questa traduzione può restare indietro: fa fede il [README inglese](../README.md).

# Reame

**Server di inferenza LLM snello e interamente testato, costruito su
[llama.cpp](https://github.com/ggml-org/llama.cpp) — pensato per l'hardware che
hai già: vCPU condivise, free tier, macchine ARM a 2 core.**

Reame è costruito per la CPU economica come prima scelta, non come ripiego per
la GPU assente. La tesi è semplice:

> **Su una CPU, mai calcolare due volte la stessa cosa.**

## A cosa serve

Carichi di lavoro **ristretti e ripetitivi sui tuoi dati, su hardware che già
paghi** — il caso in cui la risposta sta nel contesto che fornisci, non nella
conoscenza generale del modello. Lì un modello piccolo pareggia uno frontier
(misurato: 100% di accuratezza in estrazione long-context con un 7B su una
macchina ARM gratuita a 2 core) e la memoria di Reame rende la richiesta #100
una frazione del costo della #1: estrazione e classificazione di documenti
(RAG, fatture, ticket), pipeline batch notturne, feature AI in SaaS a margini
sottili, lavoro vincolato alla privacy (legale, medico, PA), autocompletamento
di codice privato.

**A cosa NON serve**: sostituire ChatGPT come tuttofare, assistenti di coding
agentici, scrittura creativa lunga su larga scala. Se il task richiede un
cervello da 100B, compralo.

## Come funziona

- 🗂️ **KV cache persistente a prefissi condivisi** — i prefissi dei prompt sono
  fotografati su disco (zstd, checksum, budget LRU) e riusati **tra prompt
  diversi, riavvii e processi**. Un system prompt si paga una volta sola.
- 📜 **Palimpsest: il server ricorda ciò che ha generato** — ogni generazione
  completata alimenta un archivio n-gram su disco; le richieste future ne
  pescano bozze a costo zero.
- 🎭 **Il Suggeritore** — il constrained decoding usa la struttura per *vietare*
  token; Reame la inverte e la usa per *proporli*: numerazioni, bullet e token
  di formato sono speculati gratis anche su contenuto mai generato prima.
- 🔮 **Speculative decoding autoregolante** — un modello draft *oppure* il
  lookup n-gram a costo zero propone token; il target li verifica in un solo
  passaggio batched. Reame *misura* se la speculazione rende sul tuo hardware
  e la spegne da sola quando non rende.
- 🏛️ **Il Conclave** — `--best-of N` genera N risposte in un unico batch
  interlacciato (un solo prefill, clonato via copia KV) ed elegge la vincente
  a maggioranza; al raggiungimento della maggioranza assoluta i ritardatari
  vengono fermati. Corregge la varianza, non il bias: più accuratezza dal
  modello che già fai girare, non un 1.5B che ragiona da 3B.
- 👥 **Serving multi-utente interlacciato** — N generazioni concorrenti
  avanzano insieme in batch multi-sequenza, condividendo ogni lettura dei
  pesi (il costo dominante del decode CPU memory-bound).
- 🌐 **API REST compatibile OpenAI** — `/v1/completions`,
  `/v1/chat/completions` (col chat template del modello), streaming SSE,
  sessioni, bearer auth, metriche.
- ⚡ **CLI zero-config** — `reame run qwen2.5-1.5b` scarica il modello una
  volta e sceglie da sé thread, quantizzazione KV e cache per l'host.

I numeri (misurati, inclusi i risultati negativi) sono nel
[README inglese](../README.md#measured-results).

## Installazione

**Homebrew** (macOS / Linux):

```bash
brew tap swellweb/reame
brew install reame
```

**Binari precompilati** — Linux x64/arm64 e macOS arm64 nella
[pagina release](https://github.com/swellweb/reame/releases)
(dipendenza runtime: libzstd).

## Avvio rapido

```bash
reame list                                  # catalogo modelli + cosa c'è su disco
reame run qwen2.5-1.5b                      # download una tantum, auto-config, chat
reame run qwen2.5-1.5b "Spiega mmap"        # risposta one-shot
reame run qwen2.5-1.5b --serve              # API compatibile OpenAI su :8080
reame run qwen2.5-1.5b "12*13-50?" --best-of 5   # il Conclave
```

## Compilazione dai sorgenti

```bash
git clone https://github.com/swellweb/reame
cd reame
git submodule update --init --depth 1 third_party/llama.cpp
./build.sh                       # Release + suite di test completa

./scripts/download_models.sh     # TinyLlama (modello di test, ~670 MB)

./build/src/reame --config config/reame.conf --prompt "Ciao" --max-tokens 32
./build/src/reame --config config/reame.conf --serve
```

Dipendenze: CMake ≥ 3.16, compilatore C++17 e, per il server, Boost (header),
nlohmann-json e zstd:

```bash
# Debian/Ubuntu
sudo apt install build-essential cmake libboost-dev nlohmann-json3-dev libzstd-dev pkg-config
# macOS
brew install cmake boost nlohmann-json zstd pkg-config
```

### API

| Endpoint | Descrizione |
|---|---|
| `GET /health` | liveness (senza auth) |
| `GET /v1/models` | modello configurato |
| `POST /v1/completions` | completion (SSE con `"stream": true`) |
| `POST /v1/chat/completions` | chat completion (SSE con `"stream": true`) |
| `POST /v1/sessions` · `.../save` · `.../load` · `DELETE .../{id}` | sessioni KV |
| `GET /metrics` | contatori server + metriche speculative |

Con `server.api_key` impostata serve `Authorization: Bearer <key>`
(tranne `/health`). Configurazione: [config/reame.conf](../config/reame.conf)
(formato INI, chiavi lette come `sezione.chiave`) — con il default
`mode = lookup` basta un solo file GGUF.

## Sviluppo (TDD)

Ogni unità ha il suo test isolato in `tests/unit/` (dipendenze mockate).
Ciclo: test RED → implementazione GREEN → lint → commit. I benchmark nel
README sono prodotti dal binario spedito sull'hardware dichiarato; anche i
risultati negativi vengono documentati.
