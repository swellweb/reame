"""The anti-invention belt: no factual atom without a source.

Contract: every number, phone number and clock time appearing in an answer
must also appear in at least one of the given sources (factsheet, approved
templates). The renderer built on byte-for-byte copy satisfies this by
construction; this module exists so CI can *prove* it on every commit, and so
any future path that lets a model near the output is caught the day it slips.

An anchored answer can still be wrong — the right value served to the wrong
question is the selector's failure, invisible here by design. This belt only
makes inventing a value a test failure instead of a production incident.

Atoms are normalised before comparison so spelling differences don't create
false alarms: "35,00" and "35" collide on 35.0; "08.30" and "8:30" collide on
"8:30"; a phone keeps only its digits. Extraction is ordered — phones first,
then clock times, then loose numbers — each match consuming its span, so a
phone's digits never leak into the number pool.
"""
import re

_TEL = re.compile(r"\b0\d{2,3}[\s./-]\d{5,7}\b")
_ORA = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")
_NUM = re.compile(r"\b\d+(?:[.,]\d{1,2})?\b")


def atomi(testo):
    """The set of factual atoms in `testo`: (kind, normalised value)."""
    trovati = set()

    def _consuma(m):
        return " " * len(m.group(0))

    def _tel(m):
        trovati.add(("tel", re.sub(r"\D", "", m.group(0))))
        return _consuma(m)

    testo = _TEL.sub(_tel, testo)

    def _ora(m):
        h, mm = int(m.group(1)), int(m.group(2))
        # "35.00" is a price with a dot, not a clock reading of hour 35.
        if h <= 23 and mm <= 59:
            trovati.add(("ora", "%d:%02d" % (h, mm)))
            return _consuma(m)
        return m.group(0)

    testo = _ORA.sub(_ora, testo)

    for m in _NUM.finditer(testo):
        trovati.add(("num", float(m.group(0).replace(",", "."))))

    return trovati


def verifica(risposta, fonti):
    """Atoms of `risposta` that no source anchors; empty means safe."""
    consentiti = set()
    for fonte in fonti:
        consentiti |= atomi(fonte)
    return sorted(atomi(risposta) - consentiti,
                  key=lambda a: (a[0], str(a[1])))
