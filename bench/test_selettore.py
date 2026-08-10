"""Isolated tests for the deterministic selector v1.

The unit under test is the DECISION: given scores over factsheet rows, either
commit to one row or answer NON PRESENTE (None). The scorer is a dependency,
so here it is a test double returning hand-picked values; the double-threshold
arithmetic below is checked by eye, not by running the code first.

    python3 -m pytest bench/test_selettore.py -q
"""
import pathlib

from selettore import espandi, normalizza, righe, seleziona

FACTSHEET_VERO = (pathlib.Path(__file__).parent / "page_factsheet.txt").read_text()

RIGHE_FINTE = ["riga zero", "riga uno", "riga due"]


def scorer_fisso(valori):
    """A scorer double: ignores the query, returns the given scores."""
    return lambda domanda, corpus: list(valori)


# --------------------------------------------------------------------------
# the double threshold
# --------------------------------------------------------------------------

def test_vince_la_riga_sopra_entrambe_le_soglie():
    # top1=3.0 ≥ 2.0 and gap 3.0−1.0=2.0 ≥ 1.0: commit to row 0.
    assert seleziona("q", RIGHE_FINTE, soglia=2.0, margine=1.0,
                     punteggia=scorer_fisso([3.0, 1.0, 0.5])) == 0


def test_sotto_la_soglia_assoluta_si_rifiuta():
    # top1=1.5 < 2.0: no row is convincing on its own.
    assert seleziona("q", RIGHE_FINTE[:2], soglia=2.0, margine=0.0,
                     punteggia=scorer_fisso([1.5, 1.0])) is None


def test_margine_stretto_significa_ambiguita_e_si_rifiuta():
    # gap 3.0−2.8=0.2 < 0.5: two rows both plausible → refuse, don't guess.
    assert seleziona("q", RIGHE_FINTE, soglia=2.0, margine=0.5,
                     punteggia=scorer_fisso([3.0, 2.8, 0.1])) is None


def test_riga_unica_convincente_vince_con_top2_a_zero():
    # A single row: top2 defaults to 0.0, gap = 3.0 ≥ 1.0.
    assert seleziona("q", ["sola"], soglia=2.0, margine=1.0,
                     punteggia=scorer_fisso([3.0])) == 0


def test_il_veto_esclude_le_righe_fuori_tipo_anche_se_prime():
    # Row 0 scores highest but is vetoed; among candidates {1,2}:
    # top1=3.0 ≥ 2.0, gap 3.0−1.0=2.0 ≥ 1.0 → row 1.
    assert seleziona("q", RIGHE_FINTE, soglia=2.0, margine=1.0,
                     punteggia=scorer_fisso([9.0, 3.0, 1.0]),
                     candidati=[1, 2]) == 1


# --------------------------------------------------------------------------
# normalisation and aliases
# --------------------------------------------------------------------------

def test_normalizza_piega_maiuscole_e_accenti():
    assert normalizza("È GRATIS il sopralluogo?") == "e gratis il sopralluogo?"


def test_espandi_aggiunge_i_sinonimi_canonici():
    # "mq" must grow the lexical hooks the factsheet actually uses.
    assert "metro quadro" in espandi("quanto costa al mq?")
    assert "pec" in espandi("mi date la mail?")


def test_espandi_non_tocca_le_domande_senza_alias():
    testo = normalizza("quanto costa il microcemento?")
    assert espandi("quanto costa il microcemento?") == testo


# --------------------------------------------------------------------------
# rows of the real factsheet — the shape production will see
# --------------------------------------------------------------------------

def test_le_righe_del_factsheet_vero_sono_27_senza_cornice():
    r = righe(FACTSHEET_VERO)
    assert len(r) == 27
    assert r[0].startswith("Prezzo — Resina epossidica")
    assert "scorciatoie" in r[-1]
    assert not any("SCHEDA" in riga for riga in r)


def test_sul_factsheet_vero_il_telefono_commerciale_vince():
    # Independent derivation: only one row holds both terms "telefono" and
    # "commerciale", so with permissive thresholds BM25 must rank it first.
    r = righe(FACTSHEET_VERO)
    scelta = seleziona("Qual è il numero di telefono commerciale?", r,
                       soglia=0.0, margine=0.0)
    assert scelta is not None and "Telefono commerciale" in r[scelta]


def test_sul_factsheet_vero_la_norvegia_viene_rifiutata():
    # No question term appears anywhere: every score is 0 < 0.5 → refuse.
    r = righe(FACTSHEET_VERO)
    assert seleziona("Qual è la capitale della Norvegia?", r,
                     soglia=0.5, margine=0.0) is None
