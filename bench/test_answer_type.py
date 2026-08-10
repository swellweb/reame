"""Isolated tests for answer-type filtering.

The premise, from measurement: BM25 finds the right block 95% of the time when
the question borrows the page's words and 50% when it does not. But the *kind*
of thing being asked for survives rewording even when the vocabulary does not —
"quanto costa la resina epossidica" and "quanto spendo per quel trattamento"
share almost no words and both want a price.

So: work out what kind of answer the question wants, keep only the blocks that
contain that kind of data, and let BM25 rank what is left.

    python3 -m pytest bench/test_answer_type.py -q
"""
import pytest

from answer_type import answer_types, block_types, top_k_typed


# --------------------------------------------------------------------------
# reading the question
# --------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "Qual è il prezzo al mq della resina epossidica autolivellante civile?",
    "Quanto spendo per un metro del trattamento base in un alloggio privato?",
    "Quanto viene la lavorazione manuale più costosa?",
    "Che tariffa applicate ai grandi magazzini?",
])
def test_price_questions_are_recognised_however_they_are_worded(question):
    assert "price" in answer_types(question)


@pytest.mark.parametrize("question,wanted", [
    ("Dopo quante ore il pavimento è pedonabile?", "duration"),
    ("Dopo quanto tempo si può calpestare?", "duration"),
    ("Quanti anni di garanzia sui pavimenti industriali?", "duration"),
    ("Entro quanti km il sopralluogo è gratuito?", "distance"),
    ("Fino a che distanza venite a vedere gratis?", "distance"),
    ("Qual è il numero di telefono commerciale?", "phone"),
    ("Che recapito uso per chiedere un'offerta?", "phone"),
    ("Quali sono gli orari dell'ufficio nei giorni feriali?", "clock"),
    ("A che ora si può telefonare durante la settimana?", "clock"),
    ("In quali province operano?", "place"),
    ("In che zone della regione siete attivi?", "place"),
])
def test_other_types_survive_rewording(question, wanted):
    assert wanted in answer_types(question)


def test_a_yes_no_question_asks_for_no_particular_type():
    # Nothing to filter on: these must fall through to plain BM25 rather than
    # being narrowed to an arbitrary subset.
    assert answer_types("Gli operai vengono anche di domenica?") == set()
    assert answer_types("Venite anche in Sardegna o in Sicilia?") == set()


def test_type_detection_ignores_case():
    assert answer_types("QUANTO COSTA?") == answer_types("quanto costa?")


# --------------------------------------------------------------------------
# reading the block
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,wanted", [
    ("Prezzo chiavi in mano: 35,00 € al metro quadro", "price"),
    ("si parte da 35 euro al metro quadro", "price"),
    ("il pavimento è pedonabile dopo 24 ore dalla stesura", "duration"),
    ("da 3 a 5 giorni lavorativi per un appartamento", "duration"),
    ("10 anni sui pavimenti industriali multistrato", "duration"),
    ("gratuito entro 30 km dalla nostra sede", "distance"),
    ("Commerciale: 0574 812345", "phone"),
    ("Orari ufficio: lun-ven 8:30-12:30", "clock"),
    ("Operiamo nelle province di Prato, Firenze", "place"),
])
def test_blocks_advertise_the_data_they_hold(text, wanted):
    assert wanted in block_types(text)


def test_a_block_of_pure_prose_holds_no_typed_data():
    prose = ("Crediamo che un pavimento non sia soltanto una superficie su cui "
             "camminare, ma il fondamento silenzioso di ogni ambiente vissuto.")
    assert block_types(prose) == set()


def test_a_year_is_not_a_duration():
    # "dal 2009" is a date, not "10 anni di garanzia". Counting it as a
    # duration would let the company-history block pass the warranty filter.
    assert "duration" not in block_types("ResinTech opera dal 2009 nel settore")


def test_a_vat_number_is_not_a_phone_number():
    assert "phone" not in block_types("P.IVA 02458730971")


# --------------------------------------------------------------------------
# the filter, where it has to earn its place
# --------------------------------------------------------------------------

def test_the_filter_overrides_a_ranking_bm25_gets_wrong():
    # BM25 alone prefers block 0: it repeats the question's words and is short,
    # which length normalisation rewards. But it holds no price, and the
    # question wants one. The filter must drop it.
    blocks = [
        "trattamento base trattamento base per alloggio privato",   # words, no price
        "Resina epossidica per interni civili, 35,00 € al metro quadro",
    ]
    question = "Quanto spendo per un metro del trattamento base in un alloggio privato?"
    assert top_k_typed(question, blocks, k=1) == [1]


def test_the_filter_falls_back_when_no_block_has_the_type():
    # Filtering to nothing would be worse than not filtering: return BM25's
    # own ranking rather than an empty result.
    blocks = ["il pavimento è bello", "la resina è resistente"]
    assert top_k_typed("quanto costa la resina?", blocks, k=2) == [1, 0]


def test_a_typeless_question_is_ranked_exactly_as_bm25_would():
    from retrieval import top_k
    blocks = ["gli applicatori riposano il weekend",
              "non lavoriamo il weekend nei cantieri",
              "la resina catalizza meglio"]
    q = "Gli operai vengono anche di domenica?"
    assert top_k_typed(q, blocks, k=3) == top_k(q, blocks, k=3)


def test_the_filter_keeps_every_block_of_the_right_type():
    # Three blocks carry a price; asking for two must return two of those
    # three, never a priceless one promoted by word overlap.
    blocks = [
        "prezzo prezzo prezzo trattamento",              # bait: words, no figure
        "epossidico civile 35,00 € al metro quadro",
        "spatolato decorativo 48,00 € al metro quadro",
        "industriale multistrato 28,00 € al metro quadro",
    ]
    picked = top_k_typed("Quanto costa il trattamento?", blocks, k=2)
    assert 0 not in picked
    assert len(picked) == 2


def test_k_larger_than_the_surviving_set_is_capped():
    blocks = ["nessun dato qui", "costa 35,00 € al metro"]
    assert top_k_typed("quanto costa?", blocks, k=5) == [1]
