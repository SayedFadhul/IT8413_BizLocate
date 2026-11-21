"""F9 on screen: the 'Report' tab (lead: Ali Haji)."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from app.config import Settings
from app.data_prep import Datasets
from app.filters import FilterOptions, Selection
from app.report import build_report, figures_csv


@st.cache_resource(show_spinner="Reading the documents...")
def get_chunks(chunk_words: int):
    try:
        from app.documents import build_chunks
        return build_chunks(chunk_words)
    except Exception:
        return None


def render_report(ds: Datasets, sel: Selection, options: FilterOptions, settings: Settings) -> None:
    st.markdown("Download a summary report for the **current filters** (sidebar): the selection, summary figures, "
                "three charts, tables, the questions asked in this session with their cited passages, and the "
                "licensing passages for the selected business groups.")
    for line in sel.describe(options):
        st.caption(line)
    answers = [a for a in st.session_state.get("answers", []) if not a.error]
    st.caption(f"Questions from this session included: {len(answers)}")
    chunks = get_chunks(settings.chunk_words)
    html_report = build_report(ds, sel, options, settings, answers=answers, chunks=chunks)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    c = st.columns(2)
    c[0].download_button("Download report (HTML)", html_report, file_name=f"BizLocate_report_{stamp}.html",
                         mime="text/html", type="primary", width="stretch")
    c[1].download_button("Download the figures (CSV)", figures_csv(ds, sel), file_name=f"BizLocate_figures_{stamp}.csv",
                         mime="text/csv", width="stretch")
    st.caption("The HTML file opens in any browser; use the browser's Print → Save as PDF for a PDF copy.")
    with st.expander("Preview"):
        st.html(html_report)
