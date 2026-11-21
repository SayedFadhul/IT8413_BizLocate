"""F2-F3 on screen: the sidebar filters and the dashboard tab (lead: Mohamed Alradhi).

The tables come from app/dashboard.py (pandas only). This file only draws them:
Altair charts with a hover tooltip, a 'Show the numbers' table under each chart,
and the same filtered data for every chart, figure and the map.
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from app import dashboard as dash
from app.config import GOVERNORATES, LISTINGS_UPDATED
from app.data_prep import Datasets
from app.filters import (FilterOptions, Selection, default_selection, filter_area, filter_businesses,
                         filter_land_use, filter_population)

# Categorical colours: the first slots of a colour-blind-checked palette, in a fixed order,
# so a governorate keeps its colour in every chart and when others are filtered out.
LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9"]
OTHER_GREY = "#8c8a85"


def _palette() -> list[str]:
    try:
        return DARK if st.context.theme.type == "dark" else LIGHT
    except Exception:
        return LIGHT


def _gov_scale() -> alt.Scale:
    return alt.Scale(domain=GOVERNORATES, range=_palette()[:4])


# ------------------------------------------------------------------ F2: sidebar filters
def sidebar_filters(options: FilterOptions) -> Selection:
    """Draw the filter controls in the sidebar and return the current Selection."""
    d = default_selection(options)
    st.sidebar.header("Filters")
    if st.sidebar.button("Reset filters", width="stretch"):
        for k in list(st.session_state):
            if k.startswith("f_"):
                del st.session_state[k]

    govs = st.sidebar.multiselect("Governorates", GOVERNORATES, default=d.governorates, key="f_gov")
    groups = st.sidebar.multiselect("Business groups", options.business_groups,
                                    default=d.business_groups, key="f_groups")
    type_options = options.types_for(groups)
    types = st.sidebar.multiselect("Business types", type_options, default=type_options, key=f"f_types_{'|'.join(groups)}",
                                   help="The list follows the business groups chosen above.")
    y_from, y_to = st.sidebar.select_slider("Population years (mid-year estimates)", options=options.years,
                                            value=(d.year_from, d.year_to), key="f_years")
    nats = st.sidebar.multiselect("Nationality", options.nationalities, default=d.nationalities, key="f_nat")
    sexes = st.sidebar.multiselect("Sex", options.sexes, default=d.sexes, key="f_sex")
    p_from, p_to = st.sidebar.select_slider("Land-use months", options=options.land_periods,
                                            value=(d.land_period_from, d.land_period_to), key="f_months")
    cats = st.sidebar.multiselect("Land-use categories", options.land_categories,
                                  default=d.land_categories, key="f_cats")
    return Selection(governorates=govs, business_groups=groups, business_types=types,
                     year_from=int(y_from), year_to=int(y_to), nationalities=nats, sexes=sexes,
                     land_period_from=p_from, land_period_to=p_to, land_categories=cats)


# ------------------------------------------------------------------ helpers
def _numbers(df: pd.DataFrame, label: str = "Show the numbers") -> None:
    with st.expander(label):
        st.dataframe(df, hide_index=True)


def _fmt(x, digits: int = 0) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "–"
    return f"{x:,.{digits}f}"


# ------------------------------------------------------------------ F3: the dashboard tab
def render_dashboard(ds: Datasets, sel: Selection, options: FilterOptions) -> None:
    b_f = filter_businesses(ds.businesses, sel)
    p_f = filter_population(ds.population, sel)
    lu_f = filter_land_use(ds.land_use, sel)
    a_f = filter_area(ds.area, sel)

    st.caption(" · ".join(sel.describe(options)))
    if b_f.empty and p_f.empty and lu_f.empty:
        st.warning("The filters leave no data. Change or reset the filters in the sidebar.")
        return

    # -------- summary figures for the current selection
    s = dash.summary_figures(b_f, p_f, lu_f, a_f)
    c = st.columns(5)
    c[0].metric("Businesses", _fmt(s.businesses), help=f"Registrations listed at the last portal update ({LISTINGS_UPDATED}); some may have closed.")
    like_for_like = s.residents_first_year is not None and s.residents_first_year >= 2012
    delta = (f"{s.residents_change_pct:+.1f}% since {s.residents_first_year}"
             if s.residents_change_pct is not None and like_for_like else None)
    c[1].metric(f"Residents {s.residents_year or ''}", _fmt(s.residents), delta=delta, delta_color="off",
                help="Mid-year estimate. No change is shown from 2010-2011: those years exclude the former "
                     "Central Governorate, so they cannot be compared with later years.")
    c[2].metric("Residents per business", _fmt(s.residents_per_business),
                help="Residents in the latest selected year ÷ selected businesses.")
    c[3].metric("Businesses per km²", _fmt(s.businesses_per_km2, 1),
                help=f"Land area of the selected governorates in {s.area_year}: {_fmt(s.area_km2, 2)} km² (area dataset).")
    c[4].metric(f"Land use, {s.land_period or '–'}", f"{_fmt(s.land_km2, 1)} km²",
                help="Land in the selected land-use categories in the latest selected month.")
    if s.land_missing:
        miss = dash.missing_land_records(lu_f)
        st.warning(f"{s.land_missing} land-use value(s) in the selection are missing in the source (not zero) and are "
                   "left out of the sums: " + "; ".join(f"{r.governorate} {r.land_use_category} {r.period}"
                                                        for r in miss.itertuples()))

    # -------- row 1: comparison between categories
    left, right = st.columns(2)
    with left:
        st.markdown("**Businesses by governorate** (comparison)")
        t = dash.businesses_by_governorate(b_f)
        if t.empty:
            st.info("No businesses match the filters.")
        else:
            long = t.reset_index().melt("governorate", var_name="group", value_name="businesses")
            groups = list(t.columns)
            chart = alt.Chart(long).mark_bar(cornerRadiusEnd=4, stroke=None).encode(
                x=alt.X("governorate:N", sort=GOVERNORATES, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("businesses:Q", title="Businesses", stack="zero"),
                color=alt.Color("group:N", title="Business group",
                                scale=alt.Scale(domain=groups, range=_palette()[4:4 + len(groups)] if len(groups) <= 3 else None),
                                legend=alt.Legend(orient="bottom")),
                tooltip=["governorate", "group", alt.Tooltip("businesses:Q", format=",")],
            ).properties(height=300)
            st.altair_chart(chart, width="stretch")
            _numbers(t.reset_index())
    with right:
        st.markdown("**Residents per business** (comparison)")
        t = dash.residents_per_business(b_f, p_f)
        if t.empty or t["businesses"].sum() == 0:
            st.info("Select at least one business type and one population group.")
        else:
            chart = alt.Chart(t).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X("governorate:N", sort=GOVERNORATES, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("residents_per_business:Q", title=f"Residents per business ({int(t['year'].iloc[0])})"),
                color=alt.Color("governorate:N", scale=_gov_scale(), legend=None),
                tooltip=["governorate", alt.Tooltip("residents:Q", format=","), alt.Tooltip("businesses:Q", format=","),
                         alt.Tooltip("residents_per_business:Q", format=",.1f", title="residents per business")],
            ).properties(height=300)
            st.altair_chart(chart, width="stretch")
            _numbers(t)

    # -------- row 2: change over time + composition
    left, right = st.columns(2)
    with left:
        st.markdown("**Residents over time** (change over time, mid-year estimates)")
        t = dash.population_trend(p_f)
        if t.empty:
            st.info("No population rows match the filters.")
        else:
            long = t.reset_index().melt("year", var_name="governorate", value_name="residents")
            base = alt.Chart(long).encode(
                x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("residents:Q", title="Residents", scale=alt.Scale(zero=False)),
                color=alt.Color("governorate:N", scale=_gov_scale(), legend=alt.Legend(orient="bottom", title=None)),
                tooltip=["year", "governorate", alt.Tooltip("residents:Q", format=",")],
            )
            chart = base.mark_line(strokeWidth=2) + base.mark_point(size=40, filled=True)
            st.altair_chart(chart.properties(height=300), width="stretch")
            if t.index.min() < 2012:
                st.caption("2010–2011 exclude the former Central Governorate, so the jump in 2012 is a boundary "
                           "change, not growth.")
            _numbers(t.reset_index())
    with right:
        st.markdown("**Mix of business types** (composition)")
        t = dash.business_type_mix(b_f)
        if t.empty:
            st.info("No businesses match the filters.")
        else:
            chart = alt.Chart(t).mark_bar(cornerRadiusEnd=4, color=_palette()[0]).encode(
                y=alt.Y("business_type:N", sort=None, title=None, axis=alt.Axis(labelLimit=220)),
                x=alt.X("businesses:Q", title="Businesses"),
                tooltip=["business_type", alt.Tooltip("businesses:Q", format=","),
                         alt.Tooltip("share_pct:Q", format=".1f", title="share %")],
            ).properties(height=300)
            st.altair_chart(chart, width="stretch")
            _numbers(t)

    # -------- row 3: land use (composition and change over time)
    left, right = st.columns(2)
    mix = dash.land_use_mix(lu_f)
    top_cats = (mix.groupby("land_use_category")["area_km2"].sum().sort_values(ascending=False).index[:6].tolist()
                if not mix.empty else [])
    with left:
        st.markdown(f"**Land use by category, {mix['period'].iloc[0] if not mix.empty else ''}** (composition)")
        if mix.empty:
            st.info("No land-use rows match the filters.")
        else:
            m = mix.copy()
            m["category"] = m["land_use_category"].where(m["land_use_category"].isin(top_cats), "Other categories")
            m = m.groupby(["governorate", "category"], as_index=False)["area_km2"].sum(min_count=1)
            domain = top_cats + (["Other categories"] if (m["category"] == "Other categories").any() else [])
            colours = _palette()[:len(top_cats)] + [OTHER_GREY]
            chart = alt.Chart(m).mark_bar(stroke=None).encode(
                x=alt.X("governorate:N", sort=GOVERNORATES, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("area_km2:Q", title="km²", stack="zero"),
                color=alt.Color("category:N", scale=alt.Scale(domain=domain, range=colours[:len(domain)]),
                                legend=alt.Legend(orient="bottom", title=None, columns=2, labelLimit=260)),
                order=alt.Order("category:N"),
                tooltip=["governorate", "category", alt.Tooltip("area_km2:Q", format=",.2f", title="km²")],
            ).properties(height=320)
            st.altair_chart(chart, width="stretch")
            _numbers(mix.drop(columns="period"))
    with right:
        st.markdown("**Land use over time** (change over time, selected governorates)")
        t = dash.land_use_trend(lu_f)
        if t.empty:
            st.info("No land-use rows match the filters.")
        else:
            cats = [c for c in top_cats if c in t.columns][:4] or list(t.columns[:4])
            long = t[cats].reset_index().melt("period", var_name="category", value_name="area_km2")
            base = alt.Chart(long).encode(
                x=alt.X("period:O", title=None),
                y=alt.Y("area_km2:Q", title="km²", scale=alt.Scale(zero=False)),
                color=alt.Color("category:N", scale=alt.Scale(domain=cats, range=_palette()[:len(cats)]),
                                legend=alt.Legend(orient="bottom", title=None)),
                tooltip=["period", "category", alt.Tooltip("area_km2:Q", format=",.2f", title="km²")],
            )
            chart = base.mark_line(strokeWidth=2) + base.mark_point(size=30, filled=True)
            st.altair_chart(chart.properties(height=320), width="stretch")
            st.caption("The four largest categories in the selection are shown.")
            _numbers(t.reset_index())

    # -------- row 4: where the selected businesses are
    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Where the selected businesses are** (map)")
        pts = dash.map_points(b_f)
        if pts.empty:
            st.info("No businesses match the filters.")
        else:
            st.map(pts, latitude="lat", longitude="lon", size=20, height=380)
    with right:
        st.markdown("**Blocks with the most selected businesses**")
        st.dataframe(dash.top_blocks(b_f), hide_index=True, height=380)
    st.caption(f"Business lists are registrations at the last portal update ({LISTINGS_UPDATED}); some businesses "
               "may have closed since. Population is published by governorate only (not by block).")
