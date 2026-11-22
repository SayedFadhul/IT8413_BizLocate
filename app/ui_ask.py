"""F4-F8 on screen: the 'Ask' tab (lead: Sayed Fadhul Hashem).

A conversation: each question is answered by app/assistant.py and shown with
  - the answer and its citations ([T1] computed figures, [P12] document passages),
  - a 'Sources' panel with every function call (arguments, figures, source) and every retrieved
    passage in full, cited ones first, so each claim can be checked (F5),
  - tokens, response time and cost (F10), and a clear label when the question is declined (F7).
Earlier questions stay in the conversation, so a question can refer to them (F8).
"""
from __future__ import annotations

import uuid

import pandas as pd
import streamlit as st

from app import query_log
from app.assistant import REFUSAL, Answer, Assistant
from app.config import Settings
from app.data_prep import Datasets
from app.gemini import Gemini, failure_tag
from app.retrieval import build_index, index_path, load_index
from app.ui_style import card, card_title

EXAMPLES = [
    "How many Italian restaurants are listed in the Capital Governorate?",
    "What share of Muharraq's residents are Bahraini?",
    "What does the food-safety guideline require for staff health?",
    "How many furniture shops are there in the Southern Governorate?",
    "Would a bakery succeed in block 905?",
]


@st.cache_resource(show_spinner=False)
def get_tools(_ds: Datasets):
    from app.data_tools import DataTools
    return DataTools(_ds)


@st.cache_resource(show_spinner="Loading the document index...")
def get_index(embedding_model: str, chunk_words: int, _settings: Settings, _built_at: float):
    return load_index(_settings)


def _index_for(settings: Settings):
    path = index_path(settings)
    return get_index(settings.embedding_model, settings.chunk_words, settings,
                     path.stat().st_mtime if path.exists() else 0.0)


def _md(text: str) -> str:
    return text.replace("$", r"\$")      # '$' would start a formula in Streamlit markdown


CITED = ":green-badge[:material/check: cited]"
NOT_CITED = ":gray-badge[retrieved, not cited]"


def render_answer(a: Answer, number: int) -> None:
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(_md(a.question))
    with st.chat_message("assistant", avatar=":material/travel_explore:"):
        if a.error:
            st.error(f"The request failed, so there is no answer: {a.error}", icon=":material/cloud_off:")
            return
        if a.refused:
            st.info("Declined: the answer is not available in the sources (F7).", icon=":material/block:")
        st.markdown(_md(a.text))
        u = a.usage
        st.caption(f"Q{number} · {u.input_tokens:,} input + {u.output_tokens:,} output tokens · "
                   f"{a.latency_s:.1f} s ({a.latency_without_waits_s:.1f} s without rate-limit waits) · "
                   f"{u.generation_calls} generation + {u.embedding_calls} embedding calls · ${a.cost():.5f}"
                   + (" · follow-up" if a.follow_up else ""))
        if a.unknown_citations:
            st.warning(f"Cited id(s) that do not belong to this answer's results or passages: "
                       f"{', '.join(a.unknown_citations)}. Check these claims against the sources.",
                       icon=":material/report:")
        with st.expander(f"Sources for Q{number}: {len(a.tool_results)} computed result(s), "
                         f"{len(a.passages)} passage(s) retrieved", icon=":material/library_books:"):
            for r in sorted(a.tool_results, key=lambda r: r["id"] not in a.cited):
                mark = CITED if r["id"] in a.cited else ":gray-badge[not cited]"
                st.markdown(f"**[{r['id']}] `{r.get('function')}`** {mark} — {_md(str(r.get('source', '')))}")
                st.caption("Arguments: " + ", ".join(f"{k} = {v}" for k, v in (r.get("arguments") or {}).items()))
                if r.get("error"):
                    st.error(r["error"])
                    continue
                st.json(r.get("result", {}), expanded=False)
                if r.get("rows"):
                    st.dataframe(pd.DataFrame(r["rows"]), hide_index=True)
                for n in r.get("notes", []):
                    st.caption("Note: " + n)
            if a.passages:
                st.markdown("**Passages retrieved** (cosine similarity to the question)")
            for p in sorted(a.passages, key=lambda p: p["id"] not in a.cited):
                mark = CITED if p["id"] in a.cited else NOT_CITED
                with st.container(border=True):
                    st.markdown(f"**[{p['id']}]** {_md(p['title'])} · score {p['score']} · {mark}")
                    st.text(p["text"])
            if a.follow_up:
                st.caption(f"Search text used (follow-up): {a.retrieval_query}")


def render_ask(ds: Datasets, settings: Settings, api_key: str | None) -> None:
    st.session_state.setdefault("answers", [])
    st.session_state.setdefault("session_id", uuid.uuid4().hex[:8])
    answers: list[Answer] = st.session_state["answers"]

    index = _index_for(settings)
    top = st.columns([3, 1], vertical_alignment="center")
    with top[0]:
        if index is not None:
            st.caption(f":material/menu_book: Document index: {index.info['passages']} passages, "
                       f"`{index.info['embedding_model']}`, {index.info['chunk_words']}-word passages. "
                       ":material/functions: Data: 7 functions over the six datasets.")
        else:
            st.warning("The document index has not been built yet, so questions about the documents cannot be "
                       "answered. Build it once (about 9 requests), or run `python scripts/build_index.py`.",
                       icon=":material/warning:")
            if api_key and st.button("Build the document index now", icon=":material/build:"):
                bar = st.progress(0.0, text="Embedding passages...")
                try:
                    build_index(Gemini(api_key, settings), settings,
                                progress=lambda msg: bar.progress(min(1.0, int(msg.split()[0]) / int(msg.split()[2])), text=msg))
                    st.rerun()
                except Exception as err:
                    st.error(f"{failure_tag(err)}: {err}")
    with top[1]:
        if st.button("New conversation", icon=":material/add_comment:", width="stretch", disabled=not answers):
            st.session_state["answers"] = []
            st.rerun()

    if not api_key:
        st.info("Add a Gemini API key (sidebar or .env file) to ask questions.", icon=":material/key:")
        return

    examples = st.empty()          # shown only before the first question
    if not answers:
        with examples.container(), card("ask_intro"):
            card_title("tips_and_updates", "What you can ask",
                       sub="Where businesses are, what an area is like (residents, land use, area), and which "
                           "registration and licensing rules apply. Every figure is computed in code and every rule "
                           "is cited to its passage.")
            st.caption("Try an example:")
            cols = st.columns(len(EXAMPLES))
            for c, ex in zip(cols, EXAMPLES):
                if c.button(ex, icon=":material/arrow_outward:", width="stretch"):
                    st.session_state["pending_question"] = ex

    conversation = st.container()
    typed = st.chat_input("Ask a question about businesses, areas or licensing rules")
    question = typed or st.session_state.pop("pending_question", None)

    if question:
        examples.empty()
        assistant = Assistant(Gemini(api_key, settings), settings, tools=get_tools(ds), index=index)
        with conversation:
            with st.spinner("Searching the documents, computing figures and writing the answer..."):
                ans = assistant.ask(question, answers)
        answers.append(ans)
        query_log.append(ans.log_record(session_id=st.session_state["session_id"], run="app"))
        st.rerun()                  # draw the page again with the new answer (and 'New conversation' enabled)

    with conversation:
        for i, a in enumerate(answers, start=1):
            render_answer(a, i)
    if answers:
        st.caption(f":material/info: Answers start with “{REFUSAL}” when the sources cannot answer. Questions in this "
                   f"conversation can refer to the previous {settings.history_turns} questions and answers.")
