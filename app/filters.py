"""F2 - Filters (lead: Mohamed Alradhi).

The sidebar builds one `Selection`. Every chart, summary figure and the report use the
same Selection, so every analytical display responds to the active filters (brief F2).

Dimensions that can be filtered:
  - governorate (shared by all six datasets)
  - business group and business type (the three location datasets)
  - time: population years, land-use months
  - population nationality and sex, land-use category

Nothing here calls the model: filtering is plain pandas.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from app.config import GOVERNORATES
from app.data_prep import Datasets


@dataclass
class Selection:
    governorates: list[str]
    business_groups: list[str]          # dataset labels, e.g. "Restaurants & Cafes"
    business_types: list[str]           # subtypes, e.g. "COFFEE SHOPS"
    year_from: int                      # population (mid-year estimates)
    year_to: int
    nationalities: list[str]
    sexes: list[str]
    land_period_from: str               # land use, e.g. "2024-07"
    land_period_to: str
    land_categories: list[str]

    def as_dict(self) -> dict:
        return asdict(self)

    def describe(self, options: "FilterOptions | None" = None) -> list[str]:
        """The selection in plain words (shown above the dashboard and printed in the report)."""
        def words(chosen: list[str], all_values: list[str] | None, label: str) -> str:
            if all_values is not None and set(chosen) == set(all_values):
                return f"all {label}"
            return ", ".join(chosen) if chosen else f"no {label}"

        o = options
        return [
            f"Governorates: {words(self.governorates, GOVERNORATES, 'governorates')}",
            f"Business groups: {words(self.business_groups, o.business_groups if o else None, 'groups')}",
            f"Business types: {words(self.business_types, o.types_for(self.business_groups) if o else None, 'types in these groups')}",
            f"Population: mid-year estimates {self.year_from}–{self.year_to}; "
            f"{words(self.nationalities, o.nationalities if o else None, 'nationalities')}; "
            f"{words(self.sexes, o.sexes if o else None, 'sexes')}",
            f"Land use: {self.land_period_from} to {self.land_period_to}; "
            f"{words(self.land_categories, o.land_categories if o else None, 'categories')}",
        ]


@dataclass
class FilterOptions:
    """The values each filter can take, read from the data (so the controls never offer a value that does not exist)."""

    business_groups: list[str]
    types_by_group: dict[str, list[str]]
    years: list[int]
    nationalities: list[str]
    sexes: list[str]
    land_periods: list[str]
    land_categories: list[str]

    def types_for(self, groups: list[str]) -> list[str]:
        return sorted({t for g in groups for t in self.types_by_group.get(g, [])})


def filter_options(ds: Datasets) -> FilterOptions:
    b, p, lu = ds.businesses, ds.population, ds.land_use
    groups = sorted(b["dataset"].unique())
    mid = p[(p["estimate"] == "mid-year") & p["current_governorate"]]
    return FilterOptions(
        business_groups=groups,
        types_by_group={g: sorted(b.loc[b["dataset"] == g, "subtype"].unique()) for g in groups},
        years=sorted(int(y) for y in mid["year"].unique()),
        nationalities=sorted(p["nationality"].unique()),
        sexes=sorted(p["sex"].unique()),
        land_periods=sorted(lu["period"].unique()),
        land_categories=sorted(lu["land_use_category"].unique()),
    )


def default_selection(options: FilterOptions) -> Selection:
    """Everything selected: the whole of Bahrain, all business types, every period."""
    return Selection(
        governorates=list(GOVERNORATES),
        business_groups=list(options.business_groups),
        business_types=options.types_for(options.business_groups),
        year_from=options.years[0],
        year_to=options.years[-1],
        nationalities=list(options.nationalities),
        sexes=list(options.sexes),
        land_period_from=options.land_periods[0],
        land_period_to=options.land_periods[-1],
        land_categories=list(options.land_categories),
    )


# ------------------------------------------------------------------ apply the selection to each dataset
def filter_businesses(b: pd.DataFrame, sel: Selection) -> pd.DataFrame:
    keep = (b["governorate"].isin(sel.governorates)
            & b["dataset"].isin(sel.business_groups)
            & b["subtype"].isin(sel.business_types))
    return b[keep]


def filter_population(p: pd.DataFrame, sel: Selection) -> pd.DataFrame:
    """Mid-year estimates only (year-end estimates exist only for 2022-2024 and would count years twice).
    Only the four current governorates: 2010-2011 'Central' and 'Not Stated' rows are left out."""
    keep = ((p["estimate"] == "mid-year")
            & p["current_governorate"]
            & p["governorate"].isin(sel.governorates)
            & p["year"].between(sel.year_from, sel.year_to)
            & p["nationality"].isin(sel.nationalities)
            & p["sex"].isin(sel.sexes))
    return p[keep]


def filter_land_use(lu: pd.DataFrame, sel: Selection) -> pd.DataFrame:
    keep = (lu["governorate"].isin(sel.governorates)
            & lu["period"].between(sel.land_period_from, sel.land_period_to)
            & lu["land_use_category"].isin(sel.land_categories))
    return lu[keep]


def filter_area(a: pd.DataFrame, sel: Selection) -> pd.DataFrame:
    """Area by governorate. Only the four current governorates (Central existed until 2013)."""
    return a[a["current_governorate"] & a["governorate"].isin(sel.governorates)]
