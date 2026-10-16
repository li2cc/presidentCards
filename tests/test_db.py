"""Database tests: run only against TEST_DATABASE_URL, never the real database."""
import os
from datetime import datetime, timezone

import pytest

from wikicard import db

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture()
def pool():
    assert URL != os.environ.get("DATABASE_URL"), "TEST_DATABASE_URL must not be the real database"
    pool = db.create_pool(URL, max_size=2)
    with pool.connection() as conn:
        conn.execute("drop table if exists competitionresults, quizresults, cards, userprofiles, users cascade")
    db.init_schema(pool)
    yield pool
    pool.close()


def test_schema_is_idempotent_and_rls_enabled(pool):
    db.init_schema(pool)
    assert db.rls_status(pool) == {t: True for t in db.TABLES}


def test_register_creates_profile_and_rejects_duplicates_ignoring_case(pool):
    user = db.register_user(pool, "Ada", "Lovelace", "ada")
    with pool.connection() as conn:
        profile = conn.execute("select * from userprofiles where user_id=%s", (user["id"],)).fetchone()
    assert profile["display_name"] == "Ada Lovelace" and profile["cards_viewed"] == 0
    with pytest.raises(db.UsernameTaken) as exc:
        db.register_user(pool, "Ada", "Two", "ADA")
    assert str(exc.value) == "The username 'ADA' is already taken."
    assert len(db.list_users(pool)) == 1


@pytest.mark.parametrize("first,last,username", [
    ("", "L", "abc"), ("A", "", "abc"), ("A", "L", "ab"), ("A", "L", "a b c"), ("A" * 41, "L", "abc"),
])
def test_register_validation(pool, first, last, username):
    with pytest.raises(ValueError):
        db.register_user(pool, first, last, username)


def test_cards_replace_and_delete(pool):
    cards = [
        {"name": f"P{i}", "answer": f"P{i}", "sort_order": i, "highlights": ["x"], "years_in_office": "1800"}
        for i in range(1, 4)
    ]
    assert db.replace_cards(pool, "US Presidents", cards) == 3
    assert db.replace_cards(pool, "US Presidents", cards[:2]) == 2
    loaded = db.load_cards(pool, "US Presidents")
    assert [c["name"] for c in loaded] == ["P1", "P2"] and loaded[0]["highlights"] == ["x"]
    assert db.delete_cards(pool, "US Presidents") == 2 and db.count_cards(pool) == 0


def test_results_stats_and_leaderboard(pool):
    a = db.register_user(pool, "Ann", "A", "annie")
    b = db.register_user(pool, "Bob", "B", "bobby")
    db.save_quiz_result(pool, a["id"], 75.0, 4, 3)
    db.save_competition_result(pool, a["id"], 900, 6, 80.5)
    db.save_competition_result(pool, b["id"], 1200, 9, 70)
    db.save_competition_result(pool, b["id"], 900, 6, 60)
    db.increment_cards_viewed(pool, a["id"])
    board = db.leaderboard(pool)
    assert [(r["student"], r["score"], r["rank"]) for r in board] == [
        ("Bob B", 1200, 1), ("Bob B", 900, 2), ("Ann A", 900, 3)]
    summary = db.leaderboard_summary(pool)
    assert summary["highest"] == 1200 and summary["players"] == 2
    stats = db.user_stats(pool, a["id"])
    assert stats["cards_viewed"] == 1 and stats["quizzes"] == 1 and stats["avg_quiz"] == 75.0
    assert stats["best_competition"] == 900
    g = db.global_stats(pool, "US Presidents")
    assert g["users"] == 2 and g["quizzes"] == 1 and g["top_score"] == 1200


def test_check_constraints(pool):
    import psycopg
    a = db.register_user(pool, "Ann", "A", "annie")
    with pytest.raises(psycopg.errors.CheckViolation):
        db.save_quiz_result(pool, a["id"], 75.0, 2, 3)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.save_competition_result(pool, a["id"], 1501, 10, 5)


def test_admin_helpers(pool):
    assert set(db.table_counts(pool)) == set(db.TABLES)
    assert all(v > 0 for v in db.table_sizes_kb(pool).values())


def test_describe_host_hides_password():
    text = db.describe_host("postgresql://postgres.abc:s3cret@aws-0-us.pooler.supabase.com:5432/postgres")
    assert text == "PostgreSQL · aws-0-us.pooler.supabase.com:5432/postgres" and "s3cret" not in text
