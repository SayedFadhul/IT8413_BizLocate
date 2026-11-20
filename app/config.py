"""F10 - Central settings and credential handling for BizLocate BH (lead: Sayed Fadhul Hashem).

Every setting the app uses is defined here, so the sidebar (F10) can show it and
every evaluation run can save it next to its results.

v1 and v2 (brief, Section 7.2): v2 must be identical to v1 except for ONE setting,
chosen after the v1 failure analysis. That one change is written in V2_CHANGE below,
so the app and the query log always show which setting differs.

The API key is NEVER stored in this file or anywhere in the repository: it is read
from the environment (a local .env file, which Git ignores) or from Streamlit secrets.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
SOURCES_CSV = ROOT / "data" / "sources.csv"
DOCS_MANIFEST = ROOT / "data" / "documents_manifest.json"
DOCS_DIR = ROOT / "documents"          # filled by scripts/setup_sources.py, not committed
OCR_DIR = DOCS_DIR / "ocr"             # OCR text of the two scanned PDFs (D1a, D3a), not committed
INDEX_DIR = DOCS_DIR / "index"         # chunk embeddings built by scripts/build_index.py, not committed
LOG_DIR = ROOT / "logs"                # query logs (F10), not committed
RESULTS_DIR = ROOT / "results"         # evaluation run outputs (answers, tokens, latency)

GOVERNORATES = ["Capital", "Muharraq", "Northern", "Southern"]

# Data snapshot used by the tool (see data/sources.csv for every source).
DATA_EXTRACTED = "17/10/2026 (area dataset refreshed 16/11/2026)"
LISTINGS_UPDATED = "28/04/2026"        # last portal update of the three business-location datasets

# Prices used for the cost metric (spreadsheet 'Settings' sheet, read 18/11/2026), US$ per 1M tokens.
PRICE_INPUT_PER_M = 0.25
PRICE_OUTPUT_PER_M = 1.50              # thinking tokens are billed as output tokens
PRICE_EMBED_PER_M = 0.15

# Free-tier limits (proposal Section 5). The client waits instead of going over them.
GENERATION_REQUESTS_PER_MINUTE = 14    # limit is 15; one request kept spare
EMBEDDING_REQUESTS_PER_MINUTE = 90     # limit is 100


@dataclass(frozen=True)
class Settings:
    """Every setting that can change an answer. Shown in the app and saved with each logged question."""

    version: str = "v1"                             # "v1" or "v2" (F10 shows which)
    # --- model (prompting and tool use)
    model: str = "gemini-3.1-flash-lite"            # generation + function calling (proposal Section 5)
    fallback_model: str = "gemini-3.5-flash-lite"   # only if the main model is retired (all runs repeated on it)
    temperature: float = 1.0                        # Gemini 3 default (course labs)
    thinking_level: str = "default"                 # "default" = the model's own default; or minimal/low/medium/high
    max_output_tokens: int = 1024
    max_generation_calls: int = 3                   # tool-use loop: at most 3 generation calls per question
    history_turns: int = 3                          # follow-ups (F8): previous question/answer pairs sent again
    # --- retrieval (F5)
    embedding_model: str = "gemini-embedding-2"     # as in Labs 3.1 and 3.3 (proposal said gemini-embedding-001; see CHANGES.md)
    chunk_words: int = 200                          # target maximum words per passage (Lab 3.3 used 200)
    top_k: int = 5                                  # passages retrieved for each question
    # --- pacing for batch runs (evaluation): pause between questions, outside the latency timer
    pause_seconds: float = 5.0

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------- v1 / v2
# The ONE setting v2 changes, decided after the v1 failure analysis (brief 7.5).
# Example once decided: V2_CHANGE = {"top_k": 8}; V2_REASON = "Wrong passage was the largest failure category".
V2_CHANGE: dict = {}
V2_REASON = "not chosen yet (decided after the v1 failure analysis)"


def get_settings(version: str = "v1") -> Settings:
    """Return the settings of v1, or of v2 = v1 with exactly the one change in V2_CHANGE."""
    base = Settings()
    if version == "v1":
        return base
    if version == "v2":
        if len(V2_CHANGE) > 1:
            raise ValueError("v2 must change exactly ONE setting of v1 (brief 7.5)")
        unknown = set(V2_CHANGE) - set(base.as_dict())
        if unknown:
            raise ValueError(f"Unknown setting(s) in V2_CHANGE: {unknown}")
        return replace(base, version="v2", **V2_CHANGE)
    raise ValueError(f"Unknown version {version!r}: use 'v1' or 'v2'")


def describe_v2_change() -> str:
    """One line for the sidebar and the log: which setting v2 changes, from what to what."""
    if not V2_CHANGE:
        return V2_REASON
    base = Settings().as_dict()
    parts = [f"{k}: {base[k]} → {v}" for k, v in V2_CHANGE.items()]
    return "; ".join(parts) + f" ({V2_REASON})"


def get_api_key() -> str | None:
    """Return the Gemini API key from the environment or Streamlit secrets, or None.

    Order: GEMINI_API_KEY environment variable (a .env file is loaded if python-dotenv
    is installed), then st.secrets["GEMINI_API_KEY"]. The key is never logged or shown.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None


def cost_usd(input_tokens: int, output_tokens: int, embed_tokens: int = 0) -> float:
    """Estimated cost of one question in US$, from the token counts and the prices above."""
    return (input_tokens * PRICE_INPUT_PER_M + output_tokens * PRICE_OUTPUT_PER_M
            + embed_tokens * PRICE_EMBED_PER_M) / 1_000_000
