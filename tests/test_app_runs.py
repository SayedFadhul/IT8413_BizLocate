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


def test_online_first_start_failure_is_shown_and_not_retried_on_every_click(monkeypatch):
    """Online copy whose documents cannot be prepared: the app says so, keeps working, and does not
    try again on the next click (a stand-in replaces the preparation; nothing is downloaded)."""
    import streamlit as st

    from app import cloud_setup
    calls = []

    def failing_prepare(*args, **kwargs):
        calls.append("prepare")
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(cloud_setup, "needed", lambda settings: True)
    monkeypatch.setattr(cloud_setup, "prepare", failing_prepare)
    monkeypatch.setenv("GEMINI_API_KEY", "test-value-not-a-key")
    st.cache_resource.clear()
    try:
        at = AppTest.from_file(str(APP), default_timeout=180)
        at.run()
        at.run()                                     # a second run, as after a click
        assert not at.exception, [e.value for e in at.exception]
        assert calls == ["prepare"]
        assert any("Document questions are not available" in e.value for e in at.error)
        assert "📊 Dashboard" in [t.label for t in at.tabs]
    finally:
        st.cache_resource.clear()
