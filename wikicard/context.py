"""Shared app context: DB pool, cached card loading, harvesting, session user, admin gate."""
from __future__ import annotations

import hmac
import threading

import streamlit as st

from . import db, scraper

CATEGORY = scraper.CATEGORY
TOPICS = [
    "US Presidents",
    "State Capitals (coming soon)",
    "Countries (coming soon)",
    "National Parks (coming soon)",
    "Programming Languages (coming soon)",
]
_harvest_lock = threading.Lock()


@st.cache_resource(show_spinner="Connecting to the database…")
def _connect(url: str):
    pool = db.create_pool(url)
    try:
        db.init_schema(pool)
    except Exception:
        pool.close()
        raise
    return pool


def get_pool():
    return _connect(db.get_database_url())


@st.cache_resource(show_spinner="Building the card database from Wikipedia…")
def auto_harvest_once(_pool) -> str:
    """Runs once per server start; harvests only when there are no cards."""
    with _harvest_lock:
        if db.count_cards(_pool, CATEGORY) == 0:
            result = scraper.harvest()
            db.replace_cards(_pool, CATEGORY, result.cards)
            return f"harvested from {result.source}"
    return "cards already present"


@st.cache_data(ttl=300, show_spinner=False)
def get_cards(_pool, category: str = CATEGORY) -> list[dict]:
    return db.load_cards(_pool, category)


def run_harvest(pool, *, wipe_first: bool, allow_snapshot: bool) -> scraper.HarvestResult:
    with _harvest_lock:
        if wipe_first:
            db.delete_cards(pool, CATEGORY)
        result = scraper.harvest(allow_snapshot=allow_snapshot)
        db.replace_cards(pool, CATEGORY, result.cards)
    get_cards.clear()
    return result


def current_user() -> dict | None:
    return st.session_state.get("user")


def require_user(action: str) -> dict | None:
    user = current_user()
    if user is None:
        st.info(f"Please log in or create a profile on the **Home** page to {action}.")
    return user


def admin_gate() -> bool:
    """Ask for ADMIN_PASSWORD when that secret is set. Returns True when access is allowed."""
    expected = db.get_secret("ADMIN_PASSWORD")
    if not expected or st.session_state.get("admin_ok"):
        return True
    with st.form("admin_gate"):
        password = st.text_input("Admin password", type="password")
        submitted = st.form_submit_button("Unlock")
    if submitted:
        if hmac.compare_digest(password.encode(), expected.encode()):
            st.session_state["admin_ok"] = True
            st.rerun()
        st.error("Incorrect password.")
    return False
