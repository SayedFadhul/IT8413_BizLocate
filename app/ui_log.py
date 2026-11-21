"""F10 on screen: the 'Query log' tab (lead: Sayed Fadhul Hashem).

Shows every question asked in the app, with the answer, citations, response time, tokens and cost,
and lets the log be downloaded (JSON Lines with every field, or CSV with the main fields).
The settings and the v1/v2 change of each record are stored in the log itself.
"""
from __future__ import annotations

import json

import streamlit as st

from app import query_log
from app.config import Settings, describe_v2_change


def render_log(settings: Settings) -> None:
    records = query_log.read()
    st.markdown(f"Every question asked in the app is saved in `logs/query_log.jsonl` (one JSON record per question). "
                f"Settings now: **{settings.version}**, model `{settings.model}`. Changed in v2: {describe_v2_change()}.")
    if not records:
        st.info("No questions have been asked yet.")
        return
    df = query_log.to_frame(records)
    c = st.columns(5)
    c[0].metric("Questions logged", f"{len(df):,}")
    c[1].metric("Declined (not in sources)", f"{int(df['refused'].sum()):,}")
    c[2].metric("Avg input tokens", f"{df['input_tokens'].mean():,.0f}")
    c[3].metric("Avg latency (s)", f"{df['latency_s'].mean():.1f}")
    c[4].metric("Cost per 1,000 questions ($)", f"{df['cost_usd'].mean() * 1000:.2f}")
    st.dataframe(df.iloc[::-1], hide_index=True)
    c = st.columns(2)
    c[0].download_button("Download the full log (JSON Lines)", "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
                         file_name="query_log.jsonl", mime="application/json", width="stretch")
    c[1].download_button("Download the table (CSV)", df.to_csv(index=False), file_name="query_log.csv",
                         mime="text/csv", width="stretch")
    with st.expander("Show one full record"):
        i = st.number_input("Record number (1 = first)", 1, len(records), len(records))
        st.json(records[int(i) - 1])
