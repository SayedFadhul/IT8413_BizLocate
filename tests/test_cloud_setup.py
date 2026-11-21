"""Tests for the online version's automatic document setup (app/cloud_setup.py).
No network, no API key: the download and the index build are replaced by stand-ins."""
import hashlib
import importlib.util
import json
import tomllib

import pytest

from app import cloud_setup, documents
from app.config import DOCS_DIR, DOCS_MANIFEST, OCR_DIR, ROOT, get_settings

MANIFEST = json.loads(DOCS_MANIFEST.read_text(encoding="utf-8"))
ON_THIS_COMPUTER = all((DOCS_DIR / name).exists() for name in MANIFEST) and all(
    (OCR_DIR / i["ocr_file"]).exists() for i in MANIFEST.values() if i.get("scanned"))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def online_copy(monkeypatch, tmp_path):
    """A small made-up manifest (one scan, one PDF with a text layer), empty folders, the matching
    Secrets, and stand-ins for the download and the index build that record what was called."""
    ocr, text = b"=== PAGE 1 ===\nArticle One\n", documents.text_copy_bytes(["Article (1)\nA rule."])
    manifest = {"A.pdf": {"code": "DA", "scanned": True, "ocr_file": "A (OCR).txt", "ocr_sha256": sha256(ocr)},
                "B.pdf": {"code": "DB", "text_sha256": sha256(text)}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(cloud_setup, "DOCS_MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(cloud_setup, "OCR_DIR", tmp_path / "ocr")
    monkeypatch.setattr(cloud_setup, "TEXT_DIR", tmp_path / "text")
    monkeypatch.setattr(cloud_setup, "ocr_from_secrets", lambda: {"DA": ocr})
    monkeypatch.setattr(cloud_setup, "text_from_secrets", lambda: {"DB": text})
    calls = []

    class Done:
        returncode = 0
        stdout = "8 OK"

    monkeypatch.setattr(cloud_setup.subprocess, "run", lambda *a, **k: calls.append("download") or Done())
    import app.retrieval
    monkeypatch.setattr(app.retrieval, "build_index", lambda *a, **k: calls.append("index") or tmp_path / "index.json")
    return tmp_path, ocr, text, calls


def test_encode_decode_round_trip():
    data = "Article One\nBD 1,000 per day — ‘quoted’ text\n".encode("utf-8")
    line = cloud_setup.encode(data)
    assert "\n" not in line and cloud_setup.decode(line) == data


def test_nothing_runs_without_online_secrets(monkeypatch):
    monkeypatch.setattr(cloud_setup, "ocr_from_secrets", lambda: None)
    assert cloud_setup.needed(get_settings("v1")) is False


def test_prepare_writes_the_checked_text_and_downloads_nothing(online_copy):
    tmp_path, ocr, text, calls = online_copy
    msg = cloud_setup.prepare(get_settings("v1"), "test-value-not-a-key")
    assert calls == ["index"] and "index" in msg
    assert (tmp_path / "ocr" / "A (OCR).txt").read_bytes() == ocr
    assert (tmp_path / "text" / "B (text).json").read_bytes() == text


def test_prepare_refuses_text_that_is_not_the_checked_version(online_copy, monkeypatch):
    tmp_path, ocr, text, calls = online_copy
    monkeypatch.setattr(cloud_setup, "text_from_secrets", lambda: {"DB": text.replace(b"rule", b"rules")})
    with pytest.raises(RuntimeError, match="text of DB"):
        cloud_setup.prepare(get_settings("v1"), "test-value-not-a-key")
    assert calls == [] and not (tmp_path / "text" / "B (text).json").exists()


def test_prepare_refuses_ocr_text_that_is_not_the_checked_version(online_copy, monkeypatch):
    tmp_path, ocr, text, calls = online_copy
    monkeypatch.setattr(cloud_setup, "ocr_from_secrets", lambda: {"DA": b"wrong text"})
    with pytest.raises(RuntimeError, match="OCR text of DA"):
        cloud_setup.prepare(get_settings("v1"), "test-value-not-a-key")
    assert calls == []


def test_prepare_downloads_only_when_the_secrets_have_no_document_text(online_copy, monkeypatch):
    tmp_path, ocr, text, calls = online_copy
    monkeypatch.setattr(cloud_setup, "text_from_secrets", lambda: None)
    cloud_setup.prepare(get_settings("v1"), "test-value-not-a-key")
    assert calls == ["download", "index"]


@pytest.mark.skipif(not ON_THIS_COMPUTER, reason="the documents are not on this computer")
def test_online_copy_reads_exactly_the_same_passages(monkeypatch, tmp_path):
    """End to end with the real documents: the Secrets made by scripts/make_cloud_secrets.py pass the
    online checks, and the text the online copy writes gives exactly the same passages as the PDFs."""
    spec = importlib.util.spec_from_file_location("make_cloud_secrets", ROOT / "scripts" / "make_cloud_secrets.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    monkeypatch.setattr(script, "OUT", tmp_path / "cloud_secrets.toml")
    assert script.main() == 0
    secrets = tomllib.loads(script.OUT.read_text(encoding="utf-8"))
    assert secrets["GEMINI_API_KEY"] == "PASTE-YOUR-KEY-HERE"          # the script never writes a real key

    online = tmp_path / "online"                                        # as online: no PDFs, only the Secrets
    monkeypatch.setattr(cloud_setup, "OCR_DIR", online / "ocr")
    monkeypatch.setattr(cloud_setup, "TEXT_DIR", online / "text")
    for table, getter in (("ocr_text", "ocr_from_secrets"), ("doc_text", "text_from_secrets")):
        monkeypatch.setattr(cloud_setup, getter,
                            lambda t=table: {c: cloud_setup.decode(v) for c, v in secrets[t].items()})
    import app.retrieval
    monkeypatch.setattr(app.retrieval, "build_index", lambda *a, **k: online / "index.json")
    cloud_setup.prepare(get_settings("v1"), "test-value-not-a-key")

    words = get_settings("v1").chunk_words
    from_pdfs = [c.as_dict() for c in documents.build_chunks(words)]
    for name, folder in (("DOCS_DIR", online), ("OCR_DIR", online / "ocr"), ("TEXT_DIR", online / "text")):
        monkeypatch.setattr(documents, name, folder)
    from_online = [c.as_dict() for c in documents.build_chunks(words)]
    assert len(from_online) > 100 and from_online == from_pdfs
