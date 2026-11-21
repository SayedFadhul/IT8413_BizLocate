"""Automatic document setup for the online version of the app (Streamlit Community Cloud).

The documents and their search index are not in GitHub (the MOIC and MOH website terms restrict
republishing), so an online copy of the app starts without them. Its private Secrets hold the text
the app reads from each document, made by scripts/make_cloud_secrets.py from the checked files:
  [ocr_text]  the OCR text of the two scanned PDFs (D1a, D3a)
  [doc_text]  the text layer of the other six PDFs, page by page
On the first start, this module then prepares everything:
  1. writes each text and checks its SHA-256 against data/documents_manifest.json, so the online
     copy reads exactly the same text, and builds the same passages, as a computer;
  2. builds the search index with the owner's key (about 9 embedding requests).
The PDFs are not downloaded online: the MOIC website refuses requests from the cloud servers
(HTTP 403, seen on 21/11/2026). Only when the Secrets have no [doc_text] table does it try to
download them with scripts/setup_sources.py instead.
On a computer, the README's setup steps do the same by hand, so nothing runs automatically there:
without the [ocr_text] Secrets, `needed()` is always False.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from app.config import DOCS_MANIFEST, OCR_DIR, ROOT, TEXT_DIR, Settings


def encode(data: bytes) -> str:
    """A text as one line for the Secrets: gzip, then base64."""
    return base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii")


def decode(value: str) -> bytes:
    return gzip.decompress(base64.b64decode(value))


def _from_secrets(table_name: str) -> dict[str, bytes] | None:
    """{document code: text bytes} from one table of the app's Secrets, or None when there is none."""
    try:
        import streamlit as st
        table = st.secrets.get(table_name)
    except Exception:                     # no Secrets at all (e.g. tests, scripts)
        return None
    if not table:
        return None
    return {code: decode(value) for code, value in dict(table).items()}


def ocr_from_secrets() -> dict[str, bytes] | None:
    return _from_secrets("ocr_text")


def text_from_secrets() -> dict[str, bytes] | None:
    return _from_secrets("doc_text")


def needed(settings: Settings) -> bool:
    """True on an online copy (OCR text in the Secrets) that has no search index yet."""
    if ocr_from_secrets() is None:
        return False
    from app.retrieval import index_path
    return not index_path(settings).exists()


def _write_checked(data: bytes | None, sha256: str, target: Path, what: str) -> None:
    """Write a text only if it is exactly the checked version (same SHA-256 as in the manifest)."""
    if data is None or hashlib.sha256(data).hexdigest() != sha256:
        raise RuntimeError(f"The {what} is missing from the Secrets or is not the checked version.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def prepare(settings: Settings, api_key: str, progress=print) -> str:
    """Write and check the text of every document, then build the index. Raises on any failure."""
    from app.documents import text_file_for

    manifest = json.loads(DOCS_MANIFEST.read_text(encoding="utf-8"))
    ocr, texts = ocr_from_secrets() or {}, text_from_secrets()
    for info in manifest.values():
        if info.get("scanned"):
            _write_checked(ocr.get(info["code"]), info["ocr_sha256"], OCR_DIR / info["ocr_file"],
                           f"OCR text of {info['code']}")
    progress("OCR text of the scanned documents written and checked")

    if texts is not None:
        for name, info in manifest.items():
            if not info.get("scanned"):
                _write_checked(texts.get(info["code"]), info["text_sha256"], TEXT_DIR / text_file_for(name),
                               f"text of {info['code']}")
        progress("Text of the other documents written and checked")
    else:
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / "setup_sources.py")], cwd=ROOT,
                             capture_output=True, text=True)
        if run.returncode != 0:
            raise RuntimeError("Downloading the documents failed:\n" + run.stdout[-1500:])
        progress("8 documents downloaded and checked")

    from app.gemini import Gemini
    from app.retrieval import build_index
    path = build_index(Gemini(api_key, settings), settings, progress=progress)
    return f"Documents ready; search index saved as {path.name}"
