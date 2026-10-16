import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import context as ctx
from .. import db, game
from ..style import hero

BLUE = "#2a78d6"
GRID = "#e8edf5"


def _layout(fig, x_title, y_title, **kw):
    fig.update_layout(
        showlegend=False, plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10), font=dict(color="#0f172a"), height=340,
        xaxis=dict(title=x_title, gridcolor=GRID), yaxis=dict(title=y_title, gridcolor=GRID),
        hoverlabel=dict(bgcolor="white"), **kw,
    )
    return fig


def quiz_figure(quiz: pd.DataFrame) -> go.Figure:
    days = quiz["date"].dt.date.nunique()
    fig = go.Figure()
    if days >= 3:
        daily = quiz.groupby(quiz["date"].dt.date)["score"].mean().reset_index()
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["score"].round(1), mode="lines+markers",
            line=dict(color=BLUE, width=3), marker=dict(size=8, color=BLUE),
            hovertemplate="%{x}<br>Average score: %{y:.1f}%<extra></extra>",
        ))
        x_title = "Date"
    else:
        fig.add_trace(go.Scatter(
            x=quiz["date"], y=quiz["score"], mode="markers", marker=dict(size=11, color=BLUE),
            customdata=quiz[["username", "correct_answers", "questions_attempted"]],
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>%{customdata[0]}: %{y:.1f}% "
                          "(%{customdata[1]} / %{customdata[2]})<extra></extra>",
        ))
        x_title = "Quiz date"
    _layout(fig, x_title, "Quiz score (%)")
    fig.update_yaxes(range=[0, 100])
    return fig


def bin_labels() -> list[str]:
    labels = [f"{lo}–{lo + 99}" for lo in range(0, 1400, 100)]
    return labels + ["1400–1500"]


def histogram_counts(scores: pd.Series) -> list[int]:
    idx = (scores // 100).clip(upper=14).astype(int)
    return [int((idx == i).sum()) for i in range(15)]


def histogram_figure(scores: pd.Series) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=bin_labels(), y=histogram_counts(scores), marker_color=BLUE,
        hovertemplate="Score %{x}<br>Games: %{y}<extra></extra>",
    ))
    _layout(fig, "Competition score (100-point bins, 0–1500)", "Number of games", bargap=0.08)
    fig.update_xaxes(tickangle=-45, type="category")
    return fig


def top_students_figure(comp: pd.DataFrame) -> go.Figure:
    best = comp.groupby("student")["score"].max().sort_values(ascending=False).head(10)
    best = best.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=best.values, y=best.index, orientation="h", marker_color=BLUE,
        text=best.values, textposition="outside",
        hovertemplate="%{y}<br>Best score: %{x}<extra></extra>",
    ))
    _layout(fig, "Best competition score", "Student")
    fig.update_xaxes(range=[0, 1650])
    return fig


def render():
    pool = ctx.get_pool()
    hero("Analytics", "How students are doing across quizzes and competitions.")
    s = db.global_stats(pool, ctx.CATEGORY)
    m = st.columns(5)
    m[0].metric("Total users", s["users"])
    m[1].metric("Total cards", s["cards"])
    m[2].metric("Quizzes taken", s["quizzes"])
    m[3].metric("Avg quiz score", f"{s['avg_quiz']:.1f}%")
    m[4].metric("Avg competition score", f"{s['avg_comp']:.0f}")

    quiz = pd.DataFrame(db.quiz_rows(pool))
    comp = pd.DataFrame(db.competition_rows(pool))

    st.subheader("Quiz scores over time")
    if quiz.empty:
        st.info("No quiz results yet.")
    else:
        quiz["date"] = pd.to_datetime(quiz["date"])
        st.plotly_chart(quiz_figure(quiz), use_container_width=True, config={"displayModeBar": False})
        st.caption("Each dot is one quiz. Once quizzes span three or more days, the line shows the daily average.")
        with st.expander("Raw quiz data"):
            st.dataframe(quiz, hide_index=True, use_container_width=True)

    st.subheader("Competition score distribution")
    if comp.empty:
        st.info("No competition results yet.")
        return
    st.plotly_chart(histogram_figure(comp["score"]), use_container_width=True, config={"displayModeBar": False})
    st.caption("How many competition games landed in each 100-point score range (maximum 1500).")
    st.subheader("Top performing students")
    st.plotly_chart(top_students_figure(comp), use_container_width=True, config={"displayModeBar": False})
    st.caption("Each student's best competition score; the top 10 are shown.")
    with st.expander("Raw competition data"):
        st.dataframe(comp.drop(columns=["id"]), hide_index=True, use_container_width=True)
