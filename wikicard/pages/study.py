import random

import streamlit as st

from .. import context as ctx
from .. import db
from ..style import card_back_html, card_front_html, hero


def render():
    pool = ctx.get_pool()
    hero("Study", "Flip through the cards, reveal the answer, and learn each president.")
    cards = ctx.get_cards(pool)
    if not cards:
        st.warning("No cards yet. An administrator can build the database from **Build Database**.")
        return
    n = len(cards)
    ss = st.session_state
    ss.setdefault("study_idx", 0)
    ss.setdefault("study_show", False)
    ss.setdefault("study_viewed", 0)
    ss.setdefault("study_seen", set())
    ss.setdefault("study_nav", 0)
    ss.setdefault("study_counted", -1)
    ss["study_idx"] = min(ss["study_idx"], n - 1)
    ss.setdefault("study_jump", ss["study_idx"])
    if ss["study_jump"] >= n:
        ss["study_jump"] = ss["study_idx"]

    def go(i: int):
        ss["study_idx"] = i % n
        ss["study_jump"] = ss["study_idx"]
        ss["study_show"] = False
        ss["study_nav"] += 1

    def on_random():
        choices = [i for i in range(n) if i != ss["study_idx"]] or [0]
        go(random.choice(choices))

    def on_jump():
        go(ss["study_jump"])

    idx = ss["study_idx"]
    if ss["study_counted"] != ss["study_nav"]:
        ss["study_counted"] = ss["study_nav"]
        ss["study_viewed"] += 1
        ss["study_seen"].add(idx)
        user = ctx.current_user()
        if user:
            db.increment_cards_viewed(pool, user["id"])

    c = st.columns(3)
    c[0].metric("Card", f"{idx + 1} / {n}")
    c[1].metric("Viewed this session", ss["study_viewed"])
    c[2].metric("Unique cards seen", f"{len(ss['study_seen'])} / {n}")
    st.progress(len(ss["study_seen"]) / n)

    card = cards[idx]
    st.markdown(card_back_html(card) if ss["study_show"] else card_front_html(card), unsafe_allow_html=True)

    b = st.columns(4)
    b[0].button("◀ Previous", on_click=lambda: go(idx - 1), use_container_width=True)
    b[1].button(
        "Hide Answer" if ss["study_show"] else "Show Answer",
        on_click=lambda: ss.update(study_show=not ss["study_show"]),
        type="primary", use_container_width=True,
    )
    b[2].button("Next ▶", on_click=lambda: go(idx + 1), use_container_width=True)
    b[3].button("🎲 Random", on_click=on_random, use_container_width=True)
    st.selectbox("Jump to a card", range(n), format_func=lambda i: f"#{i + 1}", key="study_jump", on_change=on_jump)
    if ctx.current_user() is None:
        st.caption("Log in on the Home page to keep track of the cards you have viewed.")
