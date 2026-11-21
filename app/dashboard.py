"""F3 - Analytics dashboard: the tables behind the charts and the summary figures (lead: Mohamed Alradhi).

Every function takes data that is ALREADY filtered by the current Selection (app/filters.py),
so every chart and figure follows the filters (brief F2). The charts themselves are drawn in
streamlit_app.py (on screen) and app/report.py (in the downloaded report) from these tables.

The brief asks for at least three visualizations: change over time, composition or
distribution, and a comparison between categories, plus summary figures for the selection.
  - change over time ........ population_trend, land_use_trend
  - composition ............. business_type_mix, land_use_mix
  - comparison .............. businesses_by_governorate, residents_per_business
  - where (map / blocks) .... top_blocks (and the map of the filtered businesses)
All numbers are computed here with pandas; the model is not involved.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.config import GOVERNORATES


@dataclass
class SummaryFigures:
    businesses: int
    residents: int | None              # latest selected mid-year
    residents_year: int | None
    residents_first: int | None        # earliest selected mid-year (for the change)
    residents_first_year: int | None
    residents_per_business: float | None
    area_km2: float | None             # area dataset, latest year
    area_year: int | None
    businesses_per_km2: float | None
    land_km2: float | None             # selected land-use categories, latest selected month
    land_period: str | None
    land_missing: int                  # land-use records in the selection whose value is missing in the source

    @property
    def residents_change_pct(self) -> float | None:
        if not self.residents or not self.residents_first or self.residents_year == self.residents_first_year:
            return None
        return (self.residents / self.residents_first - 1) * 100


def summary_figures(b_f: pd.DataFrame, p_f: pd.DataFrame, lu_f: pd.DataFrame, a_f: pd.DataFrame) -> SummaryFigures:
    n_bus = int(len(b_f))

    residents = residents_year = first = first_year = None
    if len(p_f):
        by_year = p_f.groupby("year")["population"].sum()
        residents_year, residents = int(by_year.index.max()), int(by_year.iloc[-1])
        first_year, first = int(by_year.index.min()), int(by_year.iloc[0])

    area_km2 = area_year = None
    if len(a_f):
        area_year = int(a_f["year"].max())
        area_km2 = float(a_f.loc[a_f["year"] == area_year, "area_km2"].sum())

    land_km2 = land_period = None
    missing = 0
    if len(lu_f):
        land_period = str(lu_f["period"].max())
        latest = lu_f[lu_f["period"] == land_period]
        land_km2 = float(latest["area_km2"].sum())       # missing values are skipped, and counted below
        missing = int(lu_f["area_km2"].isna().sum())

    return SummaryFigures(
        businesses=n_bus,
        residents=residents, residents_year=residents_year,
        residents_first=first, residents_first_year=first_year,
        residents_per_business=(residents / n_bus) if residents and n_bus else None,
        area_km2=area_km2, area_year=area_year,
        businesses_per_km2=(n_bus / area_km2) if area_km2 and n_bus else None,
        land_km2=land_km2, land_period=land_period, land_missing=missing,
    )


# ------------------------------------------------------------------ change over time
def population_trend(p_f: pd.DataFrame) -> pd.DataFrame:
    """Mid-year residents per year (rows) and governorate (columns)."""
    if p_f.empty:
        return pd.DataFrame()
    t = p_f.pivot_table(index="year", columns="governorate", values="population", aggfunc="sum")
    return t.reindex(columns=[g for g in GOVERNORATES if g in t.columns])


def land_use_trend(lu_f: pd.DataFrame) -> pd.DataFrame:
    """km² per month (rows) and land-use category (columns), summed over the selected governorates.
    A month that contains a missing value is summed without it (the dashboard warns about it)."""
    if lu_f.empty:
        return pd.DataFrame()
    return lu_f.pivot_table(index="period", columns="land_use_category", values="area_km2", aggfunc="sum")


# ------------------------------------------------------------------ composition
def business_type_mix(b_f: pd.DataFrame, top: int = 12) -> pd.DataFrame:
    """Number of businesses of each type; types after the first `top` are joined as 'Other types'."""
    if b_f.empty:
        return pd.DataFrame(columns=["business_type", "businesses", "share_pct"])
    counts = b_f["subtype"].value_counts()
    if len(counts) > top:
        counts = pd.concat([counts.iloc[:top], pd.Series({"Other types": counts.iloc[top:].sum()})])
    t = counts.rename_axis("business_type").reset_index(name="businesses")
    t["share_pct"] = (t["businesses"] / t["businesses"].sum() * 100).round(1)
    return t


def land_use_mix(lu_f: pd.DataFrame) -> pd.DataFrame:
    """km² per governorate and category in the latest selected month (long format, for a stacked bar)."""
    if lu_f.empty:
        return pd.DataFrame(columns=["governorate", "land_use_category", "area_km2", "period"])
    period = lu_f["period"].max()
    t = (lu_f[lu_f["period"] == period]
         .groupby(["governorate", "land_use_category"], as_index=False)["area_km2"].sum(min_count=1))
    t["period"] = period
    return t


# ------------------------------------------------------------------ comparison between categories
def businesses_by_governorate(b_f: pd.DataFrame) -> pd.DataFrame:
    """Businesses per governorate (rows) and business group (columns)."""
    if b_f.empty:
        return pd.DataFrame()
    t = b_f.groupby(["governorate", "dataset"]).size().unstack(fill_value=0)
    return t.reindex([g for g in GOVERNORATES if g in t.index])


def residents_per_business(b_f: pd.DataFrame, p_f: pd.DataFrame) -> pd.DataFrame:
    """For each selected governorate: residents in the latest selected year, businesses, and the two ratios."""
    if p_f.empty:
        return pd.DataFrame(columns=["governorate", "residents", "businesses",
                                     "residents_per_business", "businesses_per_10k_residents"])
    year = p_f["year"].max()
    res = p_f[p_f["year"] == year].groupby("governorate")["population"].sum()
    bus = b_f.groupby("governorate").size()
    t = pd.DataFrame({"residents": res, "businesses": bus}).fillna(0)
    t = t.reindex([g for g in GOVERNORATES if g in t.index])
    t["residents"] = t["residents"].astype(int)
    t["businesses"] = t["businesses"].astype(int)
    t["residents_per_business"] = (t["residents"] / t["businesses"].where(t["businesses"] > 0)).round(1)
    t["businesses_per_10k_residents"] = (t["businesses"] / t["residents"].where(t["residents"] > 0) * 10_000).round(2)
    t["year"] = int(year)
    return t.rename_axis("governorate").reset_index()


# ------------------------------------------------------------------ where: blocks and map
def top_blocks(b_f: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """The blocks with the most selected businesses, with the most common type in each."""
    if b_f.empty:
        return pd.DataFrame(columns=["block", "governorate", "businesses", "most_common_type"])
    g = b_f.groupby(["block", "governorate"])
    t = g.size().rename("businesses").reset_index()
    t["most_common_type"] = g["subtype"].agg(lambda s: s.value_counts().index[0]).values
    return t.sort_values(["businesses", "block"], ascending=[False, True]).head(n).reset_index(drop=True)


def map_points(b_f: pd.DataFrame) -> pd.DataFrame:
    """Coordinates of the filtered businesses for st.map."""
    return b_f.rename(columns={"y_latitude": "lat", "x_longitude": "lon"})[["lat", "lon", "name", "subtype", "block"]]


def missing_land_records(lu_f: pd.DataFrame) -> pd.DataFrame:
    """Land-use records in the selection whose area is missing in the source (shown as a warning)."""
    return lu_f.loc[lu_f["area_km2"].isna(), ["period", "governorate", "land_use_category", "area"]]
