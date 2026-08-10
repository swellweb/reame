# Reproducing the fact-extraction numbers

This directory contains everything behind the headline claim in the main
README: the same page in three input forms, the 20 questions, and the script
that scores them.

```bash
# any OpenAI-compatible server: Reame, llama-server, whatever you run
python3 bench/run_fact_exam.py --server http://127.0.0.1:8080 --model reame
```

What you should see (Marco-Nano 8B-A0.6B, 4-core Oracle ARM, €0 tier):

```
prose       TTFT   40.5s   19/20   critical 13/13
compressed  TTFT   21.0s   20/20   critical 13/13
factsheet   TTFT    6.2s   20/20   critical 13/13
```

## What is being compared

| File | What it is | Tokens |
|---|---|---|
| `page_prose.txt` | a realistic Italian business page, as written | 2137 |
| `page_compressed.txt` | same page, deterministic cleanup + learned sentence selection | 1185 |
| `page_factsheet.txt` | same facts as `label: value`, one fact per line | 405 |

`questions.jsonl` holds the 20 questions with accept/reject regexes. Thirteen
are marked critical (`"crit": "C"`): prices, phone numbers, VAT number,
negations — the ones where a wrong answer costs someone real money, as opposed
to a fact that is merely nice to have.

## Why the questions are adversarial

Easy needle tests (one fact, stated once, no distractors) make every model
look good. These don't:

- **four similar prices in one block** — 35, 48, 28 and 60 €/m², each belonging
  to a different service
- **near-duplicate durations** — walkable after 24h, driveable after 72h, fully
  cured in 7 days
- **10-year vs 5-year warranty**, in the same sentence
- **negations** — "we do not work weekends", "we do not apply resin on parquet"
- **footer-only facts** — VAT number, after-sales phone, office hours
- **a condition that changes the answer** — the showroom is open on Saturday
  *by appointment only*

## Known limits of this benchmark

- **We wrote the questions.** That is the weakest leg and we are not going to
  pretend otherwise. What keeps it honest: the same exam killed two of our own
  optimizations (4-bit `Q4_0`, which is 37% faster and drops 5 facts; and
  halving active experts during prefill, which corrupts the cached KV). If you
  know a public adversarial fact-extraction set for small models, tell us and
  we will run it.
- **One page, one language, one domain.** The effect is large and consistent
  across two different models, but a single document is not a corpus.
- **Grading is regex exact-match** on the first non-empty line. It is strict:
  a correct answer phrased unusually can score as a miss.
- **TTFT depends on a cold cache.** Reame reuses prefixes across requests, so
  the second run of the same form is much faster — that is the point of the
  server, but it is not what this table measures. Restart the server or flush
  the cache directory between forms.

## The finding

Reformatting the input is worth more than replacing the model: the fact sheet
is 6.5× faster to read *and* scores higher. The same three forms measured on
OLMoE 7B-A1B — a weaker reader — went 65.2s → 31.7s with 14/20 → 18/20, so the
weaker the model, the more the formatting buys. We dumped the attention weights
to see why: on prose, the model puts 1.9% of its attention mass on the right
price and 1.7% on the wrong one; with `label: value` it is 2.9% vs 0.4%. It was
never blind to the number — it could not bind it to the question.

Full write-up and the failed experiments: [../docs/BENCHMARKS.md](../docs/BENCHMARKS.md).

---

# The concierge bench: selection, not generation

A second wave of benches lives here since the concierge work: the answer is
never *generated*, it is *selected* from a factsheet row and copied byte for
byte — so the interesting questions become "does the selector pick the right
row when the caller uses their own words?" and "does it refuse when the
answer is genuinely absent?".

## The pieces

| File | What it is |
|---|---|
| `retrieval.py` | the prefill oracle: BM25 over word blocks (dense embeddings measured 3× worse at this — see docstring) |
| `selettore.py` | deterministic selector v1: normalisation, aliases, stopwords, answer-type veto, double threshold |
| `assenza.py` | **computed refusal**: value contrast (ISO 14001 ≠ 9001), orphan answer type, explicit negation, uncovered pivot terms |
| `fusione.py` | the fused selector: BM25 + question-space cosine over onboarding paraphrases, 3 channels |
| `grounding.py` | the anti-invention belt: every number/phone/clock in an answer must exist in the sources |
| `embedder_e5.py` | multilingual-e5-small wrapper (mean pooling, L2-norm) |
| `paraphrases_factsheet.jsonl` | the onboarding index: ~15 ways a real caller asks for each factsheet row |
| `questions_paraphrased.jsonl` | the same 20 facts asked in words the page does not use |
| `questions_absent.jsonl` | 50 trap questions whose answer is NOT in the factsheet (half on confusable nearby themes) |
| `questions_composite.jsonl` | 10 multi-fact / disambiguation / arithmetic questions |

## Reproduce

```bash
python3 -m pytest bench/ -q          # 121 isolated tests, no model needed
python3 bench/misura_selettore.py    # deterministic baseline (no model)
python3 bench/misura_esperimento.py  # the fused experiment (downloads e5-small)
```

Calibration discipline: thresholds are fitted only on held-out paraphrases
plus fresh calibration traps; the evaluation sets are never touched.

## The finding

The ranking works (paraphrased recall@1: 25% lexical-only → 75% fused), but
**similarity cannot detect absence**: max cosine medians are 0.895 for
answerable questions vs 0.879 for traps — overlapping, no usable threshold.
Absence must be *computed* from evidence, not predicted from scores. With the
computed-refusal gates: near-theme traps 92–100% refused, zero invented
values possible by construction, ~20 ms per question without any model.
