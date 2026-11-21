"""F4 - Questions over the data: the functions the model can call (lead: Ali Haji).

Tool use (function calling): the model never computes a figure itself. It chooses one of
the functions below and its arguments; our code runs the function over the prepared data
(app/data_prep.py) and returns the computed figures; the model then writes the explanation
around those figures and cites the result id, e.g. [T2] (the brief, F4).

Every result is a plain dict with:
  function   which function ran, and `arguments` it ran with
  result     the main figures (already rounded for presentation, so the model copies them as they are)
  rows       a small table behind the figures (shown in the app for verification)
  source     which dataset(s) and filters the figures come from, e.g. "[OS] subtype PHARMACIES ..."
  notes      caveats the answer should mention (missing values, boundary changes, listing date)

The function declarations at the bottom tell the model what each function does. Category
values are given as fixed lists (enums), so the model can only ask for labels that exist.
"""
from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd
from google.genai import types

from app.config import GOVERNORATES, LISTINGS_UPDATED
from app.data_prep import Datasets

GROUP_CODES = {"Restaurants & Cafes": "RC", "Other Shops": "OS", "Supermarkets & Hypermarkets": "SH"}
LISTING_NOTE = (f"Business counts are the registrations listed at the last portal update ({LISTINGS_UPDATED}); "
                "some listed businesses may have closed since.")
CENTRAL_NOTE = ("2010-2011 population figures use the former five-governorate scheme: they include the "
                "Central Governorate and a 'Not Stated' group, so per-governorate figures before 2012 cannot be "
                "compared directly with later years.")
AREA_BOUNDARY_NOTE = ("Up to 2013 the area dataset lists five governorates (including Central); from 2014 it lists "
                      "four, after the governorate boundaries changed. Areas before and after 2014 cannot be compared "
                      "directly.")


# ---------------------------------------------------------------------------- small helpers
def _clean(x: Any) -> Any:
    """Turn pandas/numpy values into plain Python values the API can send back to the model."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):
        x = x.item()
    if isinstance(x, float) and math.isnan(x):
        return None
    return x


def _ratio(numerator: float, denominator: float, digits: int) -> float | None:
    if not denominator or pd.isna(denominator) or pd.isna(numerator):
        return None
    value = numerator / denominator
    return round(value) if digits == 0 else round(value, digits)


def _pct(part: float, whole: float) -> float | None:
    return _ratio(part * 100, whole, 1)


def _as_list(value) -> list:
    if value is None or value == "" or value == []:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _norm_name(text: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", str(text).upper()).split())


class ToolError(ValueError):
    """A wrong argument. The message goes back to the model so it can correct the call."""


# ---------------------------------------------------------------------------- the functions
class DataTools:
    def __init__(self, ds: Datasets):
        self.ds = ds
        b = ds.businesses
        self.business_types = sorted(b["subtype"].unique())
        self.business_groups = sorted(b["dataset"].unique())
        self.land_categories = sorted(ds.land_use["land_use_category"].unique())
        self.land_periods = sorted(ds.land_use["period"].unique())
        pop = ds.population
        self.mid_years = sorted(int(y) for y in pop.loc[pop["estimate"] == "mid-year", "year"].unique())
        self.end_years = sorted(int(y) for y in pop.loc[pop["estimate"] == "year-end", "year"].unique())
        self.area_years = sorted(int(y) for y in ds.area["year"].unique())
        self.functions = {
            "count_businesses": self.count_businesses,
            "find_businesses": self.find_businesses,
            "get_population": self.get_population,
            "get_land_use": self.get_land_use,
            "get_area": self.get_area,
            "compare_governorates": self.compare_governorates,
            "area_profile": self.area_profile,
        }

    # ----------------------------------------------------------------- run a call from the model
    def call(self, name: str, args: dict | None) -> dict:
        """Run one function call. A wrong name or argument returns {'error': ...} instead of failing."""
        args = dict(args or {})
        if name not in self.functions:
            return {"function": name, "arguments": args, "error": f"Unknown function {name!r}."}
        try:
            out = self.functions[name](**args)
        except TypeError as err:          # an argument the function does not have
            return {"function": name, "arguments": args, "error": f"Wrong arguments: {err}"}
        except ToolError as err:
            return {"function": name, "arguments": args, "error": str(err)}
        out = {"function": name, "arguments": args, **out}
        return _clean(out)

    # ----------------------------------------------------------------- argument checks
    def _check(self, values: list, allowed: list, what: str) -> list:
        bad = [v for v in values if v not in allowed]
        if bad:
            raise ToolError(f"Unknown {what}: {bad}. Use one of: {allowed}")
        return values

    def _business_filter(self, business_types, business_groups, governorates=None, block=None) -> tuple[pd.DataFrame, str]:
        b = self.ds.businesses
        types_ = self._check(_as_list(business_types), self.business_types, "business type")
        groups = self._check(_as_list(business_groups), self.business_groups, "business group")
        govs = self._check(_as_list(governorates), GOVERNORATES, "governorate")
        keep = pd.Series(True, index=b.index)
        desc = []
        if groups:
            keep &= b["dataset"].isin(groups)
            desc.append("groups " + ", ".join(f"{g} [{GROUP_CODES[g]}]" for g in groups))
        if types_:
            keep &= b["subtype"].isin(types_)
            desc.append("types " + ", ".join(types_))
        if govs:
            keep &= b["governorate"].isin(govs)
            desc.append("governorates " + ", ".join(govs))
        if block is not None:
            keep &= b["block"] == int(block)
            desc.append(f"block {int(block)}")
        codes = sorted(b.loc[keep, "source_code"].unique()) or sorted({GROUP_CODES[g] for g in groups}) or ["RC", "OS", "SH"]
        source = "[" + "+".join(codes) + "] " + ("; ".join(desc) if desc else "all listed businesses")
        return b[keep], source

    # ----------------------------------------------------------------- 1. counts of businesses
    def count_businesses(self, business_types=None, business_groups=None, governorates=None,
                         block=None, group_by=None) -> dict:
        """Number of listed businesses matching the filters, optionally broken down."""
        if block is not None:
            try:
                block = int(block)
            except (TypeError, ValueError):
                raise ToolError("block must be a whole number, e.g. 338")
        sub, source = self._business_filter(business_types, business_groups, governorates, block)
        n = len(sub)
        result: dict = {"count": n}
        notes = [LISTING_NOTE]
        dups = int(sub["exact_duplicate"].sum())
        if dups:
            result["count_without_exact_duplicates"] = n - dups
            notes.append(f"{dups} record(s) are exact duplicates of another record (same name, type, block and "
                         "coordinates) and are kept as published.")
        govs = _as_list(governorates)
        if govs and set(govs) != set(GOVERNORATES) and block is None:
            whole, _ = self._business_filter(business_types, business_groups)
            result["bahrain_total_same_types"] = len(whole)
            result["share_of_bahrain_pct"] = _pct(n, len(whole))
        if block is not None:
            exists = bool((self.ds.businesses["block"] == block).any())
            result["block_has_any_listed_business"] = exists
            if exists:
                result["block_governorate"] = self.ds.businesses.loc[self.ds.businesses["block"] == block, "governorate"].iloc[0]
            notes.append("Blocks are used only in the business-location datasets; population, land use and area are "
                         "published by governorate, not by block.")

        rows = []
        if group_by:
            col = {"governorate": "governorate", "block": "block", "business_type": "subtype",
                   "business_group": "dataset"}.get(group_by)
            if col is None:
                raise ToolError("group_by must be one of: governorate, block, business_type, business_group")
            counts = sub.groupby(col).size()
            if col == "governorate":
                counts = counts.reindex(govs or GOVERNORATES, fill_value=0)
            counts = counts.sort_values(ascending=False, kind="stable")
            for rank, (key, c) in enumerate(counts.items(), start=1):
                row = {group_by: key, "count": int(c), "share_pct": _pct(c, n), "rank": rank}
                if col == "block":
                    row["governorate"] = sub.loc[sub["block"] == key, "governorate"].iloc[0]
                rows.append(row)
            if col == "block" and len(rows) > 20:
                result["blocks_with_businesses"] = len(rows)
                notes.append(f"Only the 20 blocks with the most businesses are listed (of {len(rows)}).")
                rows = rows[:20]
        return {"result": result, "rows": rows, "source": source, "notes": notes}

    # ----------------------------------------------------------------- 2. look up named businesses
    def find_businesses(self, name: str, governorate=None, business_types=None) -> dict:
        """Where a named business is listed (block, governorate, type), by part of its name."""
        if not name or not str(name).strip():
            raise ToolError("name is required")
        sub, _ = self._business_filter(business_types, None, governorate)
        words = _norm_name(name).split()
        names = sub["name"].map(_norm_name)
        hit = names.map(lambda n: all(w in n for w in words))
        found = sub[hit].sort_values(["name", "block"])
        rows = [{"name": r.name, "business_type": r.subtype, "business_group": r.dataset, "block": int(r.block),
                 "governorate": r.governorate, "record": f"[{r.source_code}] n = {int(r.source_row)}"}
                for r in found.head(25).itertuples()]
        notes = [f"The list shows registrations at the last portal update ({LISTINGS_UPDATED}); the data cannot "
                 "show whether a business is still open."]
        if len(found) > 25:
            notes.append(f"Only the first 25 of {len(found)} matches are listed.")
        if found.empty:
            notes.append("No listed business has all the words of this name; it may be listed under another name or "
                         "not be in the three location datasets.")
        codes = "+".join(sorted(found["source_code"].unique())) or "RC+OS+SH"
        return {"result": {"matches": int(len(found))}, "rows": rows,
                "source": f"[{codes}] name search for '{name}'", "notes": notes}

    # ----------------------------------------------------------------- 3. population
    def get_population(self, governorates=None, year=None, year_from=None, year_to=None, nationality=None,
                       sex=None, estimate="mid-year", group_by=None) -> dict:
        """Residents (population estimates) by governorate, nationality, sex and year."""
        p = self.ds.population
        if estimate not in ("mid-year", "year-end"):
            raise ToolError("estimate must be 'mid-year' or 'year-end'")
        years_ok = self.mid_years if estimate == "mid-year" else self.end_years
        govs = self._check(_as_list(governorates), GOVERNORATES + ["Central", "Not Stated"], "governorate")
        nats = self._check(_as_list(nationality), ["Bahraini", "Non-Bahraini"], "nationality")
        sexes = self._check(_as_list(sex), ["Male", "Female"], "sex")
        group_by = _as_list(group_by)
        self._check(group_by, ["governorate", "nationality", "sex", "year"], "group_by value")

        if year is not None:
            y0 = y1 = int(year)
        else:
            y0 = int(year_from) if year_from is not None else (years_ok[-1] if year_to is None else years_ok[0])
            y1 = int(year_to) if year_to is not None else years_ok[-1]
        missing = [y for y in range(y0, y1 + 1) if y not in years_ok]
        if y0 > y1 or len(missing) == (y1 - y0 + 1):
            raise ToolError(f"No {estimate} estimates for {y0}-{y1}. {estimate} years available: {years_ok}")
        if y0 != y1 and "year" not in group_by:
            group_by = ["year"] + group_by

        keep = (p["estimate"] == estimate) & p["year"].between(y0, y1)
        if govs:
            keep &= p["governorate"].isin(govs)
        if nats:
            keep &= p["nationality"].isin(nats)
        if sexes:
            keep &= p["sex"].isin(sexes)
        sub = p[keep]
        notes = ["Population is published by governorate, nationality and sex only (not by block or area smaller "
                 "than a governorate)."]
        if y0 <= 2011:
            notes.append(CENTRAL_NOTE)
        if estimate == "mid-year":
            notes.append("Mid-year (June) estimates. Year-end (December) estimates also exist for "
                         f"{self.end_years[0]}-{self.end_years[-1]} and are a different measure.")

        result: dict = {"estimate": estimate, "years": f"{y0}" if y0 == y1 else f"{y0}-{y1}"}
        rows = []
        if group_by:
            g = sub.groupby(group_by)["population"].sum().reset_index()
            if "year" in group_by and y0 != y1:
                others = [c for c in group_by if c != "year"]
                g = g.sort_values(others + ["year"])
                prev = g.groupby(others)["population"].shift() if others else g["population"].shift()
                g["change_from_previous_year"] = (g["population"] - prev).astype("Int64")
                g["change_pct"] = (g["change_from_previous_year"] / prev * 100).round(2)
                totals = sub.groupby("year")["population"].sum()
                result["first_year_total"] = int(totals.iloc[0])
                result["last_year_total"] = int(totals.iloc[-1])
                result["change_total"] = int(totals.iloc[-1] - totals.iloc[0])
                result["change_total_pct"] = _pct(totals.iloc[-1] - totals.iloc[0], totals.iloc[0])
                falls = [f"{a}->{b}" for a, b, va, vb in zip(totals.index[:-1], totals.index[1:],
                                                               totals.values[:-1], totals.values[1:]) if vb < va]
                result["years_when_total_fell"] = falls or "none"
            else:                                             # one year: each group's share of the total
                g["share_pct"] = (g["population"] / sub["population"].sum() * 100).round(1)
            rows = g.to_dict("records")
        if y0 == y1:
            result["total"] = int(sub["population"].sum())
        source = (f"[POP] {estimate} {result['years']}"
                  + (f"; governorates {', '.join(govs)}" if govs else "; all of Bahrain")
                  + (f"; {', '.join(nats)}" if nats else "") + (f"; {', '.join(sexes)}" if sexes else ""))
        return {"result": result, "rows": rows, "source": source, "notes": notes}

    # ----------------------------------------------------------------- 4. land use
    def get_land_use(self, governorates=None, categories=None, period=None, period_from=None, period_to=None,
                     group_by=None) -> dict:
        """Land area (km²) by land-use category, governorate and month (Jul 2024 - Feb 2026)."""
        lu = self.ds.land_use
        govs = self._check(_as_list(governorates), GOVERNORATES, "governorate")
        cats = self._check(_as_list(categories), self.land_categories, "land-use category")
        group_by = _as_list(group_by)
        self._check(group_by, ["governorate", "category", "period"], "group_by value")
        if period is not None:
            p0 = p1 = str(period)
        else:
            p0 = str(period_from) if period_from else (self.land_periods[-1] if not period_to else self.land_periods[0])
            p1 = str(period_to) if period_to else self.land_periods[-1]
        for p_ in (p0, p1):
            if p_ not in self.land_periods:
                raise ToolError(f"Unknown month {p_!r}. Months available (YYYY-MM): {self.land_periods}")
        if p0 != p1 and "period" not in group_by:
            group_by = ["period"] + group_by

        keep = lu["period"].between(p0, p1)
        if govs:
            keep &= lu["governorate"].isin(govs)
        all_cats = lu[keep]                                   # every category: the base for shares
        sub = all_cats[all_cats["land_use_category"].isin(cats)] if cats else all_cats
        notes = ["Land use is published by governorate and month, not by block. Areas are converted from m² to km²."]
        miss = sub[sub["area_km2"].isna()]
        result: dict = {"months": p0 if p0 == p1 else f"{p0} to {p1}"}
        if len(miss):
            result["records_missing_in_source"] = [
                f"{r.governorate}, {r.land_use_category}, {r.period} (record n = {int(r.source_row)})" for r in miss.itertuples()]
            notes.append("A missing record contains only the unit 'm2' and no number in the source: its area is NOT "
                         "AVAILABLE (it is not zero) and it is left out of every sum.")
        if len(sub) and sub["area_km2"].isna().all():
            result["total_km2"] = None
            result["status"] = "not available: every matching record is missing in the source"
        elif p0 == p1:
            result["total_km2"] = round(float(sub["area_km2"].sum()), 2)
            if cats:
                result["share_of_all_land_use_pct"] = _pct(sub["area_km2"].sum(), all_cats["area_km2"].sum())

        rows = []
        if group_by:
            col = {"governorate": "governorate", "category": "land_use_category", "period": "period"}
            keys = [col[g] for g in group_by]
            g = sub.groupby(keys)["area_km2"].sum(min_count=1).round(2).reset_index()
            base_keys = [k for k in keys if k != "land_use_category"]
            if base_keys:
                base = all_cats.groupby(base_keys)["area_km2"].sum().rename("all_categories_km2").reset_index()
                g = g.merge(base, on=base_keys, how="left")
            else:
                g["all_categories_km2"] = all_cats["area_km2"].sum()
            g["share_of_all_land_use_pct"] = (g["area_km2"] / g["all_categories_km2"] * 100).round(1)
            g = g.drop(columns="all_categories_km2").rename(columns={"land_use_category": "category"})
            if len(group_by) == 1 and group_by[0] != "period":
                g = g.sort_values("area_km2", ascending=False, na_position="last")
                g["rank"] = range(1, len(g) + 1)
            rows = g.to_dict("records")
        source = (f"[LU] {result['months']}" + (f"; governorates {', '.join(govs)}" if govs else "; all governorates")
                  + (f"; categories {', '.join(cats)}" if cats else "; all categories"))
        return {"result": result, "rows": rows, "source": source, "notes": notes}

    # ----------------------------------------------------------------- 5. area
    def get_area(self, governorates=None, year=None, year_from=None, year_to=None) -> dict:
        """Land area of each governorate in km² (2007-2024)."""
        a = self.ds.area
        govs = self._check(_as_list(governorates), GOVERNORATES + ["Central"], "governorate")
        if year is not None:
            y0 = y1 = int(year)
        else:
            y0 = int(year_from) if year_from is not None else (self.area_years[-1] if year_to is None else self.area_years[0])
            y1 = int(year_to) if year_to is not None else self.area_years[-1]
        if y0 not in self.area_years or y1 not in self.area_years:
            raise ToolError(f"Area years available: {self.area_years[0]}-{self.area_years[-1]}")
        keep = a["year"].between(y0, y1)
        if govs:
            keep &= a["governorate"].isin(govs)
        sub = a[keep].sort_values(["year", "governorate"])
        rows = [{"year": int(r.year), "governorate": r.governorate, "area_km2": float(r.area_km2),
                 "record": f"[AR] n = {int(r.source_row)}"} for r in sub.itertuples()]
        totals = sub.groupby("year")["area_km2"].sum()
        result = {"years": f"{y0}" if y0 == y1 else f"{y0}-{y1}",
                  "total_km2_by_year": {int(k): round(float(v), 2) for k, v in totals.items()}}
        notes = []
        if y0 <= 2013:
            notes.append(AREA_BOUNDARY_NOTE)
        if govs and y0 == y1:
            result["total_km2"] = round(float(sub["area_km2"].sum()), 2)
        source = f"[AR] {result['years']}" + (f"; {', '.join(govs)}" if govs else "; all governorates")
        return {"result": result, "rows": rows, "source": source, "notes": notes}

    # ----------------------------------------------------------------- 6. ratios that relate the datasets
    MEASURES = {
        "residents_per_business": "residents ÷ businesses",
        "businesses_per_10000_residents": "businesses ÷ residents × 10,000",
        "businesses_per_km2": "businesses ÷ governorate area (km²)",
        "residents_per_km2": "residents ÷ governorate area (km²)",
        "land_m2_per_business": "land of one land-use category (m²) ÷ businesses",
    }

    def compare_governorates(self, measure, business_types=None, business_groups=None, governorates=None,
                             population_year=None, nationality=None, sex=None, land_use_category=None,
                             land_use_period=None, area_year=None) -> dict:
        """One ratio for each governorate (relating businesses to residents, area or land use), ranked."""
        if measure not in self.MEASURES:
            raise ToolError(f"measure must be one of: {list(self.MEASURES)}")
        govs = self._check(_as_list(governorates), GOVERNORATES, "governorate") or list(GOVERNORATES)
        bus, bus_source = self._business_filter(business_types, business_groups)
        n_bus = bus.groupby("governorate").size().reindex(GOVERNORATES, fill_value=0)

        need_res = measure in ("residents_per_business", "businesses_per_10000_residents", "residents_per_km2")
        need_area = measure in ("businesses_per_km2", "residents_per_km2")
        need_land = measure == "land_m2_per_business"
        sources, notes, cols = [], [], {}

        if measure != "residents_per_km2":
            sources.append(bus_source)
            cols["businesses"] = n_bus
            notes.append(LISTING_NOTE)
        if need_res:
            y = int(population_year) if population_year is not None else self.mid_years[-1]
            if y not in self.mid_years:
                raise ToolError(f"population_year must be a mid-year estimate year: {self.mid_years}")
            pop_args = dict(year=y, nationality=nationality, sex=sex, group_by=["governorate"])
            pop = self.get_population(**pop_args)
            res = pd.Series({r["governorate"]: r["population"] for r in pop["rows"]}).reindex(GOVERNORATES)
            cols["residents"] = res
            sources.append(pop["source"].replace("all of Bahrain", "by governorate"))
            if y <= 2011:
                notes.append(CENTRAL_NOTE)
        if need_area:
            ay = int(area_year) if area_year is not None else self.area_years[-1]
            ar = self.ds.area
            area = ar[(ar["year"] == ay)].set_index("governorate")["area_km2"].reindex(GOVERNORATES)
            cols["area_km2"] = area
            sources.append(f"[AR] {ay}")
            if ay <= 2013:
                notes.append(AREA_BOUNDARY_NOTE)
        if need_land:
            if not land_use_category:
                raise ToolError("land_use_category is required for land_m2_per_business (e.g. 'Commercial')")
            self._check([land_use_category], self.land_categories, "land-use category")
            per = str(land_use_period) if land_use_period else self.land_periods[-1]
            if per not in self.land_periods:
                raise ToolError(f"land_use_period must be one of {self.land_periods}")
            lu = self.ds.land_use
            land = (lu[(lu["period"] == per) & (lu["land_use_category"] == land_use_category)]
                    .groupby("governorate")["area_km2"].sum(min_count=1).reindex(GOVERNORATES))
            cols[f"{land_use_category.lower()}_land_km2"] = land     # exact; the ratio is rounded
            sources.append(f"[LU] {per}; category {land_use_category}")

        t = pd.DataFrame(cols)
        if measure == "residents_per_business":
            t["value"] = [_ratio(r, b, 0) for r, b in zip(t["residents"], t["businesses"])]
        elif measure == "businesses_per_10000_residents":
            t["value"] = [_ratio(b * 10_000, r, 2) for r, b in zip(t["residents"], t["businesses"])]
        elif measure == "businesses_per_km2":
            t["value"] = [_ratio(b, a, 2) for b, a in zip(t["businesses"], t["area_km2"])]
        elif measure == "residents_per_km2":
            t["value"] = [_ratio(r, a, 0) for r, a in zip(t["residents"], t["area_km2"])]
        else:
            land_col = [c for c in t.columns if c.endswith("_land_km2")][0]
            t["value"] = [_ratio(l * 1_000_000, b, 0) for l, b in zip(t[land_col], t["businesses"])]

        # Bahrain as a whole (the four governorates), computed from the column totals
        tot = t.sum(numeric_only=True)
        if measure == "residents_per_business":
            overall = _ratio(tot["residents"], tot["businesses"], 0)
        elif measure == "businesses_per_10000_residents":
            overall = _ratio(tot["businesses"] * 10_000, tot["residents"], 2)
        elif measure == "businesses_per_km2":
            overall = _ratio(tot["businesses"], tot["area_km2"], 2)
        elif measure == "residents_per_km2":
            overall = _ratio(tot["residents"], tot["area_km2"], 0)
        else:
            overall = _ratio(tot[land_col] * 1_000_000, tot["businesses"], 0)

        t = t.loc[govs]
        ranked = t["value"].dropna().sort_values(ascending=False)
        t["rank_highest_first"] = t["value"].rank(ascending=False, method="min")
        rows = [{"governorate": g, **{k: v for k, v in r.items()}} for g, r in t.to_dict("index").items()]
        no_value = [g for g in govs if pd.isna(t.loc[g, "value"])]
        if no_value:
            notes.append(f"No value for {', '.join(no_value)}: a count of zero or a missing figure.")
        result = {"measure": measure, "formula": self.MEASURES[measure],
                  "highest": ranked.index[0] if len(ranked) else None,
                  "highest_value": ranked.iloc[0] if len(ranked) else None,
                  "lowest": ranked.index[-1] if len(ranked) else None,
                  "lowest_value": ranked.iloc[-1] if len(ranked) else None,
                  "bahrain_overall_value": overall}
        return {"result": result, "rows": rows, "source": "; ".join(sources), "notes": notes}

    # ----------------------------------------------------------------- 7. area profile
    def area_profile(self, governorate, business_types=None, business_groups=None) -> dict:
        """A summary of one governorate: businesses, residents, land use and area (the brief's 'area profile')."""
        self._check([governorate], GOVERNORATES, "governorate")
        b = self.ds.businesses
        here = b[b["governorate"] == governorate]
        by_group = here.groupby("dataset").size().to_dict()
        top_types = here["subtype"].value_counts().head(5).to_dict()
        top_blocks = here.groupby("block").size().sort_values(ascending=False).head(5).to_dict()
        chosen = None
        if business_types or business_groups:
            sub, src = self._business_filter(business_types, business_groups, [governorate])
            chosen = {"filter": src, "count": len(sub), "share_of_governorate_businesses_pct": _pct(len(sub), len(here))}

        y = self.mid_years[-1]
        p = self.ds.population
        pop = p[(p["estimate"] == "mid-year") & (p["year"] == y) & (p["governorate"] == governorate)]
        residents = int(pop["population"].sum())
        by_nat = pop.groupby("nationality")["population"].sum().to_dict()
        by_sex = pop.groupby("sex")["population"].sum().to_dict()
        first = p[(p["estimate"] == "mid-year") & (p["year"] == 2012) & (p["governorate"] == governorate)]["population"].sum()

        per = self.land_periods[-1]
        lu = self.ds.land_use
        land = lu[(lu["period"] == per) & (lu["governorate"] == governorate)]
        land_total = float(land["area_km2"].sum())
        land_top = (land.sort_values("area_km2", ascending=False).head(6)
                    .apply(lambda r: {"category": r["land_use_category"], "km2": round(float(r["area_km2"]), 2),
                                      "share_pct": _pct(r["area_km2"], land_total)}, axis=1).tolist())
        ay = self.area_years[-1]
        area = float(self.ds.area.loc[(self.ds.area["year"] == ay) & (self.ds.area["governorate"] == governorate), "area_km2"].sum())

        result = {
            "governorate": governorate,
            "businesses_total": int(len(here)),
            "businesses_by_group": by_group,
            "top_business_types": top_types,
            "top_blocks_by_businesses": {int(k): int(v) for k, v in top_blocks.items()},
            "selected_businesses": chosen,
            f"residents_mid_{y}": residents,
            "residents_by_nationality": by_nat,
            "residents_by_sex": by_sex,
            f"residents_change_2012_to_{y}_pct": _pct(residents - first, first),
            f"land_use_{per}_total_km2": round(land_total, 2),
            f"land_use_{per}_largest_categories": land_top,
            f"area_{ay}_km2": area,
            "residents_per_business": _ratio(residents, len(here), 0),
            "businesses_per_km2": _ratio(len(here), area, 2),
            "residents_per_km2": _ratio(residents, area, 0),
        }
        source = f"[RC+OS+SH] {governorate}; [POP] mid-year {y}; [LU] {per}; [AR] {ay}"
        notes = [LISTING_NOTE, "The sources describe the businesses and residents that exist; they cannot say whether a "
                 "new business would succeed, or give rents or footfall."]
        return {"result": result, "rows": [], "source": source, "notes": notes}

    # ----------------------------------------------------------------- declarations for the model
    def declarations(self) -> list[types.FunctionDeclaration]:
        gov = {"type": "array", "items": {"type": "string", "enum": GOVERNORATES},
               "description": "Governorates to include. Leave out for all of Bahrain."}
        btypes = {"type": "array", "items": {"type": "string", "enum": self.business_types},
                  "description": "Business types (subtypes) exactly as listed, e.g. COFFEE SHOPS, PHARMACIES, SUPERMARKET."}
        bgroups = {"type": "array", "items": {"type": "string", "enum": self.business_groups},
                   "description": "Whole datasets: Restaurants & Cafes [RC], Other Shops [OS], Supermarkets & Hypermarkets [SH]."}
        return [
            types.FunctionDeclaration(
                name="count_businesses",
                description=("Count listed businesses (restaurants & cafes, other shops, supermarkets & hypermarkets) "
                             "by type, governorate and block. Returns the count, the share of Bahrain's total when "
                             "governorates are chosen, and an optional breakdown with ranks."),
                parameters_json_schema={"type": "object", "properties": {
                    "business_types": btypes, "business_groups": bgroups, "governorates": gov,
                    "block": {"type": "integer", "description": "One block number, e.g. 338."},
                    "group_by": {"type": "string", "enum": ["governorate", "block", "business_type", "business_group"],
                                 "description": "Optional breakdown."}}}),
            types.FunctionDeclaration(
                name="find_businesses",
                description="Find where a named business is listed: its block, governorate and type. Matches part of the name.",
                parameters_json_schema={"type": "object", "properties": {
                    "name": {"type": "string", "description": "The business name or part of it, e.g. 'Waitrose'."},
                    "governorate": gov, "business_types": btypes}, "required": ["name"]}),
            types.FunctionDeclaration(
                name="get_population",
                description=("Residents (population estimates) by governorate, nationality and sex, 2010-2025. "
                             "Mid-year estimates by default; year-end estimates exist for 2022-2024. A year range "
                             "returns each year with the change from the previous year and the years when the total fell. "
                             "With no governorates the figures are for all of Bahrain."),
                parameters_json_schema={"type": "object", "properties": {
                    "governorates": {"type": "array", "items": {"type": "string",
                                     "enum": GOVERNORATES + ["Central", "Not Stated"]},
                                     "description": "Leave out for all of Bahrain. Central and Not Stated exist only in 2010-2011."},
                    "year": {"type": "integer", "description": f"One year, {self.mid_years[0]}-{self.mid_years[-1]}."},
                    "year_from": {"type": "integer"}, "year_to": {"type": "integer"},
                    "nationality": {"type": "array", "items": {"type": "string", "enum": ["Bahraini", "Non-Bahraini"]}},
                    "sex": {"type": "array", "items": {"type": "string", "enum": ["Male", "Female"]}},
                    "estimate": {"type": "string", "enum": ["mid-year", "year-end"]},
                    "group_by": {"type": "array", "items": {"type": "string",
                                 "enum": ["governorate", "nationality", "sex", "year"]}}}}),
            types.FunctionDeclaration(
                name="get_land_use",
                description=("Land area in km² by land-use category and governorate for one month or a range "
                             f"({self.land_periods[0]} to {self.land_periods[-1]}). Returns totals, shares of all "
                             "land-use area, ranks, and any record that is missing in the source (missing is not zero)."),
                parameters_json_schema={"type": "object", "properties": {
                    "governorates": gov,
                    "categories": {"type": "array", "items": {"type": "string", "enum": self.land_categories}},
                    "period": {"type": "string", "enum": self.land_periods, "description": "One month, YYYY-MM. Default: latest."},
                    "period_from": {"type": "string", "enum": self.land_periods},
                    "period_to": {"type": "string", "enum": self.land_periods},
                    "group_by": {"type": "array", "items": {"type": "string",
                                 "enum": ["governorate", "category", "period"]}}}}),
            types.FunctionDeclaration(
                name="get_area",
                description=("Area of each governorate in km² by year (2007-2024), with totals. Up to 2013 the "
                             "dataset has five governorates including Central; from 2014 four."),
                parameters_json_schema={"type": "object", "properties": {
                    "governorates": {"type": "array", "items": {"type": "string", "enum": GOVERNORATES + ["Central"]}},
                    "year": {"type": "integer"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"}}}),
            types.FunctionDeclaration(
                name="compare_governorates",
                description=("Compute one ratio for each governorate that relates businesses to residents, area or "
                             "land use, e.g. residents per pharmacy or commercial land per supermarket, with the "
                             "highest and lowest governorate and the value for Bahrain overall. Always set "
                             "business_types or business_groups to the kind of business asked about (e.g. "
                             "PHARMACIES); without them every listed business is counted."),
                parameters_json_schema={"type": "object", "properties": {
                    "measure": {"type": "string", "enum": list(self.MEASURES)},
                    "business_types": btypes, "business_groups": bgroups, "governorates": gov,
                    "population_year": {"type": "integer", "description": "Mid-year estimate year. Default: latest (2025)."},
                    "nationality": {"type": "array", "items": {"type": "string", "enum": ["Bahraini", "Non-Bahraini"]}},
                    "sex": {"type": "array", "items": {"type": "string", "enum": ["Male", "Female"]}},
                    "land_use_category": {"type": "string", "enum": self.land_categories},
                    "land_use_period": {"type": "string", "enum": self.land_periods},
                    "area_year": {"type": "integer"}}, "required": ["measure"]}),
            types.FunctionDeclaration(
                name="area_profile",
                description=("Area profile of one governorate: businesses by group, top types and blocks, residents "
                             "by nationality and sex, land use by category, area and densities."),
                parameters_json_schema={"type": "object", "properties": {
                    "governorate": {"type": "string", "enum": GOVERNORATES},
                    "business_types": btypes, "business_groups": bgroups}, "required": ["governorate"]}),
        ]
