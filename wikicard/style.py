"""CSS, hero banner and card HTML."""
from __future__ import annotations

from html import escape

import streamlit as st

CSS = """
<style>
:root { --wc-primary:#2a78d6; --wc-text:#0f172a; --wc-soft:#eef2f8; }
html, body, .stApp { overflow-x: hidden; }
.block-container { max-width: 1100px; padding-top: 3.5rem; }
.wc-hero { background: linear-gradient(120deg,#2a78d6 0%,#1d56a8 100%); color:#fff;
  border-radius:18px; padding:1.4rem 1.6rem; margin:0 0 1.2rem 0;
  box-shadow:0 6px 18px rgba(42,120,214,.25); }
.wc-hero h1 { color:#fff; margin:0; padding:0; font-size:1.9rem; line-height:1.2; }
.wc-hero p { color:rgba(255,255,255,.92); margin:.3rem 0 0 0; font-size:1.02rem; }
.wc-card { display:flex; gap:1.4rem; background:#fff; border-radius:18px; padding:1.3rem;
  box-shadow:0 6px 20px rgba(15,23,42,.08); margin:.6rem 0 1rem 0; align-items:flex-start; }
.wc-card.back { border-top:5px solid var(--wc-primary); }
.wc-portrait { flex:0 0 190px; width:190px; aspect-ratio:3/4; object-fit:cover;
  border-radius:12px; background:var(--wc-soft); }
.wc-body { flex:1 1 auto; min-width:0; }
.wc-body h2 { margin:0 0 .4rem 0; padding:0; font-size:1.6rem; }
.wc-chips { display:flex; flex-wrap:wrap; gap:.4rem; margin:.2rem 0 .8rem 0; }
.wc-chip { background:var(--wc-soft); color:#1d4f91; border-radius:999px;
  padding:.2rem .75rem; font-size:.85rem; font-weight:600; }
.wc-hint { font-size:1.05rem; line-height:1.55; }
.wc-desc { line-height:1.55; margin-bottom:.8rem; }
.wc-records { background:#eaf2fd; border-left:4px solid var(--wc-primary);
  border-radius:8px; padding:.7rem 1rem; margin:.6rem 0; }
.wc-records strong { display:block; margin-bottom:.3rem; }
.wc-records ul { margin:0; padding-left:1.2rem; }
.wc-records li { margin:.25rem 0; line-height:1.45; }
.wc-link { display:inline-block; margin-top:.4rem; font-weight:600; }
.wc-bonus { color:#475569; font-size:.9rem; }
@media (max-width: 640px) {
  .block-container { padding: 4.5rem .9rem 2rem .9rem; }
  .wc-hero { padding:1rem 1.1rem; }
  .wc-hero h1 { font-size:1.5rem; }
  .wc-card { flex-direction:column; align-items:center; text-align:left; padding:1rem; }
  .wc-card .wc-body { width:100%; }
  .wc-body h2 { text-align:center; }
  .wc-chips { justify-content:center; }
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:.5rem; }
  [data-testid="stColumn"] { min-width:calc(50% - .5rem) !important; }
  [data-testid="stDataFrame"], [data-testid="stPlotlyChart"] { max-width:100%; }
}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="wc-hero"><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def _chips(card: dict) -> str:
    chips = [c for c in (card.get("years_in_office"), card.get("party")) if c]
    return '<div class="wc-chips">' + "".join(f'<span class="wc-chip">{escape(c)}</span>' for c in chips) + "</div>"


def _portrait(card: dict) -> str:
    return f'<img class="wc-portrait" src="{escape(card.get("image_url") or "", quote=True)}" alt="Portrait">'


def card_front_html(card: dict) -> str:
    return (
        f'<div class="wc-card">{_portrait(card)}<div class="wc-body">{_chips(card)}'
        f'<div class="wc-hint">💡 {escape(card.get("hint") or "")}</div></div></div>'
    )


def card_back_html(card: dict) -> str:
    highlights = card.get("highlights") or []
    records = ""
    if highlights:
        items = "".join(f"<li>{escape(h)}</li>" for h in highlights)
        records = f'<div class="wc-records"><strong>Most notable records</strong><ul>{items}</ul></div>'
    link = ""
    if card.get("source_url"):
        link = (f'<a class="wc-link" href="{escape(card["source_url"], quote=True)}" '
                f'target="_blank" rel="noopener">Read more on Wikipedia →</a>')
    return (
        f'<div class="wc-card back">{_portrait(card)}<div class="wc-body">'
        f'<h2>{escape(card["name"])}</h2>{_chips(card)}'
        f'<div class="wc-desc">{escape(card.get("details") or "")}</div>{records}{link}</div></div>'
    )
