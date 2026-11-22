"""The look of the app: G3's colour scheme, the page header, cards and icons.

Colours in 60/30/10: cream (page) 60%, navy (sidebar, header, summary cards, text) 30%,
coral (buttons, active tab, highlights) 10%. The theme colours are set in .streamlit/config.toml and the
chart colours in app/palette.py. This file adds what a theme cannot: the page header, glossy summary
cards, card panels, the tab bar and Material icons in place of emoji. Nothing here changes a figure or
an answer.
"""
from __future__ import annotations

from html import escape

import streamlit as st

CSS = """
/* ------------------------------------------------------------ page */
[data-testid="stMainBlockContainer"] { padding: 2rem 2.5rem 2.5rem 2.5rem; max-width: 1680px; }
[data-testid="stHeader"] { background: transparent; }
.bl-icon { font-family: "Material Symbols Rounded"; font-weight: normal; font-style: normal; line-height: 1;
  letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap; direction: ltr;
  -webkit-font-feature-settings: "liga"; font-feature-settings: "liga"; -webkit-font-smoothing: antialiased; }

/* ------------------------------------------------------------ page header */
.bl-hero { position: relative; overflow: hidden; border-radius: 20px; padding: 24px 30px 22px 34px; margin-bottom: 6px;
  background: radial-gradient(130% 160% at 100% 0%, #2C4372 0%, #14213D 52%, #0F1A33 100%); color: #F4EDE0;
  box-shadow: 0 14px 34px rgba(20,33,61,.22), inset 0 1px 0 rgba(255,255,255,.10); }
.bl-hero::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 50%; pointer-events: none;
  background: linear-gradient(180deg, rgba(255,255,255,.13) 0%, rgba(255,255,255,0) 100%); }
.bl-hero::after { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 6px; background: #FF6B5B; }
.bl-hero-row { position: relative; display: flex; align-items: center; gap: 16px; }
.bl-logo { flex: none; width: 54px; height: 54px; border-radius: 15px; display: grid; place-items: center;
  background: linear-gradient(160deg, #FF8A7C 0%, #FF6B5B 55%, #EE5A4A 100%);
  box-shadow: 0 8px 18px rgba(255,107,91,.35), inset 0 1px 0 rgba(255,255,255,.40); }
.bl-logo .bl-icon { color: #FFFFFF; font-size: 30px; }
.bl-title { font-size: 2.05rem; font-weight: 800; letter-spacing: -.015em; line-height: 1.1; color: #F4EDE0; }
.bl-subtitle { margin-top: 3px; font-size: 1rem; color: rgba(244,237,224,.80); }
.bl-badges { position: relative; display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.bl-badge { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 999px;
  font-size: .82rem; font-weight: 600; color: #F4EDE0; background: rgba(244,237,224,.09);
  border: 1px solid rgba(244,237,224,.20); }
.bl-badge .bl-icon { font-size: 16px; color: #FF8F82; }
.bl-badge.bl-accent { background: #FF6B5B; border-color: #FF6B5B; color: #FFFFFF; }
.bl-badge.bl-accent .bl-icon { color: #FFFFFF; }

/* ------------------------------------------------------------ tab bar */
[data-testid="stTabs"] [role="tablist"] { gap: 6px; padding: 6px; background: #EAE0CE; border: 1px solid #DCCDB4;
  border-radius: 14px; width: fit-content; max-width: 100%; margin-bottom: 6px; }
[data-testid="stTabs"] [role="tab"] { padding: 8px 18px; border-radius: 10px; height: auto; }
[data-testid="stTabs"] [role="tab"] p { font-weight: 600; color: #14213D; }
[data-testid="stTabs"] [role="tab"]:hover { background: rgba(20,33,61,.07); }
[data-testid="stTabs"] [role="tab"] [data-testid="stIconMaterial"] { color: #C2473A; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { background: linear-gradient(180deg, #22355F 0%, #14213D 100%);
  box-shadow: 0 6px 14px rgba(20,33,61,.25), inset 0 1px 0 rgba(255,255,255,.14); }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] p { color: #F4EDE0; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] [data-testid="stIconMaterial"] { color: #FF8F82; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"], [data-testid="stTabs"] [data-baseweb="tab-border"] { display: none; }

/* ------------------------------------------------------------ summary cards (st.metric) */
[data-testid="stMetric"] { position: relative; overflow: hidden; padding: 16px 18px 14px 18px; border-radius: 16px;
  background: linear-gradient(160deg, #283C6C 0%, #14213D 58%, #101B34 100%); border: 1px solid rgba(255,255,255,.06);
  box-shadow: 0 10px 22px rgba(20,33,61,.18), inset 0 1px 0 rgba(255,255,255,.16); }
[data-testid="stMetric"]::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 46%; pointer-events: none;
  background: linear-gradient(180deg, rgba(255,255,255,.15) 0%, rgba(255,255,255,0) 100%); }
[data-testid="stMetric"]::after { content: ""; position: absolute; left: 18px; top: 0; width: 34px; height: 3px;
  border-radius: 0 0 3px 3px; background: #FF6B5B; }
/* cards in one row get the same height (when one card shows a change, the others grow with it) */
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) { align-items: stretch; }
[data-testid="stColumn"]:has([data-testid="stMetric"]) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has([data-testid="stMetric"]) [data-testid="stElementContainer"],
[data-testid="stColumn"]:has([data-testid="stMetric"]) [data-testid="stMetric"] { height: 100%; }
[data-testid="stMetric"] [data-testid="stMetricLabel"] p { color: rgba(244,237,224,.82); font-weight: 600; font-size: .86rem; }
[data-testid="stMetric"] [data-testid="stMetricLabel"] [data-testid="stIconMaterial"] { color: #FF8F82; }
[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #F4EDE0; }
/* narrow windows: the cards move onto a second row instead of being squeezed (each card at least 150 px wide) */
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) { flex-wrap: wrap; row-gap: 1rem; }
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] { min-width: 150px; }
[data-testid="stMetric"] [data-testid="stMetricLabel"] * { word-break: normal !important; overflow-wrap: normal !important; }
/* smaller screens (e.g. a 1280 px projector): the numbers shrink and the labels wrap instead of being cut off */
[data-testid="stMetric"] [data-testid="stMetricValue"], [data-testid="stMetric"] [data-testid="stMetricValue"] * {
  font-size: clamp(1.15rem, 1.55vw, 1.8rem) !important; }
[data-testid="stMetric"] [data-testid="stMetricLabel"], [data-testid="stMetric"] [data-testid="stMetricLabel"] * {
  white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }
[data-testid="stMetric"] [data-testid="stMetricDelta"] { background: rgba(244,237,224,.13) !important; }
[data-testid="stMetric"] [data-testid="stMetricDelta"], [data-testid="stMetric"] [data-testid="stMetricDelta"] * { color: rgba(244,237,224,.88) !important; }
[data-testid="stMetric"] [data-testid="stTooltipIcon"], [data-testid="stMetric"] [data-testid="stTooltipIcon"] * { color: rgba(244,237,224,.70); }

/* ------------------------------------------------------------ card panels (st.container with a key starting card_) */
div[class*="st-key-card_"] { background: #FBF7F0; border: 1px solid #E3D6C0; border-radius: 18px; padding: 18px 20px 12px 20px;
  box-shadow: 0 1px 2px rgba(20,33,61,.04), 0 10px 26px rgba(20,33,61,.06); }
.bl-card-title { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.02rem; color: #14213D; }
.bl-card-title .bl-icon { flex: none; width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center;
  font-size: 18px; color: #FF8F82; background: linear-gradient(160deg, #283C6C, #14213D);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.18); }
.bl-kind { margin-left: auto; flex: none; font-size: .68rem; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
  color: #A63A2B; background: rgba(255,107,91,.11); border: 1px solid rgba(255,107,91,.35); padding: 3px 9px; border-radius: 999px; }
.bl-card-sub { margin: 2px 0 0 40px; font-size: .84rem; color: #5B6478; }

/* ------------------------------------------------------------ selection pills */
.bl-pills { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 6px 0; }
.bl-pill { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 999px; font-size: .82rem;
  color: #14213D; background: #FBF7F0; border: 1px solid #E3D6C0; }
.bl-pill .bl-icon { font-size: 16px; color: #C2473A; }
.bl-pill b { font-weight: 700; }

/* ------------------------------------------------------------ buttons */
button[data-testid="stBaseButton-primary"] { color: #FFFFFF; font-weight: 700; border: 1px solid #E8594A;
  background: linear-gradient(180deg, #FF8172 0%, #FF6B5B 55%, #F25E4E 100%);
  box-shadow: 0 6px 16px rgba(255,107,91,.28), inset 0 1px 0 rgba(255,255,255,.32); }
button[data-testid="stBaseButton-primary"]:hover { color: #FFFFFF; border-color: #D94E3F; filter: brightness(.97); }
button[data-testid="stBaseButton-secondary"] { font-weight: 600; color: #14213D; background: #FBF7F0; border: 1px solid #D7C8AE; }
button[data-testid="stBaseButton-secondary"]:hover { color: #14213D; background: #FFFFFF; border-color: #14213D; }

/* ------------------------------------------------------------ sidebar */
[data-testid="stSidebar"] h2 { font-size: 1.1rem; }
[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] { color: #F4EDE0; background: rgba(244,237,224,.06);
  border: 1px solid rgba(244,237,224,.28); }
[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover { color: #FFFFFF; background: rgba(255,107,91,.16);
  border-color: #FF6B5B; }
[data-testid="stSidebar"] [data-testid="stMultiSelectTagsContainer"] > span > span { background: rgba(255,107,91,.18);
  box-shadow: inset 0 0 0 1px rgba(255,107,91,.60); }
[data-testid="stSidebar"] [data-testid="stMultiSelectTagsContainer"] > span,
[data-testid="stSidebar"] [data-testid="stMultiSelectTagsContainer"] > span * { color: #F4EDE0; }
[data-testid="stSidebar"] [data-testid="stMultiSelectTagsContainer"] > span button:hover { color: #FF8F82; }
.bl-side-brand { display: flex; align-items: center; gap: 12px; padding: 2px 0 6px 0; }
.bl-side-brand .bl-logo { width: 42px; height: 42px; border-radius: 12px; }
.bl-side-brand .bl-logo .bl-icon { font-size: 24px; }
.bl-side-name { font-weight: 800; font-size: 1.15rem; line-height: 1.1; color: #F4EDE0; }
.bl-side-tag { font-size: .78rem; color: rgba(244,237,224,.66); }

/* ------------------------------------------------------------ example questions (Ask): show the whole question */
div.st-key-card_ask_intro button { height: 100%; justify-content: flex-start; text-align: left; }
div.st-key-card_ask_intro button p { white-space: normal; text-align: left; }

/* ------------------------------------------------------------ chat (Ask) */
[data-testid="stChatMessage"] { background: #FBF7F0; border: 1px solid #E3D6C0; border-radius: 16px; padding: 14px 16px;
  box-shadow: 0 4px 14px rgba(20,33,61,.05); }

/* ------------------------------------------------------------ footer */
.bl-footer { margin-top: 26px; padding-top: 12px; border-top: 1px solid #DCCDB4; display: flex; flex-wrap: wrap;
  gap: 4px 18px; font-size: .78rem; color: #5B6478; }
"""


def _icon(name: str) -> str:
    return f'<span class="bl-icon">{escape(name)}</span>'


def apply_style() -> None:
    """Add the app's styles to the page (call once, at the top of the script)."""
    st.html(f"<style>{CSS}</style>")


def page_header(model: str, version: str, data_date: str) -> None:
    """The navy page header: name, purpose, and the model and version in use (F10)."""
    st.html(
        '<div class="bl-hero"><div class="bl-hero-row">'
        f'<div class="bl-logo">{_icon("location_on")}</div>'
        '<div><div class="bl-title">BizLocate BH</div>'
        '<div class="bl-subtitle">Business Location and Licensing Assistant for small businesses in Bahrain</div></div>'
        '</div><div class="bl-badges">'
        f'<span class="bl-badge">{_icon("school")}IT8413 · Group G3 · Brief D</span>'
        f'<span class="bl-badge">{_icon("smart_toy")}Model {escape(model)}</span>'
        f'<span class="bl-badge bl-accent">{_icon("tune")}Version {escape(version)}</span>'
        f'<span class="bl-badge">{_icon("calendar_month")}Data from data.gov.bh, {escape(data_date)}</span>'
        '</div></div>'
    )


def sidebar_brand() -> None:
    st.sidebar.html(
        f'<div class="bl-side-brand"><div class="bl-logo">{_icon("location_on")}</div>'
        '<div><div class="bl-side-name">BizLocate BH</div><div class="bl-side-tag">IT8413 · Group G3</div></div></div>'
    )


def card(name: str):
    """A light panel with a soft shadow (st.container; its key gives it the card style)."""
    return st.container(key=f"card_{name}")


def card_title(icon: str, title: str, kind: str | None = None, sub: str | None = None) -> None:
    """Title row of a card: icon, title and, on the right, what the chart shows (comparison, composition...)."""
    kind_html = f'<span class="bl-kind">{escape(kind)}</span>' if kind else ""
    sub_html = f'<div class="bl-card-sub">{escape(sub)}</div>' if sub else ""
    st.html(f'<div class="bl-card-title">{_icon(icon)}<span>{escape(title)}</span>{kind_html}</div>{sub_html}')


def pills(items: list[tuple[str, str, str]]) -> None:
    """A row of small labels, each (icon, label, value), e.g. the current filters."""
    html = "".join(f'<span class="bl-pill">{_icon(i)}{escape(label)}: <b>{escape(value)}</b></span>'
                   for i, label, value in items)
    st.html(f'<div class="bl-pills">{html}</div>')


SELECTION_ICONS = {"Governorates": "location_on", "Business groups": "category", "Business types": "sell",
                   "Population": "groups", "Land use": "landscape"}


def selection_pills(lines: list[str]) -> None:
    """The current filters (the lines of Selection.describe(), 'Label: value') as a row of labels."""
    items = []
    for line in lines:
        label, _, value = line.partition(": ")
        items.append((SELECTION_ICONS.get(label, "filter_alt"), label, value))
    pills(items)


def footer(data_date: str) -> None:
    st.html(
        '<div class="bl-footer"><span>BizLocate BH · IT8413 · Group G3</span>'
        f'<span>Datasets: data.gov.bh (Bahrain Open Government Data License v1.1), extracted {escape(data_date)}</span>'
        '<span>Documents: MOIC and MOH (see Data &amp; sources)</span>'
        '<span>Figures are computed in code; rules are cited to their passages.</span></div>'
    )
