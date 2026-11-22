"""Check the document collection (D1-D6 with amendments D1a, D3a) in documents/ against the publishers.

The official English PDFs are stored unchanged in documents/ (see ATTRIBUTION.md), so a clone has
everything it needs. This script checks them, and fetches any file that is missing:
  1. downloads a file from its official URL only if it is missing (or every file with --check),
  2. checks its SHA-256 against the value recorded when G3 last verified the sources,
  3. prints a change report: OK / CHANGED / FAILED.

A CHANGED file means the publisher has updated it since our check. The tool still works,
but the group must re-read it and re-run the ground-truth checks before trusting answers
based on it (licence clause 2 and the tutor's request to keep every answer current).

Two files (D1a, D3a) are scans with no text layer. The tool reads their text from
documents/ocr/ (one "<file> (OCR).txt" per scan, with "=== PAGE n ===" markers):
  - the group's OCR text (stored in documents/ocr/; or copy it in with  --ocr-dir <folder>)
    and its SHA-256 is checked against the manifest (OCR OK / OCR CHANGED);
  - or, without it, create a transcription with Gemini:  --transcribe  (needs the API key;
    marked "model transcription" because it is not the version G3 checked).

Usage (from the repository folder):
    python scripts/setup_sources.py                       # download missing files, report changes
    python scripts/setup_sources.py --check               # re-download everything and compare (no overwrite)
    python scripts/setup_sources.py --ocr-dir "<folder>"  # also copy the group's OCR text of the scans
    python scripts/setup_sources.py --transcribe          # or transcribe the scans with Gemini
Exit code: 0 if every file matches, 1 if any file changed or failed, or OCR text is missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "documents_manifest.json"
DOCS_DIR = ROOT / "documents"
OCR_DIR = DOCS_DIR / "ocr"
TRANSCRIBE_INSTRUCTION = (
    "Transcribe the English text of this scanned legal document exactly as printed, page by page. "
    "Start each page with a line '=== PAGE n ===' (n = the page number in the PDF, from 1). "
    "Keep article numbers, clause numbers, amounts and dates exactly. Leave out Arabic text. "
    "Do not summarise, correct or add anything.")
# moic.gov.bh refuses requests without a normal browser User-Agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BizLocate-BH setup script (IT8413 G3)"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, tries: int = 3) -> bytes:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # government sites sometimes reset the connection: retry
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"download failed after {tries} tries: {last}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="re-download every file and compare, without overwriting")
    ap.add_argument("--ocr-dir", help="folder with the group's OCR text of the scanned PDFs (copied into documents/ocr)")
    ap.add_argument("--transcribe", action="store_true", help="transcribe scans that have no OCR text, with Gemini")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    DOCS_DIR.mkdir(exist_ok=True)
    counts = {"OK": 0, "CHANGED": 0, "FAILED": 0}

    for name, info in manifest.items():
        target = DOCS_DIR / name
        try:
            if target.exists() and not args.check:
                data = target.read_bytes()
                origin = "local"
            else:
                data = download(info["url"])
                origin = "downloaded"
                if not target.exists():
                    target.write_bytes(data)
            got = sha256(data)
            if got == info["sha256"]:
                status, note = "OK", origin
            else:
                status, note = "CHANGED", f"{origin}; size {len(data)} vs {info['bytes']} bytes on {info['checked']}"
                if args.check:  # keep the new version beside the verified one for comparison
                    target.with_name(target.stem + "_NEW" + target.suffix).write_bytes(data)
        except Exception as e:
            status, note = "FAILED", str(e)
        counts[status] += 1
        print(f"{status:8s} {info['code']:3s} {name}  ({note})")

    print(f"\nSummary: {counts['OK']} OK, {counts['CHANGED']} CHANGED, {counts['FAILED']} FAILED "
          f"(of {len(manifest)}). Documents folder: {DOCS_DIR}")
    if counts["CHANGED"]:
        print("A CHANGED file differs from the version G3 verified. Re-read it and re-run the "
              "ground-truth checks before using answers based on it.")

    ocr_ok = check_ocr(manifest, args.ocr_dir, args.transcribe)
    return 0 if counts["CHANGED"] == counts["FAILED"] == 0 and ocr_ok else 1


def check_ocr(manifest: dict, ocr_dir: str | None, transcribe: bool) -> bool:
    """Make sure every scanned PDF has its text in documents/ocr/. Returns True when all are present."""
    scans = {name: info for name, info in manifest.items() if info.get("scanned")}
    if not scans:
        return True
    print("\nText of the scanned PDFs (documents/ocr/):")
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    all_ok = True
    for name, info in scans.items():
        target = OCR_DIR / info["ocr_file"]
        if not target.exists() and ocr_dir:
            src = Path(ocr_dir) / info["ocr_file"]
            if src.exists():
                target.write_bytes(src.read_bytes())
        if not target.exists() and transcribe and (DOCS_DIR / name).exists():
            try:
                target.write_text(transcribe_scan(DOCS_DIR / name), encoding="utf-8")
                print(f"TRANSCRIBED {info['code']:3s} {target.name}  (model transcription: compare it with the scan)")
                continue
            except Exception as e:
                print(f"FAILED   {info['code']:3s} transcription: {e}")
        if not target.exists():
            all_ok = False
            print(f"MISSING  {info['code']:3s} {target.name}  -> use --ocr-dir <folder> or --transcribe")
        elif sha256(target.read_bytes()) == info["ocr_sha256"]:
            print(f"OCR OK   {info['code']:3s} {target.name}")
        else:
            print(f"OCR DIFFERS {info['code']:3s} {target.name}  (not the version G3 checked, e.g. a model transcription)")
    return all_ok


def transcribe_scan(pdf: Path) -> str:
    """Ask Gemini to transcribe a scanned PDF (used only when the group's OCR text is not available)."""
    sys.path.insert(0, str(ROOT))
    from google.genai import types

    from app.config import get_api_key, get_settings
    from app.gemini import Gemini, Usage

    gemini = Gemini(get_api_key(), get_settings("v1"))
    part = types.Part.from_bytes(data=pdf.read_bytes(), mime_type="application/pdf")
    response = gemini.generate([part, TRANSCRIBE_INSTRUCTION], Usage())
    return response.text


if __name__ == "__main__":
    sys.exit(main())
