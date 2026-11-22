"""The app starts without errors (a feature is shown only when all its files are present), and the
'Reset filters' button selects everything again.
Runs the Streamlit script headless; no question is asked, so no API request is made."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
TABS = ["Dashboard", "Ask", "Report", "Query log", "Data & sources"]


def _by_label(widgets, label):
    return next(w for w in widgets if w.label == label)


def test_app_starts_without_errors():
    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    labels = [t.label for t in at.tabs]
    for tab in TABS:                                   # each tab label is an icon and the tab name
        assert any(label.endswith(" " + tab) for label in labels), (tab, labels)
    assert any("Settings in use" == e.label for e in at.sidebar.expander)   # F10: settings always shown


def test_reset_filters_selects_everything_again():
    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    govs = _by_label(at.sidebar.multiselect, "Governorates")
    everything = list(govs.value)
    govs.unselect("Capital").run()
    _by_label(at.sidebar.multiselect, "Business groups").unselect("Other Shops").run()
    _by_label(at.sidebar.multiselect, "Sex").unselect("Female").run()
    _by_label(at.sidebar.select_slider, "Population years (mid-year estimates)").set_value((2013, 2025)).run()
    assert "Capital" not in _by_label(at.sidebar.multiselect, "Governorates").value

    _by_label(at.sidebar.button, "Reset filters").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert _by_label(at.sidebar.multiselect, "Governorates").value == everything
    assert "Other Shops" in _by_label(at.sidebar.multiselect, "Business groups").value
    assert "Female" in _by_label(at.sidebar.multiselect, "Sex").value
    assert _by_label(at.sidebar.select_slider, "Population years (mid-year estimates)").value == (2010, 2025)
