"""PostgreSQL (Supabase) access layer using psycopg 3 + psycopg-pool."""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import psycopg
from psycopg import errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "supabase" / "schema.sql"
CONNECT_TIMEOUT = 8
TABLES = ["users", "userprofiles", "cards", "quizresults", "competitionresults"]
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,30}$")


class ConfigError(RuntimeError):
    pass


class UsernameTaken(Exception):
    def __init__(self, username: str):
        super().__init__(f"The username '{username}' is already taken.")
        self.username = username


def get_secret(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:
        value = None
    return str(value) if value else default


def get_database_url() -> str:
    url = get_secret("DATABASE_URL")
    if not url:
        raise ConfigError(
            "DATABASE_URL is not set. Add it to .streamlit/secrets.toml or the environment."
        )
    return url


def describe_host(url: str) -> str:
    """'PostgreSQL · host:port/dbname' without credentials."""
    parsed = urlparse(url)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or 5432
    dbname = unquote(parsed.path.lstrip("/")) or "postgres"
    return f"PostgreSQL · {host}:{port}/{dbname}"


def create_pool(url: str, max_size: int = 5) -> ConnectionPool:
    # Probe first so a failure surfaces the real error (the pool only reports a timeout).
    psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT).close()
    pool = ConnectionPool(
        url,
        min_size=1,
        max_size=max_size,
        open=False,
        timeout=CONNECT_TIMEOUT + 2,
        kwargs={
            "row_factory": dict_row,
            "connect_timeout": CONNECT_TIMEOUT,
            "prepare_threshold": None,
        },
    )
    try:
        pool.open(wait=True, timeout=CONNECT_TIMEOUT + 2)
    except Exception:
        pool.close()
        raise
    return pool


def init_schema(pool: ConnectionPool) -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with pool.connection() as conn:
        conn.execute(sql)


# ---------------------------------------------------------------- users

def validate_registration(first: str, last: str, username: str) -> list[str]:
    errs = []
    if not 1 <= len(first.strip()) <= 40:
        errs.append("First name must be 1–40 characters.")
    if not 1 <= len(last.strip()) <= 40:
        errs.append("Last name must be 1–40 characters.")
    if not USERNAME_RE.match(username.strip()):
        errs.append("Username must be 3–30 characters: letters, digits, '.', '_' or '-'.")
    return errs


def register_user(pool, first: str, last: str, username: str) -> dict:
    first, last, username = first.strip(), last.strip(), username.strip()
    errs = validate_registration(first, last, username)
    if errs:
        raise ValueError(" ".join(errs))
    try:
        with pool.connection() as conn:
            user = conn.execute(
                "insert into users (first_name, last_name, username) values (%s, %s, %s) "
                "returning id, first_name, last_name, username",
                (first, last, username),
            ).fetchone()
            conn.execute(
                "insert into userprofiles (user_id, display_name, last_login) values (%s, %s, now())",
                (user["id"], f"{first} {last}"),
            )
    except errors.UniqueViolation:
        raise UsernameTaken(username) from None
    return user


def list_users(pool) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(
            "select id, first_name, last_name, username from users order by lower(username)"
        ).fetchall()


def touch_login(pool, user_id: int) -> None:
    with pool.connection() as conn:
        conn.execute("update userprofiles set last_login = now() where user_id = %s", (user_id,))


def increment_cards_viewed(pool, user_id: int) -> None:
    with pool.connection() as conn:
        conn.execute(
            "update userprofiles set cards_viewed = cards_viewed + 1 where user_id = %s", (user_id,)
        )


# ---------------------------------------------------------------- cards

def count_cards(pool, category: str | None = None) -> int:
    with pool.connection() as conn:
        if category:
            row = conn.execute("select count(*) n from cards where category = %s", (category,))
        else:
            row = conn.execute("select count(*) n from cards")
        return row.fetchone()["n"]


def load_cards(pool, category: str) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(
            "select id, name, image_url, category, hint, answer, details, highlights, party, "
            "years_in_office, sort_order, source_url from cards where category = %s "
            "order by sort_order",
            (category,),
        ).fetchall()


def replace_cards(pool, category: str, cards: list[dict]) -> int:
    """Atomically replace all cards of a category."""
    with pool.connection() as conn:
        with conn.transaction():
            conn.execute("delete from cards where category = %s", (category,))
            with conn.cursor() as cur:
                cur.executemany(
                    "insert into cards (name, image_url, category, hint, answer, details, "
                    "highlights, party, years_in_office, sort_order, source_url) "
                    "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    [
                        (
                            c["name"], c.get("image_url"), category, c.get("hint", ""),
                            c["answer"], c.get("details", ""), Jsonb(c.get("highlights", [])),
                            c.get("party"), c.get("years_in_office"), c["sort_order"],
                            c.get("source_url"),
                        )
                        for c in cards
                    ],
                )
    return len(cards)


def delete_cards(pool, category: str) -> int:
    with pool.connection() as conn:
        return conn.execute("delete from cards where category = %s", (category,)).rowcount


# ---------------------------------------------------------------- results

def save_quiz_result(pool, user_id: int, score: float, attempted: int, correct: int) -> None:
    with pool.connection() as conn:
        conn.execute(
            "insert into quizresults (user_id, score, questions_attempted, correct_answers) "
            "values (%s, %s, %s, %s)",
            (user_id, score, attempted, correct),
        )


def save_competition_result(pool, user_id: int, score: int, correct: int, seconds: float) -> None:
    with pool.connection() as conn:
        conn.execute(
            "insert into competitionresults (user_id, score, correct_answers, completion_time) "
            "values (%s, %s, %s, %s)",
            (user_id, score, correct, round(seconds, 2)),
        )


def competition_rows(pool) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(
            "select c.id, c.score, c.correct_answers, c.completion_time::float8 as completion_time, "
            "c.date, u.first_name || ' ' || u.last_name as student, u.username "
            "from competitionresults c join users u on u.id = c.user_id"
        ).fetchall()


def leaderboard(pool, limit: int = 20) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(
            "select c.id, c.score, c.correct_answers, c.completion_time::float8 as completion_time, "
            "c.date, u.first_name || ' ' || u.last_name as student, "
            "row_number() over (order by c.score desc, c.completion_time asc, c.date asc) as rank "
            "from competitionresults c join users u on u.id = c.user_id "
            "order by c.score desc, c.completion_time asc, c.date asc limit %s",
            (limit,),
        ).fetchall()


def leaderboard_summary(pool) -> dict:
    with pool.connection() as conn:
        return conn.execute(
            "select coalesce(max(score), 0) as highest, coalesce(avg(score), 0)::float8 as average, "
            "count(distinct user_id) as players from competitionresults"
        ).fetchone()


def global_stats(pool, category: str) -> dict:
    with pool.connection() as conn:
        return conn.execute(
            "select (select count(*) from cards where category = %s) as cards, "
            "(select count(*) from users) as users, "
            "(select count(*) from quizresults) as quizzes, "
            "(select coalesce(max(score), 0) from competitionresults) as top_score, "
            "(select coalesce(avg(score), 0)::float8 from quizresults) as avg_quiz, "
            "(select coalesce(avg(score), 0)::float8 from competitionresults) as avg_comp",
            (category,),
        ).fetchone()


def user_stats(pool, user_id: int) -> dict:
    with pool.connection() as conn:
        return conn.execute(
            "select coalesce((select cards_viewed from userprofiles where user_id = %(u)s), 0) "
            "as cards_viewed, "
            "(select count(*) from quizresults where user_id = %(u)s) as quizzes, "
            "(select coalesce(avg(score), 0)::float8 from quizresults where user_id = %(u)s) "
            "as avg_quiz, "
            "(select coalesce(max(score), 0) from competitionresults where user_id = %(u)s) "
            "as best_competition",
            {"u": user_id},
        ).fetchone()


def quiz_rows(pool) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(
            "select q.id, u.username, q.score::float8 as score, q.questions_attempted, "
            "q.correct_answers, q.date from quizresults q join users u on u.id = q.user_id "
            "order by q.date"
        ).fetchall()


# ---------------------------------------------------------------- admin

def table_counts(pool) -> dict[str, int]:
    with pool.connection() as conn:
        return {t: conn.execute(f"select count(*) n from {t}").fetchone()["n"] for t in TABLES}


def table_sizes_kb(pool) -> dict[str, float]:
    with pool.connection() as conn:
        return {
            t: round(
                conn.execute("select pg_total_relation_size(%s::regclass) s", (t,)).fetchone()["s"]
                / 1024,
                1,
            )
            for t in TABLES
        }


def category_counts(pool) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(
            "select category, count(*) as cards from cards group by category order by category"
        ).fetchall()


def rls_status(pool) -> dict[str, bool]:
    with pool.connection() as conn:
        rows = conn.execute(
            "select relname, relrowsecurity from pg_class where relname = any(%s) "
            "and relnamespace = 'public'::regnamespace",
            (TABLES,),
        ).fetchall()
    return {r["relname"]: r["relrowsecurity"] for r in rows}
