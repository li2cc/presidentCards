"""Pure text helpers: years, ordinals, hints and rule-based highlights."""
from __future__ import annotations

import re

MASK = "_____"

STRONG_KEYWORDS = {
    "first", "only", "youngest", "oldest", "longest", "landslide", "assassinated",
    "impeached", "nobel", "proclamation", "amendment", "doctrine", "treaty", "act",
    "signed", "declared", "acquitted", "resigned", "unanimously", "largest",
    "purchase", "emancipation", "annexed", "acquired", "vetoed", "record",
}
MEDIUM_KEYWORDS = {
    "led", "won", "defeated", "war", "reform", "crisis", "appointed", "established",
    "victory", "expanded", "negotiated", "created", "oversaw", "campaign", "opposed",
    "supported", "policy", "policies", "economic", "military", "ended", "launched",
    "elected", "ordered", "program", "programs",
}
FILLER_WORDS = {
    "born", "graduated", "married", "buried", "raised", "educated", "attended",
    "enrolled", "childhood", "divorced", "wife", "son", "daughter", "retired",
}
PRESIDENCY_PHRASES = ("as president", "his administration", "his presidency", "her administration")
NAME_STOPLIST = {"United States", "Supreme Court", "White House"}

_ABBREVIATIONS = (
    r"Mr|Mrs|Ms|Dr|Jr|Sr|St|Gen|Col|Lt|Capt|Sen|Rep|Gov|Mt|No|vs|Inc|Co|Corp|"
    r"etc|Hon|Rev|Prof|Ft|Maj|Sgt"
)
_ABBREV_RE = re.compile(rf"(?:[A-Z]\.|(?:[A-Z]\.){{2,}}|(?:{_ABBREVIATIONS})\.)$")
_BOUNDARY_RE = re.compile(r"[.!?][\"”’)\]]*\s+(?=[\"“‘(]?[A-Z0-9])")


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_term_years(terms: list[tuple[int, int | None]]) -> str:
    """Terms are (start_year, end_year); end_year None means incumbent."""
    parts = []
    for start, end in terms:
        if end is None:
            parts.append(f"{start}–present")
        elif start == end:
            parts.append(str(start))
        else:
            parts.append(f"{start}–{end}")
    return ", ".join(parts)


def parse_term_years(term_text: str) -> tuple[int, int | None]:
    cleaned = re.sub(r"\[[^\]]*\]", " ", term_text)
    years = [int(y) for y in re.findall(r"\b(1[6-9]\d\d|2[01]\d\d)\b", cleaned)]
    if not years:
        raise ValueError(f"No years in term text: {term_text!r}")
    start = years[0]
    if re.search(r"incumbent|present", cleaned, re.I):
        return start, None
    return start, years[-1]


def ordinal_label(numbers: list[int]) -> str:
    labels = [ordinal(n) for n in numbers]
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " and " + labels[-1]


def clean_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\u00a0", " ")).strip()


def split_paragraphs(text: str) -> list[str]:
    return [clean_text(p) for p in re.split(r"\n+", text) if clean_text(p)]


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences, start = [], 0
    for m in _BOUNDARY_RE.finditer(text):
        before = text[start:m.start() + 1]
        last_token = before.split(" ")[-1].lstrip("\"“(‘")
        if _ABBREV_RE.search(last_token):
            continue
        sentences.append(text[start:m.start() + len(m.group().rstrip())].strip())
        start = m.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def name_parts(name: str, extra: list[str] | None = None) -> list[str]:
    parts = []
    for token in re.split(r"\s+", f"{name} {' '.join(extra or [])}"):
        word = re.sub(r"[^\w'’-]", "", token).strip("'’-")
        if len(word) > 2:
            parts.append(word)
    return parts


def lead_name_parts(first_sentence: str) -> list[str]:
    """Full birth name written before the first parenthesis of an article lead."""
    prefix = first_sentence.split("(")[0]
    tokens = prefix.split()
    if not 1 < len(tokens) <= 6:
        return []
    if not all(re.match(r"^[A-Z][\w.'’-]*$", t) for t in tokens):
        return []
    return tokens


def mask_names(text: str, parts: list[str]) -> str:
    for part in sorted(set(parts), key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(part)}(?!\w)", MASK, text, flags=re.I)
    return text


def build_hint(name: str, ordinals: list[int], paragraphs: list[str]) -> str:
    base = f"The {ordinal_label(ordinals)} president of the United States."
    if not paragraphs:
        return base
    first = split_sentences(paragraphs[0])
    extra = lead_name_parts(first[0]) if first else []
    parts = name_parts(name, extra)
    candidates = first[1:]
    chosen = next((s for s in candidates if 40 <= len(s) <= 300), None)
    if chosen is None:
        for paragraph in paragraphs[1:]:
            chosen = next((s for s in split_sentences(paragraph) if 40 <= len(s) <= 300), None)
            if chosen:
                break
    if chosen is None:
        return base
    return f"{base} {mask_names(chosen, parts)}"


def _tokens(sentence: str) -> set[str]:
    return set(re.findall(r"[a-z']+", sentence.lower()))


def score_sentence(sentence: str) -> int:
    tokens = _tokens(sentence)
    lowered = sentence.lower()

    def hits(words: set[str]) -> int:
        return sum(1 for w in words if w in tokens or f"{w}s" in tokens)

    score = 3 * hits(STRONG_KEYWORDS) + hits(MEDIUM_KEYWORDS) - 4 * hits(FILLER_WORDS)
    if any(p in lowered for p in PRESIDENCY_PHRASES):
        score += 2
    if len(sentence) > 260:
        score -= 2
    return score


def multiword_names(sentence: str) -> set[str]:
    words = sentence.split(" ", 1)
    body = words[1] if len(words) > 1 else ""
    found = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", body))
    return found - NAME_STOPLIST


def shorten(sentence: str, limit: int = 280) -> str:
    if len(sentence) <= limit:
        return sentence
    window = sentence[:limit - 1]
    cut = max(window.rfind(","), window.rfind(";"))
    if cut < 60:
        cut = window.rfind(" ")
    return window[:cut].rstrip(",; ") + "…"


def build_highlights(name: str, paragraphs: list[str], limit: int = 5) -> list[str]:
    parts = set(name_parts(name))
    sentences = [s for p in paragraphs[1:] for s in split_sentences(p)]
    eligible = [
        (i, s) for i, s in enumerate(sentences)
        if 50 <= len(s) <= 400 and s[0].isupper()
    ]
    scored = sorted(((score_sentence(s), -i, i, s) for i, s in eligible), reverse=True)
    chosen: list[tuple[int, str]] = []
    used_names: set[str] = set()
    for score, _, i, s in scored:
        if score <= 0 or len(chosen) >= limit:
            break
        names = {n for n in multiword_names(s) if not parts & set(n.split())}
        if names & used_names:
            continue
        chosen.append((i, s))
        used_names |= names
    if not chosen and scored:
        best = scored[0]
        chosen.append((best[2], best[3]))
    chosen.sort()
    return [shorten(s) for _, s in chosen]
