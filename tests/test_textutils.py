import pytest

from wikicard import textutils as tx


def test_ordinals():
    assert [tx.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 24, 45)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "24th", "45th"]
    assert tx.ordinal_label([22, 24]) == "22nd and 24th"


def test_years():
    assert tx.format_term_years([(1841, 1841)]) == "1841"
    assert tx.format_term_years([(1789, 1797)]) == "1789–1797"
    assert tx.format_term_years([(2017, 2021), (2025, None)]) == "2017–2021, 2025–present"


def test_parse_term():
    assert tx.parse_term_years("March 4, 1841 – April 4, 1841 [ e ]") == (1841, 1841)
    assert tx.parse_term_years("January 20, 2025 – Incumbent") == (2025, None)


def test_sentence_split_keeps_abbreviations():
    s = tx.split_sentences("Franklin D. Roosevelt led the U.S. Army. He won. Dr. Smith agreed.")
    assert s == ["Franklin D. Roosevelt led the U.S. Army.", "He won.", "Dr. Smith agreed."]


PARAS = [
    "Abe Lincoln (born 1809) was a lawyer. He was a leader in the Lincoln-Douglas debates "
    "across the western states of America. Lincoln later won the presidency.",
    "As president, Lincoln signed the Emancipation Proclamation and led the Union through the "
    "American Civil War until victory. He was born in a log cabin and later married Mary.",
    "He was assassinated in 1865 by John Wilkes Booth, becoming the first president assassinated "
    "in the United States.",
    "The Civil War ended after the Union victory, and Lincoln's plan for Reconstruction shaped "
    "the American Civil War aftermath for decades.",
]


def test_hint_masks_names_and_skips_first_sentence():
    hint = tx.build_hint("Abraham Lincoln", [16], PARAS)
    assert hint.startswith("The 16th president of the United States. ")
    assert "Lincoln" not in hint and "Abraham" not in hint and "Abe" not in hint
    assert "_____" in hint
    assert "lawyer" not in hint


def test_hint_without_candidate_sentence():
    assert tx.build_hint("A Person", [1], ["Short."]) == "The 1st president of the United States."


def test_highlights_rules():
    hl = tx.build_highlights("Abraham Lincoln", PARAS)
    assert 1 <= len(hl) <= 5
    assert not any("born" in h for h in hl)
    assert not any(h in PARAS[0] for h in hl)
    # "American Civil War" appears in two high-scoring sentences; only one is kept
    assert sum("American Civil War" in h for h in hl) == 1
    order = [PARAS[1:].index(next(p for p in PARAS[1:] if h.rstrip("…")[:30] in p)) for h in hl]
    assert order == sorted(order)


def test_highlight_fallback_gives_at_least_one():
    hl = tx.build_highlights("Some Person", ["Intro.", "He liked quiet walks along the river every single day of his life."])
    assert hl == ["He liked quiet walks along the river every single day of his life."]


def test_shorten_cuts_at_comma():
    long = "word " * 20 + "alpha, " + "beta " * 60
    out = tx.shorten(long)
    assert len(out) <= 281 and out.endswith("…")
    assert tx.shorten("short sentence here") == "short sentence here"
