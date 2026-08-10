"""Isolated tests for the anti-invention belt.

The property being pinned: every factual atom in an answer — number, phone,
clock time — must exist in at least one of the sources (factsheet, approved
templates). An answer whose atoms are all anchored can still be wrong (right
value, wrong question), but it cannot be *invented*; that residual risk is the
selector's job, not this belt's.

Every expected value below is derived by hand from the extraction rules, not
read back from the implementation.

    python3 -m pytest bench/test_grounding.py -q
"""
import pathlib

from grounding import atomi, verifica

FACTSHEET_VERO = (pathlib.Path(__file__).parent / "page_factsheet.txt").read_text()

# A miniature source for isolated cases: values chosen so each atom kind
# appears exactly once and the arithmetic below can be checked by eye.
FONTE_MINI = "Prezzo: 35,00 € al mq. Telefono: 0574 812345. Apertura 8:30."


# --------------------------------------------------------------------------
# atom extraction
# --------------------------------------------------------------------------

def test_un_prezzo_diventa_un_numero_normalizzato():
    # "35,00" and "35" must collide: same fact, two spellings.
    assert atomi("Costa 35,00 € al mq") == {("num", 35.0)}
    assert atomi("Costa 35 € al mq") == {("num", 35.0)}


def test_telefono_e_orari_non_vengono_scambiati_per_numeri():
    # The phone is one atom (digits only), each clock time one atom; none of
    # their digits may leak into loose numbers.
    assert atomi("Chiama lo 0574 812345 dalle 8:30 alle 12:30") == {
        ("tel", "0574812345"), ("ora", "8:30"), ("ora", "12:30")}


def test_il_telefono_si_normalizza_su_qualsiasi_separatore():
    assert atomi("0574-812345") == atomi("0574/812345") == atomi("0574 812345")


def test_orario_con_zero_e_punto_coincide_con_la_forma_canonica():
    # "08.30" spoken by the model must anchor to "8:30" in the factsheet.
    assert atomi("dalle 08.30") == {("ora", "8:30")}


def test_una_sigla_iso_non_e_un_orario():
    # 9001:2015 must split as two plain numbers, not a clock reading.
    assert atomi("ISO 9001:2015") == {("num", 9001.0), ("num", 2015.0)}


def test_testo_senza_fatti_produce_zero_atomi():
    assert atomi("Non è presente nel documento, mi spiace.") == set()


def test_interno_telefonico_resta_un_numero_separato():
    assert atomi("0574 812399 (interno 2)") == {("tel", "0574812399"),
                                                ("num", 2.0)}


# --------------------------------------------------------------------------
# anchoring verdicts
# --------------------------------------------------------------------------

def test_risposta_ancorata_passa():
    assert verifica("La resina costa 35,00 € al mq", [FONTE_MINI]) == []


def test_numero_inventato_viene_denunciato():
    # 42 exists nowhere in the source: exactly one violation, exactly this one.
    assert verifica("La resina costa 42 € al mq", [FONTE_MINI]) == [("num", 42.0)]


def test_telefono_inventato_viene_denunciato():
    assert verifica("Chiama lo 0574 999999", [FONTE_MINI]) == [("tel", "0574999999")]


def test_le_fonti_si_sommano():
    # The clock time lives only in the second source; together they anchor.
    assert verifica("Alle 8:30 al numero 0574 812345",
                    ["Telefono: 0574 812345"], ) == [("ora", "8:30")]
    assert verifica("Alle 8:30 al numero 0574 812345",
                    ["Telefono: 0574 812345", "apre 8:30"]) == []


def test_violazioni_in_ordine_stabile():
    # Two inventions: reported sorted (kind, value) so CI diffs are readable.
    assert verifica("Costa 99 € e richiamate lo 0111 223344", [FONTE_MINI]) == [
        ("num", 99.0), ("tel", "0111223344")]


# --------------------------------------------------------------------------
# against the real factsheet — the shape the belt will police in CI
# --------------------------------------------------------------------------

def test_risposta_vera_dal_factsheet_reale_e_ancorata():
    assert verifica("Il pavimento è carrabile dopo 72 ore", [FACTSHEET_VERO]) == []
    assert verifica("Telefono commerciale: 0574 812345, orari 8:30-12:30",
                    [FACTSHEET_VERO]) == []


def test_invenzione_sul_factsheet_reale_viene_colta():
    # 96 hours appears nowhere in the sheet (24, 48 and 72 do).
    assert verifica("È carrabile dopo 96 ore", [FACTSHEET_VERO]) == [("num", 96.0)]
