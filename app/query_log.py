"""F10 - The structured query log (lead: Sayed Fadhul Hashem).

Every question asked in the app (and in every evaluation run) is written as one JSON line:
question, answer, refusal, citations, retrieved passages, function calls with their arguments
and sources, tokens, response time, cost, model, version and every setting. JSON Lines keeps one
record per line, so the file can be read back into a table for the evaluation spreadsheet.
The log folder is git-ignored; evaluation results are exported to results/ instead.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.config import LOG_DIR

APP_LOG = LOG_DIR / "query_log.jsonl"

COLUMNS = ["timestamp", "run", "version", "model", "question", "answer", "refused", "citations",
           "input_tokens", "output_tokens", "embedding_tokens", "latency_s", "latency_without_waits_s",
           "cost_usd", "generation_calls", "error", "session_id"]


def append(record: dict, path: Path = APP_LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read(path: Path = APP_LOG) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue          # a damaged line is skipped, the rest of the log still loads
    return records


def to_frame(records: list[dict]) -> pd.DataFrame:
    """The main fields as a table (citations shown as a list of ids)."""
    if not records:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(records)
    if "citations" in df:
        df["citations"] = df["citations"].map(lambda cs: ", ".join(c["id"] for c in cs) if isinstance(cs, list) else "")
    return df[[c for c in COLUMNS if c in df.columns]]
