import streamlit as st

from .. import context as ctx
from .. import db
from ..style import hero


def _login_tab(pool):
    users = db.list_users(pool)
    if not users:
        st.info("No profiles yet. Create the first one in the next tab.")
        return
    options = {u["id"]: u for u in users}
    with st.form("login_form"):
        choice = st.selectbox(
            "Select your account",
            list(options),
            index=None,
            format_func=lambda i: f"{options[i]['username']} — {options[i]['first_name']} {options[i]['last_name']}",
        )
        submitted = st.form_submit_button("Log in", type="primary")
    if submitted:
        if choice is None:
            st.warning("Select an account first.")
        else:
            db.touch_login(pool, choice)
            st.session_state["user"] = options[choice]
            st.rerun()


def _register_tab(pool):
    with st.form("register_form"):
        first = st.text_input("First name", max_chars=40)
        last = st.text_input("Last name", max_chars=40)
        username = st.text_input("Username", max_chars=30, help="3–30 characters: letters, digits, . _ -")
        submitted = st.form_submit_button("Create profile", type="primary")
    if submitted:
        errors = db.validate_registration(first, last, username)
        if errors:
            for e in errors:
                st.error(e)
            return
        try:
            user = db.register_user(pool, first, last, username)
        except db.UsernameTaken as exc:
            st.error(str(exc))
            return
        st.session_state["user"] = user
        st.rerun()


def render():
    pool = ctx.get_pool()
    hero("WikiCard Learning System", "Learn the US presidents, test yourself and climb the leaderboard.")
    stats = db.global_stats(pool, ctx.CATEGORY)
    c = st.columns(4)
    c[0].metric("Study cards", stats["cards"])
    c[1].metric("Students", stats["users"])
    c[2].metric("Quizzes taken", stats["quizzes"])
    c[3].metric("Top competition score", stats["top_score"])

    user = ctx.current_user()
    if user is None:
        st.subheader("Get started")
        login_tab, register_tab = st.tabs(["Log in", "Create profile"])
        with login_tab:
            _login_tab(pool)
        with register_tab:
            _register_tab(pool)
        return

    st.subheader(f"Welcome back, {user['first_name']}!")
    mine = db.user_stats(pool, user["id"])
    c = st.columns(4)
    c[0].metric("Cards viewed", mine["cards_viewed"])
    c[1].metric("Quizzes completed", mine["quizzes"])
    c[2].metric("Average quiz score %", f"{mine['avg_quiz']:.1f}")
    c[3].metric("Best competition", mine["best_competition"])
