"""End-to-end exam of the whole cascade, as production will run it.

Level 0 — fused selector (this bench, calibrated on hold-out):
  * confident row        -> answer is the row, copied            (fast, safe)
  * refusal WITH EVIDENCE (value contrast, orphan type, negation,
    uncovered pivot)     -> final NON PRESENTE, no model touched
  * margin uncertainty   -> fall through to the models
Level 1 — small model on the factsheet (the nucleo lane, port 8090),
  whose server-side [escalation] already relays refusals to
Level 2 — the big model (port 8080). One POST, the server does the rest.

Scored with the bench's accept/reject regexes, case-insensitive, on the
FINAL text wherever it came from. Reports accuracy per set and how much
traffic each level absorbed.

    ssh -f -N -L 18090:127.0.0.1:8090 sovrano-oracle
    python3 bench/esame_cascata.py
"""
import json
import pathlib
import re
import time
import urllib.request

from assenza import (contrasto_valore, copertura_scoperta,
                     negazione_esplicita, tipo_orfano)
from embedder_e5 import carica_encoder
from fusione import IndiceParafrasi, punteggia_v2
from misura_selettore import carica
from selettore import ALIAS, _veto, normalizza, righe

BENCH = pathlib.Path(__file__).parent
CORPUS = righe((BENCH / "page_factsheet.txt").read_text())
FACTSHEET = (BENCH / "page_factsheet.txt").read_text()
SERVER = "http://127.0.0.1:18090/v1/chat/completions"

# Calibrated on hold-out in misura_esperimento (margine, porta-copertura).
MARGINE, GATE = 0.06, 1


def livello0(domanda, indice, lingua):
    """(esito, dettaglio): 'riga'|'assente'|'incerto'."""
    if len(copertura_scoperta(domanda, lingua)) >= GATE:
        return "assente", "pivot scoperto"
    if tipo_orfano(domanda, CORPUS):
        return "assente", "tipo orfano"
    fusi = punteggia_v2(domanda, CORPUS, indice)
    gara = sorted(_veto(normalizza(domanda), CORPUS),
                  key=lambda i: (-fusi[i], i))
    top2 = fusi[gara[1]] if len(gara) > 1 else 0.0
    if fusi[gara[0]] - top2 < MARGINE:
        return "incerto", "margine"
    riga = CORPUS[gara[0]]
    if contrasto_valore(domanda, riga):
        return "assente", "contrasto di valore"
    if negazione_esplicita(domanda, riga):
        return "assente", "negazione"
    return "riga", riga


def modelli(domanda):
    corpo = json.dumps({
        "model": "reame-nucleo", "temperature": 0, "max_tokens": 48,
        "messages": [{"role": "user", "content":
            "Documento:\n" + FACTSHEET +
            "\n\nRispondi alla domanda usando SOLO il documento, con il solo "
            "dato richiesto, in una riga. Se il documento non contiene "
            "l'informazione rispondi esattamente: NON PRESENTE.\n"
            "Domanda: " + domanda}],
    }).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request(
        SERVER, corpo, {"Content-Type": "application/json"}), timeout=300))
    return (r["choices"][0]["message"]["content"].strip(),
            bool(r.get("escalated", False)))


def corretta(q, risposta):
    if q["attesa"] == "NON PRESENTE":
        return "NON PRESENTE" in risposta.upper()
    if not any(re.search(p, risposta, re.IGNORECASE) for p in q["accept"]):
        return False
    return not any(re.search(p, risposta, re.IGNORECASE) for p in q["reject"])


def main():
    voci = carica("paraphrases_factsheet.jsonl")
    vi = [{"indice": v["indice"],
           "parafrasi": [p for j, p in enumerate(v["parafrasi"]) if j % 5 != 4]}
          for v in voci]
    print("carico l'encoder...")
    indice = IndiceParafrasi(vi, carica_encoder())
    lingua = (CORPUS + [p for v in vi for p in v["parafrasi"]]
              + [" ".join(ALIAS) + " " + " ".join(ALIAS.values())])

    for nome in ("questions.jsonl", "questions_paraphrased.jsonl",
                 "questions_absent.jsonl"):
        serie = carica(nome)
        giuste = 0
        assorbite = {"selettore": 0, "porte": 0, "0.5B": 0, "escalation": 0}
        tempi = []
        sbagli = []
        for q in serie:
            t0 = time.time()
            esito, dettaglio = livello0(q["domanda"], indice, lingua)
            if esito == "riga":
                risposta, livello = dettaglio, "selettore"
            elif esito == "assente":
                risposta, livello = "NON PRESENTE", "porte"
            else:
                risposta, scalata = modelli(q["domanda"])
                livello = "escalation" if scalata else "0.5B"
            tempi.append(time.time() - t0)
            assorbite[livello] += 1
            if corretta(q, risposta):
                giuste += 1
            else:
                sbagli.append("  %s [%s]: %r -> %r" % (
                    q["id"], livello, q["domanda"][:40], risposta[:45]))
        tempi.sort()
        print("%s: %d/%d | livelli %s | p50 %.2fs p90 %.2fs" % (
            nome, giuste, len(serie), assorbite,
            tempi[len(tempi) // 2], tempi[int(len(tempi) * 0.9)]))
        for s in sbagli:
            print(s)


if __name__ == "__main__":
    main()
