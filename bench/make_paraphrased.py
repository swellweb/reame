#!/usr/bin/env python3
"""Build questions_paraphrased.jsonl: same 20 facts, asked in different words.

BM25 wins on the original questions because they borrow the page's vocabulary
("resina epossidica autolivellante"). That is the flattering case. This file is
the unflattering one: a caller who has not read the page and asks in their own
words. Same expected answers, same regexes — only the wording changes, so any
drop in retrieval is attributable to the wording alone.

The script also reports lexical overlap with the page, so "paraphrased" is a
measured property and not a claim.
"""
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent

# Deliberately avoids the page's own terms: no "resina", "epossidica",
# "autolivellante", "spatolato", "pedonabile", "carrabile", "sopralluogo",
# "showroom", "preventivo", "sconto", "garanzia".
REWORDED = {
    "q01": "Quanto spendo per un metro del trattamento base in un alloggio privato?",
    "q02": "Quanto viene la lavorazione manuale più costosa?",
    "q03": "Che tariffa applicate ai grandi magazzini sopra i cinquecento metri?",
    "q04": "A partire da che dimensioni si ottiene una riduzione?",
    "q05": "Dopo quanto tempo si può calpestare?",
    "q06": "Dopo quanto ci posso passare con l'automobile?",
    "q07": "Quanto tempo servono gli operai in una casa normale?",
    "q08": "Che recapito uso per chiedere un'offerta?",
    "q09": "A chi mi rivolgo se ho problemi dopo il lavoro finito?",
    "q10": "Qual è il codice fiscale dell'impresa?",
    "q11": "Che riconoscimento formale avete sul controllo dei processi?",
    "q12": "A che ora si può telefonare durante la settimana?",
    "q13": "Gli operai vengono anche di domenica?",
    "q14": "Si può stendere sopra assi in rovere?",
    "q15": "Venite anche in Sardegna o in Sicilia?",
    "q16": "In che zone della regione siete attivi?",
    "q17": "Per quanto tempo coprite i difetti nei magazzini?",
    "q18": "Fino a che distanza venite a vedere gratis?",
    "q19": "Si può visitare l'esposizione di sabato?",
    "q20": "In quanto tempo mi mandate l'offerta scritta?",
}

# Words too common to say anything about topical overlap.
STOP = set("""a ad ai al alla alle allo anche c che chi ci con cosa cui da dal
dalla de del della delle dello di e è ed gli ha hanno i il in io la le lo ma
mi ne nei nel nella non o per può quale quali quando quanto quanta quante
quanti se si sono su sul sulla tra un una uno vi""".split())


def terms(text):
    return {w for w in re.findall(r"\w+", text.lower())
            if w not in STOP and len(w) > 2}


def main():
    page = terms((HERE / "page_prose.txt").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (HERE / "questions.jsonl").open(encoding="utf-8")]

    out, before, after = [], [], []
    for r in rows:
        original = r["domanda"]
        r = dict(r, domanda=REWORDED[r["id"]], domanda_originale=original)
        out.append(r)

        o, n = terms(original), terms(r["domanda"])
        before.append(len(o & page) / len(o) if o else 0)
        after.append(len(n & page) / len(n) if n else 0)

    dest = HERE / "questions_paraphrased.jsonl"
    with dest.open("w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("wrote %s (%d questions)" % (dest.name, len(out)))
    print("share of question words that also appear on the page:")
    print("  original     %.0f%%" % (100 * sum(before) / len(before)))
    print("  paraphrased  %.0f%%" % (100 * sum(after) / len(after)))
    worst = max(range(len(after)), key=lambda i: after[i])
    print("  least paraphrased: %s (%.0f%% overlap) %r"
          % (out[worst]["id"], 100 * after[worst], out[worst]["domanda"]))


if __name__ == "__main__":
    main()
