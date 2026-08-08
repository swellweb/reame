#!/usr/bin/env python3
"""Reproduce the headline measurement: same page, same model, three input forms.

Runs 20 fact questions against any OpenAI-compatible endpoint (Reame,
llama-server, anything else) and reports, per input form: time to first token
on a cold cache, exam score, and score on the 13 critical facts — the ones
where a wrong answer is a real-world error rather than a typo.

    python3 bench/run_fact_exam.py --server http://127.0.0.1:8080 --model reame

Add --form prose|compressed|factsheet to run a single form.

Honest notes, so you can judge the numbers:
  * The questions are ours. They are adversarial on purpose: four similar
    prices in one block, 24h/72h/7-day durations, a 10-year vs 5-year
    warranty, negations, and facts that appear only in the footer.
  * Grading is exact-match on regexes in questions.jsonl, first non-empty
    line only. A "MISS" is the model saying it doesn't know; a "HALLU" is a
    confident wrong answer. They are counted separately because they are not
    equally bad.
  * TTFT is wall-clock for a 1-token completion, which on CPU is dominated by
    prefill. Flush any prefix cache between forms or the second run lies.
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from retrieval import select  # noqa: E402  (needs HERE on the path)

# The first three are fixed documents: every question sees the same text, so a
# prefix cache prefills once and the other 19 questions ride for free.
# "retrieval" is not a file — it picks a different slice of the prose for each
# question, which means every question pays its own prefill. That trade is the
# thing being measured, so the report prints total wall clock as well as TTFT.
FORMS = {
    "prose": "page_prose.txt",
    "compressed": "page_compressed.txt",
    "factsheet": "page_factsheet.txt",
    "retrieval": None,
}
RETRIEVAL_K = 3
TEMPLATE = (
    "Documento:\n{doc}\n\n"
    "Rispondi alla domanda usando SOLO il documento. Rispondi con il solo dato\n"
    "richiesto, in una sola riga, senza spiegazioni. Se il documento dice che\n"
    "qualcosa NON si fa o NON è disponibile, rispondi: No. Se il documento non\n"
    "contiene l'informazione, rispondi esattamente: NON PRESENTE.\n\n"
    "Esempio.\n"
    "Domanda: Quante tinte RAL sono disponibili per l'autolivellante?\n"
    "Risposta: oltre 40\n\n"
    "Domanda: {domanda}\nRisposta:"
)
STOP = ["\nDomanda:", "\n\nDomanda:", "\nEsempio", "\n\n"]


def post(server, path, body, key=None, timeout=900):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(server.rstrip("/") + path,
                                 data=json.dumps(body).encode(), headers=headers)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def ask(server, model, key, doc, question, max_tokens=64):
    body = {"model": model,
            "prompt": TEMPLATE.format(doc=doc, domanda=question),
            "max_tokens": max_tokens, "temperature": 0, "stop": STOP}
    t0 = time.time()
    r = post(server, "/v1/completions", body, key)
    return r["choices"][0].get("text", ""), time.time() - t0


def normalize(answer):
    first = next((l for l in answer.splitlines() if l.strip()), "")
    a = first.strip().lower()
    a = re.sub(r"(\d),(\d)", r"\1.\2", a)
    a = re.sub(r"[€$£]", " ", a)
    a = re.sub(r"[^\w\s.:/-]", " ", a, flags=re.UNICODE)
    return re.sub(r"\s+", " ", a).strip()


def grade(answer, q):
    """OK / MISS / HALLU. Accept wins over the not-present marker: a correct
    value followed by noise is still a correct answer."""
    norm = normalize(answer)
    ok = (all(re.search(rx, norm, re.I) for rx in q["accept"])
          and not any(re.search(rx, norm, re.I) for rx in q["reject"]))
    if ok:
        return "OK"
    return "MISS" if "non presente" in norm else "HALLU"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, help="OpenAI-compatible base URL")
    ap.add_argument("--model", default="reame")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--form", choices=list(FORMS), action="append",
                    help="default: all three")
    ap.add_argument("--verbose", action="store_true", help="print every answer")
    ap.add_argument("--questions", default="questions.jsonl",
                    help="question file; questions_paraphrased.jsonl asks the "
                         "same 20 facts in words the page does not use")
    args = ap.parse_args()

    questions = [json.loads(l) for l in (HERE / args.questions).open(encoding="utf-8")]
    n_crit = sum(1 for q in questions if q["crit"] == "C")
    print(f"{len(questions)} questions ({n_crit} critical) · model={args.model}\n")

    rows = []
    for form in (args.form or list(FORMS)):
        if form == "retrieval":
            source = (HERE / FORMS["prose"]).read_text(encoding="utf-8")
            doc_for = lambda q: select(q["domanda"], source, k=RETRIEVAL_K)
        else:
            fixed = (HERE / FORMS[form]).read_text(encoding="utf-8")
            doc_for = lambda q: fixed
        # first call carries the cold prefill: that is the TTFT we report
        _, ttft = ask(args.server, args.model, args.api_key,
                      doc_for(questions[0]), questions[0]["domanda"])
        ok = crit_ok = hallu = miss = 0
        words = 0
        started = time.monotonic()
        for q in questions:
            doc = doc_for(q)
            words += len(doc.split())
            answer, _ = ask(args.server, args.model, args.api_key, doc, q["domanda"])
            verdict = grade(answer, q)
            ok += verdict == "OK"
            crit_ok += verdict == "OK" and q["crit"] == "C"
            hallu += verdict == "HALLU"
            miss += verdict == "MISS"
            if args.verbose and verdict != "OK":
                print(f"  [{form}] {q['id']} {verdict}: {answer.strip()[:70]!r}")
        total = time.monotonic() - started
        rows.append((form, words // len(questions), ttft, ok, crit_ok, hallu, miss, total))
        print(f"{form:11s} TTFT {ttft:6.1f}s   all {len(questions)}: {total:6.1f}s   "
              f"{ok:2d}/{len(questions)}   critical {crit_ok:2d}/{n_crit}   "
              f"hallucinated {hallu}   said-unknown {miss}")

    if len(rows) > 1:
        slow, fast = rows[0][2], rows[-1][2]
        print(f"\n{rows[0][0]} -> {rows[-1][0]}: {slow / fast:.1f}x faster, "
              f"score {rows[0][3]}/{len(questions)} -> {rows[-1][3]}/{len(questions)}")
        print("\nIf your numbers differ, please open an issue with your hardware,\n"
              "model and the output above — negative reproductions are welcome.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
