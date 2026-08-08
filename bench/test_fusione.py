"""Isolated tests for the fused selector (lexical + question-space cosine).

The embedder is a dependency, so every test injects a fake `encode` returning
hand-picked vectors; the cosine and fusion arithmetic in the expectations is
worked out by eye in the comments, never read back from the code.

    python3 -m pytest bench/test_fusione.py -q
"""
import math

import numpy as np

from fusione import (IndiceParafrasi, punteggia_fuso, seleziona_ibrido,
                     seleziona_v2)


def encode_finto(tabella):
    """An embedder double: maps each known text to a fixed vector."""
    def encode(testi):
        return np.array([tabella[t] for t in testi], dtype=np.float32)
    return encode


# Two rows, two paraphrases each, in a 2-d embedding space chosen so the
# cosines are exact: e1=(1,0), e2=(0,1), diag=(1,1)/√2.
E1, E2 = [1.0, 0.0], [0.0, 1.0]
DIAG = [1 / math.sqrt(2), 1 / math.sqrt(2)]

VOCI = [{"indice": 0, "parafrasi": ["come riga zero", "riga zero bis"]},
        {"indice": 1, "parafrasi": ["come riga uno", "riga uno bis"]}]

TABELLA = {"query: come riga zero": E1, "query: riga zero bis": DIAG,
           "query: come riga uno": E2, "query: riga uno bis": E2,
           "query: domanda uguale a riga zero": E1,
           "query: domanda diagonale": DIAG}


def _indice():
    return IndiceParafrasi(VOCI, encode_finto(TABELLA))


def test_il_coseno_per_riga_e_il_massimo_sulle_sue_parafrasi():
    ind = _indice()
    # Question = e1: row 0 has paraphrases at cos 1.0 (e1) and 1/√2 (diag)
    # → max 1.0; row 1 has both at e2 → cos 0.0.
    coseni = ind.coseni("domanda uguale a riga zero")
    assert coseni[0] == np.float32(1.0)
    assert coseni[1] == np.float32(0.0)


def test_il_coseno_della_diagonale_vale_radice_di_mezzo():
    ind = _indice()
    coseni = ind.coseni("domanda diagonale")
    # diag·e1 = 1/√2 ≈ 0.7071 for row 0 (via its e1 paraphrase, and its diag
    # paraphrase gives exactly 1.0 → max is 1.0); row 1: diag·e2 = 1/√2.
    assert abs(coseni[0] - 1.0) < 1e-6
    assert abs(coseni[1] - 1 / math.sqrt(2)) < 1e-6


def test_la_fusione_pesa_meta_lessico_normalizzato_meta_coseno():
    # bm25 [2.0, 0.0] → normalised [1.0, 0.0]; cos [0.9, 0.2];
    # fused = 0.5·cos + 0.5·bm25n = [0.95, 0.10].
    fusi = punteggia_fuso(bm25=[2.0, 0.0], coseni=[0.9, 0.2])
    assert [round(f, 6) for f in fusi] == [0.95, 0.10]


def test_lessico_muto_lascia_parlare_solo_il_coseno():
    # All-zero bm25 (the paraphrase case) must not divide by zero:
    # fused = 0.5·cos = [0.45, 0.10].
    fusi = punteggia_fuso(bm25=[0.0, 0.0], coseni=[0.9, 0.2])
    assert [round(f, 6) for f in fusi] == [0.45, 0.10]


def test_seleziona_ibrido_applica_la_doppia_soglia_sui_punteggi_fusi():
    corpus = ["riga zero", "riga uno"]
    ind = _indice()
    # Question e1: cos = [1.0, 0.0]; bm25 of "domanda uguale a riga zero" vs
    # the corpus rows — "riga" and "zero" hit row 0, so bm25n = [1.0, x<1].
    # Fused row 0 ≥ 0.5·1.0 + 0.5·1.0 = 1.0 → wins with wide margin.
    assert seleziona_ibrido("domanda uguale a riga zero", corpus, ind,
                            soglia=0.6, margine=0.2) == 0


def test_seleziona_ibrido_rifiuta_sotto_soglia():
    corpus = ["riga zero", "riga uno"]
    ind = _indice()
    # "domanda diagonale": cos = [1.0, 1/√2] → margin on cosine alone is
    # 0.29; with bm25 hitting neither row (no shared terms except "riga"
    # absent from the question), fused ≈ [0.5, 0.35] — below soglia 0.9.
    assert seleziona_ibrido("domanda diagonale", corpus, ind,
                            soglia=0.9, margine=0.0) is None


# --------------------------------------------------------------------------
# v2: computed-refusal gates around a 3-channel ranking
# --------------------------------------------------------------------------

def test_v2_rifiuta_il_termine_scoperto_senza_toccare_l_encoder():
    # "whatsapp" lives nowhere in the site's language: the refusal must cost
    # zero embeddings — an encoder call here is an architecture bug.
    ind = _indice()
    ind.encode = lambda testi: (_ for _ in ()).throw(
        AssertionError("encoder chiamato per un rifiuto calcolabile"))
    corpus = ["riga zero", "riga uno"]
    lingua = corpus + ["come riga zero", "riga zero bis",
                       "come riga uno", "riga uno bis"]
    assert seleziona_v2("Avete un numero whatsapp?", corpus, ind, lingua,
                        margine=0.0) is None


def test_v2_il_canale_a_radici_aggancia_la_flessione_del_verbo():
    # "calpestare" vs "calpestabile": no exact term match, same 6-char stem.
    # Only row 0's bundle shares it, so row 0 must win the ranking.
    voci = [{"indice": 0, "parafrasi": ["quando è calpestabile il pavimento?"]},
            {"indice": 1, "parafrasi": ["che telefono avete?"]}]
    tabella = {"query: quando è calpestabile il pavimento?": E1,
               "query: che telefono avete?": E2,
               "query: si può calpestare?": DIAG}  # cosine is neutral: 1/√2 to both
    ind = IndiceParafrasi(voci, encode_finto(tabella))
    corpus = ["riga pavimento", "riga telefono"]
    lingua = corpus + [p for v in voci for p in v["parafrasi"]]
    assert seleziona_v2("si può calpestare?", corpus, ind, lingua,
                        margine=0.0) == 0


def test_v2_il_contrasto_di_valore_boccia_il_vincitore():
    # The ISO row wins the ranking, but the question names ISO 14001 and the
    # row holds 9001: computed refusal, not a served near-miss.
    voci = [{"indice": 0, "parafrasi": ["che certificazioni avete?"]},
            {"indice": 1, "parafrasi": ["che telefono avete?"]}]
    tabella = {"query: che certificazioni avete?": E1,
               "query: che telefono avete?": E2,
               "query: avete la certificazione iso 14001?": E1}
    ind = IndiceParafrasi(voci, encode_finto(tabella))
    corpus = ["Certificazione qualità: ISO 9001:2015",
              "Telefono commerciale: 0574 812345"]
    lingua = corpus + [p for v in voci for p in v["parafrasi"]] + ["iso 14001"]
    assert seleziona_v2("avete la certificazione iso 14001?", corpus, ind,
                        lingua, margine=0.0) is None
