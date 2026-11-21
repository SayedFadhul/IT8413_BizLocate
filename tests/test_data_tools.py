"""Tests for F4: every figure a function returns is re-computed here independently with pandas.
No test-set question is used."""
import pytest

from app.data_prep import load_all
from app.data_tools import DataTools


@pytest.fixture(scope="module")
def ds():
    return load_all()


@pytest.fixture(scope="module")
def tools(ds):
    return DataTools(ds)


def test_count_and_share(ds, tools):
    out = tools.call("count_businesses", {"business_types": ["JEWELERS"], "governorates": ["Capital"]})
    b = ds.businesses
    jew = b[b["subtype"] == "JEWELERS"]
    n = (jew["governorate"] == "Capital").sum()
    assert out["result"]["count"] == n
    assert out["result"]["bahrain_total_same_types"] == len(jew)
    assert out["result"]["share_of_bahrain_pct"] == round(n / len(jew) * 100, 1)
    assert out["source"].startswith("[OS]")


def test_count_group_by_governorate_lists_all_four_with_ranks(tools):
    out = tools.call("count_businesses", {"business_types": ["IRISH RESTAURANTS"], "group_by": "governorate"})
    assert [r["rank"] for r in out["rows"]] == [1, 2, 3, 4]
    assert sum(r["count"] for r in out["rows"]) == out["result"]["count"]


def test_block_count(ds, tools):
    block = int(ds.businesses["block"].iloc[0])
    out = tools.call("count_businesses", {"block": block})
    assert out["result"]["count"] == (ds.businesses["block"] == block).sum()
    assert out["result"]["block_has_any_listed_business"] is True


def test_find_business_by_part_of_name(ds, tools):
    name = ds.businesses["name"].iloc[100]
    out = tools.call("find_businesses", {"name": name.title()})
    assert out["result"]["matches"] >= 1
    assert any(r["name"] == name for r in out["rows"])
    assert tools.call("find_businesses", {"name": "zzzz no such shop"})["result"]["matches"] == 0


def test_population_total_and_shares(ds, tools):
    out = tools.call("get_population", {"governorates": ["Southern"], "year": 2020, "group_by": ["sex"]})
    p = ds.population
    sub = p[(p["governorate"] == "Southern") & (p["period"] == "2020-06")]
    assert out["result"]["total"] == sub["population"].sum()
    assert sum(r["population"] for r in out["rows"]) == sub["population"].sum()
    assert sum(r["share_pct"] for r in out["rows"]) == pytest.approx(100, abs=0.2)


def test_population_range_finds_the_years_it_fell(ds, tools):
    out = tools.call("get_population", {"year_from": 2014, "year_to": 2022})
    p = ds.population
    tot = p[(p["estimate"] == "mid-year") & p["year"].between(2014, 2022)].groupby("year")["population"].sum()
    falls = [f"{a}->{b}" for a, b in zip(tot.index[:-1], tot.index[1:]) if tot[b] < tot[a]]
    assert out["result"]["years_when_total_fell"] == (falls or "none")
    assert out["result"]["first_year_total"] == tot.iloc[0]


def test_year_end_is_separate(tools):
    out = tools.call("get_population", {"year": 2023, "estimate": "year-end"})
    assert out["result"]["estimate"] == "year-end"
    assert "error" in tools.call("get_population", {"year": 2015, "estimate": "year-end"})


def test_land_use_missing_value_is_not_zero(tools):
    out = tools.call("get_land_use", {"governorates": ["Southern"], "categories": ["Other"], "period": "2025-09"})
    assert out["result"]["total_km2"] is None
    assert out["result"]["records_missing_in_source"]


def test_land_use_shares(ds, tools):
    out = tools.call("get_land_use", {"governorates": ["Capital"], "period": "2025-03", "group_by": ["category"]})
    lu = ds.land_use
    sub = lu[(lu["governorate"] == "Capital") & (lu["period"] == "2025-03")]
    assert out["result"]["total_km2"] == round(sub["area_km2"].sum(), 2)
    assert sum(r["share_of_all_land_use_pct"] for r in out["rows"]) == pytest.approx(100, abs=0.5)


def test_area_and_boundary_note(tools):
    out = tools.call("get_area", {"year_from": 2012, "year_to": 2015})
    assert any(r["governorate"] == "Central" for r in out["rows"])
    assert any("2014" in n for n in out["notes"])


def test_compare_governorates_matches_manual_ratio(ds, tools):
    out = tools.call("compare_governorates", {"measure": "residents_per_business", "business_types": ["FURNITURE SHOPS"]})
    b, p = ds.businesses, ds.population
    bus = b[b["subtype"] == "FURNITURE SHOPS"].groupby("governorate").size()
    res = p[p["period"] == "2025-06"].groupby("governorate")["population"].sum()
    for row in out["rows"]:
        g = row["governorate"]
        assert row["value"] == round(res[g] / bus[g])
    values = {r["governorate"]: r["value"] for r in out["rows"]}
    assert out["result"]["highest"] == max(values, key=values.get)
    assert out["result"]["lowest"] == min(values, key=values.get)


def test_area_profile_runs(tools):
    out = tools.call("area_profile", {"governorate": "Northern"})
    assert out["result"]["businesses_total"] > 0 and "notes" in out


def test_wrong_input_returns_an_error_for_the_model(tools):
    assert "error" in tools.call("count_businesses", {"business_types": ["COFFEE"]})
    assert "error" in tools.call("count_businesses", {"bad_argument": 1})
    assert "error" in tools.call("no_such_function", {})
    assert "error" in tools.call("get_land_use", {"period": "2030-01"})


def test_declarations_cover_every_function(tools):
    names = {d.name for d in tools.declarations()}
    assert names == set(tools.functions)
