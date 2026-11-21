"""Make the Secrets text for the online version of the app (Streamlit Community Cloud).

Run after scripts/setup_sources.py (it needs the checked OCR text in documents/ocr):
    python scripts/make_cloud_secrets.py

It writes documents/cloud_secrets.toml (documents/ is not in Git) with:
    GEMINI_API_KEY = "PASTE-YOUR-KEY-HERE"
    [ocr_text]   the OCR text of the two scanned PDFs, compressed, one line each
Replace the placeholder with your own key, then paste the whole file into the app's
Advanced settings -> Secrets on share.streamlit.io. Never commit this file.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cloud_setup import decode, encode  # noqa: E402
from app.config import DOCS_DIR, DOCS_MANIFEST, OCR_DIR  # noqa: E402

OUT = DOCS_DIR / "cloud_secrets.toml"


def main() -> int:
    manifest = json.loads(DOCS_MANIFEST.read_text(encoding="utf-8"))
    lines = ['GEMINI_API_KEY = "PASTE-YOUR-KEY-HERE"', "", "[ocr_text]"]
    for info in manifest.values():
        if not info.get("scanned"):
            continue
        path = OCR_DIR / info["ocr_file"]
        if not path.exists():
            print(f"Missing {path}. Run python scripts/setup_sources.py --ocr-dir <folder> first.")
            return 1
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != info["ocr_sha256"]:
            print(f"{path.name} is not the checked OCR text (SHA-256 differs).")
            return 1
        lines.append(f'{info["code"]} = "{encode(data)}"')
    text = "\n".join(lines) + "\n"
    parsed = tomllib.loads(text)                     # check the file reads back to the exact OCR bytes
    for info in manifest.values():
        if info.get("scanned"):
            assert hashlib.sha256(decode(parsed["ocr_text"][info["code"]])).hexdigest() == info["ocr_sha256"]
    OUT.write_text(text, encoding="utf-8")
    print(f"Written {OUT} ({len(text):,} characters). Put your key in place of PASTE-YOUR-KEY-HERE, "
          "then paste the whole file into the app's Secrets. Never commit it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
