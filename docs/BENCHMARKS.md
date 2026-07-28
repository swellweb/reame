# Benchmarks

Every number here came out of a terminal on the hardware named — a free
Oracle Cloud ARM box, a shared Contabo VPS, or an Apple M3 Pro laptop. The
failed experiments are kept next to the wins, because a benchmark table that
only shows wins is advertising. If a number does not reproduce on your
hardware, [open an issue](https://github.com/swellweb/reame/issues) — the
scripts are in the repo.

## Hardware

| Name | Spec | Cost |
|---|---|---|
| Oracle free tier | Ampere A1, 2 or 4 ARM cores, 12–24 GB (Always Free) | €0/mo |
| Contabo VPS | 18 oversubscribed shared vCPUs | ~€6/mo |
| Apple M3 Pro | 6 performance threads used | laptop |

Method: decode speed is measured with a two-run difference (time for N tokens
minus time for a short run) to isolate generation from model load and prefill,
or with `llama-cli`'s native `llama_perf` report where noted. Accuracy uses a
fixed long-context document with eight fact-retrieval ("needle") questions,
graded on the final answer only.

## Decode speed by model

The single most important CPU lesson: **architecture beats size**. A
mixture-of-experts model reads only its active parameters per token; a dense
model reads all of them. On memory-bandwidth-bound CPU decode, that is the
whole ballgame.

| Machine | Model | Type | Decode | Verdict |
|---|---|---|---|---|
| Oracle free (4 core) | Marco-Nano 8B-A0.6B | MoE, 0.6B active | **46.2 tok/s** | fastest here; multilingual |
| Oracle free (4 core) | OLMoE 7B-A1B | MoE, 1B active | **26.7 tok/s** | the live-serving pick |
| Oracle free (4 core) | Qwen2.5-3B | dense | 14.3 tok/s | dense reference point |
| Oracle free (2 core) | Qwen2.5-7B | dense | 3.3 tok/s | superseded by OLMoE |
| Oracle free | TriLM 3.9B TQ2_0 | dense ternary | ~10 tok/s | 1.1 GB RAM total |
| Oracle free (4 core) | Qwen3-30B-A3B | MoE, 3B active | ~335 s/question | batch only |
| Oracle free (4 core) | Qwen3.6-27B | dense | **~0.1 tok/s** | unusable here |
| Oracle free (4 core) | Ornith-1.0-9B (Qwen3.5-9B finetune) | dense | 5.4 tok/s | usable for batch judgment |
| Oracle free (4 core) | Gemma 4 E2B | dense, 2B effective | 18.2 tok/s | 8/8 needle, 3.3 GB — best small |
| Oracle free (4 core) | Gemma 4 E4B | dense, 4B effective | 10.1 tok/s | verbose, no gain over E2B |
| M3 Pro | Qwen2.5-1.5B | dense | 52 tok/s | laptop default |
| M3 Pro | Qwen3.5-9B | dense | 16.6 tok/s | judgment tasks |

Community recommendations get tested too: Ornith-1.0-9B (an HN-suggested
finetune of Qwen3.5-9B) runs at 5.4 tok/s on the free tier — the same base as
the judgment pick, and a genuinely usable 9B for reasoning batches on a €0 box.

**Fewer active parameters, faster decode — measured in one sitting.** The three
rows below were taken back-to-back on the same 4-core Oracle box, same prompt,
same two-run method, so the ratios are apples-to-apples:

| Model | Active params | Decode (same session) |
|---|---|---|
| Marco-Nano 8B-A0.6B | 0.6B | 46.2 tok/s |
| OLMoE 7B-A1B | 1B | 33.5 tok/s |
| Qwen2.5-3B | 3B (dense) | 14.3 tok/s |

Active parameter count predicts decode speed better than total size: an 8B MoE
touching 0.6B/token outruns a 3B dense model by 3.2×, despite being larger on
disk. Note the honest wrinkle: OLMoE measured **33.5 tok/s** in this session
versus the **26.7 tok/s** published above from an earlier one. Same box, same
method, different day — that spread is the run-to-run variance you should
expect on a shared cloud instance. Trust the ratios within a session more than
absolute numbers across sessions.

**Language coverage is a real axis, not a footnote.** OLMoE is English-centric:
asked in Italian it code-switches mid-sentence and drops English words into the
answer. Marco-Nano (a multilingual MoE) answers the same prompts in fluent
Italian. For a public demo that non-English speakers will poke at, that matters
as much as tok/s. Neither model is a knowledge oracle: asked for a carbonara
recipe, Marco-Nano stays plausible (guanciale, no onion) but still suggests
optional cream, which a dense Qwen3.5-9B correctly refuses. Small models on CPU
are for narrow work over supplied context, not for recall.

**Not tested: Marco-Mini 17.3B-A0.86B.** The larger sibling has no public GGUF
quantization at the time of writing, so it cannot be loaded by llama.cpp
without converting the weights first. Listed here so the gap is visible rather
than silently omitted.

Read the two extremes together: OLMoE (7B total, 1B active) serves at 26.7
tok/s, while Qwen3.6-27B (dense) crawls at ~0.1 tok/s on the same box — a
250× gap driven entirely by how many parameters each reads per token, not by
how many they contain. The 27B is also a reasoning model, so it burns hundreds
of `<think>` tokens before answering: minutes of wait for a single reply.

## Accuracy (long-context extraction)

| Machine | Model | Needle score | Note |
|---|---|---|---|
| Oracle free | Qwen2.5-7B dense | 8/8 | baseline |
| Oracle free | OLMoE 7B-A1B | 8/8 | same accuracy, far faster (see note) |
| Oracle free | Qwen3-30B-A3B | 8/8 | same accuracy, 10× the time |

(The dense 7B row was measured on a 2-core instance and the MoE on a 4-core
one, so we no longer quote a speed ratio between them — the machines differ.
The apples-to-apples comparison is the same-session table above.)

When the answer lives in the context you provide, extra parameters buy
nothing. A 7B-active model retrieves facts as accurately as a 30B one — it
just reads the document faster. This is the empirical core of Reame's thesis.

**A correction to the claim above.** That 8/8 comes from an easy needle test:
eight facts, each stated once, no distractors. We later built a harder one —
twenty questions over a realistic Italian business page, with adjacent similar
numbers (four prices in one block, 24h/72h/7 days, 10-year vs 5-year warranty),
negations ("we do not work weekends"), and facts that live only in the footer.
On that exam the parity disappears:

| Model | Hard exam (20 questions) | Critical facts (13) |
|---|---|---|
| Qwen2.5-3B dense | **20/20** | 13/13 |
| OLMoE 7B-A1B | 14/20 | 8/13 |

OLMoE's failures are stable across three prompt rewrites, so this is a model
limit, not a prompting one. What it gets wrong is *binding*: which of four
adjacent prices belongs to the service you asked about. So the honest version
of the thesis is narrower and more useful: **a 1B-active MoE matches a bigger
model at retrieving facts that are stated once and unambiguously; it does not
match it at telling near-identical facts apart.** Route accordingly — small MoE
for prose and bulk generation, a small dense model as the fact reader. Both
still run on the €0 box.

## Judgment (reasoning over your data)

Extraction is not judgment. On an SEO audit of a live page — where the model
must *reason*, not just retrieve — smaller models invented findings that
weren't there. Qwen3.5-9B was the only model tested with **zero invented
findings**, completing the full audit in **73s on the M3 Pro laptop**. For
tasks that need real reasoning in batches, a 9B is the floor.

## Feature speedups

Each of these is a way to avoid recomputing something, measured against the
same model doing the naive thing.

| Feature | Workload | Speedup |
|---|---|---|
| Warm disk cache vs cold | TinyLlama, repeated prefix | **4.8×** end-to-end |
| Palimpsest (generation archive) | Qwen2.5-1.5B, repeated request | **2.3×** (22→51 tok/s) |
| Il Suggeritore (form drafting) | Qwen2.5-1.5B, fresh list | **2.1×** (4.4s→2.1s) |
| Interleaved multi-user | TinyLlama, 3 concurrent | **1.6×** vs serialized |
| Prompt-lookup speculation | Qwen2.5-1.5B, rewrite task | **1.44×** |
| Draft-model speculation | 1.5B + 0.5B draft, Contabo | **3.2×** (87% acceptance) |
| Conclave (shared prefill + early consensus) | 1.5B ×5, arithmetic quiz | wall **97s → ~50s** |
| Warm-ahead (POST /v1/warm) | OLMoE, 1116-token doc pre-digested, Oracle free tier | TTFT **20.6s → 3.4s (6.1×)** |
| Warm-ahead | same, M3 Pro | TTFT **8.7s → 1.6s (5.3×)** |
| Nightly granary (warm-ahead on a schedule) | OLMoE, 2815-token doc, Oracle free tier | TTFT **89.7s → 16.7s (5.4×)** |
| Prefix KV save/restore across processes | OLMoE, 3356 tokens, Oracle free tier | prefill 54.4s → **3.5s cold disk / 0.10s warm RAM (15–300×)** |
| Thread + KV-type config (3→4 threads, KV q8_0→f16) | OLMoE prefill, Oracle free tier | **31.6 → 61.7 tok/s (2×)** |
| Learned sentence selection (Stenografo `x` stage) | OLMoE, unseen 2634-token page, Oracle free tier | TTFT **65.2s → 31.7s (2.06×)** |

Two of those rows deserve their story.

**The granary is warm-ahead with a clock.** A systemd timer pre-digests the
prefixes you can predict — templates, the pages your customers keep asking
about — while the box is idle at 03:00, and stores the KV. A request that hits
the granary skips the prefill entirely. The prefix save/restore row above is
what makes it work across process restarts: a *new* process inherits 54
seconds of prefill for 3.5 seconds of disk read (0.1s if the blob is still in
page cache). The cost is space, not time — 131 KB per token at f16.

**A bug worth publishing: warm-ahead was silently dead whenever speculative
decoding was on** — which was the default. The decoder branch returned before
the shared-prefix cache was consulted, so every `POST /v1/warm` wrote snapshots
nothing ever read. Measured on the production box: 90.5s with speculation on
versus 16.7s with it off, same cache, same request. The two features now
compose ([PR #6](https://github.com/swellweb/reame/pull/6)); after the fix, a
repeated query against a warm prefix answers in **2.3 seconds with speculation
enabled**. If you run Reame with a disk cache, check you are on a build that
includes it.

## L2 semantic cache — correctness across thresholds

The crux of a semantic cache is not speed, it's *not serving the answer to a
different question*. Measured with bge-small-en-v1.5 on a set of paraphrase
pairs (should hit) and different-but-topical pairs (must not):

| Cosine threshold | Recall (paraphrase hits) | False-hit (wrong answer served) |
|---|---|---|
| 0.60 | 100% | 83% |
| 0.75 | 100% | 17% |
| **0.80** | **67%** | **0%** |
| 0.85 | 67% | 0% |
| 0.95 | 0% | 0% |

At **0.80** the cache catches two-thirds of paraphrases and never serves a
wrong answer; below it, false-hits climb fast. So L2 is viable — with a strict
threshold as the safe default, not a loose one. (If higher recall is needed
without loosening, the model's RANK pooling supports a cross-encoder rerank of
the top candidate — a stage 2 to add only if the numbers demand it.)

## Document formatting is a speed *and* accuracy lever

![Time to first token by input form: 40.5s for the original prose, 21.0s
compressed, 6.2s as a fact sheet — same model, same page, same
question.](figures/ttft-per-forma.png)

The binding failure above has a cheap fix, and finding it required looking at
where the model actually looks. We dumped the post-softmax attention while
OLMoE answered "what does the epoxy cost?" on a page listing four prices:

| Document form | Attention mass on the right price (35) | On the wrong one (48) | Answer |
|---|---|---|---|
| Prose, Qwen2.5-3B | 7.0% | 0.6% | correct |
| Prose, OLMoE | 1.9% | 1.7% | **wrong** |
| `key: value`, OLMoE | 2.9% | 0.4% | **correct** |

OLMoE *sees* the right number — it just cannot separate it from its neighbour.
Gluing the label to the value does the disambiguation the attention head can't,
and the answer fixes itself with no retraining.

That turned the input compressor (`Stenografo`, deterministic, no LLM in the
request path) from a token-saving trick into an accuracy tool. Measured on the
same 20-question exam, OLMoE reading the same page in different forms:

| Page form | Tokens | OLMoE score | Critical facts |
|---|---|---|---|
| Original prose | 2634 | 14/20 | 8/13 |
| + extracted fact sheet | 2691 | 18/20 | 11/13 |
| + facts rewritten in place | 2291 | 17/20 | 11/13 |
| + learned sentence selection | **1662** | **19/20** | **13/13** |

Repeated end-to-end on the €0 Oracle box against the running server, prose
versus fully compressed: **14/20 with 9/13 critical facts in 65.2s**, versus
**18/20 with 13/13 critical facts in 31.7s**. Same model, same hardware, same
questions — half the wait and every critical fact recovered.

The last row is a 134M classifier distilled from a 3B teacher: the 3B labelled
740 sentences from real customer pages as fact-bearing or filler, the small
model learned to imitate that judgement in 44 seconds of training, and now runs
in **211 ms on CPU** for a full page. Its threshold is tuned for **1.000 recall
on facts** — dropping a fact is a real error, keeping a filler sentence costs a
few tokens. On the €0 box that trade buys ~972 tokens of prefill, about 16
seconds, for 0.2 seconds of classification.

Three formatting rules came out of these runs, each one paid for by a failed
test:
1. **The label travels with the value.** A fact re-attached without its label
   ("8:30-12:30" with no "office hours") stops answering the question it came
   from.
2. **A condition is a fact.** Keeping "9:00 to 12:00" and dropping "by
   appointment only" inverts the answer.
3. **One line, one fact.** Concatenating facts as `a | b | c` puts unrelated
   numbers back next to each other and recreates the binding problem: same
   content, 15/20 concatenated versus 17/20 on separate lines.

None of this makes the model bigger. It makes the page easier to read for the
model you already have — and it happens to halve the prefill.

### The headline number, in full

The same customer page, the same model (Marco-Nano 8B-A0.6B), the same
question, on the same €0 4-core Oracle ARM box. Only the *shape of the input*
changes. Cache flushed and the server restarted before each timing, so every
row pays a full cold prefill:

| Input form | Tokens | TTFT | Exam (20 questions) | Critical facts (13) |
|---|---|---|---|---|
| Original prose page | 2137 | 40.5 s | 19/20 | 13/13 |
| Compressed (rules + learned selection) | 1185 | 21.0 s | 20/20 | 13/13 |
| **Fact sheet only** | **405** | **6.2 s** | **20/20** | **13/13** |

**~6× on time to first token, and the score goes up rather than down.** Run
end-to-end through the public tunnel with `bench/run_fact_exam.py` the same
three forms gave 42.6s / 27.4s / 7.3s — 5.9×, with the extra seconds being
network latency and whatever else the shared box was doing. Reproduce it
yourself before believing either number:

```bash
python3 bench/run_fact_exam.py --server http://127.0.0.1:8080 --model reame
``` The
same three forms measured earlier in the week with OLMoE 7B-A1B — a weaker
reader — went 65.2 s → 31.7 s with 14/20 → 18/20 (9/13 → 13/13 critical), so
the effect is not specific to one model: the weaker the reader, the more the
formatting buys.

What the fact sheet is: every extractable fact rewritten as `label: value`,
one fact per line, conditions attached to the value they qualify ("only by
appointment" travels with the opening hours), negations quoted verbatim from
the source. Values are byte-for-byte copies — the extractor refuses a rewrite
that would drop a single number.

## Reame vs llama.cpp

Reame is built on llama.cpp and calls its kernels directly, so raw decode
speed is identical — Reame adds no per-token overhead. What Reame adds is the
memory layer llama.cpp does not have: the disk KV cache, the generation
archive, self-regulating speculation, the Conclave. On a single cold request
Reame ≈ llama.cpp; on a repeated or cached workload Reame pulls ahead by
exactly the feature-speedup factors above. The point of Reame is not to be a
faster llama.cpp — it is to be a llama.cpp that remembers.

## Negative results that shaped the design

- **A 30B-class MoE does not beat a 7B on extraction.** Same 8/8 accuracy, 10×
  the time. MoE prefill touches nearly every expert, so the active-parameter
  discount vanishes on document reading. Reserve 30B-class models for
  hard-reasoning batch jobs.
- **Speculation is counter-productive on oversubscribed shared vCPUs.** A 0.5B
  draft runs as slowly as its 7B target when the cores are contended, so the
  draft cost is pure loss. Reame measures this at runtime and disables it.
- **The Conclave does not create capability.** Majority voting over N attempts
  corrects random slips, not systematic misunderstanding: a 1.5B ×5 lands
  between a 1.5B and a 3B, never above the 3B. It is a variance knob, not a
  size upgrade.
- **A dense 27B is unusable on a free-tier CPU.** ~0.1 tok/s. Bigger is not
  better when every parameter is read every token.
- **A year of llama.cpp kernel work bought us 0%.** Same model, same box, old
  pinned submodule versus 2026 mainline: pp512 75.5 vs 75.8 tok/s, decode
  identical, runtime repack made no difference. For Q4_K_M on a Neoverse N1
  the kernels were already at the ceiling. Bump for features, not for speed.
- **Q4_0 is 37% faster at prefill and we rejected it.** Re-quantized from f16,
  it also gave +19% decode and a smaller file — then dropped 5 of 20 facts on
  the hard exam (OLMoE 8/20; a dense 3B lost only one, but that one was a
  negation). Quantization damage lands hardest on small MoE experts. Speed you
  can't trust with a customer's prices is not speed.
- **Cutting active experts corrupts the memory, not just the output.** OLMoE
  prefills 44% faster with 4 of 8 experts. But a KV built at 4 experts and
  *read back* at 8 still scores 11/20 against a 14/20 control — the damage is
  baked into the cached representation. The cheap prefill is unusable memory.
- **Expert routing is flat by design, so prefetching it is pointless.** We
  instrumented the MoE router (cb_eval on `ffn_moe_topk`, no llama.cpp patch)
  to test whether a hot expert set could be prefetched from a stored trace.
  Top-16 of 64 experts cover 29–30% of activations — uniform would be 25% —
  and same-domain overlap (26.6%) barely beats cross-domain (25.1%). The
  load-balancing loss used to train MoE models deliberately flattens exactly
  the skew we were hoping to exploit. It also explains the previous entry: if
  every expert matters equally, dropping half drops half the information.

## What small models know without a document (July 2026)

Everything above measures extraction *from a document you paste in*. This
section measures the opposite: what the model knows on its own, with nothing
supplied. It is the case where small models are at their worst, and we publish
it because the demo gets asked exactly this kind of question.

Fifty questions about Italian cooking — ingredients, origin, technique,
protected designations — graded by regex with accept/reject patterns. No
document, no retrieval. The eval set and the scorer are not in this repo yet —
they belong to a separate fine-tuning experiment still in progress. The numbers
are published here because they bound what a small model can do *without* a
document, which is the honest counterpart to every other table on this page.

![Correct answers out of 50 on Italian cooking, no document supplied:
Qwen2.5-3B 15, Marco-Nano 21, Qwen3.5-9B 32, Qwen3-30B-A3B
43.](figures/cucina-per-modello.png)

![Generation speed on the same 4-core ARM box: Qwen3.5-9B 4.9 tok/s,
Qwen3-30B-A3B 9.7 tok/s, Marco-Nano 46.2 tok/s.](figures/velocita-per-modello.png)

Read together, the two charts are the whole trade-off. **What matters is not
total size but active parameters.** Qwen2.5-3B is dense with 3B active and
scores 15/50; Qwen3-30B-A3B has the same 3B active but 30B total, and scores
43/50 — nearly three times as many correct answers for the same per-token cost
in bandwidth. Marco-Nano's 0.6B active parameters are why it answers in six
seconds *and* why it invents ingredients: same cause, both effects.

A caveat we would rather state than have found: **we wrote these fifty
questions**, so this is our exam, not a public benchmark. What keeps it honest
is that it also killed ideas of ours — see the negative results below.

### Trimming the vocabulary

`token_embd` is tied in Marco-Nano: it doubles as the output head and is re-read
in full for every generated token — 127.6 MB, **29.4% of all bytes read per
token**. Our domain (Italian, our own code, technical English) uses 9,314
distinct tokens out of 151,936.

Cutting the vocabulary to 32k is safe by construction: the tokenizer is
byte-level and all 256 byte characters are kept, so no text becomes
unrepresentable — a trimmed word merely costs an extra token. And because
`token_embd` is Q6_K with rows spanning a whole number of blocks, whole rows are
removed without ever splitting a quantized block: **the surviving weights are
bit-for-bit identical**.

![Generation speed before and after trimming the vocabulary to 32k: 46.2 to 55.0
tokens per second.](figures/potatura-decode.png)

**+17.8% on decode, measured over three independent runs with under 2% spread**,
and the 20-question fact exam scores the same (13/13 critical facts both before
and after). The theoretical ceiling from bandwidth alone was +30%; the gap is
time that isn't weight reading. The cost, measured on held-out text, is +1.9%
more tokens for the same document — so this pays off most when the input is
already short, which is exactly what the fact sheet makes it.
