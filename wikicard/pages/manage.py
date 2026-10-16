import pandas as pd
import streamlit as st

from .. import context as ctx
from .. import db
from ..style import hero


def _topic_picker(label: str, widget):
    topic = widget(label, ctx.TOPICS)
    available = topic == ctx.CATEGORY
    if not available:
        st.info(f"{topic.replace(' (coming soon)', '')} is coming soon. Only US Presidents is available today.")
    return topic, available


def _report(result, action: str):
    if result.source == "snapshot":
        for w in result.warnings:
            st.warning(w)
    st.success(
        f"{action}: {len(result.cards)} cards stored from {result.source} "
        f"({result.list_requests} list request, {result.lead_requests} lead requests)."
    )


def render_build():
    pool = ctx.get_pool()
    hero("Build Database", "Collect the study cards from Wikipedia.")
    if not ctx.admin_gate():
        return
    topic, available = _topic_picker("Choose a topic", lambda l, o: st.radio(l, o, index=0))
    count = db.count_cards(pool, ctx.CATEGORY)
    st.write(f"Cards currently stored: **{count}**")
    label = "Refresh Database" if count else "Build database"
    if st.button(label, type="primary", disabled=not available):
        with st.spinner("Collecting data from Wikipedia…"):
            try:
                result = ctx.run_harvest(pool, wipe_first=False, allow_snapshot=count == 0)
            except Exception as exc:
                st.error(f"Wikipedia could not be reached, so the existing cards were kept. ({exc})")
            else:
                _report(result, label)


def render_admin():
    pool = ctx.get_pool()
    hero("Admin", "Database health and maintenance.")
    if not ctx.admin_gate():
        return
    topic, available = _topic_picker("Topic", lambda l, o: st.selectbox(l, o))
    st.caption(db.describe_host(db.get_database_url()))

    counts, sizes = db.table_counts(pool), db.table_sizes_kb(pool)
    st.subheader("Tables")
    st.dataframe(
        pd.DataFrame({"Table": list(counts), "Rows": list(counts.values()), "Size (KB)": [sizes[t] for t in counts]}),
        hide_index=True, use_container_width=True,
    )
    st.subheader("Cards per category")
    cats = db.category_counts(pool)
    if cats:
        st.dataframe(pd.DataFrame(cats).rename(columns={"category": "Category", "cards": "Cards"}),
                     hide_index=True, use_container_width=True)
    else:
        st.info("There are no cards.")

    st.subheader("Maintenance")
    c = st.columns(3)
    if c[0].button("Refresh", disabled=not available, use_container_width=True):
        with st.spinner("Refreshing from Wikipedia…"):
            try:
                _report(ctx.run_harvest(pool, wipe_first=False, allow_snapshot=False), "Refresh")
            except Exception as exc:
                st.error(f"Refresh failed; existing cards were kept. ({exc})")
    if c[2].button("Rebuild", disabled=not available, use_container_width=True):
        with st.spinner("Rebuilding…"):
            _report(ctx.run_harvest(pool, wipe_first=True, allow_snapshot=True), "Rebuild")
    confirm = st.checkbox("I understand this can't be undone")
    if c[1].button("Delete all cards", disabled=not (confirm and available), use_container_width=True):
        deleted = db.delete_cards(pool, ctx.CATEGORY)
        ctx.get_cards.clear()
        st.success(f"Deleted {deleted} cards. They will stay deleted until you press Refresh or Rebuild.")
