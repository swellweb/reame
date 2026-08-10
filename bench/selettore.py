"""Deterministic selector v1: from a question to one factsheet row, or refusal.

This is the concierge's spine in the selection-not-generation architecture:
the answer is never written by a model, it is a row of the factsheet picked
here and rendered by templates elsewhere. v1 is deliberately model-free —
normalisation, aliases, BM25 over rows, the answer-type veto, and a double
threshold — because its score on the paraphrased bench is the honest baseline
the bi-encoder experiment must beat.

The double threshold encodes the product rule "refusing costs less than
guessing": commit to a row only if it is convincing in absolute terms AND
clearly ahead of the runner-up. Everything else is NON PRESENTE (None).
"""
import re
import unicodedata

from answer_type import answer_types, block_types
from retrieval import bm25_scores

# Canonical expansions: the words callers type → the words the factsheet uses.
# Applied additively (the original terms stay), so an alias can only add
# lexical hooks, never remove them.
ALIAS = {
    "mq": "metro quadro metri quadri",
    "m2": "metro quadro",
    "tel": "telefono",
    "cell": "telefono",
    "cellulare": "telefono",
    "mail": "pec email",
    "email": "pec",
    "iva": "partita iva",
    "metro": "mq",
    "metri": "mq",
}

# Words that carry no selective power. Without this filter BM25 gives
# "capitale della Norvegia" a nonzero score through "della" alone, and the
# absolute threshold stops meaning anything. "dopo", "oltre", "ore" are NOT
# here: on this corpus they are hooks ("Pedonabile dopo", "Oltre la soglia").
_STOPWORD = set("""e o a di da in con su per tra fra il lo la i gli le un uno
una che chi come qual quale quali quanto quanta quanti quante si no non mi ti
ci vi ma se al allo alla ai agli alle dal dallo dalla dai dagli dalle del
dello della dei degli delle nel nello nella nei negli nelle sul sullo sulla
sui sugli sulle piu meno molto poco anche voi noi vostro vostra vostri vostre
qui li""".split())


def _senza_stopword(testo):
    return " ".join(t for t in re.findall(r"\w+", testo) if t not in _STOPWORD)


def normalizza(testo):
    """Lower-case with accents folded, so 'È' and 'e' meet in the index."""
    piatto = unicodedata.normalize("NFKD", testo.lower())
    return "".join(c for c in piatto if not unicodedata.combining(c))


def espandi(testo):
    """Normalised text plus the canonical expansions of any alias present."""
    base = normalizza(testo)
    aggiunte = [ALIAS[t] for t in re.findall(r"\w+", base) if t in ALIAS]
    return base if not aggiunte else base + " " + " ".join(aggiunte)


def righe(testo_factsheet):
    """Payload rows of a factsheet: the frame lines are not selectable."""
    fuori = ("SCHEDA FATTI", "FINE SCHEDA")
    return [r.strip() for r in testo_factsheet.splitlines()
            if r.strip() and not any(f in r for f in fuori)]


def _veto(domanda, corpus):
    """Candidate rows after the answer-type veto; conservative on doubt."""
    cercati = answer_types(domanda)
    if not cercati:
        return list(range(len(corpus)))
    superstiti = [i for i, r in enumerate(corpus) if block_types(r) & cercati]
    return superstiti or list(range(len(corpus)))


def seleziona(domanda, corpus, soglia, margine, punteggia=None, candidati=None):
    """Index of the winning row, or None for NON PRESENTE.

    `punteggia` and `candidati` are injectable so the decision can be tested
    in isolation; by default BM25 scores the alias-expanded question and the
    answer-type veto narrows the field.
    """
    if punteggia is None:
        punteggia = lambda d, c: bm25_scores(
            _senza_stopword(espandi(d)),
            [_senza_stopword(normalizza(r)) for r in c])
    if candidati is None:
        candidati = _veto(normalizza(domanda), corpus)

    punteggi = punteggia(domanda, corpus)
    in_gara = sorted(candidati, key=lambda i: (-punteggi[i], i))
    if not in_gara:
        return None

    top1 = punteggi[in_gara[0]]
    top2 = punteggi[in_gara[1]] if len(in_gara) > 1 else 0.0
    if top1 >= soglia and (top1 - top2) >= margine:
        return in_gara[0]
    return None
