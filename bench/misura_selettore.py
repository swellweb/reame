"""The honest baseline: deterministic selector v1 against all three benches.

Calibration discipline: the double threshold is fitted ONLY on the original
questions (the ones that reuse the page's vocabulary). Paraphrased and trap
sets are evaluation-only — touching them here would launder the experiment
the bi-encoder is supposed to win.

A row is a correct answer when it matches at least one accept pattern and no
reject pattern; a trap is answered correctly only by refusing (None).

    python3 bench/misura_selettore.py
"""
import json
import pathlib
import re
import time

from selettore import righe, seleziona

BENCH = pathlib.Path(__file__).parent
CORPUS = righe((BENCH / "page_factsheet.txt").read_text())


def carica(nome):
    with open(BENCH / nome) as f:
        return [json.loads(r) for r in f if r.strip()]


def corretta(q, indice):
    if q["attesa"] == "NON PRESENTE":
        return indice is None
    if indice is None:
        return False
    # Case-insensitive on both sides: the patterns were written against model
    # answers ("no", "iso 9001") and the rows spell the same facts in their
    # own case ("NO:", "ISO 9001"). Same fact must mean same verdict.
    riga = CORPUS[indice]
    if not any(re.search(p, riga, re.IGNORECASE) for p in q["accept"]):
        return False
    return not any(re.search(p, riga, re.IGNORECASE) for p in q["reject"])


def valuta(domande, soglia, margine):
    return sum(corretta(q, seleziona(q["domanda"], CORPUS, soglia, margine))
               for q in domande)


def main():
    originali = carica("questions.jsonl")
    parafrasate = carica("questions_paraphrased.jsonl")
    trappole = carica("questions_absent.jsonl")

    # Grid fit on originals only; among ties keep the most conservative pair
    # (larger thresholds refuse more, and refusing costs less than guessing).
    migliore = max(
        ((valuta(originali, s / 4, m / 4), s / 4 + m / 4, s / 4, m / 4)
         for s in range(0, 33) for m in range(0, 17)),
        key=lambda t: (t[0], t[1]))
    _, _, soglia, margine = migliore
    print("taratura su originali: soglia=%.2f margine=%.2f (%d/%d)" % (
        soglia, margine, valuta(originali, soglia, margine), len(originali)))

    for nome, serie in (("originali", originali),
                        ("parafrasate", parafrasate),
                        ("trappole (tutte)", trappole),
                        ("trappole vicine",
                         [q for q in trappole if q["tema"] == "vicino"]),
                        ("trappole lontane",
                         [q for q in trappole if q["tema"] == "lontano"])):
        ok = valuta(serie, soglia, margine)
        print("  %-18s %3d/%3d  (%d%%)" % (nome, ok, len(serie),
                                           round(100 * ok / len(serie))))

    inizio = time.perf_counter()
    for q in originali + parafrasate + trappole:
        seleziona(q["domanda"], CORPUS, soglia, margine)
    per_domanda = (time.perf_counter() - inizio) / (
        len(originali) + len(parafrasate) + len(trappole))
    print("latenza media selettore: %.2f ms/domanda (M3; su N1 sara' piu' alta)"
          % (per_domanda * 1e3))

    print("\nerrori sulle parafrasate (la lacuna che l'esperimento deve chiudere):")
    for q in parafrasate:
        indice = seleziona(q["domanda"], CORPUS, soglia, margine)
        if not corretta(q, indice):
            servita = "NON PRESENTE" if indice is None else CORPUS[indice][:60]
            print("  %s: %r -> %s" % (q["id"], q["domanda"], servita))

    print("\ntrappole cadute (esca servita invece del rifiuto):")
    for q in trappole:
        indice = seleziona(q["domanda"], CORPUS, soglia, margine)
        if not corretta(q, indice):
            print("  %s [%s]: %r -> %s" % (q["id"], q["tema"], q["domanda"],
                                           CORPUS[indice][:60]))


if __name__ == "__main__":
    main()
