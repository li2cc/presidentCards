import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from wikicard import game
from wikicard.scraper import SEED_PATH

NAMES = [c["answer"] for c in json.loads(SEED_PATH.read_text(encoding="utf-8"))]


def check(guess, answer):
    return game.is_correct(guess, answer, NAMES)


@pytest.mark.parametrize("guess,answer,expected", [
    ("abraham lincoln", "Abraham Lincoln", True),
    ("Abraham Lincon", "Abraham Lincoln", True),
    ("Lincoln", "Abraham Lincoln", True),
    ("Franklin Roosevelt", "Franklin D. Roosevelt", True),
    ("Roosevelt", "Franklin D. Roosevelt", False),
    ("Roosevelt", "Theodore Roosevelt", False),
    ("George Bush", "George H. W. Bush", False),
    ("George Bush", "George W. Bush", False),
    ("George W Bush", "George W. Bush", True),
    ("George W Bush", "George H. W. Bush", False),
    ("John Adams", "John Quincy Adams", False),
    ("John Adams", "John Adams", True),
    ("", "Abraham Lincoln", False),
    ("   ", "Abraham Lincoln", False),
    ("Président Obama", "Barack Obama", True),
    ("Adams", "John Adams", False),
])
def test_answer_check(guess, answer, expected):
    assert check(guess, answer) is expected


@pytest.mark.parametrize("elapsed,points", [(0, 150), (10, 125), (20, 100), (20.01, 0), (35, 0)])
def test_points(elapsed, points):
    assert game.competition_points(True, elapsed) == points


def test_wrong_scores_zero_and_max_total():
    assert game.competition_points(False, 0) == 0
    assert sum(game.competition_points(True, 0) for _ in range(10)) == 1500


def test_quiz_score():
    assert game.quiz_score(3, 4) == 75.0
    assert game.quiz_score(0, 0) == 0
    assert game.quiz_score(1, 3) == 33.3


def test_pick_questions_distinct():
    cards = [{"id": i} for i in range(45)]
    picked = game.pick_questions(cards, 10, random.Random(1))
    assert len({c["id"] for c in picked}) == 10


def test_ranking_order():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"score": 900, "completion_time": 50.0, "date": t0},
        {"score": 1200, "completion_time": 60.0, "date": t0},
        {"score": 900, "completion_time": 40.0, "date": t0 + timedelta(days=1)},
        {"score": 900, "completion_time": 40.0, "date": t0},
    ]
    ranked = game.rank_competition(rows)
    assert [r["rank"] for r in ranked] == [1, 2, 3, 4]
    assert [(r["score"], r["completion_time"]) for r in ranked] == [
        (1200, 60.0), (900, 40.0), (900, 40.0), (900, 50.0)]
    assert ranked[1]["date"] < ranked[2]["date"]


def test_ranking_limit_and_medals():
    rows = [{"score": i, "completion_time": 1.0, "date": datetime(2026, 1, 1)} for i in range(30)]
    assert len(game.rank_competition(rows)) == 20
    assert [game.medal(i) for i in (1, 2, 3, 4)] == ["🥇", "🥈", "🥉", "4"]
