"""The decisive experiment, v2: computed refusal + 3-channel ranking.

v1 finding (kept for the record): with thresholds on the fused score,
calibration lands at soglia 0.94 and refuses everything — because e5's max
cosine cannot separate answerable questions (median 0.895) from traps
(median 0.879). Absence is not predictable from similarity on this corpus.

v2 therefore computes refusal from evidence (coverage, orphan type, value
contrast, negation — assenza.py) and uses the ranking only to pick WHICH row,
with a margin as the single calibrated ambiguity guard.

Calibration material: held-out paraphrases (3 of 15 per row, answerable, row
known by construction) + 20 fresh NON PRESENTE questions. The three
evaluation sets are never touched during calibration.

Pre-registered assertions:
  (A) paraphrased ≥ 90%   (deterministic baseline: 0%)
  (B) traps       ≥ 95%   (baseline: 78%)
  (C) zero inventions — grounding belt on every servable row
  (D) latency — measured on the Oracle box, separately.

    python3 bench/misura_esperimento.py
"""
import pathlib
import time

from embedder_e5 import carica_encoder
from fusione import IndiceParafrasi, punteggia_v2, seleziona_v2
from grounding import verifica
from misura_selettore import carica, corretta
from selettore import ALIAS, _veto, normalizza, righe

BENCH = pathlib.Path(__file__).parent
CORPUS = righe((BENCH / "page_factsheet.txt").read_text())

# Fresh NON PRESENTE questions for calibration only — disjoint from the
# evaluation traps, as the onboarding factory would generate them.
TARATURA_NO = [
    "Fate anche l'impermeabilizzazione dei terrazzi condominiali?",
    "Vendete pavimenti in laminato?",
    "Che sconto fate ai nuovi clienti al primo ordine?",
    "Avete un punto vendita a Roma?",
    "Si può pagare con carta di credito?",
    "Quanto costa lucidare il marmo?",
    "Fate manutenzione agli ascensori?",
    "Che olio consigliate per il parquet?",
    "A che ora apre la farmacia di turno?",
    "Quanti anni ha il vostro titolare?",
    "Fate posa di piastrelle antiscivolo?",
    "Il microcemento lo vendete anche sfuso al secchio?",
    "Che garanzia c'è sulla caldaia?",
    "Posso prenotare un tavolo per stasera?",
    "Quanto costa il corso di formazione per posatori?",
    "Avete il servizio di pulizia post cantiere incluso?",
    "Che certificazione antincendio avete?",
    "Il preventivo lo fate anche via WhatsApp?",
    "Dove posso ricaricare il monopattino?",
    "Fate pavimenti in resina per esterni tipo cortili?",
]


def main():
    originali = carica("questions.jsonl")
    parafrasate = carica("questions_paraphrased.jsonl")
    trappole = carica("questions_absent.jsonl")
    factsheet = (BENCH / "page_factsheet.txt").read_text()

    # Hold-out split: 12 paraphrases per row build the index, 3 stay out as
    # answerable calibration questions. Calibrating on the index's own texts
    # would score self-matches at cosine 1.0 and teach nothing.
    voci = carica("paraphrases_factsheet.jsonl")
    voci_indice, taratura_si = [], []
    for v in voci:
        dentro = [p for j, p in enumerate(v["parafrasi"]) if j % 5 != 4]
        fuori = [p for j, p in enumerate(v["parafrasi"]) if j % 5 == 4]
        voci_indice.append({"indice": v["indice"], "parafrasi": dentro})
        taratura_si += [(p, v["indice"]) for p in fuori]

    print("carico l'encoder e embeddo l'indice parafrasi (12/15 per riga)...")
    indice = IndiceParafrasi(voci_indice, carica_encoder())

    # The site's whole language, for the coverage gate: rows, bundles, alias.
    lingua = (CORPUS + [p for v in voci_indice for p in v["parafrasi"]]
              + [" ".join(ALIAS) + " " + " ".join(ALIAS.values())])

    # Ranking scores don't depend on the calibrated knobs: memoise them.
    memoria = {}

    def scegli(domanda, margine, gate):
        if domanda not in memoria:
            memoria[domanda] = (punteggia_v2(domanda, CORPUS, indice),
                                _veto(normalizza(domanda), CORPUS))
        fusi, candidati = memoria[domanda]

        from assenza import (contrasto_valore, copertura_scoperta,
                             negazione_esplicita, tipo_orfano)
        if len(copertura_scoperta(domanda, lingua)) >= gate:
            return None
        if tipo_orfano(domanda, CORPUS):
            return None
        gara = sorted(candidati, key=lambda i: (-fusi[i], i))
        top2 = fusi[gara[1]] if len(gara) > 1 else 0.0
        if fusi[gara[0]] - top2 < margine:
            return None
        riga = CORPUS[gara[0]]
        if contrasto_valore(domanda, riga) or negazione_esplicita(domanda, riga):
            return None
        return gara[0]

    # Balanced objective: neither answering everything nor refusing
    # everything can win. Ties go to the most conservative pair.
    def bonta(margine, gate):
        si = sum(scegli(p, margine, gate) == riga for p, riga in taratura_si)
        no = sum(scegli(t, margine, gate) is None for t in TARATURA_NO)
        return si / len(taratura_si) + no / len(TARATURA_NO)

    migliore = max(((bonta(m / 50, g), m / 50, g)
                    for m in range(0, 26) for g in (1, 2, 99)),
                   key=lambda t: (t[0], t[1], -t[2]))
    _, margine, gate = migliore
    si = sum(scegli(p, margine, gate) == riga for p, riga in taratura_si)
    no = sum(scegli(t, margine, gate) is None for t in TARATURA_NO)
    print("taratura hold-out: margine=%.2f porta-copertura=%s "
          "(parafrasi %d/%d, rifiuti %d/%d)" % (
              margine, gate, si, len(taratura_si), no, len(TARATURA_NO)))

    def valuta(serie):
        return sum(corretta(q, scegli(q["domanda"], margine, gate))
                   for q in serie)

    esiti = {}
    for nome, serie in (("originali", originali),
                        ("parafrasate", parafrasate),
                        ("trappole (tutte)", trappole),
                        ("trappole vicine",
                         [q for q in trappole if q["tema"] == "vicino"]),
                        ("trappole lontane",
                         [q for q in trappole if q["tema"] == "lontano"])):
        ok = valuta(serie)
        esiti[nome] = round(100 * ok / len(serie))
        print("  %-18s %3d/%3d  (%d%%)" % (nome, ok, len(serie), esiti[nome]))

    invenzioni = [v for riga in CORPUS for v in verifica(riga, [factsheet])]
    print("atomi non ancorati su tutte le righe servibili:", len(invenzioni))

    inizio = time.perf_counter()
    for q in parafrasate + trappole:
        seleziona_v2(q["domanda"], CORPUS, indice, lingua, margine, gate)
    ms = (time.perf_counter() - inizio) / (len(parafrasate) + len(trappole)) * 1e3
    print("latenza media (M3, torch fp32): %.1f ms/domanda" % ms)

    print("\nVERDETTI: A parafrasate>=90%%: %s | B trappole>=95%%: %s | C zero invenzioni: %s"
          % ("VERDE" if esiti["parafrasate"] >= 90 else "ROSSO",
             "VERDE" if esiti["trappole (tutte)"] >= 95 else "ROSSO",
             "VERDE" if not invenzioni else "ROSSO"))

    print("\nerrori residui sulle parafrasate:")
    for q in parafrasate:
        i = scegli(q["domanda"], margine, gate)
        if not corretta(q, i):
            print("  %s: %r -> %s" % (q["id"], q["domanda"],
                                      "NON PRESENTE" if i is None else CORPUS[i][:60]))
    print("trappole cadute:")
    for q in trappole:
        i = scegli(q["domanda"], margine, gate)
        if not corretta(q, i):
            print("  %s [%s]: %r -> %s" % (q["id"], q["tema"], q["domanda"],
                                           CORPUS[i][:60]))


if __name__ == "__main__":
    main()
