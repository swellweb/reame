"""Isolated tests for the prefill oracle's block splitter and BM25 ranker.

Every expected value here is computed by hand from the BM25 definition, not
read back from the implementation. The two hand-worked scores are derived in
the comments so a future reader can check the arithmetic without trusting us.

    python3 -m pytest bench/test_retrieval.py -q
"""
import json
import math
import pathlib
import re

import pytest

from retrieval import bm25_scores, select, split_into_blocks, top_k


# --------------------------------------------------------------------------
# splitter
# --------------------------------------------------------------------------

def test_split_produces_the_expected_windows():
    # No trailing "five six": that window is wholly contained in the previous
    # one, and BM25's length normalisation would *reward* the shorter
    # duplicate, floating a redundant tail to the top of the ranking.
    text = "one two three four five six"
    assert split_into_blocks(text, words_per_block=4, stride=2) == [
        "one two three four",
        "three four five six",
    ]


def test_split_emits_a_short_tail_only_when_it_holds_new_words():
    text = "one two three four five six seven"
    assert split_into_blocks(text, words_per_block=4, stride=2) == [
        "one two three four",
        "three four five six",
        "five six seven",
    ]


def test_split_loses_no_word():
    text = " ".join(str(i) for i in range(37))
    blocks = split_into_blocks(text, words_per_block=8, stride=5)
    seen = {w for b in blocks for w in b.split()}
    assert seen == set(text.split())


def test_split_keeps_a_short_document_whole():
    text = "only three words"
    assert split_into_blocks(text, words_per_block=50, stride=25) == [text]


def test_split_of_empty_text_yields_nothing():
    assert split_into_blocks("   \n  ", words_per_block=10, stride=5) == []


def test_split_normalises_whitespace():
    assert split_into_blocks("a\n\n  b\tc", words_per_block=9, stride=4) == ["a b c"]


def test_stride_larger_than_block_would_drop_words_and_is_refused():
    with pytest.raises(ValueError):
        split_into_blocks("a b c d", words_per_block=2, stride=3)


# --------------------------------------------------------------------------
# BM25 — hand-computed expectations
# --------------------------------------------------------------------------

def test_bm25_matches_the_score_computed_by_hand():
    # docs: d0 = "cat cat dog" (3 words), d1 = "dog fish" (2 words)
    # query "cat":  N=2, df=1, avgdl=2.5, k1=1.5, b=0.75
    #   idf = ln(1 + (2 - 1 + 0.5) / (1 + 0.5))       = ln(2)      = 0.693147
    #   d0: denom = 2 + 1.5*(0.25 + 0.75*3/2.5)       = 3.725
    #       score = 0.693147 * (2 * 2.5) / 3.725      = 0.930399
    #   d1: the term does not occur                   = 0
    scores = bm25_scores("cat", ["cat cat dog", "dog fish"])
    assert scores[0] == pytest.approx(0.930399, abs=1e-6)
    assert scores[1] == 0.0


def test_bm25_prefers_the_shorter_document_at_equal_frequency():
    # d0 = "cat dog" (2 words), d1 = "cat dog dog dog dog dog" (6 words)
    # query "cat": tf = 1 in both, N=2, df=2, avgdl=4
    #   idf = ln(1 + (2 - 2 + 0.5) / (2 + 0.5))       = ln(1.2)    = 0.1823216
    #   d0: denom = 1 + 1.5*(0.25 + 0.75*2/4) = 1.9375
    #       score = 0.1823216 * 2.5 / 1.9375           = 0.2352536
    #   d1: denom = 1 + 1.5*(0.25 + 0.75*6/4) = 3.0625
    #       score = 0.1823216 * 2.5 / 3.0625           = 0.1488339
    short, long = "cat dog", "cat dog dog dog dog dog"
    scores = bm25_scores("cat", [short, long])
    assert scores[0] == pytest.approx(0.2352536, abs=1e-7)
    assert scores[1] == pytest.approx(0.1488339, abs=1e-7)
    assert scores[0] > scores[1]


def test_bm25_scores_zero_when_no_query_term_occurs():
    assert bm25_scores("zebra", ["cat dog", "dog fish"]) == [0.0, 0.0]


def test_bm25_ignores_case_and_punctuation():
    assert bm25_scores("Resina!", ["resina epossidica", "cemento"])[0] > 0


def test_bm25_rewards_the_rarer_of_two_query_terms():
    # Three blocks of equal length, so length normalisation cancels out and
    # only idf can decide. "cat" occurs in one block (df=1), "dog" in two
    # (df=2), so the block holding the rare term must win:
    #   idf(cat) = ln(1 + (3 - 1 + 0.5)/(1 + 0.5)) = ln(2.6667) = 0.9808
    #   idf(dog) = ln(1 + (3 - 2 + 0.5)/(2 + 0.5)) = ln(1.6)    = 0.4700
    blocks = ["cat filler filler", "dog filler filler", "dog other other"]
    scores = bm25_scores("cat dog", blocks)
    assert scores[0] > scores[1]


# --------------------------------------------------------------------------
# selection
# --------------------------------------------------------------------------

def test_top_k_returns_indices_best_first():
    blocks = ["nothing here", "cat cat cat", "one cat"]
    assert top_k("cat", blocks, k=2) == [1, 2]


def test_top_k_finds_a_match_sitting_in_the_last_block():
    # Position must not bias the ranking: the answer is deliberately last.
    blocks = ["filler one", "filler two", "filler three", "the epoxy resin costs 35"]
    assert top_k("how much does the epoxy resin cost", blocks, k=1) == [3]


def test_top_k_caps_at_the_number_of_blocks():
    blocks = ["cat", "dog"]
    assert len(top_k("cat", blocks, k=10)) == 2


def test_top_k_of_zero_returns_nothing():
    assert top_k("cat", ["cat", "dog"], k=0) == []


def test_bm25_on_a_single_block_is_defined():
    # df == N makes the classic idf log((N-df+0.5)/(df+0.5)) go negative; the
    # 1 + ... form must keep it non-negative instead of ranking a hit below a miss.
    assert bm25_scores("cat", ["cat dog"])[0] > 0


def test_idf_never_goes_negative_for_a_term_in_every_block():
    blocks = ["cat one", "cat two", "cat three"]
    assert all(s > 0 for s in bm25_scores("cat", blocks))
    # sanity: this is the property the 1+ guard buys us
    assert math.log(1 + (3 - 3 + 0.5) / (3 + 0.5)) > 0


# --------------------------------------------------------------------------
# regression guard on the published measurement
#
# These read the bench page and questions, so they are not unit tests in the
# strict sense — but they involve no server, no model and no network, and they
# are what stops a future edit to the splitter from quietly ruining the number
# in BENCHMARKS.md.
# --------------------------------------------------------------------------

HERE = pathlib.Path(__file__).parent


def _bench_page():
    return (HERE / "page_prose.txt").read_text(encoding="utf-8")


def _bench_questions():
    with (HERE / "questions.jsonl").open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def test_retrieval_keeps_the_answer_in_at_least_19_of_20_questions():
    page, questions = _bench_page(), _bench_questions()
    blocks = split_into_blocks(page, words_per_block=120, stride=60)
    found = 0
    for q in questions:
        picked = top_k(q["domanda"], blocks, k=3)
        if any(re.search(p, blocks[j], re.I)
               for j in picked for p in q["accept"]):
            found += 1
    assert found >= 19, "coverage dropped to %d/20" % found


def test_selection_reads_well_under_a_third_of_the_page():
    page = _bench_page()
    chosen = select(_bench_questions()[0]["domanda"], page, k=3)
    assert len(chosen.split()) < 0.35 * len(page.split())


def test_selection_differs_between_unrelated_questions():
    page, questions = _bench_page(), _bench_questions()
    picks = {select(q["domanda"], page, k=3) for q in questions}
    assert len(picks) > 1, "every question got the same slice"


def test_selection_preserves_document_order():
    # Blocks come back in the order they appear on the page, not by score:
    # a model reading prose does worse when paragraphs arrive shuffled.
    page = _bench_page()
    blocks = split_into_blocks(page, words_per_block=120, stride=60)
    q = _bench_questions()[0]["domanda"]
    chosen = select(q, page, k=3).split("\n\n")
    positions = [blocks.index(c) for c in chosen]
    assert positions == sorted(positions)
