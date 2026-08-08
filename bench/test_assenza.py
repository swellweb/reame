"""Isolated tests for the computed-refusal gates.

Measured motivation: e5 cosines cannot separate answerable questions from
traps (medians 0.895 vs 0.879) — absence is not predictable from similarity.
These gates therefore COMPUTE absence from evidence: a value named in the
question that mismatches the row's value of the same kind, an answer type no
row can serve, an explicit negation of the row's own subject, question terms
covered nowhere. Pure logic; every expectation derived by hand.

    python3 -m pytest bench/test_assenza.py -q
"""
from assenza import (contrasto_valore, copertura_scoperta, negazione_esplicita,
                     tipo_orfano)


# --------------------------------------------------------------------------
# value contrast: same kind of atom, different value → the caller wants
# something the row does not hold
# --------------------------------------------------------------------------

def test_codice_diverso_della_stessa_famiglia_e_contrasto():
    assert contrasto_valore("Avete la certificazione ISO 14001?",
                            "Certificazione qualità: ISO 9001:2015")


def test_stesso_codice_non_e_contrasto():
    assert not contrasto_valore("Avete la ISO 9001?",
                                "Certificazione qualità: ISO 9001:2015")


def test_sigla_alfanumerica_diversa_e_contrasto():
    assert contrasto_valore("Avete la SOA per la categoria OG1?",
                            "Attestazione: SOA categoria OS6 classifica II")


def test_giorno_chiesto_fuori_dai_giorni_della_riga_e_contrasto():
    assert contrasto_valore("Lo showroom è aperto la domenica?",
                            "Showroom sabato: dalle 9:00 alle 12:00")


def test_domanda_senza_valori_non_contrasta_mai():
    assert not contrasto_valore("Quanto costa lo spatolato?",
                                "Prezzo — Spatolato decorativo: 48,00 €")


def test_la_quantita_instanziata_dall_utente_non_contrasta():
    # "300" is the caller's own example, not an identifier: asking about a
    # 300 m² job must not be read as asking about a different discount.
    assert not contrasto_valore("Per 300 metri quadri c'è uno sconto?",
                                "Sconto: 10% sopra i 200 mq")
    assert not contrasto_valore("Sto a 60 km, il sopralluogo quanto costa?",
                                "Oltre i 30 km contributo di 50 €")


def test_l_identificatore_a_molte_cifre_contrasta_ancora():
    # 14001 has no unit and ≥4 digits: it names a THING, not an amount.
    assert contrasto_valore("Avete la ISO 14001?",
                            "Certificazione qualità: ISO 9001:2015")


# --------------------------------------------------------------------------
# orphan answer type: the question wants a kind of datum absent from every row
# --------------------------------------------------------------------------

CORPUS_MINI = ["Prezzo — Microcemento: 60,00 € al metro quadro",
               "Telefono commerciale: 0574 812345"]


def test_spessore_in_millimetri_e_tipo_orfano_su_un_listino():
    assert tipo_orfano("Qual è lo spessore in millimetri del microcemento?",
                       CORPUS_MINI)


def test_prezzo_non_e_orfano_dove_un_prezzo_esiste():
    assert not tipo_orfano("Quanto costa il microcemento?", CORPUS_MINI)


def test_domanda_senza_tipo_riconosciuto_non_e_mai_orfana():
    assert not tipo_orfano("Mi parli della vostra azienda?", CORPUS_MINI)


# --------------------------------------------------------------------------
# explicit negation: the question itself excludes the row's subject
# --------------------------------------------------------------------------

def test_non_la_pec_esclude_la_riga_della_pec():
    assert negazione_esplicita("Qual è la vostra email ordinaria, non la PEC?",
                               "PEC: resintechpavimenti@legalmail.it")


def test_senza_appuntamento_esclude_la_riga_su_appuntamento():
    assert negazione_esplicita("Posso venire senza appuntamento?",
                               "Showroom sabato: solo su appuntamento")


def test_nessuna_negazione_nessuna_esclusione():
    assert not negazione_esplicita("Qual è la vostra PEC?",
                                   "PEC: resintechpavimenti@legalmail.it")


# --------------------------------------------------------------------------
# uncovered pivot terms: the question's content words live nowhere in the
# site's language (rows + paraphrase bundles), stem-compared
# --------------------------------------------------------------------------

LINGUA = ["Telefono commerciale: 0574 812345",
          "come vi contatto per un preventivo?",
          "quanto costa la resina al metro quadro?"]


def test_whatsapp_e_iban_sono_scoperti():
    assert copertura_scoperta("Avete un numero WhatsApp o un IBAN?",
                              LINGUA) == ["iban", "whatsapp"]


def test_domanda_dentro_la_lingua_del_sito_e_coperta():
    # "contattarvi" covers via the 6-char stem "contat" of "contatto".
    assert copertura_scoperta("Come posso contattarvi per la resina?",
                              LINGUA) == []


def test_l_italiano_comune_non_e_mai_un_pivot():
    # "spendo", "automobile", "vengono" are frequent general Italian: a site
    # that never wrote them still understands them. Only genuinely rare terms
    # count as uncovered pivots.
    assert copertura_scoperta("Quanto spendo se vengono con l'automobile?",
                              LINGUA) == []


def test_il_pivot_raro_resta_scoperto_anche_tra_parole_comuni():
    # Same sentence shape, but "monopattino" is rare and the site is silent
    # on it: the gate must still fire on exactly that word.
    assert copertura_scoperta("Quanto spendo per il monopattino?",
                              LINGUA) == ["monopattino"]
