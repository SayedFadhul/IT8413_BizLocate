"""F1 - Data loading and preparation (lead: Ali Haji).

Loads the six data.gov.bh exports in data/raw and returns tidy DataFrames that share
the common dimension `governorate` (Capital, Muharraq, Northern, Southern).

The brief asks that preparation is done in code and documented, covering missing values,
measurement units and category labels. Every decision is:
  1. commented where it happens, and
  2. recorded in a PrepLog (step, dataset, what was done, rows affected),
     which the app shows on the "Data status" page and the report can cite.

Nothing here calls the model. All figures the app shows are computed from these tables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.config import DATA_RAW, GOVERNORATES

BUSINESS_FILES = {
    # file stem                                            -> (code, dataset label)
    "geographical-locations-of-restaurants-cafes": ("RC", "Restaurants & Cafes"),
    "geographical-locations-of-other-shops": ("OS", "Other Shops"),
    "geographical-locations-of-supermarket-hypermarkets": ("SH", "Supermarkets & Hypermarkets"),
}
POPULATION_FILE = "02-population-by-governorate-nationality-sex"
LAND_USE_FILE = "01-land-use-statistics"
AREA_FILE = "02-area-by-governorate-2023"


@dataclass
class PrepLog:
    """Record of every preparation step (shown in the app, cited in the report)."""

    steps: list[dict] = field(default_factory=list)

    def add(self, dataset: str, topic: str, action: str, rows: int | None = None) -> None:
        self.steps.append({"dataset": dataset, "topic": topic, "action": action, "rows_affected": rows})

    def to_frame(self) -> pd.DataFrame:
        df = pd.DataFrame(self.steps, columns=["dataset", "topic", "action", "rows_affected"])
        df["rows_affected"] = df["rows_affected"].astype("Int64")   # whole numbers, blank when not counted
        return df


def _read(stem: str, raw_dir: Path) -> pd.DataFrame:
    # Read every column as text first, then convert on purpose (no silent type guessing).
    # utf-8-sig removes the byte-order mark the portal writes at the start of each export.
    return pd.read_csv(raw_dir / f"{stem}.csv", dtype=str, encoding="utf-8-sig", keep_default_na=False)


def _gov(s: pd.Series) -> pd.Series:
    # Category labels: location files use "CAPITAL", the other files use "Capital".
    return s.str.strip().str.title()


# --------------------------------------------------------------------------- businesses
def load_businesses(raw_dir: Path = DATA_RAW, log: PrepLog | None = None) -> pd.DataFrame:
    """Union of the three iGA location datasets (same 9 columns)."""
    log = log if log is not None else PrepLog()
    parts = []
    for stem, (code, label) in BUSINESS_FILES.items():
        df = _read(stem, raw_dir)
        df["source_code"] = code
        df["dataset"] = label
        # Portal row id "699.0" -> 699. Kept so every answer can cite the exact record.
        df["source_row"] = df["n"].astype(float).astype(int)
        parts.append(df)
    b = pd.concat(parts, ignore_index=True)
    log.add("RC+OS+SH", "structure", "Joined the 3 location datasets into one table; added dataset and source code", len(b))

    for col in ["name", "type", "subtype"]:
        b[col] = b[col].str.strip()
    log.add("RC+OS+SH", "labels", "Trimmed spaces in name, type and subtype; labels kept in the publisher's capitals")

    # Block numbers are codes, not quantities: "301.0" -> 301 (integer).
    b["block"] = b["block"].astype(float).astype(int)
    log.add("RC+OS+SH", "units", "Block stored as float text (e.g. 301.0); converted to an integer code", len(b))

    before = b["governorate"].copy()
    b["governorate"] = _gov(b["governorate"])
    log.add("RC+OS+SH", "labels", "Governorate CAPITAL -> Capital (title case) to match the other datasets",
            int((before != b["governorate"]).sum()))

    b["x_longitude"] = b["x_longitude"].astype(float)
    b["y_latitude"] = b["y_latitude"].astype(float)
    b = b.drop(columns=["n", "location"])  # `location` only repeats x/y as text
    log.add("RC+OS+SH", "structure", "Dropped `location` (duplicate of the coordinates) and `n` (kept as source_row)")

    missing = int((b[["name", "subtype", "governorate"]] == "").sum().sum())
    log.add("RC+OS+SH", "missing values", f"Checked for blank cells: {missing} found", missing)

    # Exact duplicates: same name, type, subtype, block, coordinates and dataset.
    # Kept (we cannot tell if it is an error or two outlets), but flagged so counts can be
    # reported both ways. Same name in the same block with DIFFERENT coordinates = branches.
    key = ["dataset", "name", "type", "subtype", "block", "governorate", "x_longitude", "y_latitude"]
    b["exact_duplicate"] = b.duplicated(subset=key, keep="first")
    log.add("RC+OS+SH", "duplicates",
            "Exact duplicate records kept but flagged (exact_duplicate=True on the second copy); "
            "same name in the same block with different coordinates treated as separate branches",
            int(b["exact_duplicate"].sum()))
    return b


# --------------------------------------------------------------------------- population
def load_population(raw_dir: Path = DATA_RAW, log: PrepLog | None = None) -> pd.DataFrame:
    """iGA population estimates by governorate, nationality and sex (2010-06 to 2025-06)."""
    log = log if log is not None else PrepLog()
    p = _read(POPULATION_FILE, raw_dir)
    p["population"] = p["population"].astype(int)
    p["governorate"] = _gov(p["governorate"])
    p["period"] = p["year"]                       # e.g. "2025-06" (mid-year) or "2024-12" (year-end)
    p["year"] = p["period"].str[:4].astype(int)
    p["month"] = p["period"].str[5:7].astype(int)
    p["estimate"] = p["month"].map({6: "mid-year", 12: "year-end"})
    n_ye = int((p["estimate"] == "year-end").sum())
    log.add("POP", "labels", "Split period into year and month; labelled each row mid-year (June) or "
            "year-end (December). Comparisons over time use mid-year only, so years are not counted twice", n_ye)

    # 2010-2011 use the old five-governorate scheme (Central) and a 'Not Stated' group.
    p["current_governorate"] = p["governorate"].isin(GOVERNORATES)
    log.add("POP", "labels", "Rows for Central and Not Stated (2010-2011 only) kept but flagged "
            "current_governorate=False; per-governorate figures use the 4 current governorates",
            int((~p["current_governorate"]).sum()))
    return p


# --------------------------------------------------------------------------- land use
def load_land_use(raw_dir: Path = DATA_RAW, log: PrepLog | None = None) -> pd.DataFrame:
    """UPDA land-use area by category and governorate, monthly (Jul 2024 - Feb 2026)."""
    log = log if log is not None else PrepLog()
    lu = _read(LAND_USE_FILE, raw_dir)
    # Area is text such as "16398662.168012 m2" (some with two spaces). Remove the unit, convert.
    num = lu["area"].str.replace("m2", "", regex=False).str.strip()
    lu["area_m2"] = pd.to_numeric(num, errors="coerce")
    n_missing = int(lu["area_m2"].isna().sum())
    # The one value that is only "m2" (Southern / Other / Sep 2025) has no number: it is MISSING,
    # not zero, so it stays NaN and is skipped by sums (and the app says so when it is in the selection).
    log.add("LU", "missing values", "Area values that contain only the unit ('m2') set to missing (NaN), not 0", n_missing)
    # Real zeros ("0.00 m2") are kept as 0: Green Belt land is recorded only in Capital.
    log.add("LU", "missing values", "Values recorded as '0.00 m2' kept as real zeros (Green Belt outside Capital)",
            int((lu["area_m2"] == 0).sum()))
    lu["area_km2"] = lu["area_m2"] / 1e6
    log.add("LU", "units", "Area text 'NNN m2' -> number in m2, plus area_km2 = m2 / 1,000,000", len(lu))
    lu["governorate"] = _gov(lu["governorate"])
    lu["year"] = lu["year"].astype(int)
    lu["month_num"] = lu["month"].str[:2].astype(int)
    lu["period"] = lu["year"].astype(str) + "-" + lu["month"].str[:2]
    log.add("LU", "labels", "Month '07 July' -> month_num 7 and period '2024-07'")
    # `n` is NOT unique across months, so it is kept only as a reference; records are cited by
    # period + governorate + category.
    lu["source_row"] = lu["n"].astype(int)
    lu = lu.drop(columns=["n"])
    log.add("LU", "structure", "`n` repeats across months, so records are identified by period, governorate and category")
    return lu


# --------------------------------------------------------------------------- area
def load_area(raw_dir: Path = DATA_RAW, log: PrepLog | None = None) -> pd.DataFrame:
    """SLRB area by governorate in km2, 2007-2024."""
    log = log if log is not None else PrepLog()
    a = _read(AREA_FILE, raw_dir)
    a["area_km2"] = a["value"].astype(float)          # unit column is always "Kilometer Square"
    a["year"] = a["year"].astype(int)
    a["governorate"] = _gov(a["governorate"])
    a["source_row"] = a["n"].astype(float).astype(int)
    a = a.drop(columns=["n", "value"])
    # Portal update of 04/11/2026 added one 'Total' row per year (equal to the sum of the
    # governorates). Dropped so per-governorate sums never count twice.
    n_total = int((a["governorate"] == "Total").sum())
    a = a[a["governorate"] != "Total"].copy()
    log.add("AR", "structure", "Dropped the yearly 'Total' rows added by the portal on 04/11/2026", n_total)
    a["current_governorate"] = a["governorate"].isin(GOVERNORATES)
    log.add("AR", "labels", "Central (until 2013, five-governorate scheme) kept but flagged current_governorate=False",
            int((~a["current_governorate"]).sum()))
    return a.reset_index(drop=True)


# --------------------------------------------------------------------------- all
@dataclass
class Datasets:
    businesses: pd.DataFrame
    population: pd.DataFrame
    land_use: pd.DataFrame
    area: pd.DataFrame
    log: PrepLog

    def row_counts(self) -> dict[str, int]:
        return {
            "businesses": len(self.businesses),
            "population": len(self.population),
            "land_use": len(self.land_use),
            "area": len(self.area),
        }


def load_all(raw_dir: Path = DATA_RAW) -> Datasets:
    log = PrepLog()
    return Datasets(
        businesses=load_businesses(raw_dir, log),
        population=load_population(raw_dir, log),
        land_use=load_land_use(raw_dir, log),
        area=load_area(raw_dir, log),
        log=log,
    )


if __name__ == "__main__":
    ds = load_all()
    for k, v in ds.row_counts().items():
        print(f"{k:11s} {v:5d} rows")
    print("total", sum(ds.row_counts().values()))
    print(ds.log.to_frame().to_string(index=False))
