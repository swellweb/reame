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
