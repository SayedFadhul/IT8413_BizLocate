"""Tests for F10 settings and credential handling (app/config.py). No API key is needed."""
import pytest

from app import config


def test_v1_settings_match_the_proposal():
    s = config.get_settings("v1")
    assert s.version == "v1"
    assert s.model == "gemini-3.1-flash-lite" and s.temperature == 1.0
    assert s.max_generation_calls == 3


def test_v2_changes_exactly_one_setting(monkeypatch):
    monkeypatch.setattr(config, "V2_CHANGE", {"top_k": 8})
    v1, v2 = config.get_settings("v1"), config.get_settings("v2")
    diff = {k for k, v in v2.as_dict().items() if v1.as_dict()[k] != v} - {"version"}
    assert diff == {"top_k"} and v2.version == "v2"
    assert "top_k: 5 → 8" in config.describe_v2_change()


def test_v2_with_two_changes_is_refused(monkeypatch):
    monkeypatch.setattr(config, "V2_CHANGE", {"top_k": 8, "temperature": 0.5})
    with pytest.raises(ValueError):
        config.get_settings("v2")


def test_unknown_setting_or_version_is_refused(monkeypatch):
    monkeypatch.setattr(config, "V2_CHANGE", {"no_such_setting": 1})
    with pytest.raises(ValueError):
        config.get_settings("v2")
    with pytest.raises(ValueError):
        config.get_settings("v3")


def test_api_key_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-value-not-a-key")
    assert config.get_api_key() == "test-value-not-a-key"


def test_cost_uses_the_spreadsheet_prices():
    # 1M input tokens at $0.25 + 1M output tokens at $1.50
    assert config.cost_usd(1_000_000, 1_000_000) == pytest.approx(1.75)
    assert config.cost_usd(0, 0, 1_000_000) == pytest.approx(config.PRICE_EMBED_PER_M)
