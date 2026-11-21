"""Build the document search index (F5): split the documents into passages and embed them.

Run once after scripts/setup_sources.py, and again if the chunk size or embedding model changes:
    python scripts/build_index.py              # v1 settings
    python scripts/build_index.py --version v2 # if the v2 change is the chunk size or embedding model

It sends about 9 batched embedding requests (20 passages each) and saves documents/index/*.json,
which Git ignores because it contains the documents' text.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_api_key, get_settings  # noqa: E402
from app.gemini import Gemini, failure_tag  # noqa: E402
from app.retrieval import build_index, index_path  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="v1", choices=["v1", "v2"])
    ap.add_argument("--force", action="store_true", help="rebuild even if the index exists")
    args = ap.parse_args()
    settings = get_settings(args.version)
    path = index_path(settings)
    if path.exists() and not args.force:
        print(f"Index already exists: {path} (use --force to rebuild)")
        return 0
    key = get_api_key()
    if not key:
        print("No GEMINI_API_KEY found. Create a .env file first (README, step 4).")
        return 1
    try:
        out = build_index(Gemini(key, settings), settings)
    except FileNotFoundError as err:
        print(err)
        return 1
    except Exception as err:   # print the failure plainly instead of a long traceback
        print(failure_tag(err), err)
        return 1
    print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
