#!/usr/bin/env python3
"""A/B on Palimpsest: the generation corpus on vs off, everything else equal.

Palimpsest turns the server's own past output into draft material, so
speculation sees across requests and restarts. The claim it is supposed to
support is "request #100 costs a fraction of request #1" on repetitive
workloads. This measures whether that is true, and by how much.

The two arms differ in exactly one config key, `speculative.corpus`. The disk
KV cache stays on in both — otherwise the "off" arm would lose two mechanisms
and the difference would be attributed to the wrong one.

Both arms run greedy (temperature 0), so speculative decoding is required to
reproduce the target model's output token for token. The harness checks that
the two arms produced IDENTICAL text: a speedup that changes the answer is not
a speedup, and this is the check that would catch it.

Usage:
    python3 bench/bench_palimpsest.py --model models/marco-nano-potato-32k.gguf
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
ETICHETTA = ["ON ", "OFF"]

# Un carico ripetitivo realistico: lo stesso rapporto strutturato prodotto per
# molte pagine diverse. La ripetizione sta nell'IMPALCATURA della risposta —
# le intestazioni di sezione, le formule di giudizio — non nei dati, che
# cambiano a ogni richiesta. E' il caso "audit periodici" della tabella.
#
# Nota sul metodo: i dati NON sono generati da uno script, altrimenti il
# modello imparerebbe a invertire il mio generatore di rumore invece che un
# carico vero. Sono 24 pagine scritte a mano, con difetti diversi fra loro.
MODULO = """Analizza la pagina e produci il rapporto in questo formato esatto:

SEZIONE 1 - TITOLO
SEZIONE 2 - DESCRIZIONE
SEZIONE 3 - GIUDIZIO
SEZIONE 4 - AZIONE CONSIGLIATA

Pagina da analizzare:
"""

PAGINE = [
    "Titolo: Ricambi auto Roma. Descrizione: assente. H1: mancante. Immagini senza alt: 12.",
    "Titolo: Officina meccanica Milano centro. Descrizione: 340 caratteri. H1: duplicato due volte.",
    "Titolo: vendita pneumatici. Descrizione: 22 caratteri. H1: presente. Tempo di caricamento: 8,4 s.",
    "Titolo: Carrozzeria Torino - preventivi gratuiti. Descrizione: 155 caratteri. H1: presente. Nessun link interno.",
    "Titolo: Autoricambi online spedizione 24h. Descrizione: duplicata su 14 pagine. H1: presente.",
    "Titolo: Gommista Napoli. Descrizione: assente. H1: presente. Immagini senza alt: 3. Nessun dato strutturato.",
    "Titolo: Revisione auto Bologna prezzi 2026. Descrizione: 148 caratteri. H1: presente. Tempo: 1,2 s.",
    "Titolo: Ricambi originali e compatibili. Descrizione: 210 caratteri. H1: assente. Testo: 90 parole.",
    "Titolo: Assistenza climatizzatori auto. Descrizione: 132 caratteri. H1: presente. Nessun contatto in pagina.",
    "Titolo: Batterie auto consegna rapida Firenze. Descrizione: 160 caratteri. H1: presente. 4 link rotti.",
    "Titolo: Tagliando auto multimarca. Descrizione: 95 caratteri. H1: presente. Immagini: 0.",
    "Titolo: Autoricambi usati garantiti Palermo. Descrizione: 175 caratteri. H1: duplicato. Testo: 1200 parole.",
    "Titolo: Preventivo carrozzeria online. Descrizione: assente. H1: presente. Modulo senza etichette.",
    "Titolo: Ricambi moto e scooter. Descrizione: 143 caratteri. H1: presente. Canonical mancante.",
    "Titolo: Cambio olio motore Genova. Descrizione: 205 caratteri. H1: presente. Tempo: 5,1 s.",
    "Titolo: Diagnosi elettronica centraline. Descrizione: 88 caratteri. H1: assente. Nessun H2.",
    "Titolo: Autoricambi Bari consegna in giornata. Descrizione: 168 caratteri. H1: presente. 2 immagini senza alt.",
    "Titolo: Freni e dischi per tutte le marche. Descrizione: duplicata. H1: presente. Testo: 60 parole.",
    "Titolo: Officina autorizzata Verona. Descrizione: 151 caratteri. H1: presente. Orari non indicati.",
    "Titolo: Ricambi carrozzeria paraurti fari. Descrizione: 30 caratteri. H1: presente. Tempo: 3,8 s.",
    "Titolo: Soccorso stradale h24 Catania. Descrizione: 162 caratteri. H1: presente. Telefono solo in immagine.",
    "Titolo: Pneumatici invernali offerte. Descrizione: 118 caratteri. H1: duplicato. Nessun dato strutturato.",
    "Titolo: Centro revisioni Padova prenotazione. Descrizione: 158 caratteri. H1: presente. Tempo: 0,9 s.",
    "Titolo: Ricambi elettrici alternatori motorini. Descrizione: assente. H1: assente. Immagini senza alt: 7.",
]


def scrivi_config(percorso: Path, modello: Path, cache: Path, porta: int,
                  corpus: bool, disable_after: int = 1 << 40,
                  speculazione: bool = True) -> Path:
    percorso.write_text(f"""[logging]
level = warn

[server]
host = 127.0.0.1
port = {porta}
threads = 2
enable_metrics = true
enable_request_logging = false

[model]
path = {modello}
context_length = 8192

[speculative]
enabled = {'true' if speculazione else 'false'}
mode = lookup
corpus = {"true" if corpus else "false"}
# La ghigliottina di serie giudica la speculazione sui primi 64 token
# abbozzati e la spegne per sempre sotto il 15% di accettazione. Palimpsest
# ha il corpus vuoto proprio allora: verrebbe condannato prima di poter
# imparare qualsiasi cosa, in ENTRAMBI i bracci, e l'esperimento
# misurerebbe due volte lo stesso programma.
disable_after_drafted = {disable_after}
disable_below_acceptance = 0.0

[cache]
directory = {cache}
""", encoding="utf-8")
    return percorso


def attendi(porta: int, secondi: int = 180) -> None:
    scadenza = time.time() + secondi
    while time.time() < scadenza:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{porta}/health",
                                        timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(1)
    raise TimeoutError(f"il server non risponde su {porta}")


def chiedi(porta: int, prompt: str, max_tokens: int) -> tuple[str, int, float]:
    corpo = json.dumps({
        "model": "reame",
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{porta}/v1/completions", data=corpo,
        headers={"Content-Type": "application/json"})
    inizio = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    trascorso = time.perf_counter() - inizio
    testo = d["choices"][0]["text"]
    gettoni = d.get("usage", {}).get("completion_tokens", 0)
    return testo, gettoni, trascorso


def metriche(porta: int) -> dict:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/metrics",
                                    timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return {}


class SpeculazioneSpenta(RuntimeError):
    """Il decoder speculativo non e' stato costruito: non c'e' nulla da misurare.

    Palimpsest alimenta la speculazione. Se la speculazione e' spenta, i due
    bracci sono lo stesso identico programma e la differenza misurata e'
    rumore della macchina. E' successo davvero: `lfm2moe` e' un'architettura
    ibrida, non sa fare rollback dei token rifiutati, e l'engine declassa a
    decodifica classica in silenzio (engine.cpp:200). Ventiquattro richieste
    per braccio, un +7,9% pubblicabile, e sotto non c'era niente.
    """


def arma(binario: Path, modello: Path, porta: int, corpus: bool,
         max_tokens: int, speculazione: bool = True) -> dict:
    """Un braccio dell'esperimento: cache su disco NUOVA, corpus on/off."""
    tmp = Path(tempfile.mkdtemp(prefix="palimpsest-"))
    try:
        cfg = scrivi_config(tmp / "reame.conf", modello, tmp / "cache",
                            porta, corpus, speculazione=speculazione)
        proc = subprocess.Popen(
            [str(binario), "--config", str(cfg), "--serve"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            attendi(porta)
            if speculazione and "speculative" not in metriche(porta):
                raise SpeculazioneSpenta(
                    f"{modello.name}: /metrics non espone 'speculative', quindi "
                    f"il decoder non e' stato costruito. Serve un'architettura "
                    f"che sappia fare rollback (non ricorrente, non ibrida).")
            righe = []
            for i, pagina in enumerate(PAGINE):
                testo, gettoni, secondi = chiedi(
                    porta, MODULO + pagina, max_tokens)
                righe.append({
                    "i": i,
                    "testo": testo,
                    "gettoni": gettoni,
                    "secondi": round(secondi, 3),
                    "tok_s": round(gettoni / secondi, 2) if secondi else 0.0,
                })
                print(f"  [{ETICHETTA[0] if (corpus and speculazione) else ETICHETTA[1]}]"
                      f" {i + 1:2d}/{len(PAGINE)}"
                      f"  {righe[-1]['tok_s']:6.2f} tok/s", flush=True)
            return {"corpus": corpus, "righe": righe,
                    "metriche": metriche(porta)}
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def riassumi(righe: list[dict], coda: int = 6) -> dict:
    v = [r["tok_s"] for r in righe]
    return {
        "mediana": round(statistics.median(v), 2),
        "prime": round(statistics.median(v[:coda]), 2),
        "ultime": round(statistics.median(v[-coda:]), 2),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--binary", default=str(RADICE / "build/src/reame"))
    p.add_argument("--port", type=int, default=8127)
    p.add_argument("--max-tokens", type=int, default=160)
    p.add_argument("--vary", choices=["corpus", "speculazione"], default="corpus",
                   help="corpus: Palimpsest on/off. speculazione: decodifica "
                        "speculativa on/off — quanto vale avere il rollback.")
    p.add_argument("--out", default=str(RADICE / "bench/palimpsest-ab.json"))
    a = p.parse_args()

    binario, modello = Path(a.binary), Path(a.model)
    for f in (binario, modello):
        if not f.exists():
            print(f"manca: {f}", file=sys.stderr)
            return 1

    print(f"{len(PAGINE)} richieste per braccio, {a.max_tokens} token max\n")
    # Ordine alternato: il Mac scalda e cambia carico nel tempo, e con i
    # bracci in blocco (prima tutto OFF, poi tutto ON) la deriva della
    # macchina finisce dentro il confronto. OFF,ON,ON,OFF la cancella al
    # primo ordine.
    spec_varia = a.vary == "speculazione"
    if spec_varia:
        ETICHETTA[:] = ["SPEC", "PIAN"]
    blocchi = []
    for k, acceso in enumerate([False, True, True, False]):
        b = arma(binario, modello, a.port + k,
                 corpus=True if spec_varia else acceso,
                 max_tokens=a.max_tokens,
                 speculazione=acceso if spec_varia else True)
        b["corpus"] = acceso  # "acceso" = il braccio sperimentale, comunque
        blocchi.append(b)
        print()

    def unisci(corpus: bool) -> dict:
        parti = [b for b in blocchi if b["corpus"] is corpus]
        righe = [dict(r, blocco=j) for j, b in enumerate(parti) for r in b["righe"]]
        return {"corpus": corpus, "righe": righe, "metriche": parti[-1]["metriche"]}

    spento, acceso = unisci(False), unisci(True)

    # Il controllo che rende la misura una misura: a temperatura 0 la
    # decodifica speculativa deve riprodurre l'uscita del modello bersaglio
    # token per token. Se i due bracci divergono, il guadagno non e' gratis
    # e il numero non vale niente.
    diversi = [i for i, (x, y) in enumerate(zip(spento["righe"], acceso["righe"]))
               if x["testo"] != y["testo"]]

    esito = {
        "spento": riassumi(spento["righe"]),
        "acceso": riassumi(acceso["righe"]),
        "risposte_divergenti": diversi,
        "acceptance_spento": spento["metriche"].get("speculative", {}),
        "acceptance_acceso": acceso["metriche"].get("speculative", {}),
        "righe_spento": spento["righe"],
        "righe_acceso": acceso["righe"],
    }
    Path(a.out).write_text(json.dumps(esito, ensure_ascii=False, indent=1))

    # Confronto appaiato: stessa pagina contro se stessa. Con una deviazione
    # standard del 30% sulla macchina, confrontare le mediane dei due gruppi
    # e' molto piu' debole che confrontare ogni richiesta con la sua gemella.
    rapporti = [c["tok_s"] / s["tok_s"]
                for s, c in zip(spento["righe"], acceso["righe"])
                if s["tok_s"] > 0]
    esito["rapporto_appaiato_mediano"] = round(statistics.median(rapporti), 4)
    esito["appaiati_a_favore_di_acceso"] = sum(1 for r in rapporti if r > 1)
    esito["appaiati_totali"] = len(rapporti)
    Path(a.out).write_text(json.dumps(esito, ensure_ascii=False, indent=1))

    s, c = esito["spento"], esito["acceso"]
    print(f"\n{'':10} {'mediana':>9} {'prime 6':>9} {'ultime 6':>9}")
    print(f"{'corpus OFF':10} {s['mediana']:9.2f} {s['prime']:9.2f} {s['ultime']:9.2f}")
    print(f"{'corpus ON':10} {c['mediana']:9.2f} {c['prime']:9.2f} {c['ultime']:9.2f}")
    delta = (c["mediana"] / s["mediana"] - 1) * 100 if s["mediana"] else 0.0
    print(f"\ndelta mediana:        {delta:+.1f}%")
    print(f"rapporto appaiato:    {esito['rapporto_appaiato_mediano']:.3f}  "
          f"({esito['appaiati_a_favore_di_acceso']}/{esito['appaiati_totali']} "
          f"richieste piu' veloci con il corpus)")
    for nome, m in (("OFF", esito["acceptance_spento"]),
                    ("ON ", esito["acceptance_acceso"])):
        if m:
            print(f"accettazione {nome}:     {m.get('acceptance_rate', 0):.3f}  "
                  f"(draft {m.get('total_draft_tokens', 0)}, "
                  f"accettati {m.get('total_accepted_tokens', 0)})")
    if diversi:
        print(f"ATTENZIONE: {len(diversi)} risposte divergenti fra i bracci "
              f"— il confronto non e' valido: {diversi[:5]}")
    else:
        print("le risposte dei due bracci coincidono token per token")
    print(f"\nscritto in {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
