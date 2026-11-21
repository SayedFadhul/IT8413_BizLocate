"""Tests for F10 (the structured query log) and the held-out protection of the evaluation runs.
The test spreadsheet here is made up: the real test-set questions are never used in tests."""
import pytest

from app import query_log
from app.assistant import Answer
from app.evaluation import load_test_set, with_parents


def test_query_log_round_trip(tmp_path):
    path = tmp_path / "log.jsonl"
    a = Answer(question="Q?", text="A [P1].", cited=["P1"], timestamp="2026-11-19T10:00:00")
    query_log.append(a.log_record(), path)
    query_log.append(a.log_record(), path)
    path.open("a", encoding="utf-8").write("not json\n")         # a damaged line is skipped
    records = query_log.read(path)
    assert len(records) == 2 and records[0]["question"] == "Q?"
    df = query_log.to_frame(records)
    assert {"question", "answer", "citations", "latency_s", "input_tokens", "output_tokens"} <= set(df.columns)


@pytest.fixture
def fake_test_set(tmp_path):
    """A made-up spreadsheet in the same layout (the real questions are never used in tests)."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test Set"
    ws.append(["#", "Type", "Type (in full)", "Set", "Follow-up of", "Question", "Ground-truth answer", "Source location"])
    ws.append([1, "DIR", "", "Development", None, "Made-up question one?", "x", "y"])
    ws.append([2, "DOC", "", "Held-out", None, "SECRET held-out question?", "x", "y"])
    ws.append([3, "COM", "", "Development", 1, "Made-up follow-up?", "x", "y"])
    path = tmp_path / "test_set.xlsx"
    wb.save(path)
    return path


def test_held_out_questions_are_not_loaded_by_default(fake_test_set):
    qs = load_test_set(fake_test_set)
    assert [q.number for q in qs] == [1, 3]
    assert all("SECRET" not in q.question for q in qs)
    assert [q.number for q in load_test_set(fake_test_set, allow_held_out=True)] == [1, 2, 3]


def test_follow_up_brings_its_parent(fake_test_set):
    qs = load_test_set(fake_test_set)
    picked = with_parents([q for q in qs if q.number == 3], qs)
    assert [q.number for q in picked] == [1, 3]
