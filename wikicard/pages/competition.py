import math
import time

import pandas as pd
import streamlit as st

from .. import context as ctx
from .. import db, game
from ..style import card_front_html, hero

KEY = "comp"
N = game.COMPETITION_QUESTIONS
LIMIT = game.QUESTION_SECONDS


def _start(cards):
    st.session_state[KEY] = {
        "cards": game.pick_questions(cards, N), "i": 0, "score": 0, "correct": 0,
        "rows": [], "phase": "asking", "q_start": time.time(), "last": None, "total_time": 0.0,
    }


def _record(c, guess: str, answers: list[str]):
    """Server-side timing: elapsed is measured from when the question appeared."""
    card = c["cards"][c["i"]]
    elapsed = time.time() - c["q_start"]
    timed_out = elapsed > LIMIT
    ok = (not timed_out) and game.is_correct(guess, card["answer"], answers)
    points = game.competition_points(ok, elapsed)
    bonus = game.speed_bonus(elapsed) if ok else 0
    c["score"] += points
    c["correct"] += int(ok)
    c["total_time"] += min(elapsed, LIMIT)
    c["rows"].append({
        "#": c["i"] + 1, "President": card["answer"],
        "Your answer": guess.strip() or ("(time ran out)" if timed_out else "(blank)"),
        "Result": "✅" if ok else "❌", "Time (s)": round(min(elapsed, LIMIT), 1), "Points": points,
    })
    c["last"] = {"ok": ok, "answer": card["answer"], "points": points, "bonus": bonus, "timed_out": timed_out}
    c["phase"] = "answered"


def _save_if_finished(c, pool, user):
    if c["i"] == N - 1 and c["phase"] == "answered" and not c.get("saved"):
        db.save_competition_result(pool, user["id"], c["score"], c["correct"], c["total_time"])
        c["saved"] = True


@st.fragment(run_every=1)
def _timer(answers, pool, user):
    c = st.session_state.get(KEY)
    if not c or c["phase"] != "asking":
        return
    elapsed = time.time() - c["q_start"]
    left = LIMIT - elapsed
    if left <= 0:
        _record(c, "", answers)
        _save_if_finished(c, pool, user)
        st.rerun()
    st.progress(
        max(0.0, min(1.0, left / LIMIT)),
        text=f"⏱️ {math.ceil(left)}s left · speed bonus now ≈ {game.speed_bonus(elapsed)}",
    )


def render():
    pool = ctx.get_pool()
    hero("Competition", f"{N} random presidents, {LIMIT} seconds each. Faster answers earn more points.")
    user = ctx.require_user("join the competition")
    if user is None:
        return
    cards = ctx.get_cards(pool)
    if len(cards) < N:
        st.warning(f"At least {N} cards are needed. Ask an administrator to build the database.")
        return
    answers = [c["answer"] for c in cards]
    c = st.session_state.get(KEY)

    if c is None:
        st.write(f"Answer {N} questions. Each is worth 100 points plus up to 50 for speed "
                 f"(maximum {N * 150}). Time starts when the question appears.")
        if st.button("Start competition", type="primary"):
            _start(cards)
            st.rerun()
        return

    finished = c["phase"] == "answered" and c["i"] == N - 1
    if finished:
        _save_if_finished(c, pool, user)
        st.success(f"🏁 Finished! Final score {c['score']} · {c['correct']}/{N} correct · "
                   f"{c['total_time']:.1f} s total answer time.")
        if c["correct"] == N:
            if not c.get("balloons"):
                st.balloons()
                c["balloons"] = True
        st.dataframe(pd.DataFrame(c["rows"]), hide_index=True, use_container_width=True)
        if st.button("Play again", type="primary"):
            st.session_state.pop(KEY)
            st.rerun()
        return

    m = st.columns(3)
    m[0].metric("Question", f"{c['i'] + 1} / {N}")
    m[1].metric("Score", c["score"])
    m[2].metric("Correct", c["correct"])

    card = c["cards"][c["i"]]
    if c["phase"] == "asking":
        _timer(answers, pool, user)
    st.markdown(card_front_html(card), unsafe_allow_html=True)

    if c["phase"] == "asking":
        with st.form(f"comp_form_{c['i']}", clear_on_submit=True):
            guess = st.text_input("Who is this president?", placeholder="Type a name and press Enter")
            submit = st.form_submit_button("Submit", type="primary")
        if submit:
            _record(c, guess, answers)
            _save_if_finished(c, pool, user)
            st.rerun()
    else:
        last = c["last"]
        if last["ok"]:
            st.success(f"✅ Correct! It's {last['answer']}. +{last['points']} points "
                       f"({game.BASE_POINTS} base + {last['bonus']} speed bonus)")
        elif last["timed_out"]:
            st.error(f"⏰ Time's up! It was {last['answer']}. +0 points")
        else:
            st.error(f"❌ Incorrect. The right answer is {last['answer']}. +0 points")
        if st.button("Next question", type="primary"):
            c["i"] += 1
            c["phase"] = "asking"
            c["q_start"] = time.time()
            c["last"] = None
            st.rerun()

    if st.button("Quit competition"):
        st.session_state.pop(KEY)
        st.rerun()
