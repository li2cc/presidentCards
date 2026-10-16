import random

import pandas as pd
import streamlit as st

from .. import context as ctx
from .. import db, game
from ..style import card_front_html, hero

KEY = "quiz"


def _start(cards, count):
    pool = list(cards)
    random.shuffle(pool)
    questions = pool if count == "All" else pool[: int(count)]
    st.session_state[KEY] = {
        "questions": questions, "i": 0, "attempted": 0, "correct": 0,
        "rows": [], "phase": "asking", "last": None, "saved": False, "reason": "finished",
    }


def _record(q, guess: str, all_answers: list[str], dont_know: bool):
    card = q["questions"][q["i"]]
    ok = False if dont_know else game.is_correct(guess, card["answer"], all_answers)
    q["attempted"] += 1
    q["correct"] += int(ok)
    shown = "(didn't know)" if dont_know else guess.strip()
    q["rows"].append({
        "#": q["i"] + 1, "President": card["answer"], "Your answer": shown,
        "Result": "✅ Correct" if ok else "❌ Incorrect",
    })
    q["last"] = {"ok": ok, "guess": shown, "answer": card["answer"], "dont_know": dont_know}
    q["phase"] = "answered"


def _finish(q, pool, user):
    q["phase"] = "done"
    if q["attempted"] > 0 and not q["saved"]:
        score = game.quiz_score(q["correct"], q["attempted"])
        db.save_quiz_result(pool, user["id"], score, q["attempted"], q["correct"])
        q["saved"] = True


def _next(q, pool, user):
    q["i"] += 1
    if q["i"] >= len(q["questions"]):
        _finish(q, pool, user)
    else:
        q["phase"] = "asking"
        q["last"] = None


def render():
    pool = ctx.get_pool()
    hero("Quiz", "Recognise each president from the portrait and clues.")
    user = ctx.require_user("take a quiz")
    if user is None:
        return
    cards = ctx.get_cards(pool)
    if not cards:
        st.warning("No cards yet. An administrator can build the database from **Build Database**.")
        return
    answers = [c["answer"] for c in cards]
    q = st.session_state.get(KEY)

    if q is None or q["phase"] == "setup":
        count = st.segmented_control("Number of questions", [5, 10, 20, "All"], default=10)
        if st.button("Start quiz", type="primary") and count:
            _start(cards, count)
            st.rerun()
        return

    if q["phase"] == "done":
        a, c = q["attempted"], q["correct"]
        if a == 0:
            st.info("No questions were answered, so nothing was saved.")
        else:
            st.success(f"Quiz complete! You scored {c} / {a} ({game.quiz_score(c, a):g}%). Result saved.")
            st.dataframe(pd.DataFrame(q["rows"]), hide_index=True, use_container_width=True)
        if st.button("Start a new quiz", type="primary"):
            st.session_state.pop(KEY)
            st.rerun()
        return

    total = len(q["questions"])
    m = st.columns(4)
    m[0].metric("Question", f"{q['i'] + 1} / {total}")
    m[1].metric("Attempted", q["attempted"])
    m[2].metric("Correct", q["correct"])
    m[3].metric("Incorrect", q["attempted"] - q["correct"])
    st.progress(q["i"] / total)

    card = q["questions"][q["i"]]
    st.markdown(card_front_html(card), unsafe_allow_html=True)

    if q["phase"] == "asking":
        with st.form(f"quiz_form_{q['i']}"):
            guess = st.text_input("Who is this president?", placeholder="Type a name and press Enter")
            col = st.columns(2)
            check = col[0].form_submit_button("Check answer", type="primary", use_container_width=True)
            idk = col[1].form_submit_button("I don't know", use_container_width=True)
        if check or idk:
            if check and not guess.strip():
                st.warning("Type an answer, or press “I don't know”.")
            else:
                _record(q, guess, answers, dont_know=idk)
                st.rerun()
    else:
        last = q["last"]
        if last["ok"]:
            st.success(f"✅ Correct! It's {last['answer']}.")
        else:
            st.error(f"❌ Incorrect. You answered \"{last['guess']}\". The right answer is {last['answer']}.")
        if st.button("Next question", type="primary"):
            _next(q, pool, user)
            st.rerun()

    if st.button("End quiz & save"):
        _finish(q, pool, user)
        st.rerun()
