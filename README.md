***

<p align="center">
  <img src="docs/figures/logo.svg" alt="Reame" width="300">
</p>

<p align="center">
  <a href="https://swellweb.github.io/reame/"><b>▶ Try the live demo</b></a> — a real Reame instance serving an LLM from a free Oracle ARM box, directly in your browser.
</p>

**Reame is an LLM server designed for ordinary CPUs, specifically built around ternary models — where weights are strictly −1, 0, or +1. You can run an 8-billion-parameter model in just 2.2 GB on a free-tier cloud instance, using a custom engine that actually outperforms the model vendor's own runtime.**

These aren't just marketing claims; they are measured. Running Bonsai-8B (PrismML's ternary flagship) against PrismML's own llama.cpp fork on the same hardware, using identical prompts and clean environments:

|  | Decode | Prompt Processing |
|---|---|---|
| **2 ARM cores** (Oracle Always Free) | **2.8 vs 2.46 tok/s (+14%)** | **4.3 vs 2.77 tok/s (+55%)** |
| **4 ARM cores** | **5.7 vs 4.84 tok/s (+18%)** | **7.9 vs 5.5 tok/s (+44%)** |

These figures are the median of three back-to-back runs. Accuracy sits at 19/20 on a twenty-question fact exam run against the deployed server (the missed question is a borderline knowledge fact that the same weights answer correctly when allowed to reason first). The full methodology, raw numbers, and even the benchmarks we *lose* are documented in **[docs/BENCHMARKS.md](docs/BENCHMARKS.md)**. A benchmark page that only shows wins is just advertising.

No GPU required. No per-token billing. Just a single OpenAI-compatible API that any existing client can connect to. Under the hood, it relies on two engines: **nucleo**, our custom engine built from scratch (which handles the ternary numbers above), and **[llama.cpp](https://github.com/ggml-org/llama.cpp)** for everything else.

![Two engines under one API](docs/figures/due-motori.svg)

---

## Why ternary, and why this engine

A ternary model stores each weight as one of three values. This means Bonsai-8B fits into just 2.2 GB — well within the RAM limits of a free cloud instance. On a CPU, the matrix products become highly efficient integer operations that vector instructions can process rapidly.

nucleo converts the model **once** into its own interleaved 2.125-bit format (`.nuc`), including the head and embeddings — meaning no tensor is silently kept at 6 bits. The hot loop accumulates an entire 128-weight block in exact int32 before a single floating-point operation occurs. Attention runs vectorized fp16 against the KV cache and scales across cores as the context grows. The engine was built test-first: 149 test cases, 254,000 assertions, and every kernel is validated against an independent oracle. Its single-token and batch paths produce bit-identical output by construction.

None of this code is derived from llama.cpp — llama.cpp is simply what we benchmark against.

## Get started with the ternary model

```bash
git clone https://github.com/swellweb/reame
cd reame && ./build.sh
```

```bash
# 1. download Bonsai-8B ternary (2.1 GB) from PrismML's official repo
curl -LO https://huggingface.co/prism-ml/Ternary-Bonsai-8B-gguf/resolve/main/Ternary-Bonsai-8B-Q2_0.gguf

# 2. convert once (about a minute; produces a 2.2 GB .nuc)
./build/src/reame-converti Ternary-Bonsai-8B-Q2_0.gguf bonsai-8b.nuc

# 3. serve it
./build/src/reame run bonsai-8b.nuc --serve
```

```bash
curl http://127.0.0.1:8080/v1/chat/completions -d '{
  "model": "reame",
  "messages": [{"role": "user", "content": "Ciao!"}]
}'
```

The 1.7B variant works the same way (`Ternary-Bonsai-1.7B-gguf`, 460 MB) and delivers 16-19 tok/s on the same free box. Conventional GGUF models still run through the llama.cpp lane — `reame run qwen2.5-1.5b` downloads and serves one in a single command. A configuration file is available for finer control (see [Configuration](#configuration)).

<details>
<summary><b>Build dependencies</b></summary>

CMake ≥ 3.16, C++20, Boost headers, nlohmann-json, zstd.

```bash
# Debian/Ubuntu
sudo apt install build-essential cmake libboost-dev nlohmann-json3-dev libzstd-dev pkg-config
# macOS
brew install cmake boost nlohmann-json zstd pkg-config
```
</details>

---

## What can I do with it?

### Put a concierge on your website

Imagine a visitor asking: *"How much would that smooth floor cost for my living room?"* Your price list calls it "self-levelling epoxy resin for residential interiors," a term the visitor neither knows nor cares about. Reame understands the intent and replies with "€35.00 per m²" in seconds, running on a free-tier instance.

It offers a guarantee a bare LLM cannot: when the answer is a specific piece of data — a price, a phone number, or opening hours — Reame does not generate it. It copies the value verbatim from your database. Hallucinating a price is structurally impossible, and if the information isn't there, the system says so rather than guessing.

![The concierge cascade](docs/figures/concierge-cascata.svg)

### And the rest

| You want to… | Reame gives you |
|---|---|
| extract data from documents (invoices, tickets, pages) | small model + disk cache: repeated work becomes nearly free |
| run overnight batch jobs (tag 10k products, triage email) | €0 per token, no rate limits, no data leaving your server |
| add AI to a thin-margin SaaS | a €5 VPS instead of a metered API |
| keep legal/medical/public-sector data private | everything runs and stays on your infrastructure |
| set up private code autocomplete | an OpenAI-compatible endpoint for Continue.dev |

**Not for**: Replacing ChatGPT as an all-rounder, agentic coding, or creative long-form writing. Small models on CPUs excel at narrow work over *your* context — that is the niche, and it is a significant one.

---

## How it works, in plain words

Four core ideas, each one measured. Everything else is just plumbing.

**1 — Convert once, never again.** Most runtimes reorganize the model's weights at every boot: minutes of processing, gigabytes of RAM, repeated endlessly. nucleo converts **once** to a `.nuc` file; the server simply maps it — **99 MB of RAM at startup**, ready in seconds.

**2 — Never read the same thing twice.** Processing text is the computationally expensive part on a CPU. To solve this, Reame saves a snapshot of what it has read (the *prefix cache*, on disk) and reuses it across requests, restarts, and different prompts that share a common beginning. An identical request takes half a second.

![Shared-prefix cache](docs/figures/prefix-cache.svg)

**3 — Read ahead, while nobody is waiting.** When a visitor opens your page, the widget pings Reame (`/v1/warm`), and the model starts reading the document *while the visitor is still reading the page*. By the time the question arrives, the heavy lifting is already done.

![Warm-ahead](docs/figures/warm-ahead.svg)

**4 — Understand with models, answer with data.** Language comprehension is handled by real LLMs, which is why the system survives questions phrased in a user's own words. However, the actual *values* in the answers come from your data, copied verbatim. Simple, unambiguous requests skip the models entirely (~20 ms). Anything uncertain goes to the small model, and if that fails, it escalates to a larger one via the `[escalation]` relay.

---

## The numbers

Every figure was measured on the specified hardware using the shipped binary. The methodology for each is in **[docs/BENCHMARKS.md](docs/BENCHMARKS.md)**, negative results included.

| What | Measured | Where |
|---|---|---|
| Bonsai-8B ternary vs the vendor's own runtime | **decode +14-18%, prompt +44-55%** | Oracle free tier, 2 and 4 cores |
| Fact exam on the deployed ternary lane | **19/20**, stable across four deployments | Oracle free tier |
| Bonsai-8B on disk and in RAM | **2.2 GB** (2.125 bits/weight, end to end) | — |
| Bonsai-1.7B decode on the same free box | **20.9 tok/s** at 4 cores | Oracle free tier |

What we do **not** claim: being the fastest ternary engine everywhere. llama.cpp mainline's TQ2_0 path is currently faster on the 1.7B model and on Apple Silicon. The full table, including those rows, is on the benchmarks page, right next to what we are doing to close that gap.

---

## Configuration

```ini
[model]
path = models/bonsai-8b.nuc      ; .nuc → nucleo engine, .gguf → llama.cpp
context_length = 4096
threads = 4                      ; fewer is often faster on shared vCPUs — measure!

[cache]
directory = .reame-cache
max_size_mb = 4096               ; disk budget for the prefix snapshots

[server]
port = 8080
api_key =                        ; bearer auth when set
parallel = 1                     ; >1 = interleaved multi-user serving

[escalation]                     ; the relay to a bigger model (optional)
endpoint = http://127.0.0.1:8081/v1/chat/completions
trigger = NON PRESENTE           ; regex; a blank answer always escalates
model_id = big-model
```

When the small model's response matches the trigger, the request is replayed on the deep endpoint, and the new answer is returned flagged with `"escalated": true`. If the larger model fails, the initial fast response is kept. The relay is designed to only improve the outcome.

## API

| Endpoint | What it does |
|---|---|
| `POST /v1/chat/completions` | chat (SSE streaming with `"stream": true`) |
| `POST /v1/completions` | plain completion |
| `POST /v1/warm` | pre-read a `prompt` or `messages` prefix, so the real request starts warm |
| `POST /v1/sessions` + save/load | snapshot and restore a conversation |
| `GET /metrics` · `GET /health` | counters · liveness |

---

## In addition

We believe publishing what failed is half the value of the project:

- **Similarity cannot detect absence.** Embedding scores for answerable and not-in-the-data questions overlap almost completely (medians 0.895 vs 0.879). The concierge *computes* refusals based on evidence instead.
- **Three kernel designs lost to their own predecessors** — a sum-trick on the per-16 path, wide unpacking in the batch kernel, and a tiled prefill buffer. Each was prototyped, measured, and ultimately reverted; each is documented next to the design that won.
- **Fewer MoE experts help prefill (+44%) but hurt decode.** At K=2 the model collapses entirely (0/20). The rule is: read with few, write with all.
- **Speculation on oversubscribed vCPUs is counterproductive.** Reame detects this at runtime and disables it automatically.

More details in [BENCHMARKS](docs/BENCHMARKS.md).

## When to use something else

**Ollama** is the right tool if you want to try out a variety of models on a personal laptop with zero friction. Most people should use Ollama, and Reame does not compete there. If you have GPUs, **vLLM** or **SGLang** are the right choices. 

Reame is designed for a different scenario: a single, repetitive workload running on affordable CPU hardware. In this environment, the cost per request *falls* the longer the server runs, which is the exact opposite of a per-token API billing model.

## Support

This is a free, MIT-licensed project built on nights and weekends using free-tier hardware. If it saves you API bills or GPU rentals, consider [sponsoring](https://github.com/sponsors/swellweb).

## Acknowledgments

The ternary models are from the [PrismML Bonsai](https://huggingface.co/prism-ml) family (see their respective licenses on Hugging Face) — remarkable training work that made this entire lane possible. The large-model lane relies on [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT) — excellent engineering that we happily credit, and the benchmark we measure ourselves against. The nucleo engine was written from scratch and verified token-by-token against independent references. Our disk-first cache approach owes a debt to antirez's DwarfStar4 thinking, and the speculative pipeline to the Leviathan/Chen theorem. Ideas are cited; the numbers are our own.

Documentazione in italiano: [docs/README.it.md](docs/README.it.md).

## License

[MIT](LICENSE).