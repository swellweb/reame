"""Pick which part of a document the model should read, without a model.

The prefill oracle: on a CPU, reading the whole page costs 40 seconds and
reading a tenth of it costs four. This module decides which tenth.

It ranks by BM25 — plain term counting — after measuring that a 132 MB
multilingual embedding model does the same job three times worse and four
thousand times slower on fact extraction. The reason looks fundamental rather
than incidental: a dense embedding is built to place similar things close
together, and fact extraction is the task of telling similar things apart.
"epoxy resin" and "polyurethane resin" are neighbours in embedding space and
different answers in a price list.

The measured numbers, on bench/page_prose.txt and the 20 questions next to it,
with 120-word blocks at half overlap:

    method              k=1    k=3
    dense (e5-small)    25%    45%
    BM25                80%    95%

No dependencies: the index is a Counter.
"""
import math
import re
from collections import Counter

# Robertson/Sparck Jones defaults. k1 damps the reward for repeating a term,
# b controls how hard long blocks are penalised.
K1 = 1.5
B = 0.75


def _terms(text):
    return re.findall(r"\w+", text.lower())


def split_into_blocks(text, words_per_block, stride):
    """Cut `text` into overlapping word windows.

    Overlap exists so that an answer straddling a boundary survives whole in
    at least one block. A stride wider than the block would skip words, which
    silently loses answers, so it is refused rather than tolerated.
    """
    if stride <= 0:
        raise ValueError("stride must be positive")
    if stride > words_per_block:
        raise ValueError(
            "stride %d exceeds block size %d: words between blocks would be "
            "dropped" % (stride, words_per_block))

    words = text.split()
    blocks = []
    for start in range(0, len(words), stride):
        window = words[start:start + words_per_block]
        if not window:
            break
        blocks.append(" ".join(window))
        if start + words_per_block >= len(words):
            break  # the tail is covered; further windows would only repeat it
    return blocks


def bm25_scores(query, blocks, k1=K1, b=B):
    """Score every block against `query`. Higher is a better match.

    The idf is the `1 + ...` variant: the textbook form goes negative for a
    term present in every block, which would rank a block containing the term
    below one that does not.
    """
    tokenised = [_terms(block) for block in blocks]
    if not tokenised:
        return []
    avg_len = sum(len(t) for t in tokenised) / len(tokenised)
    doc_freq = Counter(term for t in tokenised for term in set(t))

    scores = []
    for terms in tokenised:
        freq = Counter(terms)
        total = 0.0
        for term in _terms(query):
            tf = freq.get(term, 0)
            if tf == 0:
                continue
            df = doc_freq[term]
            idf = math.log(1 + (len(tokenised) - df + 0.5) / (df + 0.5))
            length_norm = k1 * (1 - b + b * len(terms) / avg_len)
            total += idf * tf * (k1 + 1) / (tf + length_norm)
        scores.append(total)
    return scores


def top_k(query, blocks, k):
    """Indices of the k best-matching blocks, best first.

    Ties break on position so the result is reproducible run to run.
    """
    scores = bm25_scores(query, blocks)
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    return order[:k]


def select(query, text, k=3, words_per_block=120, stride=60):
    """The whole oracle: document in, the text worth reading out.

    Blocks are returned in document order, not score order — the model reads
    prose, and shuffling paragraphs by relevance makes it worse.
    """
    blocks = split_into_blocks(text, words_per_block, stride)
    chosen = sorted(top_k(query, blocks, k))
    return "\n\n".join(blocks[i] for i in chosen)
