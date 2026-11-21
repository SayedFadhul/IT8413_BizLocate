"""Tests for the online version's automatic document setup (app/cloud_setup.py).
No network, no API key: the download and the index build are replaced by stand-ins."""
import hashlib
import json

import pytest

from app import cloud_setup
from app.config import DOCS_MANIFEST, OCR_DIR, get_settings

MANIFEST = json.loads(DOCS_MANIFEST.read_text(encoding="utf-8"))
SCANS = {i["code"]: i for i in MANIFEST.values() if i.get("scanned")}


def test_encode_decode_round_trip():
    data = "Article One\nBD 1,000 per day — ‘quoted’ text\n".encode("utf-8")
    line = cloud_setup.encode(data)
    assert "\n" not in line and cloud_setup.decode(line) == data


def test_nothing_runs_without_online_secrets(monkeypatch):
    monkeypatch.setattr(cloud_setup, "ocr_from_secrets", lambda: None)
    assert cloud_setup.needed(get_settings("v1")) is False


def test_prepare_refuses_ocr_text_that_is_not_the_checked_version(monkeypatch, tmp_path):
    monkeypatch.setattr(cloud_setup, "OCR_DIR", tmp_path)
    monkeypatch.setattr(cloud_setup, "ocr_from_secrets", lambda: {code: b"wrong text" for code in SCANS})
    with pytest.raises(RuntimeError):
        cloud_setup.prepare(get_settings("v1"), "test-value-not-a-key")


@pytest.mark.skipif(not all((OCR_DIR / i["ocr_file"]).exists() for i in SCANS.values()),
                    reason="the checked OCR text is not on this computer")
def test_prepare_writes_checked_ocr_text_then_downloads_and_indexes(monkeypatch, tmp_path):
    secrets = {code: cloud_setup.encode((OCR_DIR / i["ocr_file"]).read_bytes()) for code, i in SCANS.items()}
    monkeypatch.setattr(cloud_setup, "OCR_DIR", tmp_path)
    monkeypatch.setattr(cloud_setup, "ocr_from_secrets", lambda: {c: cloud_setup.decode(v) for c, v in secrets.items()})
    calls = []

    class Done:
        returncode = 0
        stdout = "8 OK"

    monkeypatch.setattr(cloud_setup.subprocess, "run", lambda *a, **k: calls.append("download") or Done())
    import app.retrieval
    monkeypatch.setattr(app.retrieval, "build_index", lambda *a, **k: calls.append("index") or tmp_path / "index.json")
    msg = cloud_setup.prepare(get_settings("v1"), "test-value-not-a-key")
    assert calls == ["download", "index"] and "index" in msg
    for i in SCANS.values():
        assert hashlib.sha256((tmp_path / i["ocr_file"]).read_bytes()).hexdigest() == i["ocr_sha256"]
