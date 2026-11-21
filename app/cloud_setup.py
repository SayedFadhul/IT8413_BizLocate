"""Automatic document setup for the online version of the app (Streamlit Community Cloud).

The documents and their search index are not in GitHub (the MOIC and MOH website terms restrict
republishing), so an online copy of the app starts without them. The online copy's private
Secrets hold the OCR text of the two scanned PDFs, in an [ocr_text] table (made by
scripts/make_cloud_secrets.py). On the first start, this module then prepares everything:
  1. writes the OCR text from the Secrets and checks its SHA-256 against the manifest,
  2. downloads the 8 official PDFs and checks each SHA-256 (scripts/setup_sources.py),
  3. builds the search index with the owner's key (about 9 embedding requests).
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

from app.config import DOCS_MANIFEST, OCR_DIR, ROOT, Settings


def encode(data: bytes) -> str:
    """OCR text as one line for the Secrets: gzip, then base64."""
    return base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii")


def decode(value: str) -> bytes:
    return gzip.decompress(base64.b64decode(value))


def ocr_from_secrets() -> dict[str, bytes] | None:
    """{document code: OCR text bytes} from the app's Secrets, or None when there are none."""
    try:
        import streamlit as st
        table = st.secrets.get("ocr_text")
    except Exception:                     # no Secrets at all (e.g. tests, scripts)
        return None
    if not table:
        return None
    return {code: decode(value) for code, value in dict(table).items()}


def needed(settings: Settings) -> bool:
    """True on an online copy (OCR text in the Secrets) that has no search index yet."""
    if ocr_from_secrets() is None:
        return False
    from app.retrieval import index_path
    return not index_path(settings).exists()


def prepare(settings: Settings, api_key: str, progress=print) -> str:
    """Write the OCR text, download and check the PDFs, and build the index. Raises on any failure."""
    manifest = json.loads(DOCS_MANIFEST.read_text(encoding="utf-8"))
    texts = ocr_from_secrets() or {}
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    for info in manifest.values():
        if not info.get("scanned"):
            continue
        data = texts.get(info["code"])
        if data is None or hashlib.sha256(data).hexdigest() != info["ocr_sha256"]:
            raise RuntimeError(f"The OCR text of {info['code']} is missing from the Secrets or is not the checked version.")
        (OCR_DIR / info["ocr_file"]).write_bytes(data)
    progress("OCR text of the scanned documents written and checked")

    run = subprocess.run([sys.executable, str(ROOT / "scripts" / "setup_sources.py")], cwd=ROOT,
                         capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError("Downloading the documents failed:\n" + run.stdout[-1500:])
    progress("8 documents downloaded and checked")

    from app.gemini import Gemini
    from app.retrieval import build_index
    path = build_index(Gemini(api_key, settings), settings, progress=progress)
    return f"Documents ready; search index saved as {path.name}"
