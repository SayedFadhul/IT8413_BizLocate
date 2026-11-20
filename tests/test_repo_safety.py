"""Tests for repository safety: no credential in the repository, secrets and documents kept out of Git,
and a complete document manifest for the setup script. No API key and no test-set question is used."""
import json
import re

from app.config import DOCS_MANIFEST, ROOT

KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_\-]{30,}")  # shape of a Google API key


def test_no_api_key_in_repo():
    for path in ROOT.rglob("*"):
        if any(part in {".git", ".venv", "venv", "documents", "logs", "__pycache__"} for part in path.parts):
            continue
        if path.name == ".env" or not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not KEY_PATTERN.search(text), f"possible API key in {path}"


def test_gitignore_protects_secrets_and_documents():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in [".env", "secrets.toml", "documents/", "logs/"]:
        assert entry in ignored


def test_env_example_has_no_key():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=" in text
    assert not KEY_PATTERN.search(text)
    line = [l for l in text.splitlines() if l.startswith("GEMINI_API_KEY=")][0]
    assert line.strip() == "GEMINI_API_KEY="                     # the value is left empty


def test_document_manifest_is_complete():
    manifest = json.loads(DOCS_MANIFEST.read_text(encoding="utf-8"))
    assert {i["code"] for i in manifest.values()} == {"D1", "D1a", "D2", "D3", "D3a", "D4", "D5", "D6"}
    for name, info in manifest.items():
        assert name.endswith(".pdf") and info["url"].startswith("https://")
        assert re.fullmatch(r"[0-9a-f]{64}", info["sha256"])
        if info.get("scanned"):                                 # the two scans also have checked OCR text
            assert re.fullmatch(r"[0-9a-f]{64}", info["ocr_sha256"]) and info["ocr_file"].endswith(".txt")
