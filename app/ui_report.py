"""F9 on screen: the 'Report' tab (lead: Ali Haji)."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from app.config import Settings
from app.data_prep import Datasets
from app.filters import FilterOptions, Selection
from app.report import build_report, figures_csv
from app.ui_style import card, card_title, selection_pills


@st.cache_resource(show_spinner="Reading the documents...")
def get_chunks(chunk_words: int):
    try:
        from app.documents import build_chunks
        return build_chunks(chunk_words)
    except Exception:
        return None


def render_report(ds: Datasets, sel: Selection, options: FilterOptions, settings: Settings) -> None:
    answers = [a for a in st.session_state.get("answers", []) if not a.error]
    chunks = get_chunks(settings.chunk_words)
    html_report = build_report(ds, sel, options, settings, answers=answers, chunks=chunks)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    with card("report"):
        card_title("summarize", "Summary report for the current filters",
                   sub="The selection, summary figures, three charts, tables, the questions asked in this session "
                       "with their cited passages, and the licensing passages for the selected business groups.")
        selection_pills(sel.describe(options))
        st.caption(f":material/forum: Questions from this session included: {len(answers)}")
        c = st.columns(2)
        c[0].download_button("Download report (HTML)", html_report, file_name=f"BizLocate_report_{stamp}.html",
                             mime="text/html", type="primary", icon=":material/download:", width="stretch")
        c[1].download_button("Download the figures (CSV)", figures_csv(ds, sel),
                             file_name=f"BizLocate_figures_{stamp}.csv", mime="text/csv",
                             icon=":material/table_view:", width="stretch")
        st.caption(":material/print: The HTML file opens in any browser; use the browser's Print → Save as PDF "
                   "for a PDF copy.")
    with st.expander("Preview", icon=":material/visibility:"):
        st.html(html_report)
