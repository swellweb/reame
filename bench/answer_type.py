"""Narrow the candidate blocks by what kind of answer the question wants.

Measured problem: BM25 finds the right block 95% of the time when the question
reuses the page's vocabulary, and 50% when the caller asks in their own words.
Three different rankers — lexical, dense, hybrid — all land at ~50% on reworded
questions, so the gap is not a ranking problem.

What survives rewording is the *kind* of answer being asked for. "Qual è il
prezzo al mq della resina epossidica" and "quanto spendo per un metro di quel
trattamento" have almost no words in common and both want a figure in euros.
A page has few blocks holding a price, a few holding a duration, one holding a
phone number — so recognising the type throws away most of the page before a
single term is counted, using nothing but regular expressions.

Two deliberate conservatisms, because a filter that removes the right block is
worse than no filter:
  * a question with no recognisable type is passed through untouched;
  * if no block carries the requested type, the filter steps aside.
"""
import re

from retrieval import bm25_scores, top_k

# What the question is reaching for. A question may want more than one thing
# ("a che ora si può telefonare" wants both a clock time and a phone number).
QUESTION_PATTERNS = {
    "price": [r"quanto cost", r"\bprezz", r"\btariff", r"quanto spend",
              r"quanto viene", r"\bcosto\b", r"quanto pago", r"\bcostos"],
    "duration": [r"dopo quant", r"quanto tempo", r"quanto dura", r"per quanto",
                 r"quant\w*\s+(?:ore|ora|anni|anno|giorni|giorno|mesi|settimane)",
                 r"entro quant\w*\s+(?:ore|giorni)", r"in quanto tempo"],
    "distance": [r"quant\w*\s+km", r"che distanza", r"quanto lontano",
                 r"chilometr", r"fino a che distanza"],
    "phone": [r"\bnumero\b", r"\brecapit", r"\btelefon", r"\bchiamar",
              r"\bcontatt"],
    "clock": [r"a che ora", r"\borari", r"che ora\b", r"quando \w+ apert"],
    "place": [r"\bdove\b", r"\bprovinc", r"\bzone\b", r"\bregion",
              r"\bcitt[àa]\b"],
}

# What a block actually holds. These match the *shape* of the datum, not words
# about it: a paragraph that discusses pricing without quoting one is not an
# answer to "how much does it cost".
BLOCK_PATTERNS = {
    # 35,00 € · 35 € · 35 euro
    "price": [r"\d+(?:[.,]\d+)?\s*€", r"\d+(?:[.,]\d+)?\s*euro"],
    # 24 ore · 5 giorni · 10 anni — at most three digits, so a year like
    # "dal 2009" stays a date and does not answer "how many years of warranty".
    "duration": [r"\b\d{1,3}\s*(?:ore|ora|giorni|giorno|anni|anno|mesi|settimane)\b"],
    "distance": [r"\b\d+\s*km\b"],
    # 0574 812345 — a separator is required, so the unbroken 11 digits of a
    # VAT number do not read as a phone number.
    "phone": [r"\b0\d{2,3}[\s./-]\d{5,7}\b"],
    "clock": [r"\b\d{1,2}[:.]\d{2}\b"],
    "place": [r"\bprovinc", r"\bsede\b", r"\boperiamo\b"],
}


def _matching(text, patterns):
    low = text.lower()
    return {name for name, exprs in patterns.items()
            if any(re.search(e, low) for e in exprs)}


def answer_types(question):
    """The kinds of answer this question is asking for; empty means unknown."""
    return _matching(question, QUESTION_PATTERNS)


def block_types(block):
    """The kinds of datum this block actually contains."""
    return _matching(block, BLOCK_PATTERNS)


def top_k_typed(query, blocks, k):
    """Rank as BM25 does, but only among blocks holding the right kind of data.

    Falls back to plain BM25 whenever the type is unknown or nothing matches —
    losing the answer costs far more than reading a few extra blocks.
    """
    wanted = answer_types(query)
    if not wanted:
        return top_k(query, blocks, k)

    survivors = [i for i, b in enumerate(blocks) if block_types(b) & wanted]
    if not survivors:
        return top_k(query, blocks, k)

    scores = bm25_scores(query, blocks)
    return sorted(survivors, key=lambda i: (-scores[i], i))[:k]
