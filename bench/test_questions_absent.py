"""Structural contract for the trap-question and composite-question sets.

The trap set exists to measure one number: how often the system says
NON PRESENTE when the answer genuinely is not in the factsheet. A malformed
trap poisons that number silently, so the shape is pinned here:

  * 50 traps, half on nearby themes (the confusable half), half far away;
  * every trap expects exactly NON PRESENTE;
  * every nearby trap carries at least one reject pattern, and each reject
    pattern must match the REAL factsheet — a reject is the true value the
    system would wrongly serve, so a reject matching nothing guards nothing.

The composite set (multi-fact, disambiguation, arithmetic) is not scored by
regex in v1; its contract is lighter: labelled handling class, non-empty
expectation.

    python3 -m pytest bench/test_questions_absent.py -q
"""
import json
import pathlib
import re

BENCH = pathlib.Path(__file__).parent
FACTSHEET = (BENCH / "page_factsheet.txt").read_text()


def _carica(nome):
    with open(BENCH / nome) as f:
        return [json.loads(r) for r in f if r.strip()]


# --------------------------------------------------------------------------
# traps
# --------------------------------------------------------------------------

def test_le_trappole_sono_cinquanta_meta_vicine_meta_lontane():
    trappole = _carica("questions_absent.jsonl")
    assert len(trappole) == 50
    temi = [t["tema"] for t in trappole]
    assert temi.count("vicino") == 25
    assert temi.count("lontano") == 25
    assert set(temi) == {"vicino", "lontano"}


def test_ogni_trappola_attende_esattamente_non_presente():
    for t in _carica("questions_absent.jsonl"):
        assert t["attesa"] == "NON PRESENTE", t["id"]
        assert t["accept"] == ["NON PRESENTE"], t["id"]


def test_id_e_domande_senza_duplicati():
    trappole = _carica("questions_absent.jsonl")
    ids = [t["id"] for t in trappole]
    domande = [t["domanda"] for t in trappole]
    assert len(set(ids)) == len(ids)
    assert len(set(domande)) == len(domande)
    for t in trappole:
        assert t["domanda"].strip(), t["id"]


def test_ogni_trappola_vicina_ha_reject_che_mordono_il_factsheet_vero():
    # A nearby trap is dangerous precisely because a plausible-but-wrong value
    # sits in the sheet; the reject pattern must prove that value exists.
    for t in _carica("questions_absent.jsonl"):
        if t["tema"] != "vicino":
            continue
        assert t["reject"], "trappola vicina senza reject: %s" % t["id"]
        for pattern in t["reject"]:
            assert re.search(pattern, FACTSHEET), \
                "reject %r di %s non trova nulla nel factsheet" % (pattern, t["id"])


# --------------------------------------------------------------------------
# composites
# --------------------------------------------------------------------------

def test_le_composte_sono_dieci_con_gestione_etichettata():
    composte = _carica("questions_composite.jsonl")
    assert len(composte) == 10
    ammesse = {"disambiguazione", "doppia-riga", "calcolo", "lista-negativa"}
    for c in composte:
        assert c["gestione"] in ammesse, c["id"]
        assert c["attesa"].strip(), c["id"]
        assert c["domanda"].strip(), c["id"]
    ids = [c["id"] for c in composte]
    assert len(set(ids)) == len(ids)
