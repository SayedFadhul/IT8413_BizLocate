"""F1 on screen: the 'Data & sources' tab (lead: Ali Haji).

Shows that the datasets are loaded and prepared (with every preparation step), the
sources with their licence, the licence statement the Bahrain Open Government Data
License asks for (clause 3.3), and whether the documents and their search index are ready.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app.config import DATA_EXTRACTED, DOCS_DIR, DOCS_MANIFEST, SOURCES_CSV
from app.data_prep import Datasets
from app.ui_style import card, card_title

LICENCE_STATEMENT = (
    "Datasets provided by the Information & eGovernment Authority (iGA), the Urban Planning and Development "
    "Authority (UPDA) and the Survey and Land Registration Bureau (SLRB) via www.data.gov.bh are governed by the "
    "Bahrain Open Government Data License available at www.nea.gov.bh/Documents/OpenDataLicense.pdf. "
    "To the fullest extent permitted by law, the government is not liable for any damage or loss of any kind "
    "caused directly or indirectly by the use or availability of the datasets or any derived analyses or applications."
)
OUR_WORK_STATEMENT = (
    f"Data extracted on {DATA_EXTRACTED}. All analysis, figures and transformations in this app are G3's own "
    "and are not attributed to iGA or to the publishing entities. Full attribution: ATTRIBUTION.md in the repository."
)


def documents_ready() -> tuple[int, int]:
    """(files present, files expected) in documents/."""
    manifest = json.loads(DOCS_MANIFEST.read_text(encoding="utf-8"))
    return sum((DOCS_DIR / name).exists() for name in manifest), len(manifest)


def render_data_page(ds: Datasets) -> None:
    b, p, lu, a = ds.businesses, ds.population, ds.land_use, ds.area
    st.subheader(":material/database: Datasets loaded and prepared (F1)")
    c = st.columns(4)
    c[0].metric(":material/storefront: Businesses (RC + OS + SH)", f"{len(b):,}")
    c[1].metric(":material/groups: Population rows", f"{len(p):,}")
    c[2].metric(":material/landscape: Land-use rows", f"{len(lu):,}")
    c[3].metric(":material/square_foot: Area rows", f"{len(a):,}")
    st.caption(f"Total working rows: {len(b) + len(p) + len(lu) + len(a):,}. Shared dimension: governorate. "
               f"Data extracted from data.gov.bh on {DATA_EXTRACTED}.")
    left, right = st.columns([2, 3], gap="medium")
    with left, card("data_counts"):
        card_title("table_chart", "Businesses by governorate and group")
        st.dataframe(b.groupby(["governorate", "dataset"]).size().unstack(fill_value=0))
    with right, card("data_steps"):
        card_title("rule", "Preparation steps", sub="Missing values, units and category labels, done in app/data_prep.py")
        st.dataframe(ds.log.to_frame(), hide_index=True)
    with st.expander("Preview the prepared tables", icon=":material/visibility:"):
        tabs = st.tabs(["Businesses", "Population", "Land use", "Area"])
        for t, df in zip(tabs, [b, p, lu, a]):
            t.dataframe(df.head(50), hide_index=True)

    st.subheader(":material/verified: Sources and licence")
    with card("data_sources"):
        card_title("source", "Every source with its publisher, page, retrieval date and version")
        src = pd.read_csv(SOURCES_CSV, encoding="utf-8-sig")
        st.dataframe(src[["code", "type", "title", "publisher", "publishing_page", "retrieved", "version"]],
                     hide_index=True)
    present, total = documents_ready()
    if present == total:
        st.success(f"Document collection ready: {present} of {total} files in documents/.", icon=":material/task_alt:")
    else:
        st.warning(f"Documents: {present} of {total} files found. Run `python scripts/setup_sources.py` to fetch the "
                   "missing ones.", icon=":material/warning:")
    st.info(LICENCE_STATEMENT + "\n\n" + OUR_WORK_STATEMENT, icon=":material/gavel:")
