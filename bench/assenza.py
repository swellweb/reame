"""Computed refusal: absence as evidence, not as a low similarity score.

Measured premise: on this corpus the bi-encoder's max cosine for answerable
questions (median 0.895) and for traps (median 0.879) overlap almost
completely — no absolute threshold separates them. So NON PRESENTE is not
predicted from scores; it is computed from four kinds of evidence, each a
piece of pure logic:

  * value contrast — the question names a value (code, number, weekday) and
    the candidate row holds a DIFFERENT value of the same kind: the caller
    asked about something else ("ISO 14001" vs "ISO 9001").
  * orphan answer type — the question wants a kind of datum (thickness in mm,
    an IBAN) that no row of the sheet contains at all.
  * explicit negation — the question itself excludes the row's subject
    ("email ordinaria, NON la PEC" must never be answered with the PEC).
  * uncovered pivot terms — content words of the question that appear nowhere
    in the site's language (rows + onboarding paraphrases), stem-compared:
    "whatsapp", "iban", "rate" on a sheet that never speaks of them.

Every gate is conservative by design: it fires on positive evidence of a
mismatch, never on a hunch.
"""
import re

from answer_type import BLOCK_PATTERNS, QUESTION_PATTERNS
from grounding import atomi
from selettore import _STOPWORD, normalizza

_CODICE = re.compile(r"\b[A-Za-z]{2,3}\d{1,4}\b")
_GIORNI = ("lunedi", "martedi", "mercoledi", "giovedi", "venerdi",
           "sabato", "domenica")

# Kinds of datum the sheet may simply not hold; extends the shared
# answer-type tables without mutating them.
_TIPI_EXTRA_DOMANDA = {
    "misura": [r"\bspessor", r"\bmillimetr", r"\bmm\b", r"quanto e spesso"],
    "iban": [r"\biban\b", r"coordinate bancarie"],
}
_TIPI_EXTRA_BLOCCO = {
    "misura": [r"\b\d+\s*(?:mm|millimetri|cm)\b"],
    "iban": [r"\bIT\d{2}[A-Za-z0-9]"],
}

# Words that ask, not words that mean: invisible to the coverage gate.
_FUNZIONALI = {"avete", "fate", "siete", "sono", "posso", "puo", "potete",
               "vorrei", "voglio", "serve", "servono", "date", "dite",
               "numero", "tipo", "modo", "cosa", "essere", "avere", "riesco",
               "riuscite", "possibile", "vostro", "vostra", "vostri", "vostre"}

# Frequent general Italian, as 6-char stems: a site that never wrote
# "automobile" or "spendo" still understands them, so common words can never
# be uncovered pivots — only genuinely rare terms carry absence evidence.
# Curated from general frequency lists (verbs with their main conjugation
# stems, common nouns/adjectives/adverbs, number words); nothing here is
# site- or bench-specific.
_FREQUENTI = {t[:6] for t in """
andare vado vai va andiamo andate vanno andro venire vengo vieni viene
veniamo venite vengono verro verrebbe fare faccio fai facciamo fanno faro
farebbe potere possiamo possono potro dovere devo devi deve dobbiamo dovete
devono dovro volere vuoi vuole vogliamo volete vogliono sapere so sai sa
sappiamo sapete sanno dire dico dici dice diciamo dicono dare do dai diamo
danno daro stare sto stai sta stiamo state stanno vedere vedo vedi vede
vediamo vedete vedono visto mettere metto metti mette mettiamo mettete
mettono messo prendere prendo prendi prende prendiamo prendete prendono
preso passare passo passi passa passiamo passate passano portare porto porti
porta portiamo portate portano arrivare arrivo arrivi arriva arriviamo
arrivate arrivano usare uso usi usa usiamo usate usano lavorare lavoro
lavori lavora lavoriamo lavorate lavorano chiamare chiamo chiami chiama
chiamiamo chiamate chiamano scrivere scrivo scrivi scrive scriviamo
scrivete scrivono scritto scritta mandare mando mandi manda mandiamo
mandate mandano inviare invio invii invia inviamo inviate inviano pagare
pago paghi paga paghiamo pagate pagano costare costo costi costa costano
costoso costosa aspettare aspetto aspetti aspetta aspettiamo aspettate
aspettano finire finisco finisci finisce finiamo finite finiscono iniziare
inizio inizi inizia iniziamo iniziate iniziano cominciare comincio cominci
comincia entrare entro entri entra entriamo entrate entrano uscire esco
esci esce usciamo uscite escono tornare torno torni torna torniamo tornate
tornano restare resto resti resta restiamo restate restano cambiare cambio
cambi cambia cambiamo cambiate cambiano aprire apro apri apre apriamo
aprite aprono aperto chiudere chiudo chiudi chiude chiudiamo chiudete
chiudono chiuso trovare trovo trovi trova troviamo trovate trovano cercare
cerco cerchi cerca cerchiamo cercate cercano chiedere chiedo chiedi chiede
chiediamo chiedete chiedono chiesto rispondere rispondo rispondi risponde
rispondiamo rispondete rispondono risposto parlare parlo parli parla
parliamo parlate parlano sentire sento senti sente sentiamo sentite
sentono capire capisco capisci capisce capiamo capite capiscono conoscere
conosco conosci conosce conosciamo conoscete conoscono pensare penso pensi
pensa pensiamo pensate pensano credere credo credi crede crediamo credete
credono sembrare sembra sembrano bastare basta bastano spendere spendo
spendi spende spendiamo spendete spendono speso ottenere ottengo ottieni
ottiene otteniamo ottenete ottengono partire parto parti parte partiamo
partite partono vivere vivo vivi vive viviamo vivete vivono comprare
compro compri compra compriamo comprate comprano vendere vendo vendi vende
vendiamo vendete vendono guidare guido guidi guida rimettere rimetto
rimetti rimette conviene convenire riferire riferisco esibire esibisco
mostrare mostro mostri mostra mostriamo mostrate mostrano
casa case giorno giorni tempo tempi anno anni ora ore persona persone
lavoro lavori parte parti volta volte posto posti zona zone nome nomi
mattina sera notte settimana settimane mese mesi momento momenti signora
signore uomo donna gente strada strade citta paese paesi regione regioni
provincia stanza stanze camera camere bagno cucina salotto soggiorno
macchina macchine automobile automobili auto furgone camion moto veicolo
veicoli mezzo mezzi documento documenti codice codici carta carte foglio
fogli lettera lettere parola parole punto punti fine inizio dimensione
dimensioni misura misure grandezza controllo controlli processo processi
manuale manuali servizio servizi prodotto prodotti materiale materiali
prezzo prezzi costo costi valore valori soldi denaro euro conto conti
azienda aziende ditta ditte impresa imprese ufficio uffici negozio negozi
titolare cliente clienti persona operaio operai tecnico tecnici capo
famiglia madre padre figlio figlia fratello sorella moglie marito nonna
nonno amico amici vicino vicini
grande grandi piccolo piccola piccoli nuovo nuova nuovi vecchio vecchia
vecchi primo prima primi ultimo ultima ultimi prossimo prossima stesso
stessa stessi altro altra altri tutto tutta tutti ogni qualche nessuno
alcuni alcune buono buona bene male meglio peggio giusto giusta sbagliato
normale normali speciale veloce lento facile difficile importante attivo
attivi attiva libero libera liberi pieno piena vuoto vuota lungo lunga
corto corta alto alta basso bassa
sopra sotto dentro fuori davanti dietro insieme subito presto tardi sempre
mai spesso ancora gia oggi domani ieri adesso allora quindi pero quando
mentre durante verso circa quasi solo soltanto proprio davvero
uno due tre quattro cinque sei sette otto nove dieci venti trenta quaranta
cinquanta sessanta settanta ottanta novanta cento duecento trecento
quattrocento cinquecento seicento settecento ottocento novecento mille
duemila diecimila milione
scattare scatta scattano condizione condizioni feriale feriali festivo
festivi standard ordinario ordinaria ordinari ordinarie valido valida
validita alloggio alloggi abitazione abitazioni fiscale fiscali
""".split()}


def _valori(testo):
    """Identifier values named in `testo`: codes, weekdays, long numbers.

    Small numbers are the caller's own quantities ("per 300 mq", "a 60 km")
    and must never be read as identifiers; only numbers of 4+ digits name a
    THING rather than an amount (ISO 14001, a year, a VAT number).
    """
    piatto = normalizza(testo)
    return {
        "num": {v for genere, v in atomi(testo)
                if genere == "num" and v >= 1000},
        "cod": {c.upper() for c in _CODICE.findall(testo)},
        "giorno": {g for g in _GIORNI if g in piatto},
    }


def contrasto_valore(domanda, riga):
    """True when question and row hold DISJOINT values of the same kind."""
    vd, vr = _valori(domanda), _valori(riga)
    return any(vd[k] and vr[k] and not (vd[k] & vr[k]) for k in vd)


def tipo_orfano(domanda, corpus):
    """True when every kind of answer the question wants exists in no row."""
    piatto = normalizza(domanda)
    dom = {**QUESTION_PATTERNS, **_TIPI_EXTRA_DOMANDA}
    blo = {**BLOCK_PATTERNS, **_TIPI_EXTRA_BLOCCO}
    cercati = {t for t, pp in dom.items()
               if any(re.search(p, piatto) for p in pp)}
    if not cercati:
        return False
    return all(not any(re.search(p, riga, re.IGNORECASE)
                       for riga in corpus for p in blo.get(t, ()))
               for t in cercati)


def negazione_esplicita(domanda, riga):
    """True when the question negates the very subject the row is about."""
    piatto = normalizza(domanda)
    negati = re.findall(r"(?:\bnon\b|\bsenza\b)\s+(?:la\s+|il\s+|lo\s+|un\s+|l')?(\w{3,})",
                        piatto)
    bersaglio = normalizza(riga)
    return any(n[:6] in bersaglio for n in negati if n not in _STOPWORD)


def copertura_scoperta(domanda, lingua):
    """Content terms of the question covered nowhere in the site's language.

    `lingua` is every text the site owns (rows + paraphrase bundles); a term
    is covered when a 5-character stem of it appears in any of them — 5, not
    6, because Italian inflection lives in the last vowel ("civile"/"civili"
    diverge at position six and are the same word). Numbers are values, not
    vocabulary, and asking-words carry no content: both are exempt. Returns
    the sorted uncovered terms; [] means fully covered.
    """
    stemmi = {t[:5] for testo in lingua
              for t in re.findall(r"\w+", normalizza(testo))}
    scoperti = set()
    for termine in re.findall(r"\w+", normalizza(domanda)):
        if (termine in _STOPWORD or termine in _FUNZIONALI
                or termine[:6] in _FREQUENTI
                or termine.isdigit() or len(termine) < 3):
            continue
        if termine[:5] not in stemmi:
            scoperti.add(termine)
    return sorted(scoperti)
