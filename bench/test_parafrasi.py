"""Structural contract for the onboarding paraphrase index.

The index simulates the onboarding factory: for every factsheet row, the ways
a real caller might ask for it. The decisive experiment stands on this file,
so its shape is pinned:

  * every one of the 27 rows is covered, with at least 12 paraphrases each;
  * paraphrases are unique and non-empty;
  * no paraphrase coincides (after normalisation) with a question of the
    evaluation sets — otherwise the experiment would grade itself on its own
    training data and the ≥90% assertion would be laundered.

    python3 -m pytest bench/test_parafrasi.py -q
"""
import json
import pathlib

from selettore import normalizza, righe

BENCH = pathlib.Path(__file__).parent
N_RIGHE = len(righe((BENCH / "page_factsheet.txt").read_text()))


def _indice():
    with open(BENCH / "paraphrases_factsheet.jsonl") as f:
        return [json.loads(r) for r in f if r.strip()]


def _domande_di_valutazione():
    fuori = set()
    for nome in ("questions.jsonl", "questions_paraphrased.jsonl",
                 "questions_absent.jsonl"):
        with open(BENCH / nome) as f:
            for r in f:
                if r.strip():
                    fuori.add(normalizza(json.loads(r)["domanda"]))
    return fuori


def test_ogni_riga_del_factsheet_ha_almeno_dodici_parafrasi():
    voci = _indice()
    assert sorted(v["indice"] for v in voci) == list(range(N_RIGHE))
    for v in voci:
        assert len(v["parafrasi"]) >= 12, "riga %d scoperta" % v["indice"]


def test_le_parafrasi_sono_uniche_e_non_vuote():
    viste = set()
    for v in _indice():
        for p in v["parafrasi"]:
            assert p.strip(), "parafrasi vuota alla riga %d" % v["indice"]
            chiave = normalizza(p)
            assert chiave not in viste, "duplicata: %r" % p
            viste.add(chiave)


def test_nessuna_parafrasi_copia_le_domande_di_valutazione():
    fuori = _domande_di_valutazione()
    for v in _indice():
        for p in v["parafrasi"]:
            assert normalizza(p) not in fuori, \
                "la parafrasi %r è una domanda del set di valutazione" % p
