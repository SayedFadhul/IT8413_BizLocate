"""Tests for F9 (the downloadable report). The report is built for the current filters, so it needs
the filters and dashboard tables (F2-F3); until those files are present these tests are skipped."""
import pytest

pytest.importorskip("app.filters", reason="the report needs the filters (F2)")
pytest.importorskip("app.dashboard", reason="the report needs the dashboard tables (F3)")

from types import SimpleNamespace  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.data_prep import load_all  # noqa: E402
from app.filters import default_selection, filter_options  # noqa: E402
from app.report import build_report, figures_csv  # noqa: E402


@pytest.fixture(scope="module")
def ds():
    return load_all()


def test_report_has_figures_chart_and_cited_passages(ds):
    options = filter_options(ds)
    sel = default_selection(options)
    sel.governorates = ["Muharraq"]
    answer = SimpleNamespace(question="Licence?", text="A licence is needed [P1].", cited=["P1"], error=None,
                             tool_results=[], passages=[{"id": "P1", "title": "D4 · guideline · p. 9", "score": 0.8,
                                                         "text": "PASSAGE TEXT HERE"}])
    html = build_report(ds, sel, options, get_settings("v1"), answers=[answer], chunks=None)
    assert "Governorates: Muharraq" in html
    assert "data:image/png;base64," in html                     # at least one chart
    assert "PASSAGE TEXT HERE" in html                          # cited passage
    assert "Bahrain Open Government Data License" in html       # licence statement (clause 3.3)


def test_figures_csv_follows_the_filters(ds):
    options = filter_options(ds)
    sel = default_selection(options)
    sel.governorates = ["Northern", "Southern"]
    rows = figures_csv(ds, sel).strip().splitlines()
    assert rows[0].startswith("governorate,residents,businesses")
    assert [r.split(",")[0] for r in rows[1:]] == ["Northern", "Southern"]
