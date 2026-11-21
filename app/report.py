"""F9 - The downloadable summary report for the current selection (lead: Ali Haji).

The report is one HTML file that opens in any browser and prints to PDF. It holds:
  - the selection (filters), the model and version, and the data extraction date (reproducibility);
  - the summary figures and tables, computed with pandas from the same filtered data as the dashboard;
  - three charts (PNG images drawn with matplotlib and embedded in the file);
  - cited document passages: those cited in this session's answers, plus the licensing passages
    for the selected business groups, found by keyword search (no model call);
  - the licence statement and attribution the Bahrain Open Government Data License requires.
"""
from __future__ import annotations

import base64
import html
import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from app import dashboard as dash  # noqa: E402
from app.config import DATA_EXTRACTED, GOVERNORATES, LISTINGS_UPDATED, Settings  # noqa: E402
from app.data_prep import Datasets  # noqa: E402
from app.filters import (FilterOptions, Selection, filter_area, filter_businesses, filter_land_use,  # noqa: E402
                         filter_population)

COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
GOV_COLOUR = dict(zip(GOVERNORATES, COLOURS))

# Fixed keyword queries for the passages printed in every report (by business group).
KEY_QUERIES = {
    None: "approvals and licenses required for practicing the activity within one year from the registration date",
    "Restaurants & Cafes": "food establishment license Ministry of Health Food Control Section operate display",
    "Supermarkets & Hypermarkets": "food establishment license Ministry of Health Food Control Section operate display",
    "Other Shops": "commercial sole proprietorship registration Bahraini nationals age",
}
LICENCE = ("Datasets provided by the Information & eGovernment Authority (iGA), the Urban Planning and Development "
           "Authority (UPDA) and the Survey and Land Registration Bureau (SLRB) via www.data.gov.bh are governed by the "
           "Bahrain Open Government Data License available at www.nea.gov.bh/Documents/OpenDataLicense.pdf. To the "
           "fullest extent permitted by law, the government is not liable for any damage or loss of any kind caused "
           "directly or indirectly by the use or availability of the datasets or any derived analyses or applications.")


def _png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _style(ax, title: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=11, loc="left")
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e5e1", linewidth=0.8)
    ax.set_axisbelow(True)


def charts(b_f, p_f) -> list[tuple[str, str]]:
    """(title, base64 PNG) for each chart in the report."""
    out = []
    t = dash.businesses_by_governorate(b_f)
    if not t.empty:
        fig, ax = plt.subplots(figsize=(6.2, 3.2))
        bottom = pd.Series(0, index=t.index)
        for i, col in enumerate(t.columns):
            ax.bar(t.index, t[col], bottom=bottom, color=COLOURS[4 + i % 3], label=col, edgecolor="white", linewidth=1)
            bottom += t[col]
        for x, v in zip(t.index, bottom):
            ax.text(x, v, f"{int(v):,}", ha="center", va="bottom", fontsize=8)
        _style(ax, "Businesses by governorate", "Businesses")
        ax.legend(frameon=False, fontsize=8)
        out.append(("Businesses by governorate (comparison)", _png(fig)))
    r = dash.residents_per_business(b_f, p_f)
    if not r.empty and r["businesses"].sum() > 0:
        fig, ax = plt.subplots(figsize=(6.2, 3.2))
        ax.bar(r["governorate"], r["residents_per_business"], color=[GOV_COLOUR[g] for g in r["governorate"]])
        for x, v in zip(r["governorate"], r["residents_per_business"]):
            if pd.notna(v):
                ax.text(x, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8)
        _style(ax, f"Residents per business ({int(r['year'].iloc[0])})", "Residents per business")
        out.append(("Residents per business (comparison)", _png(fig)))
    pt = dash.population_trend(p_f)
    if not pt.empty:
        fig, ax = plt.subplots(figsize=(6.2, 3.2))
        for g in pt.columns:
            ax.plot(pt.index, pt[g], marker="o", markersize=3, linewidth=2, color=GOV_COLOUR[g], label=g)
        _style(ax, "Residents over time (mid-year estimates)", "Residents")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.legend(frameon=False, fontsize=8, ncol=4)
        out.append(("Residents over time (change over time)", _png(fig)))
    return out


def key_passages(chunks, groups: list[str], k: int = 2) -> list[tuple[str, object]]:
    """Licensing passages for the selected business groups, by keyword search (no model call)."""
    from app.retrieval import keyword_search
    seen, out = set(), []
    for g in [None] + list(groups):
        for _, c in keyword_search(chunks, KEY_QUERIES.get(g, ""), k):
            if c.id not in seen:
                seen.add(c.id)
                out.append((KEY_QUERIES.get(g, ""), c))
    return out


def _table(df: pd.DataFrame) -> str:
    return df.to_html(index=False, border=0, classes="t", float_format=lambda v: f"{v:,.2f}", na_rep="–")


def build_report(ds: Datasets, sel: Selection, options: FilterOptions, settings: Settings,
                 answers: list | None = None, chunks: list | None = None) -> str:
    b_f = filter_businesses(ds.businesses, sel)
    p_f = filter_population(ds.population, sel)
    lu_f = filter_land_use(ds.land_use, sel)
    a_f = filter_area(ds.area, sel)
    s = dash.summary_figures(b_f, p_f, lu_f, a_f)
    esc = html.escape

    def fmt(v, d=0):
        return "–" if v is None else f"{v:,.{d}f}"

    figures = pd.DataFrame([
        ("Businesses in the selection", fmt(s.businesses)),
        (f"Residents ({s.residents_year}, mid-year)", fmt(s.residents)),
        ("Residents per business", fmt(s.residents_per_business)),
        (f"Area of the selected governorates ({s.area_year}), km²", fmt(s.area_km2, 2)),
        ("Businesses per km²", fmt(s.businesses_per_km2, 2)),
        (f"Land in the selected land-use categories ({s.land_period}), km²", fmt(s.land_km2, 2)),
        ("Land-use values missing in the source (left out of sums)", fmt(s.land_missing)),
    ], columns=["Figure", "Value"])

    parts = [f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>BizLocate BH report</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:24px auto;color:#1d1d1b;line-height:1.45;padding:0 16px}}
 h1{{margin-bottom:0}} h2{{border-bottom:2px solid #2a78d6;padding-bottom:4px;margin-top:32px}}
 .muted{{color:#5c5b56;font-size:0.9em}} table.t{{border-collapse:collapse;margin:8px 0;font-size:0.92em}}
 table.t th,table.t td{{border:1px solid #d9d8d3;padding:4px 8px;text-align:left}} table.t th{{background:#f3f2ee}}
 .passage{{border-left:4px solid #2a78d6;background:#f7f7f4;padding:8px 12px;margin:8px 0;white-space:pre-wrap;font-size:0.9em}}
 .answer{{background:#f3f7fd;padding:8px 12px;border-radius:6px}} img{{max-width:100%}}
</style></head><body>
<h1>BizLocate BH – area summary report</h1>
<p class="muted">Generated {datetime.now().strftime('%d/%m/%Y %H:%M')} · model {esc(settings.model)} · version {esc(settings.version)} ·
data extracted from data.gov.bh on {DATA_EXTRACTED} · business listings as at {LISTINGS_UPDATED}</p>
<h2>1. Selection</h2><ul>{''.join(f'<li>{esc(line)}</li>' for line in sel.describe(options))}</ul>
<h2>2. Summary figures</h2>{_table(figures)}
<p class="muted">All figures are computed in code from the published datasets. Business listings are registrations at the last
portal update; some businesses may have closed since. Population is published by governorate only.</p>
<h2>3. Charts</h2>"""]
    for title, png in charts(b_f, p_f):
        parts.append(f"<h3>{esc(title)}</h3><img alt='{esc(title)}' src='data:image/png;base64,{png}'>")

    parts.append("<h2>4. Tables</h2>")
    t = dash.businesses_by_governorate(b_f)
    if not t.empty:
        parts.append("<h3>Businesses by governorate and group</h3>" + _table(t.reset_index()))
    r = dash.residents_per_business(b_f, p_f)
    if not r.empty:
        parts.append("<h3>Residents per business</h3>" + _table(r))
    mix = dash.business_type_mix(b_f)
    if not mix.empty:
        parts.append("<h3>Mix of business types</h3>" + _table(mix))
    blocks = dash.top_blocks(b_f)
    if not blocks.empty:
        parts.append("<h3>Blocks with the most selected businesses</h3>" + _table(blocks))
    lm = dash.land_use_mix(lu_f)
    if not lm.empty:
        wide = lm.pivot_table(index="land_use_category", columns="governorate", values="area_km2").reset_index()
        parts.append(f"<h3>Land use by category, km² ({esc(str(lm['period'].iloc[0]))})</h3>" + _table(wide))

    parts.append("<h2>5. Questions asked in this session, with cited passages</h2>")
    answered = [a for a in (answers or []) if not a.error]
    if not answered:
        parts.append("<p class='muted'>No questions were asked in this session.</p>")
    for i, a in enumerate(answered, start=1):
        parts.append(f"<h3>Q{i}. {esc(a.question)}</h3><div class='answer'>{esc(a.text)}</div>")
        for res in a.tool_results:
            if res.get("id") in a.cited:
                parts.append(f"<p class='muted'>[{esc(res['id'])}] computed by <code>{esc(str(res.get('function')))}</code>: "
                             f"{esc(str(res.get('source', '')))}</p>")
        for p in a.passages:
            if p["id"] in a.cited:
                parts.append(f"<p><b>[{esc(p['id'])}] {esc(p['title'])}</b></p><div class='passage'>{esc(p['text'])}</div>")

    parts.append("<h2>6. Licensing passages for the selected business groups</h2>")
    if chunks:
        parts.append("<p class='muted'>Found by keyword search in the official documents (no model involved). "
                     "Check the full document before relying on a requirement.</p>")
        for query, c in key_passages(chunks, sel.business_groups):
            parts.append(f"<p><b>[{esc(c.id)}] {esc(c.title())}</b></p><div class='passage'>{esc(c.text)}</div>")
    else:
        parts.append("<p class='muted'>The documents are not available on this computer (run scripts/setup_sources.py).</p>")

    parts.append(f"""<h2>7. Sources, licence and limits of use</h2>
<p>{esc(LICENCE)}</p>
<p>All analysis, figures and transformations in this report are the work of IT8413 Group G3 (Bahrain Polytechnic) and are not
attributed to iGA, UPDA, SLRB or any other government entity. Documents: official English texts published by the Ministry of
Industry and Commerce and the Ministry of Health (see data/sources.csv in the repository).</p>
<p class="muted">Limits of use: this report describes businesses that are listed and the published requirements. It cannot say
whether a new business will succeed, what rents or footfall are, or whether a listed business is still open. Confirm every
requirement with the licensing authority before applying.</p>
</body></html>""")
    return "\n".join(parts)


def figures_csv(ds: Datasets, sel: Selection) -> str:
    """The comparison table behind the report, as CSV (for a spreadsheet)."""
    b_f = filter_businesses(ds.businesses, sel)
    p_f = filter_population(ds.population, sel)
    return dash.residents_per_business(b_f, p_f).to_csv(index=False)
