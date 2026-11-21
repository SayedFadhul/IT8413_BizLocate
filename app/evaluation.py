"""Evaluation runs: control, baseline, v1 and v2 on the test set (lead: Sayed Fadhul Hashem).

The four configurations of the brief (Section 7.2), all with the same model and settings:
  control   the question alone, exactly as asked; no system instruction, no data, documents, retrieval
            or tools (measures what the model knows from training).
  baseline  plain prompting: all sources pasted into the request as text (the six prepared datasets
            and the full text of the eight documents); no retrieval and no tool use.
  v1 / v2   the tool as built (app/assistant.py), with the v1 settings or the v2 settings (one change).

Held-out protection (brief 7.1): only Development questions are loaded unless the final evaluation
is explicitly unlocked (allow_held_out=True). Held-out rows are skipped before their text is read
into a question object, so no development run can see, print or log them.

Each run writes, for every question, the response, tokens (all calls added together), latency and
the run date to results/<run>_<set>_<date>.csv in the spreadsheet's column order, plus the full
records to logs/. Scoring (accuracy, groundedness, refusal, completeness, failure category) is done
by the group against the ground truth; this code never scores or changes a result.
"""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from google.genai import types

from app import query_log
from app.assistant import Answer, Assistant, response_text
from app.config import LOG_DIR, RESULTS_DIR, Settings
from app.data_prep import Datasets
from app.gemini import Gemini, failure_tag

RUNS = ("control", "baseline", "v1", "v2")
SET_DEV, SET_HELD = "Development", "Held-out"
SHEET = "Test Set"

BASELINE_INSTRUCTION = (
    "You answer questions from advisors at a business support centre in Bahrain. Use only the sources "
    "given in the request (six datasets and eight documents). If the sources do not contain the answer, "
    "say that it is not available in the sources.")


@dataclass
class TestQuestion:
    number: int
    set: str
    type: str
    follow_up_of: int | None
    question: str


def load_test_set(path: Path, allow_held_out: bool = False) -> list[TestQuestion]:
    """The questions of the test-set spreadsheet. Held-out rows are skipped unless allow_held_out is True."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = wb[SHEET].iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows)]
    col = {name: header.index(name) for name in ("#", "Type", "Set", "Follow-up of", "Question")}
    out = []
    for row in rows:
        number, qset = row[col["#"]], row[col["Set"]]
        if number is None or qset not in (SET_DEV, SET_HELD):
            continue
        if qset == SET_HELD and not allow_held_out:
            continue                                    # skipped before the question text is read
        parent = row[col["Follow-up of"]]
        out.append(TestQuestion(number=int(number), set=qset, type=str(row[col["Type"]]),
                                follow_up_of=int(parent) if parent not in (None, "") else None,
                                question=str(row[col["Question"]]).strip()))
    wb.close()
    return out


def with_parents(selected: list[TestQuestion], all_q: list[TestQuestion]) -> list[TestQuestion]:
    """Add the question each follow-up refers to (it must be asked first, in the same conversation)."""
    by_num = {q.number: q for q in all_q}
    nums = {q.number for q in selected}
    for q in selected:
        p = q.follow_up_of
        while p is not None and p in by_num and p not in nums:
            nums.add(p)
            p = by_num[p].follow_up_of
    return sorted((by_num[n] for n in nums if n in by_num), key=lambda q: q.number)


# ------------------------------------------------------------------ the baseline request text
def baseline_sources(ds: Datasets) -> str:
    """All sources as text: the six prepared datasets (CSV) and the full text of every document page."""
    from app.documents import load_pages, page_text

    b = ds.businesses[["source_code", "source_row", "name", "subtype", "block", "governorate"]]
    p = ds.population[["period", "estimate", "governorate", "nationality", "sex", "population"]]
    lu = ds.land_use[["period", "governorate", "land_use_category", "area"]]
    a = ds.area[["year", "governorate", "area_km2"]]
    parts = [
        "DATASET [RC+OS+SH] Business locations (restaurants & cafes, other shops, supermarkets & hypermarkets). "
        "source_row = record number n.\n" + b.to_csv(index=False),
        "DATASET [POP] Population by governorate, nationality and sex.\n" + p.to_csv(index=False),
        "DATASET [LU] Land use by category and governorate (area as published, in m2).\n" + lu.to_csv(index=False),
        "DATASET [AR] Area by governorate (km2).\n" + a.to_csv(index=False),
    ]
    for page in load_pages():
        parts.append(f"DOCUMENT {page.doc}, page {page.page}\n{page_text(page)}")
    return "\n\n".join(parts)


# ------------------------------------------------------------------ one run
class Runner:
    def __init__(self, run: str, gemini: Gemini, settings: Settings, ds: Datasets,
                 assistant: Assistant | None = None, sources_text: str | None = None):
        if run not in RUNS:
            raise ValueError(f"run must be one of {RUNS}")
        self.run, self.gemini, self.settings, self.ds = run, gemini, settings, ds
        self.assistant = assistant
        self.sources_text = sources_text

    def ask(self, q: TestQuestion, history: list[Answer]) -> Answer:
        if self.run in ("v1", "v2"):
            return self.assistant.ask(q.question, history)
        s = self.settings
        ans = Answer(question=q.question, model=s.model, version=self.run, settings=s.as_dict(),
                     timestamp=datetime.now().isoformat(timespec="seconds"))
        contents = []
        for h in history:
            contents.append(types.Content(role="user", parts=[types.Part(text=h.question)]))
            contents.append(types.Content(role="model", parts=[types.Part(text=h.text)]))
        if self.run == "control":
            prompt, instruction = q.question, None                     # exactly as asked
        else:
            prompt, instruction = f"Sources:\n{self.sources_text}\n\nQuestion: {q.question}", BASELINE_INSTRUCTION
        contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
        start = time.perf_counter()
        try:
            response = self.gemini.generate(contents, ans.usage, system_instruction=instruction)
            ans.text = response_text(response)
            if not ans.text:
                ans.error = "FAILED: NO TEXT"
        except Exception as err:
            ans.error = f"{failure_tag(err)}: {err}"
        ans.latency_s = time.perf_counter() - start
        low = ans.text.lower()
        ans.says_not_available = "not available in the sources" in low
        ans.refused = ans.says_not_available and len(ans.text.split()) < 80
        return ans


CSV_COLUMNS = ["#", "Set", "Type", "Question", "Response (paste)", "Input tokens", "Output tokens", "Latency (s)",
               "Run date", "Notes", "Embedding tokens", "Generation calls", "Wait (s)", "Cost ($)", "Citations", "Error"]


def run_questions(runner: Runner, questions: list[TestQuestion], pause: float, progress=print) -> tuple[Path, Path]:
    """Ask every question (follow-ups in the same conversation as their parent) and save the results."""
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    sets = "+".join(sorted({q.set for q in questions})).lower()
    csv_path = RESULTS_DIR / f"{runner.run}_{sets}_{stamp}.csv"
    log_path = LOG_DIR / f"eval_{runner.run}_{sets}_{stamp}.jsonl"
    answers: dict[int, Answer] = {}
    by_num = {q.number: q for q in questions}
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for i, q in enumerate(questions, start=1):
            history = []
            p = q.follow_up_of
            while p is not None and p in answers:          # the conversation this follow-up belongs to
                history.insert(0, answers[p])
                p = by_num[p].follow_up_of if p in by_num else None
            a = runner.ask(q, history)
            answers[q.number] = a
            query_log.append(a.log_record(session_id=f"{runner.run}-{stamp}", run=f"eval-{runner.run}"), log_path)
            u = a.usage
            notes = []
            if a.refused:
                notes.append("declined")
            if q.follow_up_of:
                notes.append(f"follow-up of Q{q.follow_up_of}")
            if a.unknown_citations:
                notes.append("unknown citations: " + ", ".join(a.unknown_citations))
            w.writerow([q.number, q.set, q.type, q.question, a.text, u.input_tokens + u.embed_tokens, u.output_tokens,
                        a.latency_without_waits_s, datetime.now().strftime("%d/%m/%Y"), "; ".join(notes),
                        u.embed_tokens, u.generation_calls, round(u.wait_seconds, 1), round(a.cost(), 6),
                        ", ".join(a.cited), a.error or ""])
            f.flush()
            progress(f"[{i}/{len(questions)}] Q{q.number} {runner.run}: "
                     + (a.error or f"{u.input_tokens + u.embed_tokens} in / {u.output_tokens} out tokens, "
                                   f"{a.latency_without_waits_s} s" + (" (declined)" if a.refused else "")))
            if i < len(questions):
                time.sleep(pause)                          # pacing between questions, outside the latency
    return csv_path, log_path
