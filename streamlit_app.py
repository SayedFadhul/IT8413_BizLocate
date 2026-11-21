"""BizLocate BH - Business Location and Licensing Assistant (IT8413 G3, Brief D).

Run:  streamlit run streamlit_app.py

Page layout
  Sidebar ........ settings in use (F10: model, settings, v1/v2 change), API key, filters (F2)
  Dashboard ...... summary figures and charts for the current filters (F3)
  Ask ............ questions over the data and documents, with citations (F4-F8)
  Report ......... downloadable report for the current filters (F9)
  Query log ...... every question asked, with answer, citations, time and tokens (F10)
  Data & sources . datasets, preparation steps, sources and licence (F1)

Each feature lives in its own files. The page shows a feature only when all the files it needs
are present, so the app still starts if a feature's files are missing.
"""
from __future__ import annotations

import importlib
import importlib.util

import streamlit as st

from app.config import V2_CHANGE, describe_v2_change, get_api_key, get_settings

st.set_page_config(page_title="BizLocate BH", layout="wide")

# The files each feature needs.
FEATURES = {
    "data": (("app.data_prep", "app.ui_data"), "Data loading and preparation (F1)"),
    "dashboard": (("app.filters", "app.dashboard", "app.ui_dashboard"), "The filters and dashboard (F2–F3)"),
    "report": (("app.report", "app.ui_report", "app.filters", "app.dashboard"),
               "The report download (F9), which also uses the filters and dashboard,"),
    "ask": (("app.assistant", "app.ui_ask", "app.data_tools", "app.documents", "app.retrieval", "app.query_log"),
            "Question answering (F4–F8)"),
    "log": (("app.query_log", "app.ui_log"), "The query log (F10)"),
}


def has(feature: str) -> bool:
    """True when every file the feature needs is present."""
    return all(importlib.util.find_spec(m) is not None for m in FEATURES[feature][0])


def not_yet(feature: str) -> None:
    st.info(f"{FEATURES[feature][1]} is not available: some of its files are missing.")


@st.cache_resource(show_spinner="Loading and preparing the datasets...")
def get_data():
    from app.data_prep import load_all
    return load_all()


ds = get_data() if has("data") else None

# ------------------------------------------------------------------ sidebar: settings in use (F10)
with st.sidebar:
    st.header("BizLocate BH")
    version = st.segmented_control("Version", ["v1", "v2"], default="v1", key="version",
                                   help="v2 = v1 with exactly one setting changed (brief 7.5).") or "v1"
    settings = get_settings(version)
    with st.expander("Settings in use", expanded=False):
        st.markdown(
            f"**Model:** `{settings.model}`  \n**Embeddings:** `{settings.embedding_model}`  \n"
            f"**Temperature:** {settings.temperature} · **Thinking:** {settings.thinking_level}  \n"
            f"**Max output tokens:** {settings.max_output_tokens}  \n"
            f"**Passages per question (k):** {settings.top_k} · **Chunk size:** {settings.chunk_words} words  \n"
            f"**Generation calls per question (max):** {settings.max_generation_calls}  \n"
            f"**Follow-up memory:** {settings.history_turns} previous questions"
        )
    st.caption(f"**Changed in v2:** {describe_v2_change()}")
    if version == "v2" and not V2_CHANGE:
        st.caption("v2 is still identical to v1.")

    key = get_api_key()
    if not key:
        key = st.text_input("Gemini API key", type="password", key="api_key_input",
                            help="Used only in this browser session; never saved. Or put it in a .env file (README, step 4).")
    st.caption("API key: " + ("found ✅" if key else "missing ❌ (README, step 4)"))
    st.divider()


@st.cache_resource(show_spinner=False)
def prepare_online_copy(_settings, _key: str, embedding_model: str, chunk_words: int) -> str | None:
    """Online version only: prepare the documents and build the search index once per server start.
    Returns None when ready, or what went wrong. A failure is kept too, so it is not retried on
    every click (rebooting the app tries again)."""
    from app import cloud_setup
    try:
        cloud_setup.prepare(_settings, _key, progress=lambda msg: None)
        return None
    except Exception as err:
        return str(err)


# Online version (Streamlit Community Cloud): the documents and index are not in GitHub, so they are
# prepared on the first start from the app's private Secrets (README, "Online version").
if key and importlib.util.find_spec("app.cloud_setup") and importlib.util.find_spec("app.retrieval"):
    from app import cloud_setup

    if cloud_setup.needed(settings):
        with st.spinner("First start of the online version: preparing the documents and building the "
                        "search index (about a minute)..."):
            problem = prepare_online_copy(settings, key, settings.embedding_model, settings.chunk_words)
        if problem:
            st.error("Document questions are not available in this online copy, because its documents could "
                     "not be prepared. The dashboard and the data questions still work.")
            with st.expander("What went wrong"):
                st.code(problem, language=None)

options = selection = None
if ds is not None and has("dashboard"):
    from app import ui_dashboard
    from app.filters import filter_options

    options = filter_options(ds)
    selection = ui_dashboard.sidebar_filters(options)

# ------------------------------------------------------------------ main page
st.title("BizLocate BH")
st.caption("Business Location and Licensing Assistant · IT8413 Group Project · G3 · "
           f"model `{settings.model}` · {version}")

tab_dash, tab_ask, tab_report, tab_log, tab_data = st.tabs(
    ["📊 Dashboard", "💬 Ask", "📄 Report", "🧾 Query log", "🗂️ Data & sources"])

with tab_dash:
    if selection is not None:
        ui_dashboard.render_dashboard(ds, selection, options)
    else:
        not_yet("dashboard" if ds is not None else "data")
with tab_ask:
    if ds is not None and has("ask"):
        importlib.import_module("app.ui_ask").render_ask(ds, settings, key)
    else:
        not_yet("ask")
with tab_report:
    if selection is not None and has("report"):
        importlib.import_module("app.ui_report").render_report(ds, selection, options, settings)
    else:
        not_yet("report")
with tab_log:
    if has("log"):
        importlib.import_module("app.ui_log").render_log(settings)
    else:
        not_yet("log")
with tab_data:
    if ds is not None:
        importlib.import_module("app.ui_data").render_data_page(ds)
    else:
        not_yet("data")
