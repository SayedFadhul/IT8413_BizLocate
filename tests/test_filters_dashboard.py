"""Tests for F2 (filters) and F3 (dashboard figures). Expected values are computed independently with pandas."""
import pandas as pd
import pytest

from app import dashboard as dash
from app.data_prep import load_all
from app.filters import (default_selection, filter_area, filter_businesses, filter_land_use, filter_options,
                         filter_population)


@pytest.fixture(scope="module")
def ds():
    return load_all()


@pytest.fixture(scope="module")
def options(ds):
    return filter_options(ds)


def _all(ds, sel):
    return (filter_businesses(ds.businesses, sel), filter_population(ds.population, sel),
            filter_land_use(ds.land_use, sel), filter_area(ds.area, sel))


def test_default_selection_is_everything(ds, options):
    sel = default_selection(options)
    b, p, lu, a = _all(ds, sel)
    assert len(b) == len(ds.businesses)
    assert set(p["estimate"]) == {"mid-year"}            # year-end estimates never mixed in
    assert set(p["governorate"]) == {"Capital", "Muharraq", "Northern", "Southern"}
    assert len(lu) == len(ds.land_use)


def test_filters_change_every_figure(ds, options):
    sel = default_selection(options)
    sel.governorates = ["Muharraq"]
    sel.business_groups = ["Restaurants & Cafes"]
    sel.business_types = options.types_for(sel.business_groups)
    b, p, lu, a = _all(ds, sel)
    s = dash.summary_figures(b, p, lu, a)
    raw = ds.businesses
    assert s.businesses == ((raw["governorate"] == "Muharraq") & (raw["dataset"] == "Restaurants & Cafes")).sum()
    pop = ds.population
    expected = pop[(pop["governorate"] == "Muharraq") & (pop["period"] == "2025-06")]["population"].sum()
    assert s.residents == expected and s.residents_year == 2025
    assert s.residents_per_business == pytest.approx(expected / s.businesses)
    t = dash.businesses_by_governorate(b)
    assert list(t.index) == ["Muharraq"] and list(t.columns) == ["Restaurants & Cafes"]


def test_time_filters(ds, options):
    sel = default_selection(options)
    sel.year_from, sel.year_to = 2015, 2020
    sel.land_period_from = sel.land_period_to = "2025-01"
    b, p, lu, a = _all(ds, sel)
    assert sorted(p["year"].unique()) == list(range(2015, 2021))
    assert set(lu["period"]) == {"2025-01"}
    assert list(dash.population_trend(p).index) == list(range(2015, 2021))


def test_missing_land_value_is_reported_not_zero(ds, options):
    sel = default_selection(options)
    sel.governorates = ["Southern"]
    sel.land_categories = ["Other"]
    sel.land_period_from = sel.land_period_to = "2025-09"
    b, p, lu, a = _all(ds, sel)
    s = dash.summary_figures(b, p, lu, a)
    assert s.land_missing == 1
    assert len(dash.missing_land_records(lu)) == 1


def test_residents_per_business_table(ds, options):
    sel = default_selection(options)
    b, p, lu, a = _all(ds, sel)
    t = dash.residents_per_business(b, p).set_index("governorate")
    for gov, row in t.iterrows():
        assert row["residents_per_business"] == pytest.approx(round(row["residents"] / row["businesses"], 1))


def test_type_mix_and_blocks(ds, options):
    sel = default_selection(options)
    b = filter_businesses(ds.businesses, sel)
    mix = dash.business_type_mix(b, top=5)
    assert mix["businesses"].sum() == len(b) and len(mix) == 6          # 5 types + 'Other types'
    blocks = dash.top_blocks(b, n=3)
    counts = b.groupby("block").size().sort_values(ascending=False)
    assert blocks["businesses"].iloc[0] == counts.iloc[0]


def test_empty_selection_does_not_fail(ds, options):
    sel = default_selection(options)
    sel.governorates = []
    b, p, lu, a = _all(ds, sel)
    s = dash.summary_figures(b, p, lu, a)
    assert s.businesses == 0 and s.residents is None
    assert dash.businesses_by_governorate(b).empty
    assert isinstance(dash.residents_per_business(b, p), pd.DataFrame)
