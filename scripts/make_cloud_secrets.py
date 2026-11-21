"""Make the Secrets text for the online version of the app (Streamlit Community Cloud).

Run after scripts/setup_sources.py (it needs the checked PDFs and OCR text in documents/):
    python scripts/make_cloud_secrets.py

It writes documents/cloud_secrets.toml (documents/ is not in Git) with:
    GEMINI_API_KEY = "PASTE-YOUR-KEY-HERE"
    [ocr_text]   the OCR text of the two scanned PDFs, compressed, one line each
    [doc_text]   the text layer of the other six PDFs, page by page, compressed, one line each
Every text is checked against its SHA-256 in data/documents_manifest.json, and the text of a PDF is
only taken from a file whose own SHA-256 matches the official version, so the online copy reads
exactly the same text as a computer. Replace the placeholder with your own key, then paste the
whole file into the app's Advanced settings -> Secrets on share.streamlit.io. Never commit this file.
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
from app.documents import pdf_page_texts, text_copy_bytes  # noqa: E402

OUT = DOCS_DIR / "cloud_secrets.toml"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    manifest = json.loads(DOCS_MANIFEST.read_text(encoding="utf-8"))
    ocr_lines, text_lines, expected = ["[ocr_text]"], ["[doc_text]"], {}
    for name, info in manifest.items():
        code = info["code"]
        if info.get("scanned"):
            path = OCR_DIR / info["ocr_file"]
            if not path.exists():
                print(f"Missing {path}. Run python scripts/setup_sources.py --ocr-dir <folder> first.")
                return 1
            data = path.read_bytes()
            if sha256(data) != info["ocr_sha256"]:
                print(f"{path.name} is not the checked OCR text (SHA-256 differs).")
                return 1
            ocr_lines.append(f'{code} = "{encode(data)}"')
            expected[("ocr_text", code)] = info["ocr_sha256"]
        else:
            pdf = DOCS_DIR / name
            if not pdf.exists() or sha256(pdf.read_bytes()) != info["sha256"]:
                print(f"{name} is missing or is not the checked PDF. Run python scripts/setup_sources.py first.")
                return 1
            data = text_copy_bytes(pdf_page_texts(pdf))
            if sha256(data) != info["text_sha256"]:
                print(f"The text read from {name} differs from the checked text (is pypdf 7.1.1 installed?).")
                return 1
            text_lines.append(f'{code} = "{encode(data)}"')
            expected[("doc_text", code)] = info["text_sha256"]
    text = "\n".join(['GEMINI_API_KEY = "PASTE-YOUR-KEY-HERE"', ""] + ocr_lines + [""] + text_lines) + "\n"
    parsed = tomllib.loads(text)                     # check the file reads back to the exact checked texts
    for (table, code), digest in expected.items():
        assert sha256(decode(parsed[table][code])) == digest
    OUT.write_text(text, encoding="utf-8")
    print(f"Written {OUT} ({len(text):,} characters). Put your key in place of PASTE-YOUR-KEY-HERE, "
          "then paste the whole file into the app's Secrets. Never commit it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
