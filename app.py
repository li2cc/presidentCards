"""WikiCard Learning System - Streamlit entry point."""
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="WikiCard Learning System", page_icon="🎴", layout="wide")

from wikicard import context as ctx  # noqa: E402
from wikicard import db  # noqa: E402
from wikicard.pages import analytics, competition, home, leaderboard, manage, quiz, study  # noqa: E402
from wikicard.style import hero, inject_css  # noqa: E402

LOGO = Path(__file__).parent / "assets" / "logo.svg"


def setup_page(error: Exception):
    hero("Setup required", "The app could not connect to its PostgreSQL database.")
    st.error(f"{type(error).__name__}: {error}")
    st.markdown(
        "1. Create a free Supabase project and copy the **Session pooler** connection string "
        "(Project → Connect). Do **not** use the `db.<ref>.supabase.co` host; it is IPv6-only.\n"
        "2. Put it in `.streamlit/secrets.toml` (or Community Cloud → Settings → Secrets) as "
        "`DATABASE_URL = \"postgresql://…\"`, or set the `DATABASE_URL` environment variable.\n"
        "3. Reload this page. The tables are created automatically."
    )
    if st.button("Retry connection"):
        st.rerun()


def sidebar_user():
    user = ctx.current_user()
    with st.sidebar:
        if user:
            st.markdown(f"Signed in as **{user['username']}**")
            if st.button("Log out", use_container_width=True):
                for key in list(st.session_state):
                    del st.session_state[key]
                st.rerun()
        else:
            st.caption("Not signed in")


inject_css()
if LOGO.exists():
    st.logo(str(LOGO), size="large")

try:
    pool = ctx.get_pool()
    ctx.auto_harvest_once(pool)
except Exception as exc:  # show the real error instead of crashing
    setup_page(exc)
    st.stop()

pages = {
    "Learn": [
        st.Page(home.render, title="Home", icon=":material/home:", default=True),
        st.Page(study.render, title="Study", icon=":material/style:", url_path="study"),
        st.Page(quiz.render, title="Quiz", icon=":material/quiz:", url_path="quiz"),
        st.Page(competition.render, title="Competition", icon=":material/timer:", url_path="competition"),
    ],
    "Results": [
        st.Page(leaderboard.render, title="Leaderboard", icon=":material/leaderboard:", url_path="leaderboard"),
        st.Page(analytics.render, title="Analytics", icon=":material/monitoring:", url_path="analytics"),
    ],
    "Manage": [
        st.Page(manage.render_build, title="Build Database", icon=":material/construction:", url_path="build"),
        st.Page(manage.render_admin, title="Admin", icon=":material/admin_panel_settings:", url_path="admin"),
    ],
}
sidebar_user()
st.navigation(pages).run()
