"""The app starts without errors (a feature is shown only when all its files are present).
Runs the Streamlit script headless; no question is asked, so no API request is made."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def test_app_starts_without_errors():
    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    labels = [t.label for t in at.tabs]
    for tab in ["📊 Dashboard", "💬 Ask", "📄 Report", "🧾 Query log", "🗂️ Data & sources"]:
        assert tab in labels
    assert any("Settings in use" == e.label for e in at.sidebar.expander)   # F10: settings always shown
