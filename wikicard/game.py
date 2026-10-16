"""Answer checking, competition scoring and leaderboard ranking (pure functions)."""
from __future__ import annotations

import difflib
import math
import random
import re
import unicodedata

QUESTION_SECONDS = 20
COMPETITION_QUESTIONS = 10
BASE_POINTS = 100
MAX_BONUS = 50
FULL_SIMILARITY = 0.85
SURNAME_SIMILARITY = 0.88
DROPPED_WORDS = {"jr", "sr", "president"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(w for w in text.split() if w not in DROPPED_WORDS)


def _tokens(name: str) -> list[str]:
    return normalize(name).split()


def name_forms(name: str) -> dict[str, set[str]]:
    """Exact forms of a card name: tier 1 (full, without initials) and tier 2 (first+last)."""
    tokens = _tokens(name)
    if not tokens:
        return {"strong": set(), "weak": set()}
    no_initials = [t for t in tokens if len(t) > 1]
    strong = {" ".join(tokens), " ".join(no_initials)}
    weak = {f"{no_initials[0]} {no_initials[-1]}"} if len(no_initials) > 1 else set()
    return {"strong": strong, "weak": weak - strong}


def surname(name: str) -> str:
    tokens = _tokens(name)
    return tokens[-1] if tokens else ""


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def is_correct(guess: str, answer: str, all_answers: list[str]) -> bool:
    """Is `guess` a correct answer for `answer`, given the names of every card?"""
    g = normalize(guess)
    if not g:
        return False
    forms = {a: name_forms(a) for a in set(all_answers) | {answer}}

    strong_owners = {a for a, f in forms.items() if g in f["strong"]}
    if strong_owners:
        return strong_owners == {answer}
    weak_owners = {a for a, f in forms.items() if g in f["weak"]}
    if weak_owners:
        return weak_owners == {answer}

    scores = {
        a: max((_ratio(g, form) for form in f["strong"] | f["weak"]), default=0.0)
        for a, f in forms.items()
    }
    best = max(scores.values())
    if best >= FULL_SIMILARITY:
        winners = [a for a, s in scores.items() if math.isclose(s, best)]
        return winners == [answer]

    if " " not in g:
        own = surname(answer)
        sharers = [a for a in forms if a != answer and surname(a) == own]
        if sharers or not own:
            return False
        if any(g == surname(a) for a in forms if a != answer):
            return False
        return _ratio(g, own) >= SURNAME_SIMILARITY
    return False


def quiz_score(correct: int, attempted: int) -> float:
    return round(100 * correct / attempted, 1) if attempted else 0.0


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def speed_bonus(elapsed: float) -> int:
    remaining = max(0.0, 1 - max(elapsed, 0.0) / QUESTION_SECONDS)
    return _round_half_up(MAX_BONUS * remaining)


def competition_points(correct: bool, elapsed: float) -> int:
    if not correct or elapsed > QUESTION_SECONDS:
        return 0
    return BASE_POINTS + speed_bonus(elapsed)


def pick_questions(cards: list[dict], count: int, rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    return rng.sample(cards, min(count, len(cards)))


def rank_competition(rows: list[dict], limit: int = 20) -> list[dict]:
    """Order by score desc, completion_time asc, date asc; add 1-based rank."""
    ordered = sorted(rows, key=lambda r: (-r["score"], r["completion_time"], r["date"]))[:limit]
    return [{**r, "rank": i} for i, r in enumerate(ordered, start=1)]


def medal(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, str(rank))
