import pandas as pd
import streamlit as st

from .. import context as ctx
from .. import db, game
from ..style import hero

SORTS = ["Rank", "Student Name", "Score", "Date"]
DEFAULT_ORDER = {"Rank": "Ascending", "Student Name": "Ascending", "Score": "Descending", "Date": "Descending"}


def _on_sort_change():
    st.session_state["lb_order"] = DEFAULT_ORDER[st.session_state["lb_sort"]]


def render():
    pool = ctx.get_pool()
    hero("Leaderboard", "The top 20 competition results, ranked by score and then by speed.")
    summary = db.leaderboard_summary(pool)
    m = st.columns(3)
    m[0].metric("Highest score ever", summary["highest"])
    m[1].metric("Average score", f"{summary['average']:.0f}")
    m[2].metric("Total players", summary["players"])

    ranked = game.rank_competition(db.competition_rows(pool))
    if not ranked:
        st.info("No competition results yet. Be the first to play!")
        return

    st.session_state.setdefault("lb_sort", "Rank")
    st.session_state.setdefault("lb_order", DEFAULT_ORDER["Rank"])
    c = st.columns(2)
    sort_by = c[0].selectbox("Sort by", SORTS, key="lb_sort", on_change=_on_sort_change)
    order = c[1].selectbox("Order", ["Ascending", "Descending"], key="lb_order")

    df = pd.DataFrame([{
        "_rank": r["rank"], "Rank": game.medal(r["rank"]), "Student Name": r["student"],
        "Score": r["score"], "Correct": f"{r['correct_answers']} / {game.COMPETITION_QUESTIONS}",
        "Time (s)": round(r["completion_time"], 1), "_date": r["date"],
        "Date": r["date"].strftime("%Y-%m-%d %H:%M"),
    } for r in ranked])
    key = {"Rank": "_rank", "Student Name": "Student Name", "Score": "Score", "Date": "_date"}[sort_by]
    if key == "Student Name":
        df = df.sort_values(key, key=lambda s: s.str.lower(), ascending=order == "Ascending", kind="stable")
    else:
        df = df.sort_values(key, ascending=order == "Ascending", kind="stable")
    st.dataframe(
        df[["Rank", "Student Name", "Score", "Correct", "Time (s)", "Date"]],
        hide_index=True, use_container_width=True,
    )
