# Roadmap

The plan, in phases. Each item is either shipped, next, or later — and a few
things are explicitly *not* goals, decided by measurement, not taste.

The through-line never changes: **on a CPU, never compute the same thing
twice.** Every phase either avoids work or shares work. And one lesson this
project keeps re-teaching: our own "not goals" are decided by measurement —
and *overturned* by measurement too (see the last section).

## Shipped

The server, its memory, and now its own engine (MIT, CI on Linux + macOS,
471 test cases across server + engine + concierge bench):

- **Two engines under one API** — llama.cpp for large/MoE models, and
  **nucleo**, our from-scratch CPU engine, for the 0.5B–3B class where it
  wins: +20–31% decode on the same ARM box, 99 MB resident at startup
  (convert-once `.nuc` format, no repacking). Verified against an independent
  NumPy reference and against llama.cpp itself.
- **Core** — OpenAI-compatible HTTP API, sessions, zero-config CLI
  (`reame run` / `list`), per-model chat templates.
- **The two-lane relay** — `/v1/warm` (now accepting `messages`, so the
  warmed tokens match the later chat request exactly) plus `[escalation]`:
  the fast lane's refusal replays automatically on the deep endpoint.
  Measured on one 4-core box with pinned cores: fast-lane latency unchanged
  while the deep lane prefills; a cold 59 s document question becomes 3.2 s
  after the page-load warm.
- **Concierge bench: selection, not generation** — the model never writes the
  answer, it points at the data row; refusals are computed from evidence
  (similarity provably cannot detect absence: overlapping cosine medians
  0.895 vs 0.879). Lives in `bench/` with 121 tests.
- **Persistent shared-prefix KV cache** — disk snapshots at block boundaries,
  reused across prompts, restarts and processes.
- **Interleaved multi-user** — N generations share each weight read.
- **The Conclave** — `--best-of N`, consensus as a quality knob.
- **MoE serving** — with the measured expert rule: prefill at K=4 (+44%),
  decode at K=8 (below that, quality collapses).
- **ARCA** — the Redis-compatible shared memory daemon: L1 exact responses,
  L4 shared generation corpus, transparent caching via one config line.
- **Speculation, Palimpsest, Il Suggeritore** — built, measured, **negative
  A/B on our hardware**; kept in-tree as instruments, off by default.
- **Launch** — public repo, Homebrew, release binaries, honest benchmarks
  page, logo, sponsors, site.

## Phase 1 — the concierge becomes a product

The flagship use case, from blueprint to installable:

1. **The widget** — a JS snippet any site pastes in: pings `/v1/warm` at page
   load, posts questions, renders answers. The privacy pitch is the point:
   the company's data answers on the company's box.
2. **The renderer** — templates with byte-for-byte copy from the factsheet,
   the interpretation echo ("Lo spatolato decorativo costa 48 €/mq" — so a
   selection mistake is visible, not silent), and the "which of the N?"
   disambiguation.
3. **DB → factsheet adapter** — SQL computes dates and availability; the
   model never does arithmetic. One config per site.
4. **The L2 parser** — only if the coverage register shows the fast lanes
   refuse more than ~15%: the small model with a pruned head emitting
   structure (intent + row id), never text.
5. **Port the selector to C++** — today the blueprint is Python in `bench/`;
   the server should own it (it is 22 ms of set logic and regex).

## Phase 2 — nucleo grows up

1. **Fold the nucleo source into this repository** (today it ships separately;
   the build already auto-detects it).
2. **The 7B class** — nucleo currently loses above 3B (Q4_K/Q6_K multi-token
   kernels). Close the gap or document the boundary honestly.
3. **A dedicated `test_nucleo_backend`** — the backend went to production
   covered by engine tests only; it deserves its own.
4. **KV q8_0 in nucleo** — fp16 shipped; halve it again.
5. **Adaptive experts (K by router confidence)** — the lab experiment: let
   the router's score concentration choose K per token. Ceiling measured at
   ~+15–25% decode; build only when the fork is warm for other reasons.

## Phase 3 — fleet & polish

1. **ARCA L2 — semantic cache** — match *similar* questions, not just
   identical ones.
2. **ARCA L3 — shared KV blocks** — one node's prefill warms the fleet.
3. **Bump the llama.cpp submodule** — a recent one brings better ARM low-bit
   kernels (KleidiAI). Re-measure after.
4. **npm package** (`npx reame`) — binaries exist; wrap them.
5. **Keep the Italian README in lockstep** with the English one.

## Not goals (decided by measurement — and revisable by it)

- **GPU offload.** Reame's moat is being CPU-first and focused. GPU inference
  is a crowded field where Reame has no edge.
- **Training / fine-tuning inside the server.** Distillation experiments live
  outside the serving path.
- ~~**A custom matmul kernel** — "a real research target but a bad product
  bet."~~ **Overturned.** We wrote the whole engine, not just the kernel, and
  it beats llama.cpp on the small-model class. This stays here, struck
  through, as a reminder of what "decided by measurement" must mean: the
  measurement can change.

## How we work

TDD, isolated test first. Each feature on its own branch → PR → CI green →
merge. Benchmarks measured on real hardware, negative results published next
to the wins.
