"""Tests for F1 (data loading and preparation).

Run from the repository folder:  python -m pytest -q
These tests use only the data files. They do NOT use any test-set question
(held-out questions must never be used before the final evaluation).
"""
import pandas as pd
import pytest

from app.config import GOVERNORATES
from app.data_prep import load_all


@pytest.fixture(scope="module")
def ds():
    return load_all()


# ---------------------------------------------------------------- sizes (match the proposal)
def test_row_counts(ds):
    assert ds.row_counts() == {"businesses": 3811, "population": 320, "land_use": 1120, "area": 79}
    assert sum(ds.row_counts().values()) == 5330


def test_business_datasets(ds):
    counts = ds.businesses["source_code"].value_counts().to_dict()
    assert counts == {"RC": 2395, "OS": 1024, "SH": 392}


# ---------------------------------------------------------------- category labels
def test_shared_dimension_governorate(ds):
    # The common dimension must use the same four labels in every dataset.
    assert set(ds.businesses["governorate"]) == set(GOVERNORATES)
    assert set(ds.land_use["governorate"]) == set(GOVERNORATES)
    assert set(ds.population.loc[ds.population["current_governorate"], "governorate"]) == set(GOVERNORATES)
    assert set(ds.area.loc[ds.area["current_governorate"], "governorate"]) == set(GOVERNORATES)


def test_old_scheme_flagged_not_dropped(ds):
    p = ds.population
    old = p.loc[~p["current_governorate"]]
    assert set(old["governorate"]) == {"Central", "Not Stated"}
    assert set(old["year"]) <= {2010, 2011}
    assert "Central" in set(ds.area["governorate"])  # area: Central until 2013, flagged


def test_population_estimate_types(ds):
    p = ds.population
    assert set(p["estimate"]) == {"mid-year", "year-end"}
    assert set(p.loc[p["estimate"] == "year-end", "year"]) == {2022, 2023, 2024}
    assert p["estimate"].notna().all()


# ---------------------------------------------------------------- units
def test_block_is_integer_code(ds):
    assert pd.api.types.is_integer_dtype(ds.businesses["block"])
    assert 301 in set(ds.businesses["block"])


def test_land_use_units(ds):
    lu = ds.land_use
    ok = lu["area_m2"].notna()
    assert (lu.loc[ok, "area_km2"] * 1e6 - lu.loc[ok, "area_m2"]).abs().max() < 1e-6
    assert (lu.loc[ok, "area_m2"] >= 0).all()


# ---------------------------------------------------------------- missing values
def test_land_use_missing_is_nan_not_zero(ds):
    lu = ds.land_use
    missing = lu[lu["area_m2"].isna()]
    assert len(missing) == 1
    row = missing.iloc[0]
    assert (row["governorate"], row["land_use_category"], row["period"]) == ("Southern", "Other", "2025-09")
    # Real zeros ("0.00 m2") stay 0: Green Belt land exists only in Capital.
    zeros = lu[lu["area_m2"] == 0]
    assert set(zeros["land_use_category"]) == {"Green Belt"}
    assert "Capital" not in set(zeros["governorate"])


def test_area_total_rows_dropped(ds):
    assert "Total" not in set(ds.area["governorate"])
    assert len(ds.area) == 79


def test_no_blank_business_fields(ds):
    assert not (ds.businesses[["name", "subtype", "governorate"]] == "").any().any()


# ---------------------------------------------------------------- duplicates
def test_exact_duplicate_flagged_once(ds):
    dup = ds.businesses[ds.businesses["exact_duplicate"]]
    assert len(dup) == 1
    r = dup.iloc[0]
    assert (r["name"], r["block"], r["source_row"]) == ("BASKIN ROBBINS", 346, 700)


# ---------------------------------------------------------------- documentation
def test_prep_log_covers_brief_topics(ds):
    topics = set(ds.log.to_frame()["topic"])
    assert {"missing values", "units", "labels"} <= topics  # the three topics the brief names
