# Benchmarks

Every number here came out of a terminal on the hardware named. The
benchmarks we lose are printed next to the ones we win — a benchmark page
with only wins is advertising. If a number does not reproduce on your
hardware, [open an issue](https://github.com/swellweb/reame/issues).

The subject is one model family: **Bonsai**, PrismML's ternary models
(weights in {−1, 0, +1}, published as GGUF Q2_0). nucleo — Reame's
from-scratch engine — converts them once into its own interleaved
2.125-bit format (`.nuc`, block-128: one fp16 row scale per 128 weights,
head and embeddings included) and serves them with integer NEON kernels
that accumulate a whole block in exact int32. None of that code comes
from llama.cpp; llama.cpp is what we measure against.

## Hardware and method

| Box | Spec | Cost |
|---|---|---|
| Oracle free tier | Ampere A1 (Neoverse N1), 2 or 4 ARM cores, 12-24 GB | €0/mo |
| Apple M3 Pro | 5P+6E laptop | laptop |

Same box, same prompt, services stopped during the measuring window and
restarted after. Rivals measured with `llama-bench` (pp256 / tg64, r=2).
nucleo measured with its chat banco: a 182-token prompt and a long greedy
generation; prefill tok/s = 182 / reported prefill seconds; decode tok/s
as reported over the full generation.

One method caveat, against ourselves: `llama-bench tg64` decodes at
near-zero context (attention is almost free there), while the chat banco
decodes at a growing 200-600-token context, paying the full attention
bill. At matched short context nucleo measures *higher* than the table
below (1.7B: 20.9 → higher; 8B 4-core: 5.6). The table keeps the harder,
real-context numbers for nucleo.

## The table

Rivals: **fork** is PrismML's own llama.cpp fork running the vendor's
Q2_0 — the official CPU runtime for Bonsai. **mainline** is llama.cpp
master running TQ2_0 (2.06 bpw).

| Box | Model | nucleo decode | rival decode | nucleo prefill | rival pp256 |
|---|---|---|---|---|---|
| **Oracle A1, 4 cores** | **Bonsai-8B** | **5.3** | **fork 4.84** | **7.7** | **5.5** |
| **Oracle A1, 2 cores** | **Bonsai-8B** | **2.8** | **fork 2.46** | **4.3** | **2.77** |
| Oracle A1, 4 cores | Bonsai-1.7B | 20.9 | mainline 31.6 | 32 | 66 |
| Oracle A1, 2 cores | Bonsai-1.7B | 11.9 | mainline 16.75 | 19.2 | 33.3 |
| Apple M3 Pro, 5 threads | Bonsai-1.7B | 85.7 | mainline 114.1 | 107 | 219 |

The bold rows are the claim: on Bonsai-8B, against the vendor's own
runtime, nucleo is **faster at both core counts on both phases** —
decode +10% at 4 cores (5.3/5.3/5.3 across three back-to-back runs) and
+14% at 2 cores; prompt processing 1.4-1.5× at both.

The rows we lose are printed too. Mainline's TQ2_0 path is faster on the
1.7B and much faster on the M3 (mature dotprod/i8mm kernels, tiled
prompt path). Two things worth knowing when reading those rows:

- **Mainline's "TQ2_0" is not pure ternary.** `perf` on its decode shows
  35.9% of the time in `ggml_vec_dot_q6_K_q8_K`: the output head stays at
  6-bit Q6_K (that is also why its 1.7B file is 590 MB against nucleo's
  454). nucleo serves the ternary weights end-to-end at 2.125 bpw, head
  included — and still scores 19/20 below.
- The M3 row was measured on an idle laptop (user idle time logged
  before and after the window to prove it) after a day of engine work —
  QoS-pinned worker threads, vectorized attention, a spin barrier —
  that nearly doubled the morning's figure. The remaining 25% is the
  target of an smmla (i8mm) kernel already merged for batch work.

## Accuracy, on the deployed server

The serving lane (temperature 0, direct-answer mode — no hidden
reasoning, because reasoning costs minutes on free cores) took a
20-question exam — arithmetic, English facts, Italian facts — graded on
the final answer only: **19/20**, stable across four consecutive exams
through four engine deployments. The one miss (longest river in Italy)
is not a quantization artifact: the same weights answer it correctly
when allowed to reason first, and the pre-optimization weights make the
same mistake. Direct-answer mode trades that question for answers in
seconds instead of minutes.

Engine sanity, same session: single-token and batch kernels produce
bit-identical outputs by construction (integer accumulation is exact,
so the float operation order is pinned), and the test suite — 149 cases,
254,585 assertions, every kernel checked against an independent oracle —
is green on both the A1 and the M3.

## What one day of kernel work bought

Same models, same box, same window — before → after, Bonsai-8B at
4 cores: decode 2.5 → 5.3 tok/s (+112%); Bonsai-1.7B: 10.9 → 20.9
(+92%). The levers, each measured alone: int32 block accumulation (+54%
on the bare kernel), a sum-trick on the raw 2-bit codes (+12%,
bit-identical by construction), interleaving the tied head (the
flat-format head was eating 22% of decode; the vocabulary is 151,669
rows — not a multiple of 4 — so the last quad carries ghost rows at
weight zero), vectorized fp16 attention with keys processed in pairs
(the inner loop was scalar and ate 32% of prefill), decode attention
parallelized across heads past 128 context (it ran on one thread while
the others idled: +19% alone), and a hybrid spin-then-sleep barrier in
the thread pool (13 µs → 0.7 µs per barrier, 228 barriers per token).

The failures are part of the record: a sum-trick on the older per-16
path lost to its predecessor and was reverted; wide unpacking lost in
the batch kernel (register spills); a tiled prefill buffer lost to the
plain loop; and the first spin barrier deadlocked in the test suite on
the N1 — a textbook store-buffer reordering, caught by the suite before
it ever touched a measurement or production, fixed by moving every
sleep transition under the mutex.

## What is next

The 1.7B and M3 rows are the open front: the current profile puts the
remaining gap in serial per-token work (the worker threads spin for
22.6% of decode while norms, softmax and sampling run on one thread)
and, on the M3, in i8mm kernels — an smmla path for batch work is
already merged and awaiting a clean-laptop measurement. The engine's
per-thread ternary kernel already exceeds mainline's (12.8 vs ~9.9
Gweights/s measured in isolation); what remains is engineering, and it
is listed here so you can hold us to it.
