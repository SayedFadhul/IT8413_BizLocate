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
from app.config import DATA_EXTRACTED, LISTINGS_UPDATED, Settings  # noqa: E402
from app.data_prep import Datasets  # noqa: E402
from app.filters import (FilterOptions, Selection, filter_area, filter_businesses, filter_land_use,  # noqa: E402
                         filter_population)
from app.palette import CARD, GOV_COLOURS, GROUP_COLOURS, INK_MUTED, NAVY, OTHER_GREY  # noqa: E402

GRID, AXIS = "#E9DFCF", "#CDBFA6"

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

# The report's look: the app's colours (navy, cream, coral). Every rule starts with .bl-report (or the report
# page's own body class), so the styles cannot change the app when the report is previewed inside it.
REPORT_CSS = """
body.bl-report-page{margin:0;background:#F4EDE0}
.bl-report{font-family:Inter,"Segoe UI",Arial,sans-serif;color:#14213D;line-height:1.5;max-width:980px;margin:0 auto;
 padding:28px 20px 40px;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.bl-report *{box-sizing:border-box}
.bl-report .r-hero{position:relative;overflow:hidden;border-radius:18px;padding:22px 26px 20px 32px;color:#F4EDE0;
 background:radial-gradient(130% 160% at 100% 0%,#2C4372 0%,#14213D 52%,#0F1A33 100%);box-shadow:0 12px 28px rgba(20,33,61,.20)}
.bl-report .r-hero:before{content:"";position:absolute;left:0;right:0;top:0;height:50%;
 background:linear-gradient(180deg,rgba(255,255,255,.12),rgba(255,255,255,0))}
.bl-report .r-hero:after{content:"";position:absolute;left:0;top:0;bottom:0;width:6px;background:#FF6B5B}
.bl-report h1{position:relative;margin:0;padding:0;border:0;font-family:"Plus Jakarta Sans",Inter,"Segoe UI",Arial,sans-serif;
 font-size:1.75rem;font-weight:800;letter-spacing:-.01em;color:#F4EDE0}
.bl-report .r-meta{position:relative;margin-top:6px;font-size:.85rem;color:rgba(244,237,224,.84)}
.bl-report .r-tags{position:relative;display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.bl-report .r-tag{font-size:.75rem;font-weight:600;padding:3px 10px;border-radius:999px;color:#F4EDE0;
 background:rgba(244,237,224,.10);border:1px solid rgba(244,237,224,.22)}
.bl-report .r-tag.accent{background:#FF6B5B;border-color:#FF6B5B;color:#FFFFFF}
.bl-report h2{display:flex;align-items:center;gap:10px;margin:30px 0 12px;padding:0;border:0;
 font-family:"Plus Jakarta Sans",Inter,"Segoe UI",Arial,sans-serif;font-size:1.2rem;font-weight:800;color:#14213D}
.bl-report h2 .n{display:inline-grid;place-items:center;flex:none;width:28px;height:28px;border-radius:8px;
 background:#14213D;color:#FF8F82;font-size:.9rem;font-weight:800}
.bl-report h3{margin:0 0 8px;padding:0;border:0;font-size:.98rem;font-weight:700;color:#14213D}
.bl-report p{margin:8px 0}
.bl-report .muted{color:#5B6478;font-size:.86rem}
.bl-report .card{background:#FBF7F0;border:1px solid #E3D6C0;border-radius:14px;padding:16px 18px;margin:10px 0;
 box-shadow:0 6px 18px rgba(20,33,61,.05)}
.bl-report ul.sel{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0;margin:0}
.bl-report ul.sel li{background:#FBF7F0;border:1px solid #E3D6C0;border-radius:999px;padding:5px 12px;font-size:.85rem}
.bl-report .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.bl-report .kpi{position:relative;overflow:hidden;border-radius:14px;padding:14px 16px;color:#F4EDE0;
 background:linear-gradient(160deg,#283C6C 0%,#14213D 60%,#101B34 100%);box-shadow:inset 0 1px 0 rgba(255,255,255,.14)}
.bl-report .kpi:after{content:"";position:absolute;left:16px;top:0;width:30px;height:3px;border-radius:0 0 3px 3px;background:#FF6B5B}
.bl-report .kpi .l{font-size:.8rem;font-weight:600;color:rgba(244,237,224,.84)}
.bl-report .kpi .v{margin-top:4px;font-size:1.45rem;font-weight:800;color:#F4EDE0}
.bl-report img{display:block;max-width:100%;height:auto}
.bl-report table.t{width:100%;border-collapse:separate;border-spacing:0;font-size:.86rem;border:1px solid #E3D6C0;
 border-radius:10px;overflow:hidden;background:#FFFFFF}
.bl-report table.t th{background:#14213D;color:#F4EDE0;text-align:left;padding:7px 10px;font-weight:600;border:0}
.bl-report table.t td{padding:6px 10px;border:0;border-top:1px solid #EDE3D2;text-align:left;color:#14213D}
.bl-report table.t tr:nth-child(even) td{background:#F7F1E6}
.bl-report .answer{background:#FFFFFF;border:1px solid #E3D6C0;border-left:4px solid #14213D;border-radius:10px;
 padding:10px 14px;white-space:pre-wrap}
.bl-report .ptitle{font-weight:700;font-size:.9rem;margin:12px 0 4px}
.bl-report .passage{background:#FFFFFF;border:1px solid #E3D6C0;border-left:4px solid #FF6B5B;border-radius:10px;
 padding:10px 14px;margin:6px 0 10px;white-space:pre-wrap;font-size:.86rem}
.bl-report .limits{margin-top:10px;background:rgba(255,107,91,.10);border:1px solid rgba(255,107,91,.40);border-radius:12px;
 padding:12px 16px}
.bl-report code{background:#EAE0CE;padding:1px 5px;border-radius:5px;font-size:.85em}
.bl-report .r-foot{margin-top:28px;padding-top:12px;border-top:1px solid #DCCDB4;font-size:.78rem;color:#5B6478}
@media print{body.bl-report-page{background:#FFFFFF}.bl-report{padding:0}
 .bl-report .card,.bl-report .kpi,.bl-report .passage,.bl-report table.t{break-inside:avoid}.bl-report h2{break-after:avoid}}
"""


def _png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _figure():
    """A chart on the card colour, the same quiet style as the app's charts."""
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    fig.patch.set_facecolor(CARD)
    ax.set_facecolor(CARD)
    return fig, ax


def _style(ax, ylabel: str) -> None:
    """The chart's title is printed above the image in the report, so the image itself has none."""
    ax.set_ylabel(ylabel, color=INK_MUTED, fontsize=9)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=INK_MUTED, labelsize=8.5, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _legend(ax, **kw) -> None:
    ax.legend(frameon=False, fontsize=8, labelcolor=NAVY, **kw)


def charts(b_f, p_f) -> list[tuple[str, str]]:
    """(title, base64 PNG) for each chart in the report."""
    out = []
    t = dash.businesses_by_governorate(b_f)
    if not t.empty:
        fig, ax = _figure()
        bottom = pd.Series(0, index=t.index)
        for col in t.columns:
            ax.bar(t.index, t[col], bottom=bottom, color=GROUP_COLOURS.get(col, OTHER_GREY), label=col,
                   edgecolor=CARD, linewidth=1.5, width=0.6)
            bottom += t[col]
        for x, v in zip(t.index, bottom):
            ax.text(x, v, f"{int(v):,}", ha="center", va="bottom", fontsize=8, color=NAVY)
        _style(ax, "Businesses")
        _legend(ax)
        out.append(("Businesses by governorate (comparison)", _png(fig)))
    r = dash.residents_per_business(b_f, p_f)
    if not r.empty and r["businesses"].sum() > 0:
        fig, ax = _figure()
        ax.bar(r["governorate"], r["residents_per_business"], width=0.55,
               color=[GOV_COLOURS.get(g, OTHER_GREY) for g in r["governorate"]])
        for x, v in zip(r["governorate"], r["residents_per_business"]):
            if pd.notna(v):
                ax.text(x, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8, color=NAVY)
        _style(ax, f"Residents per business ({int(r['year'].iloc[0])})")
        out.append(("Residents per business (comparison)", _png(fig)))
    pt = dash.population_trend(p_f)
    if not pt.empty:
        fig, ax = _figure()
        for g in pt.columns:
            ax.plot(pt.index, pt[g], marker="o", markersize=4, linewidth=2, color=GOV_COLOURS.get(g, OTHER_GREY), label=g)
        _style(ax, "Residents (mid-year estimates)")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        _legend(ax, ncol=4)
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
    # rename_axis: a named column index (e.g. 'dataset') would add an extra empty first column to the HTML table
    return df.rename_axis(columns=None).to_html(index=False, border=0, classes="t",
                                                float_format=lambda v: f"{v:,.2f}", na_rep="–")


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

    generated = datetime.now().strftime("%d/%m/%Y %H:%M")
    kpis = "".join(f'<div class="kpi"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div></div>'
                   for label, value in figures.itertuples(index=False))
    parts = [f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BizLocate BH report</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Plus+Jakarta+Sans:wght@700;800&display=swap">
</head><body class="bl-report-page"><div class="bl-report">
<style>{REPORT_CSS}</style>
<header class="r-hero"><h1>BizLocate BH – area summary report</h1>
<div class="r-meta">Generated {generated} · model {esc(settings.model)} · version {esc(settings.version)} ·
data extracted from data.gov.bh on {DATA_EXTRACTED} · business listings as at {LISTINGS_UPDATED}</div>
<div class="r-tags"><span class="r-tag">IT8413 · Group G3 · Brief D</span><span class="r-tag accent">Version {esc(settings.version)}</span>
<span class="r-tag">Business Location and Licensing Assistant</span></div></header>
<h2><span class="n">1</span>Selection</h2><ul class="sel">{''.join(f'<li>{esc(line)}</li>' for line in sel.describe(options))}</ul>
<h2><span class="n">2</span>Summary figures</h2><div class="kpis">{kpis}</div>
<p class="muted">All figures are computed in code from the published datasets. Business listings are registrations at the last
portal update; some businesses may have closed since. Population is published by governorate only.</p>
<h2><span class="n">3</span>Charts</h2>"""]
    for title, png in charts(b_f, p_f):
        parts.append(f"<div class='card'><h3>{esc(title)}</h3><img alt='{esc(title)}' src='data:image/png;base64,{png}'></div>")

    parts.append("<h2><span class='n'>4</span>Tables</h2>")
    t = dash.businesses_by_governorate(b_f)
    if not t.empty:
        parts.append("<div class='card'><h3>Businesses by governorate and group</h3>" + _table(t.reset_index()) + "</div>")
    r = dash.residents_per_business(b_f, p_f)
    if not r.empty:
        parts.append("<div class='card'><h3>Residents per business</h3>" + _table(r) + "</div>")
    mix = dash.business_type_mix(b_f)
    if not mix.empty:
        parts.append("<div class='card'><h3>Mix of business types</h3>" + _table(mix) + "</div>")
    blocks = dash.top_blocks(b_f)
    if not blocks.empty:
        parts.append("<div class='card'><h3>Blocks with the most selected businesses</h3>" + _table(blocks) + "</div>")
    lm = dash.land_use_mix(lu_f)
    if not lm.empty:
        wide = lm.pivot_table(index="land_use_category", columns="governorate", values="area_km2").reset_index()
        parts.append(f"<div class='card'><h3>Land use by category, km² ({esc(str(lm['period'].iloc[0]))})</h3>"
                     + _table(wide) + "</div>")

    parts.append("<h2><span class='n'>5</span>Questions asked in this session, with cited passages</h2>")
    answered = [a for a in (answers or []) if not a.error]
    if not answered:
        parts.append("<p class='muted'>No questions were asked in this session.</p>")
    for i, a in enumerate(answered, start=1):
        parts.append(f"<div class='card'><h3>Q{i}. {esc(a.question)}</h3><div class='answer'>{esc(a.text)}</div>")
        for res in a.tool_results:
            if res.get("id") in a.cited:
                parts.append(f"<p class='muted'>[{esc(res['id'])}] computed by <code>{esc(str(res.get('function')))}</code>: "
                             f"{esc(str(res.get('source', '')))}</p>")
        for p in a.passages:
            if p["id"] in a.cited:
                parts.append(f"<p class='ptitle'>[{esc(p['id'])}] {esc(p['title'])}</p><div class='passage'>{esc(p['text'])}</div>")
        parts.append("</div>")

    parts.append("<h2><span class='n'>6</span>Licensing passages for the selected business groups</h2>")
    if chunks:
        parts.append("<p class='muted'>Found by keyword search in the official documents (no model involved). "
                     "Check the full document before relying on a requirement.</p>")
        for query, c in key_passages(chunks, sel.business_groups):
            parts.append(f"<p class='ptitle'>[{esc(c.id)}] {esc(c.title())}</p><div class='passage'>{esc(c.text)}</div>")
    else:
        parts.append("<p class='muted'>The documents are not available on this computer (run scripts/setup_sources.py).</p>")

    parts.append(f"""<h2><span class="n">7</span>Sources, licence and limits of use</h2>
<div class="card"><p>{esc(LICENCE)}</p>
<p>All analysis, figures and transformations in this report are the work of IT8413 Group G3 (Bahrain Polytechnic) and are not
attributed to iGA, UPDA, SLRB or any other government entity. Documents: official English texts published by the Ministry of
Industry and Commerce and the Ministry of Health (see data/sources.csv in the repository).</p></div>
<div class="limits"><b>Limits of use:</b> this report describes businesses that are listed and the published requirements. It cannot say
whether a new business will succeed, what rents or footfall are, or whether a listed business is still open. Confirm every
requirement with the licensing authority before applying.</div>
<div class="r-foot">BizLocate BH · IT8413 · Group G3 · generated {generated}</div>
</div></body></html>""")
    return "\n".join(parts)


def figures_csv(ds: Datasets, sel: Selection) -> str:
    """The comparison table behind the report, as CSV (for a spreadsheet)."""
    b_f = filter_businesses(ds.businesses, sel)
    p_f = filter_population(ds.population, sel)
    return dash.residents_per_business(b_f, p_f).to_csv(index=False)
