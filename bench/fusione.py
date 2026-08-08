"""Fused selector: lexical BM25 + question-space cosine over paraphrases.

The measured hole in the deterministic selector is paraphrase blindness (0%
with safe thresholds): when the caller's words differ from the sheet's, no
lexical hook fires. The fix stays true to matching-not-generation — at
onboarding every factsheet row grows a bundle of question-paraphrases, and at
runtime the caller's question is compared question-to-question, the task a
bi-encoder is actually trained for. The row's score on this channel is the
MAX cosine over its bundle: one good paraphrase is enough, and averaging
would punish rows with many diverse phrasings.

Fusion is a half-and-half sum: BM25 is normalised per query (its scale is
query-dependent; cosine's is not), so either channel alone can lift a row to
at most 0.5 and agreement pushes toward 1.0. The double threshold then works
exactly as in the deterministic selector, on the fused scale.
"""
import re

import numpy as np

from assenza import (contrasto_valore, copertura_scoperta,
                     negazione_esplicita, tipo_orfano)
from retrieval import bm25_scores
from selettore import _senza_stopword, _veto, espandi, normalizza


class IndiceParafrasi:
    """Paraphrase bundles embedded once at onboarding; cosines at runtime.

    `encode` maps a list of texts to L2-normalised row vectors; it is
    injected so tests run on hand-picked geometry and production runs on
    the real bi-encoder. Texts carry the "query: " prefix on both sides —
    stored paraphrases and incoming questions are the same kind of object.
    """

    def __init__(self, voci, encode):
        self.encode = encode
        piatte, self.riga_di = [], []
        ordinate = sorted(voci, key=lambda v: v["indice"])
        for v in ordinate:
            for p in v["parafrasi"]:
                piatte.append("query: " + p)
                self.riga_di.append(v["indice"])
        self.n_righe = max(self.riga_di) + 1
        # The bundle as one text per row: the lexical question-space channel
        # reads it with stems, catching inflections cosine confuses.
        self.bundle = [" ".join(v["parafrasi"]) for v in ordinate]
        self.matrice = encode(piatte)
        self.riga_di = np.array(self.riga_di)

    def coseni(self, domanda):
        """Per-row max cosine between the question and the row's bundle."""
        q = self.encode(["query: " + domanda])[0]
        tutti = self.matrice @ q
        per_riga = np.zeros(self.n_righe, dtype=np.float32)
        np.maximum.at(per_riga, self.riga_di, tutti)
        return per_riga


def punteggia_fuso(bm25, coseni):
    """0.5·cos + 0.5·(bm25 / max bm25); a silent lexical channel scores 0."""
    massimo = max(bm25) if bm25 else 0.0
    norma = [b / massimo if massimo > 0 else 0.0 for b in bm25]
    return [0.5 * c + 0.5 * b for c, b in zip(coseni, norma)]


def _stemmi6(testo):
    return " ".join(t[:6] for t in re.findall(r"\w+", testo))


def punteggia_v2(domanda, corpus, indice):
    """Three channels, each normalised per query to its own maximum, averaged.

    Absolute values are NOT trusted (the measured cosine distributions of
    answerable and absent questions overlap); only the ordering and the
    margin matter, and absence is decided by the gates, not by a threshold.
    """
    d_lessico = _senza_stopword(espandi(domanda))
    b_righe = bm25_scores(d_lessico,
                          [_senza_stopword(normalizza(r)) for r in corpus])
    d_stemmi = _stemmi6(_senza_stopword(normalizza(domanda)))
    b_bundle = bm25_scores(d_stemmi,
                           [_stemmi6(_senza_stopword(normalizza(b)))
                            for b in indice.bundle])
    coseni = list(indice.coseni(domanda))

    def norma(v):
        massimo = max(v) if v else 0.0
        return [x / massimo if massimo > 0 else 0.0 for x in v]

    return [(a + b + c) / 3 for a, b, c in
            zip(norma(b_righe), norma(b_bundle), norma(coseni))]


def seleziona_v2(domanda, corpus, indice, lingua, margine, gate_scoperti=1):
    """v2: computed-refusal gates around the 3-channel ranking.

    Cheapest evidence first — the coverage and orphan gates refuse before any
    embedding is computed. The ranking then only resolves WHICH row, and the
    value-contrast and negation gates audit the winner it proposes.
    """
    if len(copertura_scoperta(domanda, lingua)) >= gate_scoperti:
        return None
    if tipo_orfano(domanda, corpus):
        return None

    fusi = punteggia_v2(domanda, corpus, indice)
    candidati = _veto(normalizza(domanda), corpus)
    gara = sorted(candidati, key=lambda i: (-fusi[i], i))
    if not gara:
        return None
    top2 = fusi[gara[1]] if len(gara) > 1 else 0.0
    if fusi[gara[0]] - top2 < margine:
        return None

    riga = corpus[gara[0]]
    if contrasto_valore(domanda, riga) or negazione_esplicita(domanda, riga):
        return None
    return gara[0]


def seleziona_ibrido(domanda, corpus, indice, soglia, margine):
    """Winning row index or None, double threshold on the fused score."""
    bm25 = bm25_scores(_senza_stopword(espandi(domanda)),
                       [_senza_stopword(normalizza(r)) for r in corpus])
    fusi = punteggia_fuso(bm25, indice.coseni(domanda))

    candidati = _veto(normalizza(domanda), corpus)
    in_gara = sorted(candidati, key=lambda i: (-fusi[i], i))
    if not in_gara:
        return None
    top1 = fusi[in_gara[0]]
    top2 = fusi[in_gara[1]] if len(in_gara) > 1 else 0.0
    if top1 >= soglia and (top1 - top2) >= margine:
        return in_gara[0]
    return None
