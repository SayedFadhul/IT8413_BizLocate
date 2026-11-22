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
from app.palette import CHART_COLOURS, GOV_COLOURS, GROUP_COLOURS, INK_MUTED, NAVY, OTHER_GREY
from app.ui_style import card, card_title, selection_pills

# Colours follow the thing they show, never its rank: a governorate or business group keeps its colour
# in every chart and when others are filtered out (colours from app/ui_style.py, checked for colour blindness).
LAND_SLOTS = CHART_COLOURS[4:8]          # land-use categories (not the governorate colours: governorates are on the x-axis)
LAND_SHOWN = 4                           # the largest categories are drawn; the rest are 'Other categories'


def _scale(names: list[str], colours: dict[str, str]) -> alt.Scale:
    """Colour scale for the names present, each in its own fixed colour."""
    return alt.Scale(domain=list(names), range=[colours.get(n, OTHER_GREY) for n in names])


def _land_colours(shown: list[str], ranking: list[str]) -> dict[str, str]:
    """Fixed colours for the largest land-use categories of the whole dataset; a smaller category that is
    shown because of the filters takes a colour that is free."""
    fixed = {c: LAND_SLOTS[i] for i, c in enumerate(ranking[:len(LAND_SLOTS)])}
    out = {c: fixed[c] for c in shown if c in fixed}
    spare = [c for c in LAND_SLOTS if c not in out.values()]
    for c in shown:
        if c not in out:
            out[c] = spare.pop(0) if spare else OTHER_GREY
    return out


def _finish(chart: alt.TopLevelMixin, height: int, right_padding: int = 0) -> alt.TopLevelMixin:
    """Same quiet axes, grid and legend in every chart, on the card background."""
    return (chart.properties(height=height, padding={"left": 2, "top": 6, "right": 6 + right_padding, "bottom": 2})
            .configure(background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=INK_MUTED, titleColor=INK_MUTED, gridColor="#E9DFCF", domainColor="#CDBFA6",
                            tickColor="#CDBFA6", labelFontSize=11, titleFontSize=11, titleFontWeight=600)
            .configure_legend(labelColor=NAVY, titleColor=INK_MUTED, labelFontSize=11, titleFontSize=11,
                              symbolType="circle", symbolSize=90))


# ------------------------------------------------------------------ F2: sidebar filters
def _reset_filters() -> None:
    """'Reset filters' button (runs before the page is redrawn).

    Every filter control's key ends with a reset number. Adding 1 to it makes each control a new one, so it
    starts again from its default value both on the server and on screen. (Deleting the old keys instead
    reset only the server side: the controls on screen kept the removed values, and those came back on
    the next click.)"""
    st.session_state["filters_reset"] = st.session_state.get("filters_reset", 0) + 1


def _differs(key: str, default) -> bool:
    """True when the control with this key holds something other than its default (that filter is in use)."""
    if key not in st.session_state:
        return False
    value = st.session_state[key]
    return tuple(value) != tuple(default) if isinstance(default, tuple) else set(value) != set(default)


def _section(name: str, in_use: bool) -> str:
    return f"{name} · filtered" if in_use else name


def sidebar_filters(options: FilterOptions) -> Selection:
    """Draw the filter controls in the sidebar and return the current Selection.

    Governorates (used by every dataset) stay in view; the other filters are in three sections that open and
    close (Businesses, Population, Land use), so the sidebar stays short. A section's title says 'filtered'
    when one of its filters is in use."""
    d = default_selection(options)
    n = st.session_state.setdefault("filters_reset", 0)
    st.sidebar.header(":material/filter_alt: Filters")
    st.sidebar.button("Reset filters", icon=":material/restart_alt:", width="stretch", key="reset_filters",
                      on_click=_reset_filters, help="Select everything again.")
    govs = st.sidebar.multiselect("Governorates", GOVERNORATES, default=d.governorates, key=f"f_gov_{n}")

    groups_now = st.session_state.get(f"f_groups_{n}", d.business_groups)
    in_use = {
        "Businesses": _differs(f"f_groups_{n}", d.business_groups)
                      or _differs(f"f_types_{n}_{'|'.join(groups_now)}", options.types_for(groups_now)),
        "Population": _differs(f"f_years_{n}", (d.year_from, d.year_to)) or _differs(f"f_nat_{n}", d.nationalities)
                      or _differs(f"f_sex_{n}", d.sexes),
        "Land use": _differs(f"f_months_{n}", (d.land_period_from, d.land_period_to))
                    or _differs(f"f_cats_{n}", d.land_categories),
    }
    with st.sidebar.expander(_section("Businesses", in_use["Businesses"]), icon=":material/storefront:",
                             key="fx_businesses"):
        groups = st.multiselect("Business groups", options.business_groups,
                                default=d.business_groups, key=f"f_groups_{n}")
        type_options = options.types_for(groups)
        # The key also holds the chosen groups, so the type list starts again from all types when the groups change.
        types = st.multiselect("Business types", type_options, default=type_options,
                               key=f"f_types_{n}_{'|'.join(groups)}",
                               help="The list follows the business groups chosen above.")
    with st.sidebar.expander(_section("Population", in_use["Population"]), icon=":material/groups:",
                             key="fx_population"):
        y_from, y_to = st.select_slider("Population years (mid-year estimates)", options=options.years,
                                        value=(d.year_from, d.year_to), key=f"f_years_{n}")
        nats = st.multiselect("Nationality", options.nationalities, default=d.nationalities, key=f"f_nat_{n}")
        sexes = st.multiselect("Sex", options.sexes, default=d.sexes, key=f"f_sex_{n}")
    with st.sidebar.expander(_section("Land use", in_use["Land use"]), icon=":material/landscape:",
                             key="fx_land_use"):
        p_from, p_to = st.select_slider("Land-use months", options=options.land_periods,
                                        value=(d.land_period_from, d.land_period_to), key=f"f_months_{n}")
        cats = st.multiselect("Land-use categories", options.land_categories,
                              default=d.land_categories, key=f"f_cats_{n}")
    return Selection(governorates=govs, business_groups=groups, business_types=types,
                     year_from=int(y_from), year_to=int(y_to), nationalities=nats, sexes=sexes,
                     land_period_from=p_from, land_period_to=p_to, land_categories=cats)


# ------------------------------------------------------------------ helpers
def _numbers(df: pd.DataFrame, label: str = "Show the numbers") -> None:
    with st.expander(label, icon=":material/table_view:"):
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

    selection_pills(sel.describe(options))
    if b_f.empty and p_f.empty and lu_f.empty:
        st.warning("The filters leave no data. Change or reset the filters in the sidebar.",
                   icon=":material/filter_alt_off:")
        return

    # -------- summary figures for the current selection
    s = dash.summary_figures(b_f, p_f, lu_f, a_f)
    c = st.columns(5)
    c[0].metric(":material/storefront: Businesses", _fmt(s.businesses),
                help=f"Registrations listed at the last portal update ({LISTINGS_UPDATED}); some may have closed.")
    like_for_like = s.residents_first_year is not None and s.residents_first_year >= 2012
    delta = (f"{s.residents_change_pct:+.1f}% since {s.residents_first_year}"
             if s.residents_change_pct is not None and like_for_like else None)
    c[1].metric(f":material/groups: Residents {s.residents_year or ''}", _fmt(s.residents), delta=delta,
                delta_color="off",
                help="Mid-year estimate. No change is shown from 2010-2011: those years exclude the former "
                     "Central Governorate, so they cannot be compared with later years.")
    c[2].metric(":material/person_pin_circle: Residents per business", _fmt(s.residents_per_business),
                help="Residents in the latest selected year ÷ selected businesses.")
    c[3].metric(":material/grid_view: Businesses per km²", _fmt(s.businesses_per_km2, 1),
                help=f"Land area of the selected governorates in {s.area_year}: {_fmt(s.area_km2, 2)} km² (area dataset).")
    c[4].metric(f":material/landscape: Land use, {s.land_period or '–'}", f"{_fmt(s.land_km2, 1)} km²",
                help="Land in the selected land-use categories in the latest selected month.")
    if s.land_missing:
        miss = dash.missing_land_records(lu_f)
        st.warning(f"{s.land_missing} land-use value(s) in the selection are missing in the source (not zero) and are "
                   "left out of the sums: " + "; ".join(f"{r.governorate} {r.land_use_category} {r.period}"
                                                        for r in miss.itertuples()), icon=":material/info:")

    # -------- row 1: comparison between categories
    left, right = st.columns(2, gap="medium")
    with left, card("businesses"):
        card_title("bar_chart", "Businesses by governorate", "Comparison", "Registered businesses in each business group")
        t = dash.businesses_by_governorate(b_f)
        if t.empty:
            st.info("No businesses match the filters.", icon=":material/search_off:")
        else:
            long = t.reset_index().melt("governorate", var_name="group", value_name="businesses")
            groups = list(t.columns)
            chart = alt.Chart(long).mark_bar(cornerRadiusEnd=4, stroke="#FBF7F0", strokeWidth=2).encode(
                x=alt.X("governorate:N", sort=GOVERNORATES, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("businesses:Q", title="Businesses", stack="zero"),
                color=alt.Color("group:N", title=None, scale=_scale(groups, GROUP_COLOURS),
                                legend=alt.Legend(orient="bottom")),
                order=alt.Order("group:N"),
                tooltip=["governorate", "group", alt.Tooltip("businesses:Q", format=",")],
            )
            st.altair_chart(_finish(chart, 300), width="stretch")
            _numbers(t.reset_index())
    with right, card("per_business"):
        card_title("person_pin_circle", "Residents per business", "Comparison",
                   "Residents for each selected business (a higher number can mean fewer competitors)")
        t = dash.residents_per_business(b_f, p_f)
        if t.empty or t["businesses"].sum() == 0:
            st.info("Select at least one business type and one population group.", icon=":material/search_off:")
        else:
            chart = alt.Chart(t).mark_bar(cornerRadiusEnd=4, size=46).encode(
                x=alt.X("governorate:N", sort=GOVERNORATES, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("residents_per_business:Q", title=f"Residents per business ({int(t['year'].iloc[0])})"),
                color=alt.Color("governorate:N", scale=_scale(list(t["governorate"]), GOV_COLOURS), legend=None),
                tooltip=["governorate", alt.Tooltip("residents:Q", format=","), alt.Tooltip("businesses:Q", format=","),
                         alt.Tooltip("residents_per_business:Q", format=",.1f", title="residents per business")],
            )
            st.altair_chart(_finish(chart, 300), width="stretch")
            _numbers(t)

    # -------- row 2: change over time + composition
    left, right = st.columns(2, gap="medium")
    with left, card("residents"):
        card_title("show_chart", "Residents over time", "Change over time", "Mid-year population estimates")
        t = dash.population_trend(p_f)
        if t.empty:
            st.info("No population rows match the filters.", icon=":material/search_off:")
        else:
            long = t.reset_index().melt("year", var_name="governorate", value_name="residents")
            govs = list(t.columns)
            base = alt.Chart(long).encode(
                x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("residents:Q", title="Residents", scale=alt.Scale(zero=False)),
                color=alt.Color("governorate:N", scale=_scale(govs, GOV_COLOURS),
                                legend=alt.Legend(orient="bottom", title=None)),
                tooltip=["year", "governorate", alt.Tooltip("residents:Q", format=",")],
            )
            # Name each line at its last point; names that would overlap are moved apart a little.
            last = long[long["year"] == long["year"].max()].sort_values("residents").copy()
            gap = (long["residents"].max() - long["residents"].min()) * 0.07
            ys: list[float] = []
            for v in last["residents"]:
                ys.append(v if not ys else max(v, ys[-1] + gap))
            last["label_y"] = ys
            names = alt.Chart(last).mark_text(align="left", dx=8, fontSize=11, fontWeight=600, color=NAVY).encode(
                x="year:O", y="label_y:Q", text="governorate:N")
            chart = base.mark_line(strokeWidth=2) + base.mark_point(size=64, filled=True) + names
            st.altair_chart(_finish(chart, 300, right_padding=70), width="stretch")
            if t.index.min() < 2012:
                st.caption("2010–2011 exclude the former Central Governorate, so the jump in 2012 is a boundary "
                           "change, not growth.")
            _numbers(t.reset_index())
    with right, card("mix"):
        card_title("donut_small", "Mix of business types", "Composition",
                   "The most common business types in the selection")
        t = dash.business_type_mix(b_f)
        if t.empty:
            st.info("No businesses match the filters.", icon=":material/search_off:")
        else:
            chart = alt.Chart(t).mark_bar(cornerRadiusEnd=4, color=CHART_COLOURS[0]).encode(
                y=alt.Y("business_type:N", sort=None, title=None, axis=alt.Axis(labelLimit=220, labelOverlap=False)),
                x=alt.X("businesses:Q", title="Businesses"),
                tooltip=["business_type", alt.Tooltip("businesses:Q", format=","),
                         alt.Tooltip("share_pct:Q", format=".1f", title="share %")],
            )
            st.altair_chart(_finish(chart, max(300, 24 * len(t))), width="stretch")
            _numbers(t)

    # -------- row 3: land use (composition and change over time)
    left, right = st.columns(2, gap="medium")
    latest_all = ds.land_use[ds.land_use["period"] == ds.land_use["period"].max()]
    ranking = latest_all.groupby("land_use_category")["area_km2"].sum().sort_values(ascending=False).index.tolist()
    mix = dash.land_use_mix(lu_f)
    shown = (mix.groupby("land_use_category")["area_km2"].sum().sort_values(ascending=False)
             .index[:LAND_SHOWN].tolist() if not mix.empty else [])
    land_colours = _land_colours(shown, ranking)
    with left, card("land_mix"):
        card_title("landscape", f"Land use by category, {mix['period'].iloc[0] if not mix.empty else ''}",
                   "Composition", f"The {LAND_SHOWN} largest categories in the selection; the rest are grouped")
        if mix.empty:
            st.info("No land-use rows match the filters.", icon=":material/search_off:")
        else:
            m = mix.copy()
            m["category"] = m["land_use_category"].where(m["land_use_category"].isin(shown), "Other categories")
            m = m.groupby(["governorate", "category"], as_index=False)["area_km2"].sum(min_count=1)
            domain = shown + (["Other categories"] if (m["category"] == "Other categories").any() else [])
            chart = alt.Chart(m).mark_bar(stroke="#FBF7F0", strokeWidth=2).encode(
                x=alt.X("governorate:N", sort=GOVERNORATES, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("area_km2:Q", title="km²", stack="zero"),
                color=alt.Color("category:N", scale=_scale(domain, land_colours),
                                legend=alt.Legend(orient="bottom", title=None, columns=2, labelLimit=260)),
                order=alt.Order("category:N"),
                tooltip=["governorate", "category", alt.Tooltip("area_km2:Q", format=",.2f", title="km²")],
            )
            st.altair_chart(_finish(chart, 320), width="stretch")
            _numbers(mix.drop(columns="period"))
    with right, card("land_trend"):
        card_title("timeline", "Land use over time", "Change over time", "The same categories, month by month")
        t = dash.land_use_trend(lu_f)
        if t.empty:
            st.info("No land-use rows match the filters.", icon=":material/search_off:")
        else:
            cats = [c for c in shown if c in t.columns] or list(t.columns[:LAND_SHOWN])
            long = t[cats].reset_index().melt("period", var_name="category", value_name="area_km2")
            base = alt.Chart(long).encode(
                x=alt.X("period:O", title=None),
                y=alt.Y("area_km2:Q", title="km²", scale=alt.Scale(zero=False)),
                color=alt.Color("category:N", scale=_scale(cats, _land_colours(cats, ranking)),
                                legend=alt.Legend(orient="bottom", title=None, columns=2, labelLimit=260)),
                tooltip=["period", "category", alt.Tooltip("area_km2:Q", format=",.2f", title="km²")],
            )
            chart = base.mark_line(strokeWidth=2) + base.mark_point(size=64, filled=True)
            st.altair_chart(_finish(chart, 320), width="stretch")
            _numbers(t.reset_index())

    # -------- row 4: where the selected businesses are
    left, right = st.columns([3, 2], gap="medium")
    with left, card("map"):
        card_title("map", "Where the selected businesses are", "Map")
        pts = dash.map_points(b_f)
        if pts.empty:
            st.info("No businesses match the filters.", icon=":material/search_off:")
        else:
            st.map(pts, latitude="lat", longitude="lon", size=20, color="#E8594ACC", height=380)
    with right, card("blocks"):
        card_title("format_list_numbered", "Blocks with the most selected businesses", "Ranking")
        st.dataframe(dash.top_blocks(b_f), hide_index=True, height=380)
    st.caption(f"Business lists are registrations at the last portal update ({LISTINGS_UPDATED}); some businesses "
               "may have closed since. Population is published by governorate only (not by block).")
