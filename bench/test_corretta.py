"""Pin the scoring semantics of the bench: matching is about facts, not case.

Found the hard way: the selector picked «NO: "Non serviamo le isole"» for
"Servono le isole?" — the objectively right row — and the scorer rejected it
because the accept pattern '^no\\b' was written lowercase for model answers.
A scorer that fails the correct answer is a bug in the bench, and a bench bug
is worse than a code bug: it lies about every number it produces.

    python3 -m pytest bench/test_corretta.py -q
"""
from misura_selettore import CORPUS, corretta


def _domanda(accept, reject, attesa="x"):
    return {"attesa": attesa, "accept": accept, "reject": reject}


def _indice_di(frammento):
    (i,) = [i for i, r in enumerate(CORPUS) if frammento in r]
    return i


def test_il_no_maiuscolo_della_riga_soddisfa_il_pattern_minuscolo():
    q = _domanda(["^no\\b"], ["^s[iì]"])
    assert corretta(q, _indice_di("Non serviamo le isole"))


def test_prato_con_la_maiuscola_soddisfa_il_pattern_minuscolo():
    q = _domanda(["prato", "firenze", "pistoia", "lucca"], [])
    assert corretta(q, _indice_di("Province servite"))


def test_iso_in_maiuscolo_soddisfa_il_pattern_minuscolo():
    q = _domanda(["iso\\s*9001(:2015)?"], [])
    assert corretta(q, _indice_di("ISO 9001"))


def test_anche_il_reject_ignora_il_case():
    # A reject written lowercase must still catch the uppercase bait,
    # otherwise the trap silently stops trapping.
    q = _domanda(["qualunque"], ["os6"])
    assert not corretta(q, _indice_di("SOA categoria OS6"))


def test_none_resta_sbagliato_per_le_domande_con_risposta():
    assert not corretta(_domanda(["^no\\b"], []), None)


def test_none_resta_giusto_per_le_trappole():
    assert corretta(_domanda(["NON PRESENTE"], [], attesa="NON PRESENTE"), None)
